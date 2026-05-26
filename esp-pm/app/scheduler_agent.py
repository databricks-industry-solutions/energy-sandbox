"""
Agentic AI Maintenance Scheduler for Permian Basin ESP facilities.
Implements a perceive–reason–act loop:
  1. Perceive: pull asset telemetry, diagnostics, SAP history
  2. Reason:   predict failures, rank urgency, decide maintenance timing
  3. Act:      create work orders with human-readable justifications,
               assign technicians based on availability and skill
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any

import simulator
import sap_data
import diagnostics

# ── Technician roster ────────────────────────────────────────────────────────
TECHNICIANS = [
    {"id": "T-101", "name": "J. Martinez", "skills": ["electrical", "mechanical", "vsd"],
     "zone": "Permian Basin", "capacity_hrs": 8, "booked_hrs": 0},
    {"id": "T-102", "name": "R. Thompson", "skills": ["mechanical", "bearing", "workover"],
     "zone": "Eagle Ford",    "capacity_hrs": 8, "booked_hrs": 0},
    {"id": "T-103", "name": "A. Singh",    "skills": ["electrical", "instrumentation", "motor"],
     "zone": "DJ Basin",      "capacity_hrs": 8, "booked_hrs": 0},
    {"id": "T-104", "name": "D. Patel",    "skills": ["vsd", "motor", "electrical"],
     "zone": "Bakken",        "capacity_hrs": 8, "booked_hrs": 0},
    {"id": "T-105", "name": "K. Williams", "skills": ["mechanical", "workover", "pump"],
     "zone": "Marcellus",     "capacity_hrs": 8, "booked_hrs": 0},
    {"id": "T-106", "name": "M. Garcia",   "skills": ["chemical", "scale", "instrumentation"],
     "zone": "Permian Basin", "capacity_hrs": 8, "booked_hrs": 0},
]

# Fault → required skill mapping
_FAULT_SKILLS: Dict[str, str] = {
    "MOTOR_OVERLOAD":       "vsd",
    "GAS_INTERFERENCE":     "mechanical",
    "BEARING_WEAR":         "bearing",
    "CRITICAL_TEMP":        "motor",
    "PUMP_WEAR":            "pump",
    "SCALE_BUILDUP":        "chemical",
    "UNDERLOAD":            "vsd",
    "BEARING_FAILURE_RISK": "bearing",
    "HIGH_TEMP":            "motor",
}

# Severity → urgency window (hours)
_URGENCY_WINDOW = {
    "CRITICAL": 4,
    "HIGH":     24,
    "MEDIUM":   72,
    "LOW":      168,
}


def _reset_technicians() -> List[Dict[str, Any]]:
    """Return fresh technician roster with zero bookings."""
    return [dict(t, booked_hrs=0) for t in TECHNICIANS]


# ═══════════════════════════════════════════════════════════════════════════════
# PERCEIVE — gather all fleet telemetry, diagnostics, and maintenance context
# ═══════════════════════════════════════════════════════════════════════════════
def perceive(wells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect current sensor state, diagnostics, and SAP history per well."""
    perceptions = []
    for w in wells:
        diags = diagnostics.diagnose(w)
        sap = sap_data.get_sap_data(w["esp_id"])
        open_wos = sap.get("work_orders", [])
        history = sap.get("history", [])
        last_pm_cost = history[0]["COST_USD"] if history else 0
        days_since_last_pm = 0
        if history:
            from datetime import datetime as dt
            try:
                last_date = dt.strptime(history[0]["IDAT"], "%Y-%m-%d")
                days_since_last_pm = (datetime.utcnow() - last_date).days
            except Exception:
                days_since_last_pm = 999

        perceptions.append({
            "esp_id":              w["esp_id"],
            "well_name":           w["name"],
            "field":               w["field"],
            "run_status":          w["run_status"],
            "risk_score":          w["risk_score"],
            "risk_bucket":         w["risk_bucket"],
            "motor_temp_f":        w["motor_temp_f"],
            "vibration_mms":       w["vibration_mms"],
            "motor_current_pct":   w["motor_current_pct"],
            "intake_pressure_psi": w["intake_pressure_psi"],
            "pump_efficiency_pct": w["pump_efficiency_pct"],
            "flow_rate_bpd":       w["flow_rate_bpd"],
            "fault_codes":         w.get("fault_codes", []),
            "diagnostics":         diags,
            "open_work_orders":    len(open_wos),
            "days_since_last_pm":  days_since_last_pm,
            "last_pm_cost":        last_pm_cost,
            "pm_next_date":        sap.get("pm_next_date", "N/A"),
        })
    return perceptions


