"""
ESP Diagnostic Rules Engine.
Based on industry best practices: API RP 11S series, SPE papers,
Baker Hughes REDA and Schlumberger OEM guidelines.
"""
from __future__ import annotations
from typing import List, Dict, Any


def diagnose(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply diagnostic rules to current sensor parameters.
    Returns list of active diagnoses sorted by severity.
    """
    results: List[Dict[str, Any]] = []

    temp  = params.get("motor_temp_f", 0)
    pip   = params.get("intake_pressure_psi", 1000)
    vib   = params.get("vibration_mms", 0)
    cur   = params.get("motor_current_pct", 80)
    eff   = params.get("pump_efficiency_pct", 85)
    dp    = params.get("discharge_pressure_psi", 2500)
    flow  = params.get("flow_rate_bpd", 1200)

    # Rule 1: MOTOR_OVERLOAD
    # Ref: Baker Hughes REDA Application Engineering Guide — motor loading section
    if cur > 112:
        results.append({
            "fault_code":               "MOTOR_OVERLOAD",
            "severity":                 "CRITICAL",
            "description":             (
                f"Motor current at {cur:.1f}% nameplate — exceeds 112% threshold. "
                "Risk of stator insulation breakdown and thermal winding damage."
            ),
            "recommended_action":      (
                "Reduce VSD frequency by 2-3 Hz increments until current drops below 100%. "
                "Throttle production choke. Verify downhole conditions have not changed."
            ),
            "estimated_hours_to_failure": max(2, round((120 - cur) * 0.5)),
            "reference":               "API RP 11S3; Baker Hughes REDA Motor Sizing Guide",
        })

    # Rule 2: GAS_INTERFERENCE
    # Ref: SPE-126882 — Gas Interference in ESP Systems
    if pip < 800 and vib > 2.0:
        results.append({
            "fault_code":               "GAS_INTERFERENCE",
            "severity":                 "HIGH",
            "description":             (
                f"PIP at {pip:.0f} psi (below 800 psi threshold) with vibration at "
                f"{vib:.2f} mm/s indicates gas slug entrainment. Cavitation likely."
            ),
            "recommended_action":      (
                "Increase pump intake pressure by reducing drawdown rate. "
                "Lower production choke setting or reduce VSD frequency. "
                "Consider gas separator installation if gas-oil ratio is persistent."
            ),
            "estimated_hours_to_failure": 24 if pip < 600 else 72,
            "reference":               "SPE-126882; SPE-153988 — ESP Gas Handling",
        })

    # Rule 3: BEARING_WEAR
    # Ref: Schlumberger Oilfield Review — ESP Failure Mode Analysis
    if vib > 3.5 and temp > 183:
        results.append({
            "fault_code":               "BEARING_WEAR",
            "severity":                 "HIGH",
            "description":             (
                f"Radial bearing degradation detected: vibration {vib:.2f} mm/s "
                f"(>3.5 threshold) combined with elevated motor temp {temp:.1f}°F. "
                "Progressive wear pattern consistent with bearing race damage."
            ),
            "recommended_action":      (
                "Schedule bearing replacement within 72 hours. "
                "Collect oil sample for metallic particle analysis. "
                "Review run-life data and consider full pump inspection."
            ),
            "estimated_hours_to_failure": max(12, round(72 - (vib - 3.5) * 20)),
            "reference":               "SPE-171374; Schlumberger ESP Diagnostics Manual §4.3",
        })

    # Rule 4: CRITICAL_TEMP
    # Ref: API RP 11S4 — Recommended Practice for Sizing and Selection of Electric Motor Systems
    if temp > 200:
        results.append({
            "fault_code":               "CRITICAL_TEMP",
            "severity":                 "CRITICAL",
            "description":             (
                f"Motor winding temperature at {temp:.1f}°F exceeds 200°F critical limit. "
                "Class F insulation rated to 311°F but derating applies above 200°F. "
                "Risk of immediate winding failure and motor destruction."
            ),
            "recommended_action":      (
                "Initiate controlled shutdown within 4 hours. "
                "Do not increase production. Investigate cooling water flow, "
                "check for obstructions in motor section. Schedule workover."
            ),
            "estimated_hours_to_failure": max(1, round((220 - temp) * 0.3)),
            "reference":               "API RP 11S4; NEMA MG-1 Motor Standards",
        })

    # Rule 5: PUMP_WEAR
    # Ref: SPE-93987 — ESP Performance Monitoring and Diagnostics
    if eff < 55:
        results.append({
            "fault_code":               "PUMP_WEAR",
            "severity":                 "HIGH",
            "description":             (
                f"Pump efficiency at {eff:.1f}% (below 55% threshold). "
                "Stage wear causing impeller-diffuser clearance increase. "
                "Energy waste and suboptimal production rate."
            ),
            "recommended_action":      (
                "Conduct pump performance test with production logging. "
                "Compare current P-Q curve against OEM baseline. "
                "Evaluate workhorse (continued operation with reduced rate) "
                "vs. workover (stage replacement) economics."
            ),
            "estimated_hours_to_failure": max(168, round((eff - 20) * 8)),
            "reference":               "SPE-93987; Baker Hughes REDA Pump Wear Diagnostics §7",
        })

    # Rule 6: SCALE_BUILDUP
    # Ref: SPE-164075 — Scale Management in ESP Completions
    if dp > 3200 and flow < 1100:
        results.append({
            "fault_code":               "SCALE_BUILDUP",
            "severity":                 "HIGH",
            "description":             (
                f"Discharge pressure elevated to {dp:.0f} psi with reduced flow "
                f"{flow:.0f} bpd. Pattern consistent with carbonate or sulfate scale "
                "restricting pump discharge and/or production tubing."
            ),
            "recommended_action":      (
                "Initiate EDTA or HCl chemical squeeze treatment. "
                "Increase scale inhibitor injection rate. "
                "Schedule downhole camera survey if chemical treatment ineffective. "
                "Review produced water chemistry for scaling tendency (Stiff-Davis index)."
            ),
            "estimated_hours_to_failure": max(48, round((3800 - dp) * 0.1)),
            "reference":               "SPE-164075; Schlumberger Scale Removal Guidelines §3.2",
        })

    # Rule 7: UNDERLOAD
    # Ref: Baker Hughes REDA Application Guide — Minimum Rate Operation
    if cur < 40 and flow < 400:
        results.append({
            "fault_code":               "UNDERLOAD",
            "severity":                 "MEDIUM",
            "description":             (
                f"Motor current at {cur:.1f}% with flow {flow:.0f} bpd. "
                "ESP operating well below minimum recommended rate. "
                "Insufficient fluid circulation for motor cooling — thermal risk."
            ),
            "recommended_action":      (
                "Increase VSD frequency to minimum of 45 Hz. "
                "Review wellbore inflow — may indicate well depletion or "
                "skin damage. Consider stimulation or frequency adjustment."
            ),
            "estimated_hours_to_failure": 96,
            "reference":               "Baker Hughes REDA Application Guide §5.4; API RP 11S2",
        })

    # Rule 8: NORMAL (no issues)
    if not results:
        results.append({
            "fault_code":               "NORMAL",
            "severity":                 "LOW",
            "description":             (
                "All parameters operating within normal ranges. "
                f"Motor temp {temp:.1f}°F, vibration {vib:.2f} mm/s, "
                f"current {cur:.1f}%, PIP {pip:.0f} psi, efficiency {eff:.1f}%."
            ),
            "recommended_action":      (
                "Continue normal monitoring. Maintain scheduled PM intervals. "
                "Review trend data weekly for early degradation indicators."
            ),
            "estimated_hours_to_failure": 8760,
            "reference":               "Standard operating envelope — all parameters nominal",
        })

    # Sort: CRITICAL first, then HIGH, MEDIUM, LOW
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    results.sort(key=lambda x: severity_order.get(x["severity"], 9))
    return results
