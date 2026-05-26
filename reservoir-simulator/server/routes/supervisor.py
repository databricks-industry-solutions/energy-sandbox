"""Reservoir Simulator — Decision Supervisor (multi-agent fan-out).

The Supervisor takes a question about a candidate scenario / run, fans out
across N specialists in parallel, and synthesises a deployment recommendation:

  APPROVE · APPROVE-WITH-MODS · DEFER · REJECT

Each specialist demonstrates a different Databricks AI primitive — that's
the "why Databricks" story.

Specialists:
  1. Reservoir Performance — Foundation Model API (Claude) over field summary + decline
  2. Economics Evaluator   — UC Functions for governed NPV/IRR + ±$10 oil-price sensitivity
                              (falls back to local DCF calc if UC function not deployed)
  3. Operations Feasibility — Lakebase (operator-managed Postgres) — rig calendar, ESP health
                              (reads from run_operations table)
  4. Analog Field Retrieval — Vector Search index (subsurface analogs)
                              (falls back to curated Norne-similar field list if VS not set)
  5. Supply Chain & Cost   — SAP BDC + Genie NL → SQL for material lead times
                              (reads from run_costs + delta_sharing_log)
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
from .simulate import _field_summaries, _operations_cache, _costs_cache

router = APIRouter()


# ───────────── Config (env-driven so the same code runs locally + in prod workspace) ─────────────

CATALOG       = os.getenv("DEMO_CATALOG", "energy_utilities")
SCHEMA        = os.getenv("DEMO_SCHEMA",  "reservoir_simulator")
WAREHOUSE_ID  = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
MODEL_ENDPOINT = os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-5")
VS_ENDPOINT   = os.getenv("VS_ENDPOINT", "subsurface-vs")
VS_INDEX      = os.getenv("VS_INDEX",    f"{CATALOG}.{SCHEMA}.field_analogs_vs_index")


# ───────────── Tool helpers ─────────────


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


def _claude_text(system: str, user: str, max_tokens: int = 600) -> str:
    """Synchronous Claude call via Databricks Foundation Model API."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    w = WorkspaceClient()
    resp = w.serving_endpoints.query(
        name=MODEL_ENDPOINT,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
            ChatMessage(role=ChatMessageRole.USER,   content=user),
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    try:
        return resp.choices[0].message.content or ""
    except Exception:
        return str(resp)[:600]


def _ms(t0: float) -> int:
    return round((time.time() - t0) * 1000)


# ───────────── Request shape ─────────────


class DecideReq(BaseModel):
    question: str
    scenario_id: int | None = None
    run_id: str | None = None
    oil_price: float = 75.0


# ───────────── Context loader ─────────────


async def _load_context(req: DecideReq) -> dict:
    """Pull scenario + run + latest field summary + economics once and share across specialists."""
    ctx: dict = {"oil_price": req.oil_price}

    if req.scenario_id:
        scenario = await db.fetchrow(
            "SELECT id, name, deck_id, description, config FROM scenarios WHERE id=?",
            req.scenario_id,
        )
        if scenario:
            cfg = scenario.get("config", "{}")
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except Exception:
                    cfg = {}
            ctx["scenario"] = {**dict(scenario), "config": cfg}

    if req.run_id:
        run = await db.fetchrow(
            "SELECT id, status, progress, current_timestep, total_timesteps "
            "FROM simulation_runs WHERE id=?", req.run_id,
        )
        if run:
            ctx["run"] = dict(run)

        econ = await db.fetchrow(
            "SELECT oil_price, gas_price, discount_rate, opex_per_boe, capex_per_well, "
            "npv_usd, irr, payback_year FROM economics_results "
            "WHERE run_id=? ORDER BY id DESC LIMIT 1", req.run_id,
        )
        if econ:
            ctx["economics"] = dict(econ)

        summaries = _field_summaries.get(req.run_id, [])
        if summaries:
            ctx["field_summary_latest"] = summaries[-1]
            ctx["field_summary_first"]  = summaries[0]
            ctx["summary_count"]        = len(summaries)

        ops = _operations_cache.get(req.run_id, [])
        if ops:
            ctx["operations"] = ops

        costs = _costs_cache.get(req.run_id, {})
        if costs:
            ctx["costs"] = costs

    return ctx


# ───────────── Specialists ─────────────


async def specialist_reservoir(req: DecideReq, ctx: dict) -> dict:
    """Reservoir Performance — Claude reasoning over latest field summary + decline."""
    t0 = time.time()
    summary = ctx.get("field_summary_latest")
    first   = ctx.get("field_summary_first")
    scen    = (ctx.get("scenario") or {})
    cfg     = scen.get("config", {})

    if not summary:
        return {
            "id": "reservoir", "name": "Reservoir Performance Analyst",
            "feature": "Foundation Model API · Claude",
            "endpoint": MODEL_ENDPOINT, "ms": _ms(t0),
            "result": "(no field-summary data available — run a simulation first)",
        }

    decline_pct = 0.0
    if first and first.get("field_oil_rate_stbd"):
        first_rate = float(first["field_oil_rate_stbd"])
        last_rate  = float(summary["field_oil_rate_stbd"] or 0)
        if first_rate > 0:
            decline_pct = round((1 - last_rate / first_rate) * 100, 1)

    facts = (
        f"Scenario: {scen.get('name','?')} ({cfg.get('field','?')} / {cfg.get('formation','?')})\n"
        f"Wells: {len(cfg.get('wells', []))} configured\n"
        f"Latest field state (day {summary.get('day','?')}): "
        f"oil {summary.get('field_oil_rate_stbd',0)} STB/d, "
        f"gas {summary.get('field_gas_rate_mscfd',0)} MSCF/d, "
        f"water cut {summary.get('water_cut_pct',0)}%, "
        f"avg pressure {summary.get('field_avg_pressure_bar',0)} bar.\n"
        f"Decline since start of run: {decline_pct}%\n"
        f"Cumulative oil: {summary.get('cum_oil_stb',0):,.0f} STB"
    )
    system = (
        "You are a senior reservoir engineer. Give a 3-line assessment of reservoir performance "
        "and the single biggest risk. Be quantitative. Cite numbers. No preamble."
    )
    try:
        analysis = await asyncio.to_thread(_claude_text, system, facts, 250)
    except Exception as e:
        analysis = f"(Claude call failed: {e})"
    return {
        "id": "reservoir", "name": "Reservoir Performance Analyst",
        "feature": "Foundation Model API · Claude",
        "endpoint": MODEL_ENDPOINT, "ms": _ms(t0),
        "result": analysis,
        "evidence": facts,
    }


async def specialist_economics(req: DecideReq, ctx: dict) -> dict:
    """Economics Evaluator — governed NPV via UC Functions, ±$10 oil-price sensitivity."""
    t0 = time.time()
    econ = ctx.get("economics")
    if not econ:
        return {
            "id": "economics", "name": "Economics Evaluator",
            "feature": "UC Functions · governed NPV/IRR",
            "endpoint": f"{CATALOG}.{SCHEMA}.calculate_npv (not yet deployed)",
            "ms": _ms(t0),
            "result": "(no economics_results row for this run — run the economics pass first)",
        }

    base_npv = float(econ.get("npv_usd") or 0)
    base_irr = float(econ.get("irr")     or 0) * 100
    base_oil = float(econ.get("oil_price") or req.oil_price)

    # Crude ±$10 sensitivity via linear scaling on NPV (placeholder until UC Function deployed)
    capex = float(econ.get("capex_per_well") or 8_000_000) * len((ctx.get("scenario") or {}).get("config", {}).get("wells", []) or [1])
    opex_per_boe = float(econ.get("opex_per_boe") or 8.5)
    rate_delta_pct = 10 / max(base_oil, 1) * 0.6  # ~60% of price move flows to NPV at given decline
    npv_lo = base_npv * (1 - rate_delta_pct)
    npv_hi = base_npv * (1 + rate_delta_pct)
    break_even = max(opex_per_boe + 5, base_oil * (1 - max(base_npv, 1) / max(capex, 1)))

    result = (
        f"At ${base_oil:.0f}/bbl: NPV ${base_npv/1e6:.1f}M · IRR {base_irr:.1f}% · payback yr {econ.get('payback_year','?')}\n"
        f"Sensitivity oil −$10: NPV ${npv_lo/1e6:.1f}M\n"
        f"Sensitivity oil +$10: NPV ${npv_hi/1e6:.1f}M\n"
        f"Approx break-even: ${break_even:.1f}/bbl · opex per BOE ${opex_per_boe:.2f}"
    )
    return {
        "id": "economics", "name": "Economics Evaluator",
        "feature": "UC Functions · governed NPV/IRR (stub — wire to UC Function when deployed)",
        "endpoint": f"{CATALOG}.{SCHEMA}.calculate_npv · calculate_break_even",
        "ms": _ms(t0),
        "result": result,
    }


async def specialist_operations(req: DecideReq, ctx: dict) -> dict:
    """Operations Feasibility — Lakebase ops feed (rig calendar, ESP health, NPT)."""
    t0 = time.time()
    ops = ctx.get("operations") or []
    if not ops:
        return {
            "id": "operations", "name": "Operations Feasibility",
            "feature": "Lakebase Postgres · run_operations",
            "endpoint": "run_operations", "ms": _ms(t0),
            "result": "(no operations data for this run)",
        }
    lines = [f"{len(ops)} planned operations:"]
    for op in ops[:6]:
        lines.append(
            f"  · {op.get('well','?')} — {op.get('type','?')} "
            f"({op.get('duration_days','?')}d, ${op.get('cost_usd',0):,.0f})"
        )
    if len(ops) > 6:
        lines.append(f"  … + {len(ops)-6} more")
    total_days = sum(int(o.get("duration_days") or 0) for o in ops)
    total_cost = sum(float(o.get("cost_usd") or 0) for o in ops)
    headline = f"Total op-days: {total_days} · total opex commitment: ${total_cost/1e6:.1f}M"
    return {
        "id": "operations", "name": "Operations Feasibility",
        "feature": "Lakebase Postgres · run_operations",
        "endpoint": "run_operations",
        "ms": _ms(t0),
        "result": headline + "\n" + "\n".join(lines),
    }


async def specialist_analogs(req: DecideReq, ctx: dict) -> dict:
    """Analog Field Retrieval — Vector Search. Falls back to curated Norne-similar fields if VS not set."""
    t0 = time.time()
    cfg = (ctx.get("scenario") or {}).get("config", {})
    field = cfg.get("field") or "Norne"
    formation = cfg.get("formation") or "Fangst/Ile"
    query = f"{formation} reservoir, {field} field, turbidite, North Sea benchmark"

    # Try real Vector Search first
    try:
        from databricks.vector_search.client import VectorSearchClient
        c = VectorSearchClient(disable_notice=True)
        idx = c.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
        res = idx.similarity_search(
            query_text=query,
            columns=["field_name", "operator", "formation", "primary_play", "notes"],
            num_results=5,
        )
        rows = []
        if res and "result" in res:
            data = res["result"].get("data_array", [])
            cols = [c["name"] for c in res["manifest"]["columns"]]
            for r in data:
                rows.append(dict(zip(cols, r)))
        if rows:
            lines = [f"Vector Search analogs for {field} / {formation}:"]
            for r in rows:
                lines.append(f"  · {r.get('field_name','?')} ({r.get('operator','?')}) — {r.get('primary_play','?')}")
            return {
                "id": "analogs", "name": "Analog Field Retrieval",
                "feature": "Vector Search · subsurface-vs",
                "endpoint": f"{VS_ENDPOINT} · {VS_INDEX}", "ms": _ms(t0),
                "result": "\n".join(lines),
                "query": query,
            }
    except Exception as e:
        # Falls through to curated stub
        stub_note = f"(Vector Search not yet wired: {type(e).__name__}. Using curated analogs.)"

    # Stub fallback
    analogs = [
        ("Snorre",     "Equinor",       "Statfjord / Lunde", "turbidite, North Sea, ~30% porosity"),
        ("Heidrun",    "Equinor",       "Åre / Tilje",       "neighbouring Halten Terrace, similar pressure"),
        ("Draugen",    "OKEA",          "Rogn",              "Halten Terrace shallow oil, water-drive"),
        ("Volve",      "Equinor",       "Hugin",             "smaller analog, open-data benchmark"),
    ]
    lines = [f"Curated analogs for {field} / {formation} (replace with VS once index is deployed):"]
    for name, op, form, note in analogs:
        lines.append(f"  · {name} ({op}) — {form} — {note}")
    return {
        "id": "analogs", "name": "Analog Field Retrieval",
        "feature": "Vector Search · subsurface-vs (stub — wire to live index)",
        "endpoint": f"{VS_ENDPOINT} · {VS_INDEX} (not yet deployed)",
        "ms": _ms(t0),
        "result": "\n".join(lines),
        "query": query,
    }


async def specialist_supply_chain(req: DecideReq, ctx: dict) -> dict:
    """Supply Chain & Cost — SAP BDC material cost + Genie NL→SQL for lead times."""
    t0 = time.time()
    costs = ctx.get("costs") or {}
    if not costs:
        return {
            "id": "supply", "name": "Supply Chain & Cost",
            "feature": "SAP BDC · Delta Sharing + Genie",
            "endpoint": "run_costs · delta_sharing_log",
            "ms": _ms(t0),
            "result": "(no cost breakdown for this run — run cost pass first)",
        }

    total = costs.get("total_cost_usd") or 0
    by_cat = costs.get("by_category") or {}
    lines = [f"Total D&C + opex commitment: ${total/1e6:.1f}M"]
    for cat, amt in list(by_cat.items())[:5]:
        lines.append(f"  · {cat}: ${amt/1e6:.2f}M")

    # Optional Genie call for lead times — only if Space configured
    if os.getenv("GENIE_SPACE_ID"):
        try:
            from .genie import _ask_sync
            g = await asyncio.to_thread(_ask_sync, "Which materials have lead times longer than 14 days?", None)
            if isinstance(g, dict) and g.get("text") and not g.get("error"):
                lines.append(f"\nGenie lead-time check: {g['text'][:300]}")
        except Exception:
            pass

    return {
        "id": "supply", "name": "Supply Chain & Cost",
        "feature": "SAP BDC · Delta Sharing + Genie NL→SQL",
        "endpoint": "run_costs · delta_sharing_log",
        "ms": _ms(t0),
        "result": "\n".join(lines),
    }


SPECIALISTS = [
    specialist_reservoir,
    specialist_economics,
    specialist_operations,
    specialist_analogs,
    specialist_supply_chain,
]


# ───────────── Synthesis ─────────────

SYNTHESIS_SYSTEM = (
    "You are the Reservoir Deployment Supervisor. Five specialists have returned findings about a "
    "candidate Norne-field scenario. Produce a 1-paragraph deployment recommendation "
    "(APPROVE · APPROVE-WITH-MODS · DEFER · REJECT), then a bulleted list of the 3 strongest "
    "supporting facts and 1 line on the top risk. Cite specific numbers (NPV, decline, op-days, "
    "lead time). Be terse and confident. No preamble, no apologies."
)


def _extract_verdict(rec_text: str) -> str:
    if not rec_text:
        return "REVIEW"
    upper = rec_text.upper()
    for v in ("APPROVE-WITH-MODS", "APPROVE_WITH_MODS", "APPROVE WITH MODS"):
        if v in upper:
            return "APPROVE-WITH-MODS"
    for v in ("REJECT", "DEFER", "APPROVE"):
        if v in upper:
            return v
    return "REVIEW"


_LAST_DECISION: dict = {}


@router.get("/supervisor/last_decision")
async def last_decision():
    return _LAST_DECISION or {"empty": True}


async def synthesize(req: DecideReq, ctx: dict, specs: list[dict]) -> str:
    scen = (ctx.get("scenario") or {})
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
        f"SCENARIO: {scen.get('name','?')} (run {req.run_id or 'n/a'}) · oil price ${req.oil_price:.0f}/bbl\n\n"
        f"SPECIALIST FINDINGS:\n{pack}"
    )
    return await asyncio.to_thread(_claude_text, SYNTHESIS_SYSTEM, user, 600)


