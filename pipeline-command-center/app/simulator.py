"""
Pipeline Command Center — Real-Time Pipeline Telemetry Simulator
40-tick event cycle with realistic midstream pipeline incidents.
"""

from __future__ import annotations

import random, math, copy
from datetime import datetime, timezone

from mock_data import (
    ASSETS, SENSOR_DEFS, RUL_PREDICTIONS, FAILURE_PATTERNS,
    WORK_ORDERS, SPARE_PARTS, CREW, OPERATIONS_CYCLE,
)

# ── Constants ──────────────────────────────────────────────────────
PIPELINE_ID   = "PL-EAGLE-FORD-24"
PIPELINE_NAME = "Eagle Ford Midstream Trunk"
ROUTE         = "Karnes County TX → Corpus Christi Terminal"
LENGTH_MI     = 87.3
DIAMETER      = "24″ OD × 0.500″ WT — API 5L X65"
CYCLE_LEN     = 40

# History caps
MAX_READINGS  = 5000
MAX_EVENTS    = 200
MAX_ANOMALIES = 200

# ── State Buffers ──────────────────────────────────────────────────
_tick: int = 0
_history_readings: list[dict] = []
_history_events: list[dict]   = []
_history_anomalies: list[dict] = []
_component_health: dict[str, float] = {a["asset_id"]: 1.0 for a in ASSETS}

# ── Helpers ────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_event(severity: str, source: str, message: str):
    ev = {"ts": _ts(), "severity": severity, "source": source, "message": message}
    _history_events.append(ev)
    if len(_history_events) > MAX_EVENTS:
        _history_events.pop(0)
    return ev


def _add_anomaly(asset_id: str, tag: str, value: float, severity: str, message: str):
    an = {"ts": _ts(), "asset_id": asset_id, "tag": tag, "value": value,
          "severity": severity, "message": message}
    _history_anomalies.append(an)
    if len(_history_anomalies) > MAX_ANOMALIES:
        _history_anomalies.pop(0)
    return an


def _noise(base: float, noise: float) -> float:
    return base + random.uniform(-noise, noise)


# ── Scenario Injectors ────────────────────────────────────────────

def _inject_scenario(phase: int, readings: dict[str, dict[str, float]]):
    """Inject anomalies into the current tick based on the 40-tick cycle phase."""
    new_events = []
    new_anomalies = []

    if 10 <= phase <= 14:
        # Segment 2 — external corrosion + pressure drop
        seg = readings.get("SEG-02", {})
        seg["CORR_RATE"] = _noise(8.5, 0.5)          # way above 5 mpy threshold
        seg["PRESS_OUT"] = _noise(880, 10)            # dropping
        _component_health["SEG-02"] = 0.58
        new_anomalies.append(_add_anomaly("SEG-02", "CORR_RATE", seg["CORR_RATE"],
                                          "WARNING", "Corrosion rate elevated — possible coating failure at MP 35"))
        new_events.append(_add_event("WARNING", "SEG-02", "Corrosion rate 8.5 mpy exceeds 5 mpy threshold"))

    elif 15 <= phase <= 19:
        # Compressor Alpha — high vibration + bearing temp rise
        cs = readings.get("CS-01", {})
        cs["VIBRATION"]  = _noise(9.8, 0.6)           # alarm at 7.5 mm/s
        cs["TEMP_BEAR"]  = _noise(215, 5)              # alarm at 200°F
        cs["RPM"]        = _noise(3450, 30)            # slight speed drop
        _component_health["CS-01"] = 0.42
        new_anomalies.append(_add_anomaly("CS-01", "VIBRATION", cs["VIBRATION"],
                                          "CRITICAL", "Compressor Alpha vibration exceeds trip threshold"))
        new_anomalies.append(_add_anomaly("CS-01", "TEMP_BEAR", cs["TEMP_BEAR"],
                                          "WARNING", "Bearing temperature rising — degradation trend"))
        new_events.append(_add_event("CRITICAL", "CS-01", "Compressor vibration alarm — potential impeller imbalance"))

    elif 20 <= phase <= 24:
        # Pump Station 1 — seal leak + flow imbalance
        ps = readings.get("PS-01", {})
        ps["CURRENT"]    = _noise(340, 10)             # high current
        ps["VIBRATION"]  = _noise(6.5, 0.4)            # elevated
        ps["TEMP_BEAR"]  = _noise(195, 5)              # warming
        _component_health["PS-01"] = 0.50
        # Meter drift at inlet
        met = readings.get("MET-01", {})
        met["FLOW"] = _noise(8200, 60)                 # divergence from delivery meter
        _component_health["MET-01"] = 0.72
        new_anomalies.append(_add_anomaly("PS-01", "CURRENT", ps["CURRENT"],
                                          "WARNING", "Pump motor drawing excess current — possible seal degradation"))
        new_anomalies.append(_add_anomaly("MET-01", "FLOW", met["FLOW"],
                                          "INFO", "Flow imbalance 300 bbl/h between inlet and delivery meters"))
        new_events.append(_add_event("WARNING", "PS-01", "Pump seal leak suspected — elevated motor current and vibration"))

    elif 25 <= phase <= 29:
        # Block Valve 2 — slow stroke + RTU-02 comm intermittent
        vlv = readings.get("VLV-02", {})
        vlv["ACTUATOR_P"] = _noise(52, 3)              # low actuator pressure
        vlv["POSITION"]   = _noise(97, 1)              # not fully open
        _component_health["VLV-02"] = 0.55
        rtu = readings.get("RTU-02", {})
        rtu["SIGNAL_STR"] = _noise(-82, 2)             # weak signal
        rtu["COMM_OK"]    = 0 if random.random() < 0.4 else 1
        _component_health["RTU-02"] = 0.60
        new_anomalies.append(_add_anomaly("VLV-02", "ACTUATOR_P", vlv["ACTUATOR_P"],
                                          "WARNING", "Block Valve 2 actuator pressure low — slow stroke risk"))
        new_anomalies.append(_add_anomaly("RTU-02", "SIGNAL_STR", rtu["SIGNAL_STR"],
                                          "WARNING", "SCADA RTU Midpoint — intermittent comm loss"))
        new_events.append(_add_event("WARNING", "VLV-02", "Valve actuator pressure below 60 psig minimum"))

    elif 30 <= phase <= 34:
        # Recovery — health improving
        for aid in ["SEG-02", "CS-01", "PS-01", "MET-01", "VLV-02", "RTU-02"]:
            h = _component_health[aid]
            _component_health[aid] = min(1.0, h + 0.08)
        new_events.append(_add_event("INFO", "SYSTEM", "Recovery — anomaly conditions stabilizing"))

    elif 35 <= phase <= 39:
        # CP system under-protection + segment 3 corrosion concern
        cp = readings.get("CP-01", {})
        cp["PIPE_POT"] = _noise(-750, 10)              # above -850 mV → under-protected
        cp["RECT_A"]   = _noise(4.2, 0.3)              # low output
        _component_health["CP-01"] = 0.55
        seg3 = readings.get("SEG-03", {})
        seg3["CORR_RATE"] = _noise(5.8, 0.4)
        _component_health["SEG-03"] = 0.68
        new_anomalies.append(_add_anomaly("CP-01", "PIPE_POT", cp["PIPE_POT"],
                                          "CRITICAL", "Pipe-to-soil potential above -850 mV — under-protection"))
        new_anomalies.append(_add_anomaly("SEG-03", "CORR_RATE", seg3["CORR_RATE"],
                                          "WARNING", "Segment 3 corrosion rate trending up — CP issue downstream"))
        new_events.append(_add_event("CRITICAL", "CP-01", "Cathodic protection below NACE SP0169 criteria"))

    return new_events, new_anomalies


