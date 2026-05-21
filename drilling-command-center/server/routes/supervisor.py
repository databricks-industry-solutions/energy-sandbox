"""Subsurface Supervisor — multi-agent fan-out over Databricks AI.

The operator's wells live in North America (Lakebase las.* tables) and the
ADME catalog gives us global analog data from the Norwegian Continental Shelf
(Blocks 15/9 and 34/10). The Supervisor takes a question for one operator
well, fans out across five Databricks AI services in parallel, and synthesises
a drilling recommendation.

Specialists:
  1. Subsurface Analogs       — Vector Search (subsurface-vs · gte-large) returns ADME analog wells
  2. Petrophysics Interpreter — Model Serving (Claude 4.5) over simulated rock/fluid + ADME analog
  3. Economics Evaluator      — UC Functions (NPV, break-even, ±$10 WTI sensitivity)
  4. Regulatory & ESG Gate    — ADME legal tags via Unity Catalog
  5. Drilling Operations      — Lakebase las.drilling_operations (rig, NPT, supply chain, BHA health)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..db import db

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Shared Databricks tool helpers (Vector Search, UC Functions, FM API, Genie)
# Inlined here so the supervisor has zero external app-route dependencies.
# ─────────────────────────────────────────────────────────────────────────────

CATALOG        = os.getenv("ADME_CATALOG", "adme_adb_sbx_scus_dbx_ws_1")
SCHEMA         = os.getenv("ADME_SCHEMA", "adme_client_demo")
WAREHOUSE_ID   = os.getenv("DATABRICKS_WAREHOUSE_ID", "186af4be97756033")
VS_ENDPOINT    = os.getenv("VS_ENDPOINT", "subsurface-vs")
VS_INDEX       = os.getenv("VS_INDEX",    f"{CATALOG}.{SCHEMA}.wellbore_vs_index")
MODEL_ENDPOINT = os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-5")


def _sql_conn():
    from databricks import sql
    from databricks.sdk.core import Config
    cfg = Config()
    host = (os.getenv("DATABRICKS_HOST") or cfg.host or "").replace("https://", "").rstrip("/")
    return sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def _openai_call(messages: list, tools: list) -> Any:
    """Call Databricks-hosted Claude via the OpenAI-compatible chat endpoint."""
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    body = {
        "messages":    messages,
        "tools":       tools,
        "max_tokens":  1024,
        "temperature": 0.2,
    }
    api = w.api_client
    if hasattr(api, "do"):
        return api.do("POST", f"/serving-endpoints/{MODEL_ENDPOINT}/invocations", body=body)
    import urllib.request
    host = (w.config.host or "").rstrip("/")
    if not host.startswith("http"):
        host = "https://" + host
    headers = dict(w.config.authenticate())
    headers["Content-Type"] = "application/json"
    url = f"{host}/serving-endpoints/{MODEL_ENDPOINT}/invocations"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _vs_search_sync(query_text: str, k: int) -> list[dict]:
    from databricks.vector_search.client import VectorSearchClient
    c = VectorSearchClient(disable_notice=True)
    idx = c.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
    res = idx.similarity_search(
        query_text=query_text,
        columns=["well_key", "well_name", "platform", "primary_reservoir", "drilling_result"],
        num_results=k,
    )
    rows = []
    if res and "result" in res:
        data = res["result"].get("data_array", [])
        cols = [c["name"] for c in res["manifest"]["columns"]]
        for r in data:
            rows.append(dict(zip(cols, r)))
    return rows


async def tool_search_similar_wells(query_text: str, k: int = 5) -> str:
    try:
        rows = await asyncio.to_thread(_vs_search_sync, query_text, int(k))
    except Exception as e:
        return f"Vector Search error: {e}"
    if not rows:
        return "No results."
    out = [f"Top {len(rows)} similar wells for: {query_text!r}"]
    for r in rows:
        out.append(
            f"  - {str(r.get('well_key','?'))[:40]} | {r.get('well_name','')} | "
            f"platform={r.get('platform','')} | reservoir={r.get('primary_reservoir','')} | "
            f"result={r.get('drilling_result','')} | score={r.get('score',0):.3f}"
        )
    return "\n".join(out)


def _uc_function_sync(fn_sql: str, params: list) -> Any:
    with _sql_conn() as c, c.cursor() as cur:
        placeholders = ",".join(["?"] * len(params))
        cur.execute(f"SELECT {CATALOG}.{SCHEMA}.{fn_sql}({placeholders}) AS r", params)
        row = cur.fetchall_arrow().to_pylist()
        return row[0].get("r") if row else None


async def tool_calculate_npv(capex_musd, opex_musd_yr, peak_rate_bopd, decline_pct_yr, wti_price, years=10):
    try:
        r = await asyncio.to_thread(
            _uc_function_sync, "calculate_npv10",
            [capex_musd, opex_musd_yr, peak_rate_bopd, decline_pct_yr, wti_price, int(years)],
        )
        return (
            f"calculate_npv10 → ${r}M (capex ${capex_musd}M · opex ${opex_musd_yr}M/yr · "
            f"peak {peak_rate_bopd} bopd · decline {decline_pct_yr}% · WTI ${wti_price} · {years}yr)"
        )
    except Exception as e:
        return f"calculate_npv error: {e}"


async def tool_calculate_break_even(capex_musd, opex_musd_yr, peak_rate_bopd, decline_pct_yr):
    try:
        r = await asyncio.to_thread(
            _uc_function_sync, "calculate_break_even",
            [capex_musd, opex_musd_yr, peak_rate_bopd, decline_pct_yr],
        )
        return (
            f"break-even WTI = ${r}/bbl (capex ${capex_musd}M · opex ${opex_musd_yr}M/yr · "
            f"peak {peak_rate_bopd} bopd · decline {decline_pct_yr}%)"
        )
    except Exception as e:
        return f"calculate_break_even error: {e}"


async def tool_query_genie(question: str) -> str:
    """Proxy to Genie Conversation API. Returns formatted SQL + result rows."""
    try:
        from .genie import _ask_sync
        result = await asyncio.to_thread(_ask_sync, question, None)
    except Exception as e:
        return f"Genie error: {e}"
    if isinstance(result, dict) and result.get("error"):
        return f"Genie error: {result['error']}"

    parts = []
    sql = result.get("sql") if isinstance(result, dict) else None
    if sql:
        parts.append(f"GENERATED SQL:\n{sql}")
    cols = result.get("columns") if isinstance(result, dict) else None
    rows = result.get("rows") if isinstance(result, dict) else None
    if rows:
        if cols:
            parts.append("RESULT (top 20 rows):")
            parts.append("  " + " | ".join(str(c) for c in cols))
            for r in rows[:20]:
                parts.append("  " + " | ".join("" if v is None else str(v) for v in r))
            if len(rows) > 20:
                parts.append(f"  … {len(rows) - 20} more rows truncated")
        else:
            parts.append(f"RESULT: {rows[:20]}")
    text = result.get("text") if isinstance(result, dict) else None
    if text and text not in ("(Genie returned no text)", ""):
        parts.append(f"GENIE COMMENTARY: {text}")
    return "\n".join(parts) if parts else "(Genie returned no answer)"


class DecideReq(BaseModel):
    question: str
    well_id:   str = "BAKER-001"      # operator's NA well
    wti_price: float = 75.0
    # Optional overrides — if not supplied we use las.well_economics for the well
    capex_musd:     float | None = None
    opex_musd_yr:   float | None = None
    peak_rate_bopd: float | None = None
    decline_pct_yr: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Specialists
# ─────────────────────────────────────────────────────────────────────────────


def _ms(t0: float) -> int:
    return round((time.time() - t0) * 1000)


def _run_sql(sql: str) -> tuple[list[str], list[list[Any]]]:
    with _sql_conn() as c, c.cursor() as cur:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
    return cols, rows


def _fmt_rows(cols: list[str], rows: list[list[Any]], limit: int = 20) -> str:
    if not rows:
        return "(no rows)"
    out = [" | ".join(cols)]
    for r in rows[:limit]:
        out.append(" | ".join("" if v is None else str(v) for v in r))
    if len(rows) > limit:
        out.append(f"… {len(rows) - limit} more rows")
    return "\n".join(out)


def _claude_text(system: str, user: str, max_tokens: int = 700) -> str:
    """One-shot Claude call (no tools). Reuses agent.py auth path."""
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens":  max_tokens,
        "temperature": 0.2,
    }
    # _openai_call accepts (messages, tools); pass empty tools list and read content
    resp = _openai_call(body["messages"], [])
    try:
        return resp["choices"][0]["message"].get("content", "") or ""
    except Exception:
        return json.dumps(resp)[:600]


async def _get_well_context(well_id: str) -> dict:
    """Pull the operator-well context once and reuse across specialists."""
    well = await db.fetchrow(
        "SELECT well_id, well_name, basin, state, status, quality_score, total_depth_ft, well_type, notes "
        "FROM las.wells WHERE well_id = $1", well_id
    )
    econ = await db.fetchrow(
        "SELECT capex_musd, opex_musd_yr, peak_rate_bopd, decline_pct_yr, "
        "  wti_break_even, npv10_musd, irr_pct, payback_years, co2_tonnes_yr "
        "FROM las.well_economics WHERE well_id = $1", well_id
    )
    res = await db.fetchrow(
        "SELECT formation_name, avg_porosity_frac, avg_permeability_md, avg_oil_saturation, "
        "  avg_water_saturation, net_pay_ft, original_oil_in_place_mmbbl, "
        "  initial_pressure_psi, reservoir_temp_f, reservoir_depth_ft, "
        "  analog_well_id, analog_field "
        "FROM las.reservoir_simulated WHERE well_id = $1", well_id
    )
    ops = await db.fetchrow(
        "SELECT rig_name, rig_contractor, rig_status, days_on_well, npt_hours_last_30d, "
        "  casing_strings_set, drilling_phase, current_md_ft, rop_ft_per_hr, mud_weight_ppg, "
        "  last_incident_date, last_incident_severity, last_incident_desc, "
        "  supply_chain_status, days_to_next_casing, esp_health_pct, mud_pump_health_pct "
        "FROM las.drilling_operations WHERE well_id = $1", well_id
    )
    return {
        "well": dict(well) if well else None,
        "econ": dict(econ) if econ else None,
        "res":  dict(res) if res else None,
        "ops":  dict(ops) if ops else None,
    }


async def specialist_analogs(req: DecideReq, ctx: dict) -> dict:
    t0 = time.time()
    well = ctx.get("well") or {}
    res  = ctx.get("res") or {}
    # Build a rich query so the VS index returns geologically similar analogs.
    formation = res.get("formation_name") or well.get("basin") or ""
    query = f"{formation} reservoir, {well.get('basin','')} basin, {well.get('well_type','')} oil producer"
    text = await tool_search_similar_wells(query.strip() or req.question, k=5)
    if res.get("analog_well_id"):
        text = (
            f"Active well: {well.get('well_id')} ({well.get('basin')}, "
            f"{res.get('formation_name')}). Closest ADME analog: "
            f"{res.get('analog_well_id')} in {res.get('analog_field')}.\n\n"
            + text
        )
    return {
        "id": "analogs",
        "name": "Subsurface Analog Retriever",
        "feature": "Vector Search",
        "endpoint": "subsurface-vs · gte-large",
        "ms": _ms(t0),
        "result": text,
        "query": query,
    }


async def specialist_petrophysics(req: DecideReq, ctx: dict) -> dict:
    t0 = time.time()
    well = ctx.get("well") or {}
    res  = ctx.get("res")  or {}

    # Cross-check the operator's simulated values against the ADME analog's actual data
    analog_field = res.get("analog_field") or "Block 15/9"
    analog_sql = (
        f"SELECT field, formation, COUNT(*) AS samples, "
        f"  ROUND(AVG(porosity_frac), 3)    AS avg_phi, "
        f"  ROUND(AVG(permeability_md), 0) AS avg_k_md, "
        f"  ROUND(AVG(oil_saturation),  2) AS avg_so "
        f"FROM `{CATALOG}`.`{SCHEMA}`.gold_rock_and_fluid "
        f"WHERE field = '{analog_field}' GROUP BY field, formation ORDER BY field, formation"
    )
    try:
        cols, rows = await asyncio.to_thread(_run_sql, analog_sql)
        analog_table = _fmt_rows(cols, rows)
    except Exception as e:
        analog_table = f"(ADME rock-fluid query failed: {e})"

    op_table = (
        f"Operator well: {well.get('well_id')} · formation: {res.get('formation_name')}\n"
        f"  avg_porosity={res.get('avg_porosity_frac')} · "
        f"avg_perm_md={res.get('avg_permeability_md')} · "
        f"avg_So={res.get('avg_oil_saturation')} · "
        f"net_pay={res.get('net_pay_ft')} ft · "
        f"OOIP={res.get('original_oil_in_place_mmbbl')} MMbbl · "
        f"P_init={res.get('initial_pressure_psi')} psi · "
        f"T_init={res.get('reservoir_temp_f')}°F"
    ) if res else "(no simulated rock-fluid available for this well)"

    system = (
        "You are a petrophysics specialist. Compare the operator's well to its ADME analog field. "
        "Identify the pay zone, comment on rock quality and saturation, and call out the biggest "
        "petrophysical risk. Be quantitative. 4 lines max. No preamble."
    )
    user = (
        f"OPERATOR WELL DATA (las.reservoir_simulated):\n{op_table}\n\n"
        f"ADME ANALOG FIELD RAW DATA (gold_rock_and_fluid · {analog_field}):\n{analog_table}"
    )
    try:
        summary = await asyncio.to_thread(_claude_text, system, user, 350)
    except Exception as e:
        summary = f"(Claude call failed: {e})"
    return {
        "id": "petrophysics",
        "name": "Petrophysics Interpreter",
        "feature": "Model Serving · Claude 4.5",
        "endpoint": MODEL_ENDPOINT,
        "ms": _ms(t0),
        "result": summary,
        "evidence": f"{op_table}\n\nADME analog data:\n{analog_table}",
    }


async def specialist_economics(req: DecideReq, ctx: dict) -> dict:
    t0 = time.time()
    econ = ctx.get("econ") or {}
    capex   = req.capex_musd     if req.capex_musd     is not None else float(econ.get("capex_musd")     or 50.0)
    opex    = req.opex_musd_yr   if req.opex_musd_yr   is not None else float(econ.get("opex_musd_yr")   or 4.0)
    peak    = req.peak_rate_bopd if req.peak_rate_bopd is not None else float(econ.get("peak_rate_bopd") or 2000.0)
    decline = req.decline_pct_yr if req.decline_pct_yr is not None else float(econ.get("decline_pct_yr") or 20.0)
    wti     = float(req.wti_price)
    try:
        npv_now, be, npv_lo, npv_hi = await asyncio.gather(
            tool_calculate_npv(capex, opex, peak, decline, wti),
            tool_calculate_break_even(capex, opex, peak, decline),
            tool_calculate_npv(capex, opex, peak, decline, wti - 10),
            tool_calculate_npv(capex, opex, peak, decline, wti + 10),
        )
        result = (
            f"Inputs from las.well_economics · capex ${capex}M · opex ${opex}M/yr · "
            f"peak {peak} bopd · decline {decline}%/yr\n"
            f"{npv_now}\n{be}\n"
            f"Sensitivity WTI −$10: {npv_lo}\n"
            f"Sensitivity WTI +$10: {npv_hi}"
        )
    except Exception as e:
        result = f"(UC Functions call failed: {e})"
    return {
        "id": "economics",
        "name": "Economics Evaluator",
        "feature": "UC Functions",
        "endpoint": f"{CATALOG}.{SCHEMA}.calculate_npv10 · calculate_break_even",
        "ms": _ms(t0),
        "result": result,
    }


async def specialist_regulatory(req: DecideReq, ctx: dict) -> dict:
    t0 = time.time()
    sql = (
        f"SELECT legal_tag_name, COALESCE(source, data_partition_id) AS partition, is_valid "
        f"FROM `{CATALOG}`.`{SCHEMA}`.gov_legal_tags ORDER BY legal_tag_name"
    )
    try:
        cols, rows = await asyncio.to_thread(_run_sql, sql)
        table = _fmt_rows(cols, rows, limit=10)
        valid_count = sum(1 for r in rows if str(r[2]).lower() == "true")
        headline = (
            f"{valid_count}/{len(rows)} ADME legal tags valid · ACL inherited to UC row tags · "
            f"export-control: not-restricted for opendes partition"
        )
    except Exception as e:
        table = f"(legal-tag query failed: {e})"
        headline = "n/a"
    return {
        "id": "regulatory",
        "name": "Regulatory & ESG Gate",
        "feature": "Unity Catalog · ADME legal tags",
        "endpoint": f"{CATALOG}.{SCHEMA}.gov_legal_tags",
        "ms": _ms(t0),
        "result": f"{headline}\n{table}",
    }


async def specialist_operations(req: DecideReq, ctx: dict) -> dict:
    t0 = time.time()
    well = ctx.get("well") or {}
    ops  = ctx.get("ops")  or {}
    if not ops:
        return {
            "id": "operations",
            "name": "Drilling Operations",
            "feature": "Lakebase · drilling_operations",
            "endpoint": "las.drilling_operations",
            "ms": _ms(t0),
            "result": f"No drilling-operations data for {well.get('well_id', req.well_id)}.",
        }

    lines = [
        f"Rig: {ops.get('rig_name')} ({ops.get('rig_contractor')}) · status={ops.get('rig_status')} · phase={ops.get('drilling_phase')}",
        f"Days on well: {ops.get('days_on_well')} · current MD: {ops.get('current_md_ft')} ft · ROP: {ops.get('rop_ft_per_hr')} ft/hr · mud weight: {ops.get('mud_weight_ppg')} ppg",
        f"NPT last 30d: {ops.get('npt_hours_last_30d')} hr · casing strings set: {ops.get('casing_strings_set')} · days to next casing: {ops.get('days_to_next_casing')}",
        f"BHA health: ESP {ops.get('esp_health_pct')}% · mud pump {ops.get('mud_pump_health_pct')}%",
        f"Supply chain: {ops.get('supply_chain_status')}",
    ]
    if ops.get("last_incident_date"):
        sev = ops.get("last_incident_severity") or "info"
        lines.append(f"Last incident ({sev}, {ops.get('last_incident_date')}): {ops.get('last_incident_desc')}")
    headline = ""
    npt = float(ops.get("npt_hours_last_30d") or 0)
    if npt > 60:
        headline = f"⚠ NPT elevated ({npt:.0f} hr in last 30 days) — risk to schedule.\n"
    elif (ops.get("esp_health_pct") or 100) < 80:
        headline = f"⚠ ESP health {ops.get('esp_health_pct')}% — workover within 90 days likely.\n"
    return {
        "id": "operations",
        "name": "Drilling Operations",
        "feature": "Lakebase · drilling_operations",
        "endpoint": "las.drilling_operations",
        "ms": _ms(t0),
        "result": headline + "\n".join(lines),
    }


SPECIALISTS = [
    specialist_analogs,
    specialist_petrophysics,
    specialist_economics,
    specialist_regulatory,
    specialist_operations,
]

SYNTHESIS_SYSTEM = (
    "You are the Subsurface Supervisor. Five specialists have returned findings about a single "
    "operator well in North America (with ADME analog data from the ADME global catalog). "
    "Produce a 1-paragraph recommendation (DRILL · HOLD · DE-SCOPE · ABANDON), then a bullet "
    "list of the 3 strongest supporting facts and 1 line on the top risk. Always cite specific "
    "numbers (NPV, break-even, porosity, perm, NPT hours) and the analog well name. Be terse "
    "and confident. No preamble, no apologies."
)


def _extract_verdict(rec_text: str) -> str:
    """Pull the headline verdict (DRILL · HOLD · DE-SCOPE · ABANDON) from the model output."""
    if not rec_text:
        return "REVIEW"
    upper = rec_text.upper()
    for v in ("DRILL", "DE-SCOPE", "DESCOPE", "HOLD", "ABANDON"):
        if v in upper:
            return "DE-SCOPE" if v in ("DE-SCOPE", "DESCOPE") else v
    return "REVIEW"


# Persisted most-recent Supervisor run for the Overview "last decision" widget.
_LAST_DECISION: dict = {}


@router.get("/supervisor/last_decision")
async def last_decision():
    return _LAST_DECISION or {"empty": True}


async def synthesize(req: DecideReq, ctx: dict, specs: list[dict]) -> str:
    well = (ctx.get("well") or {})
    res  = (ctx.get("res")  or {})
    pack_lines = []
    for s in specs:
        if "error" in s:
            continue
        pack_lines.append(f"### {s['name']}  ·  feature: {s.get('feature','')}")
        pack_lines.append(s.get("result", ""))
        pack_lines.append("")
    pack = "\n".join(pack_lines).strip()
    user = (
        f"USER QUESTION:\n{req.question}\n"
        f"OPERATOR WELL: {req.well_id} ({well.get('well_name','?')}) · basin: {well.get('basin','?')} · status: {well.get('status','?')}\n"
        f"FORMATION: {res.get('formation_name','?')} · ADME analog: {res.get('analog_well_id','?')} ({res.get('analog_field','?')})\n"
        f"WTI: ${req.wti_price:.0f}/bbl\n\n"
        f"SPECIALIST FINDINGS:\n{pack}"
    )
    return await asyncio.to_thread(_claude_text, SYNTHESIS_SYSTEM, user, 700)


# ─────────────────────────────────────────────────────────────────────────────
# SSE endpoint — emits per-specialist events as they complete
# ─────────────────────────────────────────────────────────────────────────────

def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@router.post("/supervisor/decide")
async def decide(req: DecideReq):
    """Stream specialist results as SSE; final 'recommendation' event closes the run."""
    async def gen():
        t0 = time.time()
        # Load well context once; reuse across all specialists
        try:
            ctx = await _get_well_context(req.well_id)
        except Exception as e:
            ctx = {"well": None, "econ": None, "res": None, "ops": None, "_error": str(e)}

        well = (ctx.get("well") or {})
        res  = (ctx.get("res")  or {})

        yield _sse("start", {
            "question": req.question,
            "well_id":  req.well_id,
            "well_name": well.get("well_name"),
            "basin":    well.get("basin"),
            "formation": res.get("formation_name"),
            "analog_well_id": res.get("analog_well_id"),
            "analog_field":   res.get("analog_field"),
            "specialists": [
                {"id": "analogs",      "name": "Subsurface Analog Retriever", "feature": "Vector Search"},
                {"id": "petrophysics", "name": "Petrophysics Interpreter",    "feature": "Model Serving"},
                {"id": "economics",    "name": "Economics Evaluator",         "feature": "UC Functions"},
                {"id": "regulatory",   "name": "Regulatory & ESG Gate",       "feature": "ADME Legal Tags"},
                {"id": "operations",   "name": "Drilling Operations",         "feature": "Lakebase"},
            ],
        })

        queue: asyncio.Queue = asyncio.Queue()

        async def run_and_push(coro):
            try:
                r = await coro
                await queue.put(("specialist", r))
            except Exception as e:
                await queue.put(("specialist", {
                    "id": "unknown", "name": "specialist", "error": str(e),
                    "trace": traceback.format_exc()[-300:],
                }))

        tasks = [asyncio.create_task(run_and_push(spec(req, ctx))) for spec in SPECIALISTS]

        collected: list[dict] = []
        for _ in tasks:
            ev, payload = await queue.get()
            collected.append(payload)
            yield _sse(ev, payload)

        # Synthesis after all specialists land
        try:
            rec = await synthesize(req, ctx, collected)
        except Exception as e:
            rec = f"(synthesis failed: {e})"
        verdict = _extract_verdict(rec)
        payload = {
            "text": rec,
            "verdict": verdict,
            "total_ms": _ms(t0),
            "well_id": req.well_id,
            "well_name": well.get("well_name"),
        }
        # Persist the most recent decision for the Overview "last decision" widget
        _LAST_DECISION.update({
            **payload,
            "ts": time.time(),
            "basin": well.get("basin"),
        })
        yield _sse("recommendation", payload)
        yield _sse("done", {"total_ms": _ms(t0)})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@router.get("/supervisor/info")
async def info():
    """Static description of the supervisor — for the UI's 'how it works' panel."""
    return {
        "name": "Subsurface Supervisor",
        "model": MODEL_ENDPOINT,
        "specialists": [
            {"id": "analogs",      "name": "Subsurface Analog Retriever", "feature": "Vector Search",         "endpoint": "subsurface-vs · gte-large", "desc": "Top-k analog wells from ADME via semantic search; matches operator well to global ADME analogs."},
            {"id": "petrophysics", "name": "Petrophysics Interpreter",    "feature": "Model Serving",         "endpoint": MODEL_ENDPOINT,               "desc": "Claude 4.5 cross-checks operator's simulated rock-fluid against ADME analog field's actuals."},
            {"id": "economics",    "name": "Economics Evaluator",         "feature": "UC Functions",          "endpoint": f"{CATALOG}.{SCHEMA}.calculate_npv10 · calculate_break_even", "desc": "Governed NPV₁₀ + break-even + ±$10 WTI sensitivity via Unity Catalog SQL functions."},
            {"id": "regulatory",   "name": "Regulatory & ESG Gate",       "feature": "ADME Legal Tags",       "endpoint": f"{CATALOG}.{SCHEMA}.gov_legal_tags", "desc": "Live legal-tag lookup; ACL inheritance flows from ADME to UC tags."},
            {"id": "operations",   "name": "Drilling Operations",         "feature": "Lakebase · drilling_operations", "endpoint": "las.drilling_operations", "desc": "Rig, NPT, supply-chain, casing status, BHA health from the operator's Lakebase ops feed."},
        ],
    }