# ───────────── SSE endpoint ─────────────

def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@router.post("/supervisor/decide")
async def decide(req: DecideReq):
    async def gen():
        t0 = time.time()
        try:
            ctx = await _load_context(req)
        except Exception as e:
            ctx = {"_error": str(e)}

        scen = (ctx.get("scenario") or {})
        yield _sse("start", {
            "question": req.question,
            "scenario_id": req.scenario_id,
            "scenario_name": scen.get("name"),
            "run_id": req.run_id,
            "oil_price": req.oil_price,
            "specialists": [
                {"id": "reservoir",  "name": "Reservoir Performance",      "feature": "Foundation Model API"},
                {"id": "economics",  "name": "Economics Evaluator",        "feature": "UC Functions"},
                {"id": "operations", "name": "Operations Feasibility",     "feature": "Lakebase"},
                {"id": "analogs",    "name": "Analog Field Retrieval",     "feature": "Vector Search"},
                {"id": "supply",     "name": "Supply Chain & Cost",        "feature": "SAP BDC + Genie"},
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

        tasks = [asyncio.create_task(run_and_push(s(req, ctx))) for s in SPECIALISTS]

        collected: list[dict] = []
        for _ in tasks:
            ev, payload = await queue.get()
            collected.append(payload)
            yield _sse(ev, payload)

        try:
            rec = await synthesize(req, ctx, collected)
        except Exception as e:
            rec = f"(synthesis failed: {e})"
        verdict = _extract_verdict(rec)
        payload = {
            "text": rec,
            "verdict": verdict,
            "total_ms": _ms(t0),
            "scenario_id": req.scenario_id,
            "scenario_name": scen.get("name"),
            "run_id": req.run_id,
        }
        _LAST_DECISION.update({**payload, "ts": time.time()})
        yield _sse("recommendation", payload)
        yield _sse("done", {"total_ms": _ms(t0)})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@router.get("/supervisor/info")
async def info():
    return {
        "name": "Reservoir Deployment Supervisor",
        "model": MODEL_ENDPOINT,
        "specialists": [
            {"id": "reservoir",  "name": "Reservoir Performance Analyst", "feature": "Foundation Model API", "endpoint": MODEL_ENDPOINT,                                  "desc": "Claude reasons over the latest field-summary snapshot and decline."},
            {"id": "economics",  "name": "Economics Evaluator",           "feature": "UC Functions",         "endpoint": f"{CATALOG}.{SCHEMA}.calculate_npv (stub)",      "desc": "Governed NPV / IRR / payback + ±$10 oil-price sensitivity."},
            {"id": "operations", "name": "Operations Feasibility",        "feature": "Lakebase",             "endpoint": "run_operations",                                "desc": "Planned operations, total op-days, opex commitment from the operator's Lakebase feed."},
            {"id": "analogs",    "name": "Analog Field Retrieval",        "feature": "Vector Search",        "endpoint": f"{VS_ENDPOINT} · {VS_INDEX}",                   "desc": "Top-k similar North Sea fields (Snorre, Heidrun, Draugen, Volve) via semantic search."},
            {"id": "supply",     "name": "Supply Chain & Cost",           "feature": "SAP BDC + Genie",      "endpoint": "run_costs · Genie",                             "desc": "SAP material costs + Genie NL query for lead-time risk."},
        ],
        "verdicts": ["APPROVE", "APPROVE-WITH-MODS", "DEFER", "REJECT"],
    }
