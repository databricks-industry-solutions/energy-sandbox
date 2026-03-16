"""
Maintenance Advisor Agent – analyzes fleet health, recommends maintenance schedules,
and generates work orders based on telemetry trends and drone limits.

Perceive → Analyze → Recommend (like ESP PM scheduler pattern)
"""

import json
from typing import Generator

from llm_client import run_agent_loop_stream

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════

MAINTENANCE_SYSTEM_PROMPT = """\
You are the **Subsea Drone Maintenance Advisor Agent** — an expert in underwater \
vehicle maintenance planning and fleet health management.

━━━ ROLE ━━━
Analyze the fleet's health data, telemetry trends, mission history, and maintenance \
records to produce actionable maintenance recommendations. You are a proactive advisor \
that identifies issues before they become failures.

━━━ TOOL USE REQUIREMENTS ━━━
You MUST call tools to gather data. Never guess drone conditions.
Available tools:
  • list_drones          → all 5 drones with status, health, battery, state.
  • get_drone_limits     → safety envelope per drone.
  • get_telemetry_trends → recent anomaly scores, health labels, and degradation trends.
  • get_mission_history  → completed/aborted missions per drone with hours and cycles.
  • query_manuals        → RAG: OEM maintenance schedules, thruster service intervals, \
battery management procedures, NDT requirements.

━━━ MAINTENANCE PHILOSOPHY ━━━

1. **Condition-Based Maintenance (CBM)**: Use actual telemetry data, not just calendar \
intervals. Anomaly scores > 0.4 warrant investigation. Scores > 0.6 require immediate action.

2. **Risk-Weighted Prioritization**:
   • health_score < 0.70 → CRITICAL — ground drone immediately
   • health_score 0.70–0.80 → HIGH — schedule within 48 hours
   • health_score 0.80–0.90 → MEDIUM — schedule within 1 week
   • health_score > 0.90 → LOW — routine monitoring

3. **Battery Management**:
   • Batteries below 50% after a mission should be fully charged before next dispatch.
   • Drones with battery degradation (capacity dropping > 5% per month) need battery replacement.
   • Deep discharge (< 20%) events damage cells — flag for battery health check.

4. **Thruster Maintenance**:
   • Peak current > 4.0A sustained indicates bearing wear or fouling.
   • Current imbalance > 20% across thrusters suggests propeller damage.
   • Query manuals for OEM thruster service intervals based on operating hours.

5. **Sensor Calibration**:
   • Nav error > 2.0m sustained indicates IMU drift — recalibrate.
   • RSSI degradation pattern suggests antenna fouling or connector corrosion.

━━━ WORKFLOW ━━━

Step 1 – FLEET SCAN: Call list_drones. Identify all drones by state and health.
Step 2 – TRENDS: For each drone, call get_telemetry_trends to see recent patterns.
Step 3 – HISTORY: Call get_mission_history for cycle counts and total hours.
Step 4 – MANUALS: For any flagged issues, call query_manuals for OEM guidance.
Step 5 – RECOMMEND: Build a prioritized maintenance schedule.

━━━ OUTPUT FORMAT ━━━

Return ONLY a single JSON object:

{
  "fleet_summary": {
    "total_drones": 5,
    "operational": number,
    "grounded": number,
    "avg_health": number,
    "avg_battery": number
  },
  "drone_assessments": [
    {
      "drone_id": "string",
      "health_score": number,
      "risk_level": "low | medium | high | critical",
      "findings": ["string"],
      "degradation_trend": "stable | degrading | improving"
    }
  ],
  "maintenance_schedule": [
    {
      "priority": number,
      "drone_id": "string",
      "action": "string",
      "category": "battery | thruster | sensor | hull | software | inspection",
      "urgency": "immediate | 48h | 1week | routine",
      "estimated_downtime_hours": number,
      "justification": "string",
      "manual_refs": [{"doc": "string", "section": "string", "excerpt": "string"}]
    }
  ],
  "next_review_date": "string"
}
"""

# ═══════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════

MAINTENANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_drones",
            "description": "List all 5 drones with current status, battery, health, state.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drone_limits",
            "description": "Get safety limits for a specific drone.",
            "parameters": {
                "type": "object",
                "properties": {"drone_id": {"type": "string"}},
                "required": ["drone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_telemetry_trends",
            "description": "Get recent telemetry trends: anomaly scores, health labels, thruster currents, temps, nav error over last 7 days.",
            "parameters": {
                "type": "object",
                "properties": {"drone_id": {"type": "string"}},
                "required": ["drone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mission_history",
            "description": "Get completed missions, total hours, cycle count for a drone.",
            "parameters": {
                "type": "object",
                "properties": {"drone_id": {"type": "string"}},
                "required": ["drone_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_manuals",
            "description": "RAG query against subsea manuals for maintenance procedures and OEM intervals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "num_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════
# TOOL EXECUTORS
# ═══════════════════════════════════════════════════════════════

import db

def _exec_tool(name: str, args: dict) -> str:
    if name == "list_drones":
        return json.dumps(db.get_all_drones(), default=str)

    if name == "get_drone_limits":
        drone = db.get_drone(args["drone_id"])
        if not drone:
            return json.dumps({"error": f"Drone {args['drone_id']} not found"})
        return json.dumps({k: drone[k] for k in [
            "drone_id", "max_depth_m", "max_duration_min",
            "min_battery_reserve_pct_low_risk", "min_battery_reserve_pct_med_risk",
            "min_battery_reserve_pct_high_risk",
        ]}, default=str)

    if name == "get_telemetry_trends":
        features = db.sql_query(f"""
            SELECT drone_id, mission_id, window_start_ts, anomaly_score, health_label,
                   peak_thruster_current_a, max_internal_temp_c, mean_nav_error_m, comms_loss_fraction
            FROM telemetry_features
            WHERE drone_id = '{args["drone_id"]}'
            ORDER BY window_end_ts DESC LIMIT 10
        """)
        return json.dumps(features, default=str)

    if name == "get_mission_history":
        missions = db.sql_query(f"""
            SELECT i.mission_id, i.asset_id, i.asset_type, i.status, i.start_ts, i.end_ts
            FROM inspections i
            JOIN autopilot_decisions d ON i.mission_id = d.mission_id AND d.decision_type = 'launch'
            WHERE d.input_json LIKE '%{args["drone_id"]}%' OR d.tool_outputs_json LIKE '%{args["drone_id"]}%'
            ORDER BY i.start_ts DESC LIMIT 20
        """)
        if not missions:
            missions = db.sql_query(f"""
                SELECT mission_id, asset_id, asset_type, status, start_ts, end_ts
                FROM inspections ORDER BY start_ts DESC LIMIT 10
            """)
        return json.dumps(missions, default=str)

    if name == "query_manuals":
        chunks = db.query_manual_chunks(args["query"], args.get("num_results", 5))
        return json.dumps(chunks, default=str)

    return json.dumps({"error": f"Unknown tool: {name}"})


# ═══════════════════════════════════════════════════════════════
# AGENT RUNNER
# ═══════════════════════════════════════════════════════════════

def run_agent_stream(user_prompt: str) -> Generator[dict, None, None]:
    yield from run_agent_loop_stream(
        MAINTENANCE_SYSTEM_PROMPT, user_prompt,
        MAINTENANCE_TOOLS, _exec_tool, max_iterations=10, max_tokens=6144,
    )
