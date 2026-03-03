"""
ESP Well Simulator — physics-based parameter simulation for 12 wells.
Live-streaming mode: 3s refresh, 20-tick loop with cycle-driven critical events.

Cycle map (tick % 20):
  0– 4  ESP-009 Sunrise-2    → temperature spike → HIGH_TEMP CRITICAL
  5– 9  ESP-007 Redstone-4   → motor overload surge → MOTOR_OVERLOAD CRITICAL
 10–14  ESP-003 Crawford-1   → bearing failure escalation → BEARING_FAILURE_RISK CRITICAL
 15–19  ESP-002 Meridian-2B  → gas interference surge → GAS_INTERFERENCE HIGH
"""
from __future__ import annotations
import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

WELLS = [
    {"esp_id": "ESP-001", "name": "Meridian-1A",  "field": "Permian Basin", "depth_ft": 8500,  "hp": 150, "stage": "healthy",          "days_online": 142},
    {"esp_id": "ESP-002", "name": "Meridian-2B",  "field": "Permian Basin", "depth_ft": 8200,  "hp": 125, "stage": "gas_interference",  "days_online": 287},
    {"esp_id": "ESP-003", "name": "Crawford-1",   "field": "Eagle Ford",    "depth_ft": 9100,  "hp": 200, "stage": "bearing_wear",      "days_online": 521},
    {"esp_id": "ESP-004", "name": "Crawford-3A",  "field": "Eagle Ford",    "depth_ft": 9300,  "hp": 175, "stage": "healthy",           "days_online": 63},
    {"esp_id": "ESP-005", "name": "Oakhurst-7",   "field": "DJ Basin",      "depth_ft": 7200,  "hp": 100, "stage": "pump_wear",         "days_online": 412},
    {"esp_id": "ESP-006", "name": "Oakhurst-12",  "field": "DJ Basin",      "depth_ft": 7400,  "hp": 100, "stage": "healthy",           "days_online": 89},
    {"esp_id": "ESP-007", "name": "Redstone-4",   "field": "Bakken",        "depth_ft": 10200, "hp": 250, "stage": "overload",          "days_online": 334},
    {"esp_id": "ESP-008", "name": "Redstone-9A",  "field": "Bakken",        "depth_ft": 10400, "hp": 225, "stage": "healthy",           "days_online": 201},
    {"esp_id": "ESP-009", "name": "Sunrise-2",    "field": "Marcellus",     "depth_ft": 11500, "hp": 300, "stage": "critical_temp",     "days_online": 678},
    {"esp_id": "ESP-010", "name": "Sunrise-5B",   "field": "Marcellus",     "depth_ft": 11200, "hp": 275, "stage": "scale_buildup",     "days_online": 156},
    {"esp_id": "ESP-011", "name": "Prairie-1",    "field": "Permian Basin", "depth_ft": 8900,  "hp": 150, "stage": "healthy",           "days_online": 34},
    {"esp_id": "ESP-012", "name": "Prairie-3",    "field": "Permian Basin", "depth_ft": 8700,  "hp": 150, "stage": "healthy",           "days_online": 98},
]

# Cycle-driven critical event windows (cycle_start, cycle_end) within tick % 20
_CYCLE_EVENTS: Dict[str, tuple] = {
    "ESP-009": (0,  4),   # temperature spike
    "ESP-007": (5,  9),   # motor overload
    "ESP-003": (10, 14),  # bearing failure
    "ESP-002": (15, 19),  # gas interference surge
}


def _g(mu: float, sigma: float) -> float:
    """Gaussian noise helper."""
    return random.gauss(mu, sigma)


def _cycle_intensity(cycle: int, start: int, end: int) -> float:
    """Return 0-1 sine envelope for cycle events (peaks at midpoint of window)."""
    if start <= cycle <= end:
        return math.sin(((cycle - start) / max(end - start, 1)) * math.pi)
    return 0.0