# ── Main Simulation Tick ───────────────────────────────────────────

def simulate_tick() -> dict:
    """Generate one tick of the pipeline simulation."""
    global _tick
    phase = _tick % CYCLE_LEN
    _tick += 1

    # Reset health for normal ticks
    if phase < 10:
        for aid in _component_health:
            _component_health[aid] = min(1.0, _component_health.get(aid, 1.0) + 0.03)

    # ── Generate baseline readings ─────────────────────────────────
    readings: dict[str, dict[str, float]] = {}
    for asset in ASSETS:
        aid  = asset["asset_id"]
        atype = asset["type"]
        defs = SENSOR_DEFS.get(atype, [])
        r = {}
        for sd in defs:
            r[sd["tag"]] = _noise(sd["base"], sd["noise"])
        readings[aid] = r

    # ── Inject scenario anomalies ──────────────────────────────────
    tick_events, tick_anomalies = _inject_scenario(phase, readings)

    # ── Store history ──────────────────────────────────────────────
    ts = _ts()
    for aid, vals in readings.items():
        for tag, val in vals.items():
            _history_readings.append({"ts": ts, "asset_id": aid, "tag": tag, "value": val})
    if len(_history_readings) > MAX_READINGS:
        _history_readings[:] = _history_readings[-MAX_READINGS:]

    # ── Component summary ──────────────────────────────────────────
    components = []
    for asset in ASSETS:
        aid = asset["asset_id"]
        components.append({
            **asset,
            "health": round(_component_health.get(aid, 1.0), 2),
            "readings": readings.get(aid, {}),
        })

    # ── Pipeline status ────────────────────────────────────────────
    min_health = min(_component_health.values())
    if min_health >= 0.8:
        status, reason = "NORMAL", "All systems nominal"
    elif min_health >= 0.6:
        status, reason = "WATCH", "Anomaly detected — monitoring"
    else:
        status, reason = "ACT_NOW", "Critical condition — intervention required"

    # ── Current operation ──────────────────────────────────────────
    op_idx = (_tick // 8) % len(OPERATIONS_CYCLE)
    current_op = OPERATIONS_CYCLE[op_idx]

    # ── KPIs ───────────────────────────────────────────────────────
    avg_health = sum(_component_health.values()) / len(_component_health)
    active_anomalies = sum(1 for a in _history_anomalies[-20:] if a["severity"] in ("WARNING", "CRITICAL"))
    open_wos = sum(1 for w in WORK_ORDERS if w["status"] in ("OPEN", "IN_PROGRESS"))

    kpis = {
        "avg_health": round(avg_health, 2),
        "min_health": round(min_health, 2),
        "throughput_bblh": round(_noise(8500, 100)),
        "active_anomalies": active_anomalies,
        "open_work_orders": open_wos,
        "uptime_pct": round(99.2 + random.uniform(-0.3, 0.3), 1),
    }

    return {
        "pipeline_id":   PIPELINE_ID,
        "pipeline_name": PIPELINE_NAME,
        "route":         ROUTE,
        "length_mi":     LENGTH_MI,
        "diameter":      DIAMETER,
        "tick":          _tick,
        "ts":            ts,
        "status":        status,
        "status_reason": reason,
        "components":    components,
        "readings":      readings,
        "events":        list(_history_events),
        "anomalies":     list(_history_anomalies),
        "current_op":    current_op,
        "kpis":          kpis,
    }
