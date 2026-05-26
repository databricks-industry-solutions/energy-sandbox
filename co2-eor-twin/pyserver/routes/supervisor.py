"""CO2-EOR Decision Supervisor — multi-agent fan-out.

Question: "Where should the next CO2 injection slug go?"
Verdicts: INJECT-PATTERN-A · INJECT-PATTERN-B · HOLD-INJECTION · DIVERT-TO-STORAGE

Specialists (5 — one per Databricks AI primitive):
  1. Reservoir State        — Foundation Model API (Claude) over per-pattern mass-balance summary
  2. Analog Field Retrieval — Vector Search (published EOR pilots; falls back to curated list)
  3. Net-CO2 Economics      — UC Functions (stub — local DCF until UC fn deployed)
  4. 45Q + Class VI Compliance — UC tags (stub — curated compliance gate)
  5. Live Ops Constraints   — Lakebase (injection limits, compressor health, surface status)

Each specialist pulls context from the Express twin API (/api/twin/state) running on
localhost:3001, so the same in-memory twin model powers the AI surface.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from typing import Any

import urllib.request
import urllib.error

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


# ─────── Config ───────

CATALOG       = os.getenv("DEMO_CATALOG", "oil_pump_monitor_catalog")
SCHEMA        = os.getenv("DEMO_SCHEMA",  "co2_eor")
MODEL_ENDPOINT = os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-5")
VS_ENDPOINT   = os.getenv("VS_ENDPOINT", "co2-eor-vs")
VS_INDEX      = os.getenv("VS_INDEX",    f"{CATALOG}.{SCHEMA}.published_pilots_vs_index")

# Express twin API (sidecar pattern — both run inside the same app container).
TWIN_BASE     = os.getenv("TWIN_BASE_URL", "http://localhost:3001")


# ─────── Tool helpers ───────


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


def _http_json(url: str, timeout: float = 3.0) -> dict | None:
    """Cheap blocking JSON GET (run via to_thread). Returns None on error."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"twin-fetch failed [{url}]: {e}")
        return None


# ─────── Request shape ───────


class DecideReq(BaseModel):
    question: str
    pattern_id: str | None = None      # selected injection pattern (e.g. "P-NORTH-A")
    co2_price: float = 35.0            # $/tCO2 delivered
    oil_price: float = 75.0            # $/bbl


# ─────── Context loader ───────


async def _load_context(req: DecideReq) -> dict:
    """Pull twin state, alerts, shift label from the Express sidecar once."""
    ctx: dict = {"co2_price": req.co2_price, "oil_price": req.oil_price}

    state = await asyncio.to_thread(_http_json, f"{TWIN_BASE}/api/twin/state")
    if state:
        ctx["twin"] = state
        # Optional convenience views
        ctx["kpis"]     = state.get("kpis") or {}
        ctx["patterns"] = state.get("patterns") or []
        ctx["wells"]    = state.get("wells")    or []
        ctx["alerts"]   = state.get("alerts")   or []

        if req.pattern_id:
            pat = next((p for p in ctx["patterns"] if p.get("id") == req.pattern_id), None)
            if pat:
                ctx["pattern"] = pat

    return ctx


# ─────── Specialists ───────


