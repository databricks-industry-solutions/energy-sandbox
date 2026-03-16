"""
Subsea Inspection Analysis Agent – image + telemetry + manuals → structured report.
"""

import json
from typing import Generator

from llm_client import run_agent_loop, run_agent_loop_stream

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════

INSPECTION_SYSTEM_PROMPT = """\
You are the **Subsea Inspection Analysis Agent** — a specialist that analyzes \
underwater inspection data and produces structured integrity reports.

━━━ ROLE ━━━
Given a completed (or in-progress) mission, you:
1. Review camera frames and their ML model outputs (corrosion, coating damage, marine \
growth, anode depletion, cracks, clamp/connector issues).
2. Correlate with drone telemetry and anomaly scores to assess mission quality.
3. Query the manuals/procedures vector index (RAG) to ground recommendations in \
actual standards and OEM criteria.
4. Produce a structured inspection report.

You are NOT conversational. You always use tools, never fabricate data.

━━━ TOOL USE REQUIREMENTS ━━━
You MUST call tools. Available tools:
  • get_inspection_frames   → returns frames for a mission: frame_id, image_path, depth_m, \
model_output_json (defect type, confidence, bounding box), severity_score.
  • run_image_inference     → re-run or refresh ML inference on specific frames. Returns \
updated model_output_json per frame.
  • get_telemetry_summary   → mission-level telemetry: anomaly_score, health_label, \
mean_nav_error_m, comms_loss_fraction, max_depth_m, mean_depth_m.
  • query_manuals           → RAG query against subsea manuals and procedures. Returns \
doc_name, section, chunk_text for the top-k matches.
  • write_report            → persist the final report_json to the inspections table.

━━━ WORKFLOW ━━━

Step 1 – FRAMES: Call get_inspection_frames for the mission. Identify the top frames \
by severity_score (focus on severity ≥ 0.3). Note defect types and confidence.

Step 2 – INFERENCE REFRESH: If any high-severity frames have stale or missing \
model_output_json, call run_image_inference on those frame IDs.

Step 3 – DEFECT SUMMARY: Group findings by asset_part and defect_type. For each group:
   • Count affected frames.
   • Extract quantitative metrics where available (corrosion_area_pct from model output, \
coating_loss_area_pct, anode_utilization_pct, approx_crack_length_mm).
   • Assign severity: low (<0.3), medium (0.3–0.6), high (>0.6) based on max severity_score.
   • Record evidence_frames (list of frame_ids).

Step 4 – DRONE HEALTH: Call get_telemetry_summary. Summarize:
   • overall: "normal" if anomaly_score < 0.3 and health_label == "normal", \
"warning" if anomaly < 0.6, else "critical".
   • notes: flag high nav_error (>2m), comms losses (>10%), depth exceedances.

Step 5 – MANUAL LOOKUP: For EACH defect group with severity ≥ medium, call \
query_manuals with a query like:
   "criteria for [defect_type] on [asset_type] [asset_part]"
   "repair procedure for [defect_type] on [asset_part]"
Attach the returned references to the issue. NEVER invent manual references.

Step 6 – RECOMMENDATIONS: Based on defects and manual criteria, generate prioritized \
recommended_actions. Priority 1 = most urgent. Include:
   • action: specific repair/monitoring action.
   • justification: why, referencing defect data and manual criteria.
   • target_date_days: suggested timeline (7 = urgent, 30 = planned, 90 = monitoring).

Step 7 – BUILD REPORT: Assemble the final report_json and call write_report.

━━━ CONSERVATIVE ANALYSIS RULES ━━━
• If visibility was low (comms_loss_fraction > 0.15 or nav_error > 3m), note reduced \
confidence in findings. Do NOT upgrade severity for poor-quality data.
• If model confidence < 0.5 for a defect, classify as "suspected" not "confirmed".
• Never invent manual references. Only cite what query_manuals returns.
• If fewer than 3 frames show a defect, note "limited evidence" in the issue.

━━━ OUTPUT FORMAT ━━━

Return ONLY a single JSON object (no markdown, no backticks). While working, you \
may emit status lines like "Analyzing frames 100–120…" but the FINAL message must \
be exactly:

{
  "issues": [
    {
      "asset_part": "string",
      "defect_type": "string",
      "severity": "low | medium | high",
      "confidence": "confirmed | suspected",
      "defect_metrics": {
        "corrosion_area_pct": number or null,
        "coating_loss_area_pct": number or null,
        "anode_utilization_pct": number or null,
        "approx_crack_length_mm": number or null
      },
      "evidence_frames": ["frame_id_1", "frame_id_2"],
      "manual_refs": [
        {"doc": "string", "section": "string", "excerpt": "string"}
      ]
    }
  ],
  "drone_health": {
    "overall": "normal | warning | critical",
    "notes": "string"
  },
  "recommended_actions": [
    {
      "priority": 1,
      "action": "string",
      "justification": "string",
      "target_date_days": number
    }
  ]
}
"""