def _simulate_params(well: Dict[str, Any], tick: int) -> Dict[str, Any]:
    """Simulate sensor parameters for a single well."""
    esp_id = well["esp_id"]
    stage  = well["stage"]
    t      = tick * 0.1                         # legacy progressive factor
    cycle  = tick % 20                          # 20-step live loop
    phi    = (cycle / 20.0) * 2.0 * math.pi    # phase for sinusoidal oscillation

    # ── Base values with sinusoidal oscillation for live "breathing" feel ──────
    motor_temp_f       = _g(165 + 4.0 * math.sin(phi),           3.0)
    intake_pressure    = _g(1150 + 30.0 * math.sin(phi + 1.0),  40.0)
    discharge_pressure = _g(2450 + 80.0 * math.cos(phi),        60.0)
    motor_current_pct  = _g(80 + 3.0 * math.sin(phi + 0.5),      4.0)
    frequency_hz       = _g(52 + 1.5 * math.sin(phi + 2.0),      2.0)
    vibration_mms      = _g(1.2 + 0.3 * abs(math.sin(phi)),      0.2)
    flow_rate_bpd      = _g(1300 + 100.0 * math.cos(phi + 0.8), 80.0)
    fluid_temp_f       = _g(162 + 3.0 * math.sin(phi),           4.0)
    wellhead_pressure  = _g(380 + 20.0 * math.sin(phi + 1.5),   30.0)

    # ── Stage-specific deviations ─────────────────────────────────────────────
    if stage == "gas_interference":
        pip_dev = -350 + 20 * math.sin(t)
        intake_pressure    += _g(pip_dev, 15)
        vibration_mms      += _g(1.8, 0.3)
        flow_rate_bpd      += _g(-400, 30)
        motor_current_pct  += _g(-12, 2)

    elif stage == "bearing_wear":
        vibration_mms      += _g(2.1 + 0.1 * tick, 0.2)
        motor_temp_f       += _g(12, 2)
        motor_current_pct  += _g(6, 1.5)

    elif stage == "pump_wear":
        flow_rate_bpd      += _g(-350, 25)
        motor_current_pct  += _g(15, 2)
        discharge_pressure += _g(-300, 40)
        vibration_mms      += _g(1.0, 0.2)

    elif stage == "overload":
        motor_current_pct  += _g(25, 3)
        motor_temp_f       += _g(18, 2)
        flow_rate_bpd      += _g(400, 50)

    elif stage == "critical_temp":
        motor_temp_f       += _g(32 + 0.1 * tick, 2)
        fluid_temp_f       += _g(20, 3)
        vibration_mms      += _g(1.5, 0.3)
        motor_current_pct  += _g(10, 2)

    elif stage == "scale_buildup":
        discharge_pressure += _g(450 + 3 * tick, 30)
        flow_rate_bpd      += _g(-280, 25)
        motor_current_pct  += _g(18, 2)

    # ── Cycle-driven critical event overlay ──────────────────────────────────
    if esp_id in _CYCLE_EVENTS:
        ev_start, ev_end = _CYCLE_EVENTS[esp_id]
        intensity = _cycle_intensity(cycle, ev_start, ev_end)
        if intensity > 0:
            if esp_id == "ESP-009":
                # Temperature spike: push motor_temp past 200°F → HIGH_TEMP CRITICAL
                motor_temp_f      += intensity * 45.0
                fluid_temp_f      += intensity * 25.0
                vibration_mms     += intensity * 1.5
            elif esp_id == "ESP-007":
                # Motor overload surge: push current past 112% → MOTOR_OVERLOAD CRITICAL
                motor_current_pct += intensity * 32.0
                motor_temp_f      += intensity * 20.0
            elif esp_id == "ESP-003":
                # Bearing failure: push vibration past 5.0 mm/s → BEARING_FAILURE_RISK CRITICAL
                vibration_mms     += intensity * 5.5
                motor_temp_f      += intensity * 15.0
            elif esp_id == "ESP-002":
                # Gas interference surge: drop intake pressure, spike vibration
                intake_pressure   -= intensity * 450.0
                vibration_mms     += intensity * 2.5

    # ── 5% random micro-spike (live streaming noise) ──────────────────────────
    if random.random() < 0.05:
        spike = random.randint(0, 4)
        if spike == 0:
            motor_temp_f      += random.uniform(8, 18)
        elif spike == 1:
            vibration_mms     += random.uniform(0.8, 2.0)
        elif spike == 2:
            motor_current_pct += random.uniform(8, 20)
        elif spike == 3:
            intake_pressure   -= random.uniform(50, 150)
        else:
            flow_rate_bpd     -= random.uniform(100, 250)

    # ── Clamp to physical limits ──────────────────────────────────────────────
    motor_temp_f       = max(140, min(240, motor_temp_f))
    intake_pressure    = max(200, min(2000, intake_pressure))
    discharge_pressure = max(800, min(5000, discharge_pressure))
    motor_current_pct  = max(10, min(130, motor_current_pct))
    frequency_hz       = max(30, min(65, frequency_hz))
    vibration_mms      = max(0.1, min(10, vibration_mms))
    flow_rate_bpd      = max(50, min(3000, flow_rate_bpd))
    fluid_temp_f       = max(120, min(220, fluid_temp_f))
    wellhead_pressure  = max(50, min(1000, wellhead_pressure))

    pump_efficiency_pct = max(20, min(95, 85 - (motor_current_pct - 78) * 0.5 - (vibration_mms - 1.2) * 3))
    power_kw = round(well["hp"] * 0.746 * (motor_current_pct / 100), 1)

    return {
        "motor_temp_f":           round(motor_temp_f, 1),
        "intake_pressure_psi":    round(intake_pressure, 1),
        "discharge_pressure_psi": round(discharge_pressure, 1),
        "motor_current_pct":      round(motor_current_pct, 1),
        "frequency_hz":           round(frequency_hz, 1),
        "vibration_mms":          round(vibration_mms, 2),
        "flow_rate_bpd":          round(flow_rate_bpd, 0),
        "fluid_temp_f":           round(fluid_temp_f, 1),
        "wellhead_pressure_psi":  round(wellhead_pressure, 1),
        "pump_efficiency_pct":    round(pump_efficiency_pct, 1),
        "power_kw":               power_kw,
    }


