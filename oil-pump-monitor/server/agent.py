"""
Genie AI Agent for oil pump operations monitoring.
Uses Claude via Databricks Foundation Model API with tool-calling to
analyze vibration data, detect faults, and make operational recommendations.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from .config import get_oauth_token, get_workspace_host, IS_DATABRICKS_APP
from .db import db
from .simulator import generate_vibration_reading, generate_spectrum, PUMP_PROFILES

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_field_summary",
            "description": (
                "Get the latest live reading for every pump in the Bakken field. "
                "Returns pump name, GPS location, vibration amplitude (mm/s), "
                "frequency (Hz), RPM, temperature (°F), wellbore pressure (PSI), "
                "and current alert_level (normal/warning/critical)."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pump_history",
            "description": (
                "Get time-series vibration readings for a specific pump over the "
                "last N minutes. Use this to spot trends, spikes, or sustained anomalies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pump_id": {
                        "type": "string",
                        "description": "Pump ID, e.g. PUMP-ND-001",
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "How many minutes of history (1-120)",
                        "default": 15,
                    },
                },
                "required": ["pump_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pump_stats",
            "description": (
                "Get aggregated statistics for a pump over the last hour: "
                "avg/max amplitude, avg RPM, avg temp, anomaly count, critical count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pump_id": {
                        "type": "string",
                        "description": "Pump ID, e.g. PUMP-ND-001",
                    }
                },
                "required": ["pump_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_alerts",
            "description": (
                "Get the most recent anomaly alerts across all pumps. "
                "Each alert includes pump_id, timestamp, alert_level, amplitude, RPM, temperature."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max alerts to return (default 20)",
                        "default": 20,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spectrum",
            "description": (
                "Get the latest FFT frequency spectrum for a pump. "
                "Returns frequency bins (0–50 Hz) and amplitudes, useful for "
                "identifying harmonic patterns indicative of bearing faults or imbalance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pump_id": {
                        "type": "string",
                        "description": "Pump ID, e.g. PUMP-ND-001",
                    }
                },
                "required": ["pump_id"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def execute_tool(name: str, args: dict) -> str:
    """Run a tool call and return JSON string result."""
    try:
        if name == "get_field_summary":
            rows = await db.fetch(
                """SELECT p.pump_id, p.name, p.latitude, p.longitude,
                          latest.frequency_hz, latest.amplitude_mm_s, latest.rpm,
                          latest.temperature_f, latest.pressure_psi, latest.alert_level,
                          latest.timestamp as last_reading
                   FROM pumps p
                   LEFT JOIN LATERAL (
                       SELECT frequency_hz, amplitude_mm_s, rpm, temperature_f,
                              pressure_psi, alert_level, timestamp
                       FROM vibration_readings WHERE pump_id = p.pump_id
                       ORDER BY timestamp DESC LIMIT 1
                   ) latest ON true
                   ORDER BY p.pump_id"""
            )
            if rows:
                return json.dumps([dict(r) for r in rows], default=str)
            # Demo fallback
            result = []
            for pump_id, profile in PUMP_PROFILES.items():
                r = generate_vibration_reading(pump_id)
                result.append({k: str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v
                               for k, v in r.items()})
            return json.dumps(result)

        elif name == "get_pump_history":
            pump_id = args["pump_id"]
            minutes = min(int(args.get("minutes", 15)), 120)
            since = datetime.utcnow() - timedelta(minutes=minutes)
            rows = await db.fetch(
                """SELECT timestamp, frequency_hz, amplitude_mm_s, rpm,
                          temperature_f, pressure_psi, is_anomaly, alert_level
                   FROM vibration_readings
                   WHERE pump_id = $1 AND timestamp >= $2
                   ORDER BY timestamp DESC LIMIT 200""",
                pump_id, since
            )
            if rows:
                data = [dict(r) for r in rows]
                # Summarise to avoid token explosion
                anomalies = [r for r in data if r["is_anomaly"]]
                summary = {
                    "pump_id": pump_id,
                    "period_minutes": minutes,
                    "total_readings": len(data),
                    "anomaly_count": len(anomalies),
                    "max_amplitude": max(r["amplitude_mm_s"] for r in data),
                    "avg_amplitude": sum(r["amplitude_mm_s"] for r in data) / len(data),
                    "max_rpm": max(r["rpm"] for r in data),
                    "avg_rpm": sum(r["rpm"] for r in data) / len(data),
                    "max_temp": max(r["temperature_f"] for r in data),
                    "recent_alerts": [
                        {"timestamp": str(r["timestamp"]), "level": r["alert_level"],
                         "amplitude": r["amplitude_mm_s"], "rpm": r["rpm"]}
                        for r in anomalies[:5]
                    ],
                }
                return json.dumps(summary)
            return json.dumps({"pump_id": pump_id, "message": "No data yet - simulator starting up"})

        elif name == "get_pump_stats":
            pump_id = args["pump_id"]
            row = await db.fetchrow(
                """SELECT COUNT(*) as total_readings,
                          AVG(frequency_hz) as avg_frequency,
                          AVG(amplitude_mm_s) as avg_amplitude,
                          MAX(amplitude_mm_s) as max_amplitude,
                          AVG(rpm) as avg_rpm,
                          AVG(temperature_f) as avg_temperature,
                          AVG(pressure_psi) as avg_pressure,
                          SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) as anomaly_count,
                          SUM(CASE WHEN alert_level = 'critical' THEN 1 ELSE 0 END) as critical_count
                   FROM vibration_readings
                   WHERE pump_id = $1 AND timestamp >= NOW() - INTERVAL '1 hour'""",
                pump_id
            )
            if row:
                return json.dumps(dict(row), default=str)
            return json.dumps({"pump_id": pump_id, "message": "No data yet"})

        elif name == "get_recent_alerts":
            limit = min(int(args.get("limit", 20)), 50)
            rows = await db.fetch(
                """SELECT vr.pump_id, p.name as pump_name, vr.timestamp,
                          vr.alert_level, vr.amplitude_mm_s, vr.frequency_hz,
                          vr.rpm, vr.temperature_f, vr.pressure_psi
                   FROM vibration_readings vr
                   JOIN pumps p ON p.pump_id = vr.pump_id
                   WHERE vr.alert_level != 'normal'
                   ORDER BY vr.timestamp DESC LIMIT $1""",
                limit
            )
            if rows:
                return json.dumps([dict(r) for r in rows], default=str)
            return json.dumps([])

        elif name == "get_spectrum":
            pump_id = args["pump_id"]
            row = await db.fetchrow(
                """SELECT pump_id, timestamp,
                          frequencies[1:10] as freq_sample,
                          amplitudes[1:10] as amp_sample
                   FROM spectrum_readings WHERE pump_id = $1
                   ORDER BY timestamp DESC LIMIT 1""",
                pump_id
            )
            if row:
                d = dict(row)
                return json.dumps(d, default=str)
            spec = generate_spectrum(pump_id)
            return json.dumps({
                "pump_id": pump_id,
                "fundamental_hz": PUMP_PROFILES.get(pump_id, {}).get("base_freq", 5.0),
                "message": "Demo spectrum data",
            })

        return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def _get_client():
    """Return OpenAI-compatible client pointed at Databricks Foundation Models."""
    from openai import AsyncOpenAI
    host = get_workspace_host()
    token = get_oauth_token()
    return AsyncOpenAI(api_key=token, base_url=f"{host}/serving-endpoints")


SYSTEM_PROMPT = """You are the Genie Operations AI for the Bakken Formation fracking field in North Dakota.
You monitor 6 oil pump units (PUMP-ND-001 through PUMP-ND-006) in real time.

