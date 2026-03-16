"""
Subsea Drone Autopilot Agent – mission planning, dispatch, and safety enforcement.

Perceive → Plan → Validate → Decide (plan+launch | plan-only | refuse | abort)
"""

import json
import uuid
from typing import Generator

from llm_client import run_agent_loop, run_agent_loop_stream

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════

AUTOPILOT_SYSTEM_PROMPT = """\
You are the **Subsea Drone Autopilot Agent** — the autonomous mission planner and \
safety controller for a fleet of 5 underwater inspection drones (DRONE-01 through DRONE-05).

━━━ ROLE ━━━
Plan, validate, and dispatch subsea inspection missions. Every decision must be \
traceable and safety-first. You are NOT a conversational assistant; you are a \
deterministic controller that always uses tools before making decisions.

━━━ TOOL USE REQUIREMENTS ━━━
You MUST call tools to gather data. Never guess or assume drone states.
Available tools:
  • list_drones          → returns all 5 drones with battery_pct, depth_m, health_score, \
state, maintenance_required, current_mission_id.
  • get_drone_limits     → per-drone: max_depth_m, max_duration_min, battery reserves by risk.
  • plan_route           → given asset_id, inspection_type, depth_range, returns waypoints, \
estimated_duration_min, estimated_distance_m, estimated_battery_use_pct.
  • dispatch_mission     → sends planned route to drone control gateway; returns mission_id.
  • get_telemetry_summary → per-drone recent telemetry: anomaly_score, health_label, \
mean_nav_error_m, comms_loss_fraction.
  • abort_mission        → emergency abort; drone surfaces on shortest path.

━━━ SAFETY RULES (NON-NEGOTIABLE) ━━━

1. Battery reserves by risk level:
   • low  risk: battery after mission ≥ 30%
   • medium risk: battery after mission ≥ 40%
   • high risk: battery after mission ≥ 50%
   Formula: battery_reserve = battery_pct − estimated_battery_use_pct
   If battery_reserve < required reserve → REFUSE.

2. Duration guard:
   estimated_duration_min must be ≤ 0.8 × max_duration_min.
   If exceeded → REFUSE.

3. Depth safety margin:
   depth_range_m.max ≤ max_depth_m − 10  (10 m margin).
   If exceeded → REFUSE.

4. High-risk missions:
   • Routes must be shorter and focused (≤ 8 waypoints).
   • Abort threshold: anomaly_score > 0.6 OR comms_loss_fraction > 0.15.
   • Must pick the drone with highest health_score among eligible.

5. Drone eligibility:
   • state must be 'idle'.
   • maintenance_required must be false.
   • health_score ≥ 0.70.

━━━ MISSION PLANNING FLOW ━━━

Step 1 – PERCEIVE: Call list_drones. Filter to eligible drones (idle, no maintenance, health ≥ 0.70).
Step 2 – SELECT: Among eligible, pick the safest drone:
   • Highest health_score.
   • Highest battery_pct.
   • Lowest recent anomaly_score (call get_telemetry_summary).
   • Break ties by drone_id ascending.
Step 3 – LIMITS: Call get_drone_limits for the selected drone.
Step 4 – ROUTE: Call plan_route with the asset, inspection type, and depth range.
Step 5 – VALIDATE:
   a. Check battery reserve vs risk threshold.
   b. Check duration vs 0.8 × max_duration_min.
   c. Check depth range vs max_depth_m − 10.
   d. For high-risk: verify route ≤ 8 waypoints, set stricter abort thresholds.
   If any check fails → output status="refused" with explanation.
Step 6 – DECIDE:
   • If user asked to plan+launch and all checks pass → call dispatch_mission → status="launched".
   • If user asked plan-only → status="planned" (do NOT dispatch).
   • If any check fails → status="refused".

━━━ MONITORING / ABORT ━━━

During an active mission, if called with a monitoring prompt:
  • Call get_telemetry_summary.
  • If health_label == "critical" OR anomaly_score > 0.7 OR comms_loss_fraction > 0.20:
    → Call abort_mission immediately.
    → Output status="aborted" with reason.

━━━ OUTPUT FORMAT ━━━

Return ONLY a single JSON object (no markdown, no backticks, no extra text).
While working, you may emit short status lines like "Checking drones…" or "Planning route…"
but the FINAL message must be exactly this JSON shape:

{
  "mission_id": "string or null",
  "selected_drone": "string or null",
  "status": "planned | launched | refused | aborted",
  "plan": {
    "asset_id": "string",
    "asset_type": "string",
    "target_depth_m": number or null,
    "depth_range_m": {"min": number or null, "max": number or null},
    "inspection_type": "string",
    "risk_level": "low | medium | high",
    "environment": {
      "sea_state": "calm | moderate | rough | unknown",
      "current_speed_knots": number or null,
      "visibility_m": number or null
    },
    "drone_limits": {
      "max_depth_m": number,
      "max_duration_min": number,
      "min_battery_reserve_pct": number
    },
    "estimated": {
      "duration_min": number,
      "distance_m": number,
      "battery_use_pct": number,
      "battery_reserve_pct": number
    },
    "waypoints": [{"lat": number or null, "lon": number or null, "depth_m": number}],
    "safety_checks": ["string"],
    "constraints": ["string"],
    "objectives": ["string"]
  },
  "summary": "string"
}

If status is "refused", plan may be partial (no waypoints) but must include the reason in summary.
If status is "aborted", include the trigger condition in summary.
"""