def _compute_fault_codes(params: Dict[str, Any]) -> List[Dict[str, str]]:
    """Determine active fault codes from sensor parameters."""
    faults = []
    temp = params["motor_temp_f"]
    vib  = params["vibration_mms"]
    cur  = params["motor_current_pct"]
    pip  = params["intake_pressure_psi"]
    eff  = params["pump_efficiency_pct"]
    dp   = params["discharge_pressure_psi"]
    flow = params["flow_rate_bpd"]

    if cur > 112:
        faults.append({"code": "MOTOR_OVERLOAD", "severity": "CRITICAL"})
    if pip < 800 and vib > 2.0:
        faults.append({"code": "GAS_INTERFERENCE", "severity": "HIGH"})
    if vib > 3.5 and temp > 183:
        faults.append({"code": "BEARING_WEAR", "severity": "HIGH"})
    if temp > 200:
        faults.append({"code": "HIGH_TEMP", "severity": "CRITICAL"})
    if eff < 55:
        faults.append({"code": "PUMP_WEAR", "severity": "HIGH"})
    if dp > 3200 and flow < 1100:
        faults.append({"code": "SCALE_BUILDUP", "severity": "HIGH"})
    if cur < 40 and flow < 400:
        faults.append({"code": "UNDERLOAD", "severity": "MEDIUM"})
    if vib > 5.0:
        faults.append({"code": "BEARING_FAILURE_RISK", "severity": "CRITICAL"})
    return faults


