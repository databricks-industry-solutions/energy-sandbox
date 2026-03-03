"""
BOP Guardian — real-time BOP stack simulator.
Generates telemetry for a single offshore rig with realistic drilling context.

Rig: Deepwater Horizon-class (demo name: "Deepwater Sentinel")
BOP Stack: 18-3/4" 15K ram/annular
Components: Annular, Upper Pipe Ram, Lower Pipe Ram, Blind Shear Ram,
            Pod A, Pod B, Pump 1, Pump 2, Accumulator, PLC

40-tick event cycle:
  0-9   Normal operations — all green
 10-14  Annular pressure creep (slow leak developing)
 15-19  Pod A intermittent comm loss
 20-24  Pump 1 high current draw (bearing wear)
 25-29  Blind shear ram slow close detected
 30-34  Recovery / stabilisation
 35-39  Accumulator pressure decay anomaly
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any


RIG_ID = "RIG-SENTINEL"
RIG_NAME = "Deepwater Sentinel"
WELL_ID = "GOM-DS-001"
WELL_NAME = "Mississippi Canyon Block 252 #1"

COMPONENTS = [
    {"asset_id": "BOP-ANN-01", "component_type": "ANNULAR", "name": "18-3/4 Annular Preventer"},
    {"asset_id": "BOP-UPR-01", "component_type": "UPPER_PIPE_RAM", "name": "Upper Pipe Ram 6-5/8"},
    {"asset_id": "BOP-LPR-01", "component_type": "LOWER_PIPE_RAM", "name": "Lower Pipe Ram 6-5/8"},
    {"asset_id": "BOP-BSR-01", "component_type": "BLIND_SHEAR_RAM", "name": "Blind Shear Ram"},
    {"asset_id": "POD-A", "component_type": "POD_A", "name": "Control Pod A (Blue)"},
    {"asset_id": "POD-B", "component_type": "POD_B", "name": "Control Pod B (Yellow)"},
    {"asset_id": "PMP-01", "component_type": "PUMP", "name": "Koomey Pump Unit 1"},
    {"asset_id": "PMP-02", "component_type": "PUMP", "name": "Koomey Pump Unit 2"},
    {"asset_id": "ACC-01", "component_type": "ACCUMULATOR", "name": "Accumulator Bank"},
    {"asset_id": "PLC-01", "component_type": "PLC", "name": "BOP Control PLC"},
]

# Sensor baselines per component type
SENSOR_DEFS: dict[str, list[dict]] = {
    "ANNULAR": [
        {"tag": "ANN_CLOSE_PRESS", "base": 3000, "noise": 40, "unit": "psi"},
        {"tag": "ANN_OPEN_PRESS", "base": 1500, "noise": 30, "unit": "psi"},
        {"tag": "ANN_REG_PRESS", "base": 1800, "noise": 25, "unit": "psi"},
        {"tag": "ANN_TEMP", "base": 145, "noise": 3, "unit": "F"},
    ],
    "UPPER_PIPE_RAM": [
        {"tag": "UPR_CLOSE_PRESS", "base": 3200, "noise": 35, "unit": "psi"},
        {"tag": "UPR_OPEN_PRESS", "base": 1600, "noise": 25, "unit": "psi"},
        {"tag": "UPR_CLOSE_TIME", "base": 28, "noise": 1.5, "unit": "sec"},
    ],
    "LOWER_PIPE_RAM": [
        {"tag": "LPR_CLOSE_PRESS", "base": 3200, "noise": 35, "unit": "psi"},
        {"tag": "LPR_OPEN_PRESS", "base": 1600, "noise": 25, "unit": "psi"},
        {"tag": "LPR_CLOSE_TIME", "base": 30, "noise": 1.5, "unit": "sec"},
    ],
    "BLIND_SHEAR_RAM": [
        {"tag": "BSR_CLOSE_PRESS", "base": 4500, "noise": 50, "unit": "psi"},
        {"tag": "BSR_OPEN_PRESS", "base": 2200, "noise": 40, "unit": "psi"},
        {"tag": "BSR_CLOSE_TIME", "base": 35, "noise": 2, "unit": "sec"},
        {"tag": "BSR_SHEAR_PRESS", "base": 5200, "noise": 80, "unit": "psi"},
    ],
    "POD_A": [
        {"tag": "PODA_SIGNAL_STR", "base": 95, "noise": 2, "unit": "%"},
        {"tag": "PODA_VOLTAGE", "base": 24.0, "noise": 0.3, "unit": "V"},
        {"tag": "PODA_TEMP", "base": 120, "noise": 5, "unit": "F"},
        {"tag": "PODA_COMM_OK", "base": 1.0, "noise": 0, "unit": "bool"},
    ],
    "POD_B": [
        {"tag": "PODB_SIGNAL_STR", "base": 93, "noise": 2, "unit": "%"},
        {"tag": "PODB_VOLTAGE", "base": 24.0, "noise": 0.3, "unit": "V"},
        {"tag": "PODB_TEMP", "base": 118, "noise": 5, "unit": "F"},
        {"tag": "PODB_COMM_OK", "base": 1.0, "noise": 0, "unit": "bool"},
    ],
    "PUMP": [
        {"tag": "PUMP_PRESS", "base": 3000, "noise": 50, "unit": "psi"},
        {"tag": "PUMP_FLOW", "base": 12, "noise": 0.5, "unit": "gpm"},
        {"tag": "PUMP_CURRENT", "base": 45, "noise": 2, "unit": "A"},
        {"tag": "PUMP_TEMP", "base": 160, "noise": 5, "unit": "F"},
        {"tag": "PUMP_VIBRATION", "base": 2.5, "noise": 0.3, "unit": "mm/s"},
    ],
    "ACCUMULATOR": [
        {"tag": "ACC_PRESS", "base": 3000, "noise": 30, "unit": "psi"},
        {"tag": "ACC_PRECHARGE", "base": 1000, "noise": 15, "unit": "psi"},
        {"tag": "ACC_VOLUME", "base": 85, "noise": 2, "unit": "%"},
        {"tag": "ACC_TEMP", "base": 130, "noise": 4, "unit": "F"},
    ],
    "PLC": [
        {"tag": "PLC_CPU_LOAD", "base": 35, "noise": 5, "unit": "%"},
        {"tag": "PLC_MEMORY", "base": 42, "noise": 3, "unit": "%"},
        {"tag": "PLC_SCAN_TIME", "base": 15, "noise": 2, "unit": "ms"},
        {"tag": "PLC_IO_ERRORS", "base": 0, "noise": 0, "unit": "count"},
    ],
}

# Drilling operations cycle
DRILLING_OPS = [
    {"op_code": "DRILL", "description": "Drilling 12-1/4\" hole", "section": "12-1/4\" Section",
     "is_low_risk": True, "depth_md": 14200, "depth_tvd": 11800},
    {"op_code": "CIRC", "description": "Circulating bottoms up", "section": "12-1/4\" Section",
     "is_low_risk": True, "depth_md": 14200, "depth_tvd": 11800},
    {"op_code": "TRIP", "description": "Tripping out for bit change", "section": "12-1/4\" Section",
     "is_low_risk": False, "depth_md": 14200, "depth_tvd": 11800},
    {"op_code": "BOP_TEST", "description": "BOP pressure test", "section": "12-1/4\" Section",
     "is_low_risk": False, "depth_md": 14200, "depth_tvd": 11800},
    {"op_code": "DRILL", "description": "Drilling ahead", "section": "12-1/4\" Section",
     "is_low_risk": True, "depth_md": 14500, "depth_tvd": 12000},
]

# ── State ─────────────────────────────────────────────────

_tick = 0
_telemetry_history: list[dict] = []
_events: list[dict] = []
_anomalies: list[dict] = []


def _now():
    return datetime.now(timezone.utc)


def simulate_tick() -> dict[str, Any]:
    """Run one simulation tick. Returns full rig state snapshot."""
    global _tick
    _tick += 1
    phase = _tick % 40
    now = _now()
    tick_events = []
    tick_anomalies = []

    # Generate telemetry for each component
    readings = []
    component_health = {}

    for comp in COMPONENTS:
        ctype = comp["component_type"]
        aid = comp["asset_id"]
        # Handle PUMP type (two pumps share same sensor defs)
        sensor_key = ctype if ctype != "PUMP" else "PUMP"
        if ctype in ("UPPER_PIPE_RAM", "LOWER_PIPE_RAM"):
            sensor_key = ctype
        defs = SENSOR_DEFS.get(sensor_key, SENSOR_DEFS.get(ctype, []))

        health = 1.0
        anomaly_flag = False
        anomaly_type = None

        for sdef in defs:
            base = sdef["base"]
            noise = sdef["noise"]
            tag = sdef["tag"]
            value = base + random.gauss(0, noise) + base * 0.01 * math.sin(_tick * 0.15)

            # Apply phase-based anomalies
            if ctype == "ANNULAR" and 10 <= phase <= 14:
                if "PRESS" in tag:
                    value *= 0.92 - (phase - 10) * 0.015  # pressure leak
                    health = min(health, 0.65)
                    anomaly_flag = True
                    anomaly_type = "PRESSURE_LEAK"

            elif ctype == "POD_A" and 15 <= phase <= 19:
                if tag == "PODA_COMM_OK":
                    value = 0.0 if random.random() < 0.6 else 1.0
                    health = min(health, 0.45)
                    anomaly_flag = True
                    anomaly_type = "COMM_LOSS"
                elif tag == "PODA_SIGNAL_STR":
                    value *= 0.4
                    health = min(health, 0.50)

            elif aid == "PMP-01" and 20 <= phase <= 24:
                if tag == "PUMP_CURRENT":
                    value *= 1.35 + (phase - 20) * 0.05
                    health = min(health, 0.55)
                    anomaly_flag = True
                    anomaly_type = "HIGH_CURRENT"
                elif tag == "PUMP_VIBRATION":
                    value *= 2.2
                    health = min(health, 0.60)
                elif tag == "PUMP_TEMP":
                    value *= 1.15

            elif ctype == "BLIND_SHEAR_RAM" and 25 <= phase <= 29:
                if tag == "BSR_CLOSE_TIME":
                    value *= 1.6 + (phase - 25) * 0.08  # slow close
                    health = min(health, 0.50)
                    anomaly_flag = True
                    anomaly_type = "SLOW_CLOSE"
                elif tag == "BSR_CLOSE_PRESS":
                    value *= 1.12

            elif ctype == "ACCUMULATOR" and 35 <= phase <= 39:
                if tag == "ACC_PRESS":
                    value *= 0.85 - (phase - 35) * 0.02
                    health = min(health, 0.58)
                    anomaly_flag = True
                    anomaly_type = "PRESSURE_DECAY"
                elif tag == "ACC_VOLUME":
                    value *= 0.88

            value = max(value, 0)
            readings.append({
                "rig_id": RIG_ID, "asset_id": aid, "asset_type": ctype,
                "ts": now.isoformat(), "tag": tag,
                "value": round(value, 2), "unit": sdef["unit"],
            })

        if not anomaly_flag:
            health = min(1.0, 0.85 + random.uniform(0, 0.15))

        component_health[aid] = {
            "asset_id": aid, "component_type": ctype, "name": comp["name"],
            "health_score": round(health, 3),
            "anomaly_flag": anomaly_flag, "anomaly_type": anomaly_type,
        }

        if anomaly_flag and anomaly_type:
            tick_anomalies.append({
                "rig_id": RIG_ID, "asset_id": aid, "component_type": ctype,
                "anomaly_type": anomaly_type,
                "severity": 3 if health < 0.5 else 2,
                "ts": now.isoformat(),
            })
            tick_events.append({
                "rig_id": RIG_ID, "asset_id": aid,
                "event_type": "ANOMALY_DETECTED",
                "severity": 3 if health < 0.5 else 2,
                "message": f"{ctype} {aid}: {anomaly_type} detected (health={health:.2f})",
                "ts": now.isoformat(),
            })

    # Store history
    _telemetry_history.extend(readings)
    if len(_telemetry_history) > 5000:
        _telemetry_history[:] = _telemetry_history[-5000:]
    _events.extend(tick_events)
    if len(_events) > 200:
        _events[:] = _events[-200:]
    _anomalies.extend(tick_anomalies)
    if len(_anomalies) > 200:
        _anomalies[:] = _anomalies[-200:]

    # Current drilling operation
    op_idx = (_tick // 8) % len(DRILLING_OPS)
    current_op = DRILLING_OPS[op_idx].copy()
    current_op["depth_md"] = current_op["depth_md"] + _tick * 0.8
    current_op["depth_tvd"] = current_op["depth_tvd"] + _tick * 0.6

    # Overall rig status
    min_health = min(h["health_score"] for h in component_health.values())
    if min_health < 0.5:
        rig_status = "ACT_NOW"
        status_reason = next(
            (f'{h["component_type"]}: {h["anomaly_type"]}' for h in component_health.values()
             if h["health_score"] < 0.5), "Critical anomaly"
        )
    elif min_health < 0.7:
        rig_status = "WATCH"
        status_reason = next(
            (f'{h["component_type"]}: {h["anomaly_type"]}' for h in component_health.values()
             if h["health_score"] < 0.7 and h["anomaly_flag"]), "Anomaly under observation"
        )
    else:
        rig_status = "NORMAL"
        status_reason = "All BOP systems nominal"

    return {
        "rig_id": RIG_ID,
        "rig_name": RIG_NAME,
        "well_id": WELL_ID,
        "well_name": WELL_NAME,
        "tick": _tick,
        "ts": now.isoformat(),
        "status": rig_status,
        "status_reason": status_reason,
        "components": component_health,
        "readings": readings,
        "events": tick_events,
        "anomalies": tick_anomalies,
        "current_op": current_op,
        "kpis": {
            "min_health": round(min_health, 3),
            "active_anomalies": sum(1 for h in component_health.values() if h["anomaly_flag"]),
            "total_components": len(COMPONENTS),
            "healthy_components": sum(1 for h in component_health.values() if h["health_score"] >= 0.8),
            "depth_md": round(current_op["depth_md"], 0),
            "depth_tvd": round(current_op["depth_tvd"], 0),
        },
    }


def get_telemetry_history(asset_id: str | None = None, tag: str | None = None,
                          limit: int = 200) -> list[dict]:
    result = _telemetry_history
    if asset_id:
        result = [r for r in result if r["asset_id"] == asset_id]
    if tag:
        result = [r for r in result if r["tag"] == tag]
    return result[-limit:]


def get_events(limit: int = 30) -> list[dict]:
    return _events[-limit:]


def get_anomalies(limit: int = 30) -> list[dict]:
    return _anomalies[-limit:]