# ═══════════════════════════════════════════════════════════════
# TOOL DEFINITIONS (for function-calling)
# ═══════════════════════════════════════════════════════════════

AUTOPILOT_TOOLS = [
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
            "name": "plan_route",
            "description": "Plan inspection route. Returns waypoints, estimated duration/distance/battery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "asset_type": {"type": "string"},
                    "inspection_type": {"type": "string"},
                    "target_depth_m": {"type": "number"},
                    "depth_range_min": {"type": "number"},
                    "depth_range_max": {"type": "number"},
                },
                "required": ["asset_id", "inspection_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_mission",
            "description": "Send planned mission to drone control gateway. Returns mission_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drone_id": {"type": "string"},
                    "route_json": {"type": "string"},
                },
                "required": ["drone_id", "route_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_telemetry_summary",
            "description": "Get recent telemetry summary for a drone: anomaly_score, health_label, nav_error, comms_loss.",
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
            "name": "abort_mission",
            "description": "Emergency abort. Drone surfaces immediately.",
            "parameters": {
                "type": "object",
                "properties": {"mission_id": {"type": "string"}},
                "required": ["mission_id"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════
# TOOL EXECUTORS (wired to db.py / drone control API)
# ═══════════════════════════════════════════════════════════════

import db

def _exec_tool(name: str, args: dict) -> str:
    """Execute a tool call and return JSON string result."""

    if name == "list_drones":
        drones = db.get_all_drones()
        return json.dumps(drones, default=str)

    if name == "get_drone_limits":
        drone = db.get_drone(args["drone_id"])
        if not drone:
            return json.dumps({"error": f"Drone {args['drone_id']} not found"})
        return json.dumps({
            "drone_id": drone["drone_id"],
            "max_depth_m": drone["max_depth_m"],
            "max_duration_min": drone["max_duration_min"],
            "min_battery_reserve_pct_low_risk": drone["min_battery_reserve_pct_low_risk"],
            "min_battery_reserve_pct_med_risk": drone["min_battery_reserve_pct_med_risk"],
            "min_battery_reserve_pct_high_risk": drone["min_battery_reserve_pct_high_risk"],
        }, default=str)

    if name == "plan_route":
        # In production: calls route-planning service.
        # Here: returns a realistic simulated route.
        depth = args.get("target_depth_m", 100)
        return json.dumps({
            "waypoints": [
                {"lat": 6.123, "lon": 1.456, "depth_m": depth * 0.3},
                {"lat": 6.124, "lon": 1.457, "depth_m": depth * 0.6},
                {"lat": 6.125, "lon": 1.458, "depth_m": depth * 0.9},
                {"lat": 6.126, "lon": 1.459, "depth_m": depth},
                {"lat": 6.125, "lon": 1.458, "depth_m": depth * 0.5},
            ],
            "estimated_duration_min": 75 + depth * 0.2,
            "estimated_distance_m": 420 + depth * 1.5,
            "estimated_battery_use_pct": 25 + depth * 0.08,
        })

    if name == "dispatch_mission":
        mission_id = f"MIS-{uuid.uuid4().hex[:12].upper()}"
        # In production: POST to drone control gateway.
        return json.dumps({"mission_id": mission_id, "status": "dispatched"})

    if name == "get_telemetry_summary":
        anom = db.get_latest_anomaly(args["drone_id"])
        if anom:
            return json.dumps(anom, default=str)
        return json.dumps({"anomaly_score": 0.05, "health_label": "normal",
                           "mean_nav_error_m": 0.3, "comms_loss_fraction": 0.01})

    if name == "abort_mission":
        db.update_inspection_status(args["mission_id"], "aborted")
        return json.dumps({"status": "aborted", "mission_id": args["mission_id"]})

    return json.dumps({"error": f"Unknown tool: {name}"})


# ═══════════════════════════════════════════════════════════════
# AGENT RUNNER
# ═══════════════════════════════════════════════════════════════

def run_agent(user_prompt: str) -> dict:
    """Run Autopilot Agent synchronously. Returns final JSON dict."""
    return run_agent_loop(
        AUTOPILOT_SYSTEM_PROMPT, user_prompt,
        AUTOPILOT_TOOLS, _exec_tool, max_iterations=10,
    )


def run_agent_stream(user_prompt: str) -> Generator[dict, None, None]:
    """Run Autopilot Agent with streaming. Yields status/final event dicts."""
    yield from run_agent_loop_stream(
        AUTOPILOT_SYSTEM_PROMPT, user_prompt,
        AUTOPILOT_TOOLS, _exec_tool, max_iterations=10,
    )