def _compute_risk(params: Dict[str, Any], faults: List[Dict[str, str]]) -> float:
    """Compute risk score 0-1 based on parameter thresholds and fault codes."""
    score = 0.05  # baseline

    temp = params["motor_temp_f"]
    vib  = params["vibration_mms"]
    cur  = params["motor_current_pct"]
    pip  = params["intake_pressure_psi"]

    if temp > 200:
        score += 0.30
    elif temp > 190:
        score += 0.20
    elif temp > 183:
        score += 0.10

    if vib > 5.0:
        score += 0.30
    elif vib > 3.5:
        score += 0.20
    elif vib > 2.5:
        score += 0.10

    if cur > 112:
        score += 0.25
    elif cur > 105:
        score += 0.15
    elif cur < 40:
        score += 0.10

    if pip < 600:
        score += 0.20
    elif pip < 800:
        score += 0.10

    critical_codes = {"BEARING_FAILURE_RISK", "HIGH_TEMP", "MOTOR_OVERLOAD"}
    high_codes     = {"BEARING_WEAR", "GAS_INTERFERENCE", "PUMP_WEAR", "SCALE_BUILDUP"}
    for f in faults:
        if f["code"] in critical_codes:
            score += 0.15
        elif f["code"] in high_codes:
            score += 0.08

    return min(1.0, round(score, 3))


def _generate_trend_history(well: Dict[str, Any], tick: int) -> Dict[str, List[float]]:
    """Generate 24 hourly historical readings for trend charts."""
    history: Dict[str, List[float]] = {
        "motor_temp_f": [],
        "vibration_mms": [],
        "motor_current_pct": [],
        "intake_pressure_psi": [],
        "flow_rate_bpd": [],
        "pump_efficiency_pct": [],
    }
    for h in range(24):
        past_tick = max(0, tick - (23 - h))
        params = _simulate_params(well, past_tick)
        for key in history:
            history[key].append(params[key])
    return history


def simulate_all_wells(tick: int) -> List[Dict[str, Any]]:
    """Simulate all 12 ESP wells and return list of well data dicts."""
    results = []
    for well in WELLS:
        params = _simulate_params(well, tick)
        faults = _compute_fault_codes(params)
        risk   = _compute_risk(params, faults)

        if risk > 0.65:
            risk_bucket = "HIGH"
        elif risk > 0.30:
            risk_bucket = "MEDIUM"
        else:
            risk_bucket = "LOW"

        if risk > 0.80:
            run_status = "CRITICAL"
        elif risk > 0.45:
            run_status = "WARNING"
        else:
            run_status = "RUNNING"

        history = _generate_trend_history(well, tick)

        record = {
            **well,
            **params,
            "fault_codes":   faults,
            "risk_score":    risk,
            "risk_bucket":   risk_bucket,
            "run_status":    run_status,
            "trend_history": history,
            "simulated_at":  datetime.utcnow().isoformat(),
            "cycle":         tick % 20,
        }
        results.append(record)
    return results


def get_fleet_kpis(wells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute fleet-level KPIs from simulated well list."""
    high   = sum(1 for w in wells if w["risk_bucket"] == "HIGH")
    medium = sum(1 for w in wells if w["risk_bucket"] == "MEDIUM")
    low    = sum(1 for w in wells if w["risk_bucket"] == "LOW")
    avg_eff    = round(sum(w["pump_efficiency_pct"] for w in wells) / len(wells), 1) if wells else 0
    total_flow = round(sum(w["flow_rate_bpd"] for w in wells), 0) if wells else 0
    critical_count = sum(1 for w in wells if w["run_status"] == "CRITICAL")
    warning_count  = sum(1 for w in wells if w["run_status"] == "WARNING")
    return {
        "high_count":     high,
        "medium_count":   medium,
        "low_count":      low,
        "critical_count": critical_count,
        "warning_count":  warning_count,
        "avg_efficiency": avg_eff,
        "total_flow_bpd": total_flow,
    }