async def specialist_reservoir(req: DecideReq, ctx: dict) -> dict:
    """Reservoir State — Claude over per-pattern mass-balance summary."""
    t0 = time.time()
    patterns = ctx.get("patterns") or []
    pat = ctx.get("pattern")
    kpis = ctx.get("kpis") or {}
    prod = kpis.get("production") or {}

    if not patterns:
        return {
            "id": "reservoir", "name": "Reservoir State Analyst",
            "feature": "Foundation Model API · Claude",
            "endpoint": MODEL_ENDPOINT, "ms": _ms(t0),
            "result": "(no twin pattern data available)",
        }

    target = pat or patterns[0]
    facts = (
        f"Active patterns: {len(patterns)}\n"
        f"Target pattern: {target.get('id','?')} ({target.get('name','?')})\n"
        f"  · injection rate: {target.get('injectionRate','?')} Mcf/d CO2\n"
        f"  · WAG cycle: {target.get('wagPhase','?')}, cum CO2 slug: {target.get('cumCO2','?')} Mscf\n"
        f"  · pattern VRR: {target.get('vrr','?')} · breakthrough flag: {target.get('breakthrough','?')}\n"
        f"Field totals: oil {prod.get('totalOil','?')} bbl/d, gas {prod.get('totalGas','?')} Mcf/d, "
        f"CO2 injected {prod.get('co2Injected','?')} Mcf/d, incremental oil {prod.get('incrementalOil','?')} bbl/d, "
        f"CO2 utilisation {prod.get('co2Utilization','?')}%."
    )
    system = (
        "You are a senior reservoir engineer focused on CO2-EOR. Give a 3-line assessment of "
        "the target pattern's slug-placement attractiveness vs other patterns, and the single "
        "biggest reservoir risk (early CO2 breakthrough, VRR imbalance, pressure run-up). "
        "Be quantitative. Cite numbers. No preamble."
    )
    try:
        analysis = await asyncio.to_thread(_claude_text, system, facts, 250)
    except Exception as e:
        analysis = f"(Claude call failed: {e})"
    return {
        "id": "reservoir", "name": "Reservoir State Analyst",
        "feature": "Foundation Model API · Claude",
        "endpoint": MODEL_ENDPOINT, "ms": _ms(t0),
        "result": analysis,
        "evidence": facts,
    }


async def specialist_analogs(req: DecideReq, ctx: dict) -> dict:
    """Analog Field Retrieval — Vector Search of published EOR pilots."""
    t0 = time.time()
    pat = ctx.get("pattern") or (ctx.get("patterns") or [{}])[0]
    formation = pat.get("formation") or "carbonate, miscible CO2"
    query = f"miscible CO2 flood, {formation}, WAG injection, sweep efficiency"

    try:
        from databricks.vector_search.client import VectorSearchClient
        c = VectorSearchClient(disable_notice=True)
        idx = c.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
        res = idx.similarity_search(
            query_text=query,
            columns=["pilot_name", "operator", "formation", "miscible_pressure_psi", "notes"],
            num_results=5,
        )
        rows = []
        if res and "result" in res:
            data = res["result"].get("data_array", [])
            cols = [c["name"] for c in res["manifest"]["columns"]]
            for r in data:
                rows.append(dict(zip(cols, r)))
        if rows:
            lines = [f"Vector Search analogs for {formation}:"]
            for r in rows:
                lines.append(f"  · {r.get('pilot_name','?')} ({r.get('operator','?')}) — {r.get('formation','?')}")
            return {
                "id": "analogs", "name": "Analog EOR Pilot Retrieval",
                "feature": "Vector Search · co2-eor-vs",
                "endpoint": f"{VS_ENDPOINT} · {VS_INDEX}", "ms": _ms(t0),
                "result": "\n".join(lines),
                "query": query,
            }
    except Exception as e:
        # falls through to curated stub
        pass

    analogs = [
        ("SACROC Unit",          "Kinder Morgan",   "San Andres carbonate",      "longest-running CO2 flood, 1972 onward, mature WAG"),
        ("Weyburn-Midale",       "Whitecap / Cenovus", "Mississippian carbonate", "300 Mt cumulative storage, MMV benchmark"),
        ("Wasson Denver Unit",   "Occidental",      "San Andres carbonate",      "tight matrix, miscible, ~16% IOR uplift"),
        ("Salt Creek",           "Anadarko",        "Wall Creek sandstone",      "hybrid CO2/H2O flood, EPA Class II permitted"),
        ("Bell Creek",           "Denbury",         "Muddy sandstone",           "tertiary CO2 flood, 45Q-claimed storage"),
    ]
    lines = [f"Curated analogs for {formation} (replace with VS once index is deployed):"]
    for name, op, form, note in analogs:
        lines.append(f"  · {name} ({op}) — {form} — {note}")
    return {
        "id": "analogs", "name": "Analog EOR Pilot Retrieval",
        "feature": "Vector Search · co2-eor-vs (stub — wire to live index)",
        "endpoint": f"{VS_ENDPOINT} · {VS_INDEX} (not yet deployed)",
        "ms": _ms(t0),
        "result": "\n".join(lines),
        "query": query,
    }