# ═══════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════

INSPECTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_inspection_frames",
            "description": "Get camera frames for a mission with ML model outputs and severity scores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["mission_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_image_inference",
            "description": "Re-run ML inference on specific frames. Returns updated model outputs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission_id": {"type": "string"},
                    "frame_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["mission_id", "frame_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_telemetry_summary",
            "description": "Get mission-level telemetry summary: anomaly_score, health_label, nav_error, comms_loss.",
            "parameters": {
                "type": "object",
                "properties": {"mission_id": {"type": "string"}},
                "required": ["mission_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_manuals",
            "description": "RAG query against subsea manuals and procedures. Returns top-k matching chunks.",
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
    {
        "type": "function",
        "function": {
            "name": "write_report",
            "description": "Persist the final inspection report JSON to the inspections table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mission_id": {"type": "string"},
                    "report_json": {"type": "string"},
                },
                "required": ["mission_id", "report_json"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════
# TOOL EXECUTORS
# ═══════════════════════════════════════════════════════════════

import db

def _exec_tool(name: str, args: dict) -> str:

    if name == "get_inspection_frames":
        frames = db.get_inspection_frames(args["mission_id"], args.get("limit", 50))
        return json.dumps(frames, default=str)

    if name == "run_image_inference":
        # In production: calls model serving endpoint for vision inference.
        # Simulated: returns existing model outputs refreshed.
        frames = db.get_inspection_frames(args["mission_id"], limit=200)
        target_ids = set(args.get("frame_ids", []))
        results = [
            {"frame_id": f["frame_id"], "model_output_json": f.get("model_output_json", "{}"),
             "severity_score": f.get("severity_score", 0.0)}
            for f in frames if f["frame_id"] in target_ids
        ]
        return json.dumps(results, default=str)

    if name == "get_telemetry_summary":
        features = db.get_telemetry_features(args["mission_id"])
        if not features:
            return json.dumps({"anomaly_score": 0.05, "health_label": "normal",
                               "mean_nav_error_m": 0.4, "comms_loss_fraction": 0.02})
        last = features[-1]
        return json.dumps({
            "anomaly_score": last.get("anomaly_score", 0.05),
            "health_label": last.get("health_label", "normal"),
            "mean_nav_error_m": last.get("mean_nav_error_m", 0.4),
            "comms_loss_fraction": last.get("comms_loss_fraction", 0.02),
            "max_depth_m": max((f.get("mean_depth_m", 0) for f in features), default=0),
        }, default=str)

    if name == "query_manuals":
        chunks = db.query_manual_chunks(args["query"], args.get("num_results", 5))
        return json.dumps(chunks, default=str)

    if name == "write_report":
        db.update_inspection_status(
            args["mission_id"], "completed", summary_json=args["report_json"]
        )
        return json.dumps({"status": "saved", "mission_id": args["mission_id"]})

    return json.dumps({"error": f"Unknown tool: {name}"})


# ═══════════════════════════════════════════════════════════════
# AGENT RUNNER
# ═══════════════════════════════════════════════════════════════

def run_agent(user_prompt: str) -> dict:
    """Run Inspection Agent synchronously. Returns report_json dict."""
    return run_agent_loop(
        INSPECTION_SYSTEM_PROMPT, user_prompt,
        INSPECTION_TOOLS, _exec_tool, max_iterations=12, max_tokens=8192,
    )


def run_agent_stream(user_prompt: str) -> Generator[dict, None, None]:
    """Run Inspection Agent with streaming. Yields status/final event dicts."""
    yield from run_agent_loop_stream(
        INSPECTION_SYSTEM_PROMPT, user_prompt,
        INSPECTION_TOOLS, _exec_tool, max_iterations=12, max_tokens=8192,
    )

    yield {"event": "final", "data": {"error": "Max iterations exceeded."}}
