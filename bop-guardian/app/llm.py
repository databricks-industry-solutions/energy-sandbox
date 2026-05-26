"""
BOP Guardian — Foundation Model API integration.
Uses Databricks Model Serving (pay-per-token) for the Guardian Advisor chat.
Falls back to rule-based responses when the LLM is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── Model config ─────────────────────────────────────────────────────────────

MODEL_NAME = os.getenv("BOP_LLM_MODEL", "databricks-meta-llama-3-3-70b-instruct")
MAX_TOKENS = int(os.getenv("BOP_LLM_MAX_TOKENS", "800"))
TEMPERATURE = float(os.getenv("BOP_LLM_TEMPERATURE", "0.3"))

# ── Lazy client ──────────────────────────────────────────────────────────────

_client = None


def _get_client():
    """Lazy-init the Databricks WorkspaceClient (auth handled by app framework)."""
    global _client
    if _client is None:
        try:
            from databricks.sdk import WorkspaceClient
            _client = WorkspaceClient()
        except Exception as e:
            logger.warning("Failed to init WorkspaceClient: %s", e)
    return _client


# ── System prompt builder ────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """\
You are **Guardian AI**, the agentic command-center advisor for the offshore drilling rig \
"{rig_name}" operating on well "{well_name}".

Your role is to help the rig crew, subsea engineers, drilling engineers, and the OIM \
make safety-critical decisions about the BOP (Blowout Preventer) stack. You have \
real-time access to all BOP telemetry, predictive maintenance models, SAP ERP work \
orders, spare parts inventory, and crew status.

IMPORTANT RULES:
- Always prioritize SAFETY. If there is any doubt, recommend cautious action.
- Reference specific asset IDs (e.g. BOP-BSR-01), sensor readings, and data.
- When recommending actions, specify WHO should do it and estimated time.
- Use concise, professional offshore drilling language.
- Format responses with markdown (**bold** for emphasis, bullet lists for actions).
- Do NOT hallucinate data — only reference what is provided in the context below.

---
## CURRENT RIG STATE (Tick {tick})

**Status:** {rig_status} — {status_reason}
**Current Op:** {current_op}
**Depth:** {depth_md:,.0f} ft MD / {depth_tvd:,.0f} ft TVD

### Component Health
{component_health}

### Active Anomalies
{active_anomalies}

### AI Agent Recommendations
{recommendations}

### RUL Predictions (Remaining Useful Life)
{rul_predictions}

### SAP Work Orders
{work_orders}

### Spare Parts Inventory
{spare_parts}

### Crew On Rig
{crew_status}
---
"""


def _build_system_prompt(sim: dict, agent_state: Any) -> str:
    """Build a rich system prompt from current simulator state and agent data."""
    from app.mock_data import (
        RUL_PREDICTIONS, SAP_WORK_ORDERS, SAP_SPARES, CREW,
        get_intervention_eta,
    )
    from app.agent import SEV_LABEL

    # Component health
    comp_lines = []
    for aid, c in sim["components"].items():
        hs = c["health_score"]
        status = "ANOMALY" if c["anomaly_flag"] else "OK"
        atype = (c.get("anomaly_type") or "").replace("_", " ")
        comp_lines.append(
            f"- **{aid}** ({c['component_type']}): health={hs:.0%} [{status}]"
            + (f" — {atype}" if atype else "")
        )

    # Active anomalies
    anomalies = [c for c in sim["components"].values() if c["anomaly_flag"]]
    if anomalies:
        anom_lines = [
            f"- {c['asset_id']}: {(c.get('anomaly_type') or '').replace('_', ' ')} "
            f"(health {c['health_score']:.0%})"
            for c in anomalies
        ]
    else:
        anom_lines = ["No active anomalies."]

    # Recommendations from rule-based agents
    recs = agent_state.recommendations[-10:] if agent_state.recommendations else []
    if recs:
        rec_lines = []
        for r in recs:
            sev = SEV_LABEL.get(r.severity, "INFO")
            rec_lines.append(f"- [{sev}] {r.agent}: {r.title}")
            if r.actions:
                for a in r.actions[:2]:
                    rec_lines.append(f"  - {a}")
    else:
        rec_lines = ["No active recommendations."]

    # RUL
    rul_lines = [
        f"- {r['asset_id']} ({r['component_type']}): {r['predicted_rul_days']}d RUL, "
        f"7d fail prob {r['failure_prob_7d']:.1%}, 30d {r['failure_prob_30d']:.1%}"
        for r in sorted(RUL_PREDICTIONS, key=lambda x: x["predicted_rul_days"])
    ]

    # Work orders
    wo_lines = [
        f"- {w['wo_id']} [{w['status']}] P{w['priority']}: {w['description']} "
        f"({w['equipment_id']})"
        for w in SAP_WORK_ORDERS
    ]

    # Spare parts
    sp_lines = [
        f"- {s['material_id']}: {s['description']} — qty {s['available_qty']} "
        f"(min {s['min_stock']}) {'LOW' if s['available_qty'] <= s['min_stock'] else 'OK'}"
        for s in SAP_SPARES
    ]

    # Crew
    crew_lines = [
        f"- {c['name']} ({c['role']}, {c['company']}) — {c['shift']} shift, "
        f"{c['zone'].replace('_', ' ')}, ETA {get_intervention_eta(c)}m, "
        f"certs: {', '.join(cert.replace('_', ' ') for cert in c.get('certs', []))}"
        for c in CREW
    ]

    op = sim["current_op"]
    return SYSTEM_PROMPT_TEMPLATE.format(
        rig_name=sim.get("rig_name", "Deepwater Sentinel"),
        well_name=sim.get("well_name", ""),
        tick=sim["tick"],
        rig_status=sim["status"].replace("_", " "),
        status_reason=sim.get("status_reason", ""),
        current_op=f"{op['description']} ({op['op_code']})",
        depth_md=op["depth_md"],
        depth_tvd=op["depth_tvd"],
        component_health="\n".join(comp_lines),
        active_anomalies="\n".join(anom_lines),
        recommendations="\n".join(rec_lines),
        rul_predictions="\n".join(rul_lines),
        work_orders="\n".join(wo_lines),
        spare_parts="\n".join(sp_lines),
        crew_status="\n".join(crew_lines),
    )


# ── Chat completion ──────────────────────────────────────────────────────────

def chat(query: str, sim: dict, agent_state: Any,
         chat_history: list[dict] | None = None) -> str | None:
    """
    Send a query to the Foundation Model API with full BOP context.

    Returns the LLM response text, or None if the call fails (caller should
    fall back to rule-based response).
    """
    client = _get_client()
    if client is None:
        return None

    system_prompt = _build_system_prompt(sim, agent_state)

    messages = [{"role": "system", "content": system_prompt}]

    # Include recent chat history for conversational context
    if chat_history:
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    try:
        response = client.serving_endpoints.query(
            name=MODEL_NAME,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        # Response structure: response.choices[0].message.content
        if hasattr(response, "choices") and response.choices:
            return response.choices[0].message.content
        # Fallback for dict-style response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
        return None
    except Exception as e:
        logger.warning("Foundation Model API call failed: %s", e)
        return None