async def specialist_economics(req: DecideReq, ctx: dict) -> dict:
    """Net-CO2 Economics — UC Functions (stubbed local DCF, ±$10/bbl sensitivity)."""
    t0 = time.time()
    kpis = ctx.get("kpis") or {}
    econ = kpis.get("economics") or {}
    env  = kpis.get("environmental") or {}
    prod = kpis.get("production") or {}

    netback     = float(econ.get("netback")            or 0)
    inc_netback = float(econ.get("incrementalNetback") or 0)
    co2_per_boe = float(econ.get("co2CostPerBoe")      or 0)
    breakeven   = float(econ.get("breakeven")          or 0)
    revenue     = float(econ.get("revenue")            or 0)
    inc_oil     = float(prod.get("incrementalOil")     or 0)
    co2_stored  = float(env.get("co2Stored")           or 0)

    # ±$10/bbl sensitivity on incremental netback
    sens_lo = inc_netback - 10 * 0.6   # ~60% of price move flows through after royalty/tax
    sens_hi = inc_netback + 10 * 0.6
    # Approx 45Q credit value ($85/t for secure geologic storage, EPS-44)
    q45_value_day = co2_stored * 85

    result = (
        f"At ${req.oil_price:.0f}/bbl oil / ${req.co2_price:.0f}/tCO2:\n"
        f"  · daily revenue ${revenue/1e3:.1f}k · netback ${netback:.2f}/boe (incremental ${inc_netback:.2f}/boe)\n"
        f"  · CO2 cost ${co2_per_boe:.2f}/boe · break-even oil ${breakeven:.1f}/bbl\n"
        f"  · incremental oil from this pattern: {inc_oil:.0f} bbl/d\n"
        f"  · ±$10/bbl sensitivity on incremental netback: ${sens_lo:.2f} ↔ ${sens_hi:.2f}/boe\n"
        f"  · 45Q credit (estimate): ${q45_value_day/1e3:.1f}k/d at ${co2_stored:.0f} tCO2/d stored"
    )
    return {
        "id": "economics", "name": "Net-CO2 Economics",
        "feature": "UC Functions · fn_co2_eor_npv (stub — wire to UC Function when deployed)",
        "endpoint": f"{CATALOG}.{SCHEMA}.fn_co2_eor_npv",
        "ms": _ms(t0),
        "result": result,
    }


