"""
Subsea Knowledge Assistant Agent – answers operator questions using RAG over
manuals, procedures, standards, and historical inspection data.

General-purpose Q&A for the operations team.
"""

import json
from typing import Generator

from llm_client import run_agent_loop_stream

# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════

KNOWLEDGE_SYSTEM_PROMPT = """\
You are the **Subsea Knowledge Assistant** — an expert AI that answers questions \
from subsea engineers, ROV operators, and integrity managers.

━━━ ROLE ━━━
Answer questions accurately using the available tools. You have access to:
- Company manuals and procedures (OEM drone manuals, thruster manuals, inspection \
procedures, asset drawings, integrity standards).
- Fleet status and telemetry data.
- Inspection history and defect records.

You are conversational but precise. Always cite your sources.

━━━ TOOL USE REQUIREMENTS ━━━
Available tools:
  • query_manuals        → RAG search across all PDF manuals and procedures.
  • get_fleet_status     → current state of all 5 drones.
  • get_inspection_history → recent inspections with defect summaries.
  • get_telemetry_data   → recent telemetry for a specific drone.

━━━ GUIDELINES ━━━

1. Always call query_manuals for questions about procedures, standards, limits, or \
how things work. Do NOT answer from memory alone.

2. For questions about current fleet state, call get_fleet_status.

3. For questions about past inspections, call get_inspection_history.

4. Cite sources: "According to [Document Name], Section X: ..."

5. If you cannot find an answer in the tools, say so clearly. Do NOT fabricate.

6. Keep answers concise but thorough. Use bullet points for multi-part answers.

7. For safety-critical questions, always add a disclaimer: "Verify with your \
competent person before taking action."

━━━ OUTPUT FORMAT ━━━

Return a JSON object:

{
  "answer": "string (markdown-formatted answer)",
  "sources": [
    {"doc": "string", "section": "string", "relevance": "high | medium | low"}
  ],
  "confidence": "high | medium | low",
  "follow_up_suggestions": ["string"]
}
"""

# ═══════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════

KNOWLEDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_manuals",
            "description": "RAG query across all subsea manuals, procedures, and standards.",
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
            "name": "get_fleet_status",
            "description": "Get current status of all 5 drones.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inspection_history",
            "description": "Get recent inspection records with status and summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_telemetry_data",
            "description": "Get recent telemetry features for a specific drone.",
            "parameters": {
                "type": "object",
                "properties": {"drone_id": {"type": "string"}},
                "required": ["drone_id"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════
# TOOL EXECUTORS
# ═══════════════════════════════════════════════════════════════

import db

def _exec_tool(name: str, args: dict) -> str:
    if name == "query_manuals":
        chunks = db.query_manual_chunks(args["query"], args.get("num_results", 5))
        return json.dumps(chunks, default=str)

    if name == "get_fleet_status":
        return json.dumps(db.get_all_drones(), default=str)

    if name == "get_inspection_history":
        limit = args.get("limit", 10)
        inspections = db.sql_query(f"""
            SELECT mission_id, asset_id, asset_type, status, start_ts, end_ts, summary_json
            FROM inspections ORDER BY start_ts DESC LIMIT {limit}
        """)
        return json.dumps(inspections, default=str)

    if name == "get_telemetry_data":
        features = db.sql_query(f"""
            SELECT * FROM telemetry_features
            WHERE drone_id = '{args["drone_id"]}'
            ORDER BY window_end_ts DESC LIMIT 10
        """)
        return json.dumps(features, default=str)

    return json.dumps({"error": f"Unknown tool: {name}"})


# ═══════════════════════════════════════════════════════════════
# AGENT RUNNER
# ═══════════════════════════════════════════════════════════════

def run_agent_stream(user_prompt: str) -> Generator[dict, None, None]:
    yield from run_agent_loop_stream(
        KNOWLEDGE_SYSTEM_PROMPT, user_prompt,
        KNOWLEDGE_TOOLS, _exec_tool, max_iterations=8,
    )