Your role:
1. DIAGNOSE issues using vibration data, frequency spectra, and historical trends
2. ALERT operators immediately when critical faults are detected
3. RECOMMEND specific corrective actions based on fault signatures
4. EXPLAIN what the data means in plain operational language

Fault signatures to watch for:
- Bearing fault: amplitude >2× baseline, elevated 2nd/3rd harmonics
- Cavitation: erratic amplitude, pressure drop >200 PSI below baseline
- Imbalance: elevated 1× fundamental, amplitude >1.5× baseline
- Overspeed: RPM >400, high frequency, elevated temperature
- Overheating: temperature >170°F — stop pump risk
- High vibration: amplitude >5 mm/s — structural damage risk

Bakken baseline parameters per pump:
- P001: 280 RPM, 4.67 Hz, 2.1 mm/s, 145°F, 2850 PSI
- P002: 320 RPM, 5.33 Hz, 1.8 mm/s, 138°F, 3100 PSI
- P003: 295 RPM, 4.92 Hz, 2.4 mm/s, 152°F, 2950 PSI
- P004: 310 RPM, 5.17 Hz, 1.9 mm/s, 141°F, 3050 PSI
- P005: 275 RPM, 4.58 Hz, 2.2 mm/s, 149°F, 2800 PSI
- P006: 305 RPM, 5.08 Hz, 2.0 mm/s, 143°F, 3000 PSI