async def specialist_compliance(req: DecideReq, ctx: dict) -> dict:
    """45Q + Class VI Compliance gate — UC tags (stub)."""
    t0 = time.time()
    pat = ctx.get("pattern") or (ctx.get("patterns") or [{}])[0]
    env = (ctx.get("kpis") or {}).get("environmental") or {}
    compliance = float(env.get("complianceScore") or 0)
    flaring    = float(env.get("flaring")         or 0)
    leaks      = int(env.get("methaneLeaks")      or 0)

    # Curated UC-tag-driven gating logic until `gov.45q_eligibility` + `class_vi_permits` wired
    gates = []
    if compliance >= 95:
        gates.append("compliance score >= 95% → ✓ 45Q audit-ready")
    else:
        gates.append(f"compliance score {compliance:.1f}% → △ below 95% audit threshold")
    if leaks == 0:
        gates.append("methane leak count = 0 → ✓ Subpart W clear")
    else:
        gates.append(f"methane leaks = {leaks} → ⚠️ MRV plan needs update before slug")
    if flaring < 1:
        gates.append(f"flaring {flaring:.2f} MMcf/d → ✓ within state cap")
    else:
        gates.append(f"flaring {flaring:.2f} MMcf/d → ⚠️ approaching state cap")

    permit_status = pat.get("permitStatus", "Class VI active")
    gates.append(f"pattern {pat.get('id','?')} permit: {permit_status}")

    result = "Compliance gate:\n  · " + "\n  · ".join(gates)

    return {
        "id": "compliance", "name": "45Q + Class VI Compliance",
        "feature": "UC tags + audit (stub — wire to gov.45q_eligibility + class_vi_permits)",
        "endpoint": f"{CATALOG}.gov.45q_eligibility · class_vi_permits",
        "ms": _ms(t0),
        "result": result,
    }


async def specialist_ops(req: DecideReq, ctx: dict) -> dict:
    """Live Ops Constraints — Lakebase (injection limits, compressor health, surface status)."""
    t0 = time.time()
    pat = ctx.get("pattern") or (ctx.get("patterns") or [{}])[0]
    twin = ctx.get("twin") or {}
    facilities = twin.get("facilities") or []
    alerts = ctx.get("alerts") or []

    inj_rate = float(pat.get("injectionRate") or 0)
    inj_limit = float(pat.get("injectionLimit") or inj_rate * 1.2 or 1)
    headroom = inj_limit - inj_rate

    compressors = [f for f in facilities if "compress" in str(f.get("type","")).lower()]
    comp_health = "ok"
    if compressors:
        avg_health = sum(float(c.get("health", 100)) for c in compressors) / len(compressors)
        if avg_health < 80:
            comp_health = f"degraded (avg health {avg_health:.0f}%)"
        else:
            comp_health = f"ok (avg health {avg_health:.0f}%)"

    crit_alerts = [a for a in alerts if a.get("severity") in ("critical", "emergency") and not a.get("acknowledged")]

    lines = [
        f"Pattern {pat.get('id','?')} ops envelope:",
        f"  · injection {inj_rate:.0f} Mcf/d · permit limit {inj_limit:.0f} Mcf/d · headroom {headroom:.0f} Mcf/d",
        f"  · compressors: {comp_health}",
        f"  · unacknowledged critical alerts: {len(crit_alerts)}",
    ]
    if crit_alerts:
        for a in crit_alerts[:3]:
            lines.append(f"      ⚠️ {a.get('message','?')} [{a.get('source','?')}]")

    return {
        "id": "ops", "name": "Live Ops Constraints",
        "feature": "Lakebase Postgres · injection_limits + facility_health",
        "endpoint": "lakebase://co2_eor/injection_limits · facility_health",
        "ms": _ms(t0),
        "result": "\n".join(lines),
    }


SPECIALISTS = [
    specialist_reservoir,
    specialist_analogs,
    specialist_economics,
    specialist_compliance,
    specialist_ops,
]


# ─────── Synthesis ───────

SYNTHESIS_SYSTEM = (
    "You are the CO2-EOR Injection Supervisor. Five specialists have returned findings about "
    "where to place the next CO2 injection slug. Produce a 1-paragraph deployment recommendation "
    "(INJECT-PATTERN-A · INJECT-PATTERN-B · HOLD-INJECTION · DIVERT-TO-STORAGE), then a bulleted "
    "list of the 3 strongest supporting facts and 1 line on the top risk. Cite specific numbers "
    "(VRR, netback, headroom, 45Q $/d). Be terse and confident. No preamble, no apologies."
)