# ═══════════════════════════════════════════════════════════════════════════════
# REASON — rank wells, predict optimal timing, generate justifications
# ═══════════════════════════════════════════════════════════════════════════════
def reason(perceptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Score each well and produce prioritized maintenance decisions."""
    decisions = []
    for p in perceptions:
        active_faults = [d for d in p["diagnostics"] if d["fault_code"] != "NORMAL"]
        if not active_faults:
            continue

        top_fault = active_faults[0]
        severity = top_fault["severity"]
        urgency_hrs = _URGENCY_WINDOW.get(severity, 168)
        ttf = top_fault.get("estimated_hours_to_failure", 8760)

        # Composite priority: lower = more urgent
        priority = round(
            (1.0 - p["risk_score"]) * 30
            + max(0, ttf - urgency_hrs) * 0.1
            + (0 if p["open_work_orders"] == 0 else 20)
        , 1)

        # Determine recommended window
        if severity == "CRITICAL":
            window = "IMMEDIATE (0-4h)"
            schedule_dt = datetime.utcnow() + timedelta(hours=2)
        elif severity == "HIGH":
            window = "URGENT (4-24h)"
            schedule_dt = datetime.utcnow() + timedelta(hours=12)
        elif severity == "MEDIUM":
            window = "PLANNED (1-3 days)"
            schedule_dt = datetime.utcnow() + timedelta(days=2)
        else:
            window = "ROUTINE (next PM cycle)"
            schedule_dt = datetime.utcnow() + timedelta(days=7)

        # Estimate job duration (hours)
        est_hours = 2 if severity == "CRITICAL" else (4 if severity == "HIGH" else 6)

        # Build human-readable reasoning chain
        reasoning = (
            f"PERCEIVE: {p['esp_id']} ({p['well_name']}) shows {top_fault['fault_code']} "
            f"[{severity}]. Motor temp {p['motor_temp_f']}°F, vibration {p['vibration_mms']} mm/s, "
            f"current {p['motor_current_pct']}%. Risk score: {p['risk_score']*100:.0f}%. "
            f"Estimated {ttf}h to failure.\n"
            f"REASON: Priority score {priority}. {len(active_faults)} active fault(s). "
            f"{'No existing WO — create new.' if p['open_work_orders'] == 0 else str(p['open_work_orders']) + ' WO(s) exist — verify coverage.'} "
            f"Last PM was {p['days_since_last_pm']}d ago (${p['last_pm_cost']:,}).\n"
            f"ACT: Schedule {window}. Recommended action: {top_fault['recommended_action'][:120]}"
        )

        required_skill = _FAULT_SKILLS.get(top_fault["fault_code"], "mechanical")

        decisions.append({
            "esp_id":           p["esp_id"],
            "well_name":        p["well_name"],
            "field":            p["field"],
            "fault_code":       top_fault["fault_code"],
            "severity":         severity,
            "risk_score":       p["risk_score"],
            "ttf_hours":        ttf,
            "priority_score":   priority,
            "window":           window,
            "schedule_dt":      schedule_dt,
            "est_hours":        est_hours,
            "required_skill":   required_skill,
            "reasoning":        reasoning,
            "recommended_action": top_fault["recommended_action"],
            "has_existing_wo":  p["open_work_orders"] > 0,
        })

    # Sort by priority (lower = more urgent)
    decisions.sort(key=lambda d: d["priority_score"])
    return decisions


# ═══════════════════════════════════════════════════════════════════════════════
# ACT — assign technicians and produce work orders
# ═══════════════════════════════════════════════════════════════════════════════
def act(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assign technicians, create work orders, build daily schedule."""
    roster = _reset_technicians()
    work_orders = []
    schedule = {t["id"]: {"name": t["name"], "zone": t["zone"], "jobs": []} for t in roster}

    for i, dec in enumerate(decisions):
        # Find best technician: has skill, has capacity, prefer same zone
        skill = dec["required_skill"]
        candidates = [
            t for t in roster
            if skill in t["skills"] and (t["capacity_hrs"] - t["booked_hrs"]) >= dec["est_hours"]
        ]
        if not candidates:
            # Fallback: any tech with capacity
            candidates = [t for t in roster if (t["capacity_hrs"] - t["booked_hrs"]) >= dec["est_hours"]]

        if candidates:
            # Prefer same zone
            same_zone = [t for t in candidates if t["zone"] == dec["field"]]
            tech = same_zone[0] if same_zone else candidates[0]
            tech["booked_hrs"] += dec["est_hours"]
        else:
            tech = {"id": "UNASSIGNED", "name": "Unassigned", "zone": "—"}

        wo_id = f"AI-WO-{5000 + i:04d}"
        wo = {
            "wo_id":        wo_id,
            "esp_id":       dec["esp_id"],
            "well_name":    dec["well_name"],
            "field":        dec["field"],
            "fault_code":   dec["fault_code"],
            "severity":     dec["severity"],
            "risk_pct":     round(dec["risk_score"] * 100),
            "priority":     dec["priority_score"],
            "window":       dec["window"],
            "scheduled":    dec["schedule_dt"].strftime("%Y-%m-%d %H:%M"),
            "est_hours":    dec["est_hours"],
            "tech_id":      tech["id"],
            "tech_name":    tech["name"],
            "reasoning":    dec["reasoning"],
            "action":       dec["recommended_action"],
            "status":       "AI-GENERATED",
        }
        work_orders.append(wo)

        if tech["id"] != "UNASSIGNED" and tech["id"] in schedule:
            schedule[tech["id"]]["jobs"].append({
                "wo_id":     wo_id,
                "well":      dec["well_name"],
                "fault":     dec["fault_code"],
                "severity":  dec["severity"],
                "hours":     dec["est_hours"],
                "window":    dec["window"],
            })

    return {
        "work_orders": work_orders,
        "schedule":    schedule,
        "roster":      roster,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY SUMMARY — GET /agent/daily-summary
# ═══════════════════════════════════════════════════════════════════════════════
def daily_summary(work_orders: List[Dict[str, Any]], roster: List[Dict[str, Any]],
                  wells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Produce the agent's daily summary report."""
    critical_wos = [wo for wo in work_orders if wo["severity"] == "CRITICAL"]
    high_wos     = [wo for wo in work_orders if wo["severity"] == "HIGH"]
    total_hrs    = sum(wo["est_hours"] for wo in work_orders)
    techs_used   = len(set(wo["tech_id"] for wo in work_orders if wo["tech_id"] != "UNASSIGNED"))
    avg_util     = round(sum(t["booked_hrs"] / t["capacity_hrs"] * 100 for t in roster) / len(roster), 1)
    fleet_risk   = round(sum(w["risk_score"] for w in wells) / len(wells) * 100, 1)

    return {
        "generated_at":    datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_wos":       len(work_orders),
        "critical_count":  len(critical_wos),
        "high_count":      len(high_wos),
        "total_labor_hrs": total_hrs,
        "techs_assigned":  techs_used,
        "avg_utilization":  avg_util,
        "fleet_avg_risk":  fleet_risk,
        "top_actions": [
            f"{'IMMEDIATE' if wo['severity']=='CRITICAL' else 'URGENT'}: {wo['well_name']} — "
            f"{wo['fault_code']} (Risk {wo['risk_pct']}%) → {wo['tech_name']}"
            for wo in work_orders[:5]
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RUN FULL LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def run_agent_loop(wells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute the full perceive → reason → act cycle. Returns all outputs."""
    perceptions = perceive(wells)
    decisions = reason(perceptions)
    result = act(decisions)
    summary = daily_summary(result["work_orders"], result["roster"], wells)
    return {
        "perceptions": perceptions,
        "decisions":   decisions,
        "work_orders": result["work_orders"],
        "schedule":    result["schedule"],
        "roster":      result["roster"],
        "summary":     summary,
    }