Always use your tools to get real-time data before responding.
Be concise but complete. Use structured responses with ALERT, DIAGNOSIS, and RECOMMENDATION sections when faults are found.
Always end with a priority action list ranked by urgency."""


async def _gather_field_context(user_query: str = "") -> tuple[str, list]:
    """
    Pre-fetch real-time sensor data in parallel.
    Returns (context_text, critical_pump_ids).
    """
    q = user_query.lower()

    # Always fetch: field summary + recent alerts
    tasks = [
        execute_tool("get_field_summary", {}),
        execute_tool("get_recent_alerts", {"limit": 15}),
    ]

    # If a specific pump is mentioned, also fetch its history and stats
    pump_ids = [f"PUMP-ND-{str(i).zfill(3)}" for i in range(1, 7)]
    extra_pumps = [pid for pid in pump_ids if pid.lower() in q or pid.replace("PUMP-ND-0", "p0").replace("PUMP-ND-", "p") in q]
    if not extra_pumps and any(w in q for w in ["all", "every", "each", "field", "overview", "status", "priorit"]):
        extra_pumps = []  # Field-wide; summary is enough
    elif not extra_pumps:
        extra_pumps = []  # No specific pump mentioned

    for pid in extra_pumps[:2]:  # max 2 to keep latency low
        tasks.append(execute_tool("get_pump_history", {"pump_id": pid, "minutes": 15}))
        tasks.append(execute_tool("get_pump_stats", {"pump_id": pid}))

    results = await asyncio.gather(*tasks)
    field_json, alerts_json = results[0], results[1]
    extra_results = results[2:]

    # Parse critical pumps
    critical_pumps = []
    try:
        field_data = json.loads(field_json)
        critical_pumps = [p["pump_id"] for p in field_data if p.get("alert_level") == "critical"]
    except Exception:
        pass

    # Build readable context block
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"=== LIVE BAKKEN FIELD DATA — {ts} ===",
        "",
        "--- Field Summary (all pumps, latest readings) ---",
        field_json,
        "",
        "--- Recent Anomaly Alerts ---",
        alerts_json,
    ]
    for i, pid in enumerate(extra_pumps[:2]):
        if i * 2 + 1 < len(extra_results):
            lines += ["", f"--- {pid} History (last 15 min) ---", extra_results[i * 2]]
        if i * 2 + 2 < len(extra_results):
            lines += ["", f"--- {pid} Hourly Stats ---", extra_results[i * 2 + 1]]

    return "\n".join(lines), critical_pumps


async def run_agent(messages: list, model: str = "databricks-claude-sonnet-4-6") -> dict:
    """
    Data-first agent: pre-fetch all sensor data, inject as context, single LLM call.
    Avoids tool-call multi-turn format issues with the Databricks serving endpoint.
    Returns {"response": str, "critical_pumps": list, "recommendations": list}
    """
    client = _get_client()

    user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_query = m.get("content", "")
            break

    # Gather live field data in parallel before calling Claude
    context_text, critical_pumps = await _gather_field_context(user_query)

    # Inject live data into the system prompt so Claude has full real-time context
    enriched_system = SYSTEM_PROMPT + f"\n\n{context_text}"

    full_messages = [{"role": "system", "content": enriched_system}] + [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    response = await client.chat.completions.create(
        model=model,
        messages=full_messages,
        max_tokens=2048,
        temperature=0.2,
    )

    final_text = response.choices[0].message.content or ""

    # Parse action-item recommendations
    recommendations = []
    for line in final_text.split("\n"):
        stripped = line.strip("•- *123456789.)").strip()
        if len(stripped) > 12 and any(stripped.lower().startswith(kw) for kw in
               ["shut", "reduc", "inspect", "check", "monitor", "stop", "replace",
                "alert", "dispatch", "schedule", "increase", "decrease", "run",
                "restart", "contact", "deploy", "verify", "perform", "investigate"]):
            recommendations.append(stripped)

    return {
        "response": final_text,
        "critical_pumps": list(set(critical_pumps)),
        "recommendations": recommendations[:8],
    }


# ---------------------------------------------------------------------------
# Proactive scan (called periodically by background task)
# ---------------------------------------------------------------------------

async def proactive_scan() -> Optional[dict]:
    """
    Scan all pumps for critical conditions.
    Returns alert payload if critical issues found, else None.
    """
    rows = await db.fetch(
        """SELECT pump_id, amplitude_mm_s, rpm, temperature_f, pressure_psi, alert_level
           FROM vibration_readings
           WHERE timestamp >= NOW() - INTERVAL '30 seconds'
             AND alert_level != 'normal'
           ORDER BY timestamp DESC"""
    )
    if not rows:
        return None

    critical = [dict(r) for r in rows if r["alert_level"] == "critical"]
    if not critical:
        return None

    pump_ids = list({r["pump_id"] for r in critical})
    user_msg = (
        f"URGENT: Critical anomalies just detected on {', '.join(pump_ids)}. "
        f"Analyze immediately and provide emergency recommendations."
    )
    result = await run_agent([{"role": "user", "content": user_msg}])
    result["trigger"] = "proactive"
    result["affected_pumps"] = pump_ids
    return result