def _extract_verdict(rec_text: str) -> str:
    if not rec_text:
        return "REVIEW"
    upper = rec_text.upper()
    if "DIVERT-TO-STORAGE" in upper or "DIVERT TO STORAGE" in upper:
        return "DIVERT-TO-STORAGE"
    if "HOLD-INJECTION" in upper or "HOLD INJECTION" in upper or "HOLD" in upper.split():
        return "HOLD-INJECTION"
    if "INJECT-PATTERN-A" in upper or "PATTERN A" in upper:
        return "INJECT-PATTERN-A"
    if "INJECT-PATTERN-B" in upper or "PATTERN B" in upper:
        return "INJECT-PATTERN-B"
    if "INJECT" in upper:
        return "INJECT-PATTERN-A"
    return "REVIEW"


_LAST_DECISION: dict = {}


@router.get("/supervisor/last_decision")
async def last_decision():
    return _LAST_DECISION or {"empty": True}


async def synthesize(req: DecideReq, ctx: dict, specs: list[dict]) -> str:
    pat = ctx.get("pattern") or {}
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
        f"TARGET PATTERN: {pat.get('id','(none selected)')} · "
        f"oil ${req.oil_price:.0f}/bbl · CO2 ${req.co2_price:.0f}/tCO2\n\n"
        f"SPECIALIST FINDINGS:\n{pack}"
    )
    return await asyncio.to_thread(_claude_text, SYNTHESIS_SYSTEM, user, 600)


# ─────── SSE endpoint ───────

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

        pat = ctx.get("pattern") or {}
        yield _sse("start", {
            "question": req.question,
            "pattern_id": req.pattern_id,
            "pattern_name": pat.get("name"),
            "co2_price": req.co2_price,
            "oil_price": req.oil_price,
            "specialists": [
                {"id": "reservoir",  "name": "Reservoir State",            "feature": "Foundation Model API"},
                {"id": "analogs",    "name": "Analog EOR Pilots",          "feature": "Vector Search"},
                {"id": "economics",  "name": "Net-CO2 Economics",          "feature": "UC Functions"},
                {"id": "compliance", "name": "45Q + Class VI Compliance",  "feature": "UC Tags"},
                {"id": "ops",        "name": "Live Ops Constraints",       "feature": "Lakebase"},
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
            "pattern_id": req.pattern_id,
            "pattern_name": pat.get("name"),
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
        "name": "CO2-EOR Injection Supervisor",
        "model": MODEL_ENDPOINT,
        "specialists": [
            {"id": "reservoir",  "name": "Reservoir State Analyst",     "feature": "Foundation Model API", "endpoint": MODEL_ENDPOINT,                              "desc": "Claude reasons over per-pattern mass-balance, VRR and breakthrough flags."},
            {"id": "analogs",    "name": "Analog EOR Pilot Retrieval",  "feature": "Vector Search",        "endpoint": f"{VS_ENDPOINT} · {VS_INDEX}",               "desc": "Top-k similar CO2 floods (SACROC, Weyburn, Wasson, Bell Creek) via semantic search."},
            {"id": "economics",  "name": "Net-CO2 Economics",           "feature": "UC Functions",         "endpoint": f"{CATALOG}.{SCHEMA}.fn_co2_eor_npv (stub)",  "desc": "Net-CO2 NPV, ±$10/bbl sensitivity, 45Q credit value per day."},
            {"id": "compliance", "name": "45Q + Class VI Compliance",   "feature": "UC Tags",              "endpoint": "gov.45q_eligibility · class_vi_permits",    "desc": "Audit-readiness gate: compliance score, methane leaks, flaring vs cap, permit status."},
            {"id": "ops",        "name": "Live Ops Constraints",        "feature": "Lakebase",             "endpoint": "injection_limits · facility_health",        "desc": "Injection headroom vs permit, compressor health, unacknowledged critical alerts."},
        ],
        "verdicts": ["INJECT-PATTERN-A", "INJECT-PATTERN-B", "HOLD-INJECTION", "DIVERT-TO-STORAGE"],
    }
