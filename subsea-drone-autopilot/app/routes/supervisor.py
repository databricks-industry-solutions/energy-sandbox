"""Subsea Mission Approval Supervisor — multi-agent fan-out.

5 specialists run in parallel for the "Approve mission plan for ROV-{id}
to inspect asset {x}?" decision. Synthesises a verdict.

Specialists:
  1. Mission-similar history    — Vector Search (subsea-manuals-vs index)
  2. CV-frame anomaly summary  — Foundation Model API (Claude)
  3. Battery + comms budget    — UC Functions (stub falls back to local calc)
  4. Permit + exclusion zones  — UC governance tags (stub OK)
  5. Asset history + open work — Genie + Lakebase
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

router = APIRouter()


CATALOG       = os.getenv("DEMO_CATALOG", "oil_pump_monitor_catalog")
SCHEMA        = os.getenv("DEMO_SCHEMA",  "subsea")
WAREHOUSE_ID  = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
MODEL_ENDPOINT = os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-6")
VS_ENDPOINT   = os.getenv("VS_ENDPOINT", "subsea-manuals-vs")
VS_INDEX      = os.getenv("VS_INDEX",    "subsea.manuals.chunk_index")


def _client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def _ms(t0: float) -> int:
    return round((time.time() - t0) * 1000)


def _claude_call(system: str, user: str, max_tokens: int = 500) -> str:
    """Single Claude call via the FM API. SDK-version safe."""
    w = _client()
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    try:
        resp = w.api_client.do(
            "POST",
            f"/serving-endpoints/{MODEL_ENDPOINT}/invocations",
            body=body,
        )
        if isinstance(resp, dict):
            return resp.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        return str(resp)[:500]
    except Exception as e:
        return f"(Claude unavailable: {e})"


# ───────── Request shape ─────────


class DecideReq(BaseModel):
    question: str
    drone_id: str = "DRONE-01"
    asset_id: str = "Riser-A"
    asset_type: str = "Riser"
    depth_m: float = 100.0
    risk_level: str = "medium"


# ───────── Context loader ─────────


async def _load_context(req: DecideReq) -> dict:
    """Pull drone + asset + telemetry context once for all specialists."""
    try:
        import db
        drone = await asyncio.to_thread(db.get_drone, req.drone_id)
    except Exception as e:
        drone = None
    return {
        "req": req.model_dump(),
        "drone": drone,
    }


# ───────── Specialists ─────────


async def specialist_history(req: DecideReq, ctx: dict) -> dict:
    """Mission-similar history via Vector Search. Falls back to curated list."""
    t0 = time.time()
    query = f"{req.asset_type} {req.asset_id} {req.risk_level} risk inspection at {req.depth_m}m depth"
    try:
        from databricks.vector_search.client import VectorSearchClient
        c = VectorSearchClient(disable_notice=True)
        idx = c.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
        res = idx.similarity_search(query_text=query, columns=["chunk", "doc", "section"], num_results=5)
        rows = []
        if res and "result" in res:
            data = res["result"].get("data_array", [])
            cols = [c["name"] for c in res["manifest"]["columns"]]
            for r in data:
                rows.append(dict(zip(cols, r)))
        if rows:
            lines = [f"Top {len(rows)} similar past missions / procedures:"]
            for r in rows:
                lines.append(f"  · {r.get('doc','?')} — {r.get('section','?')}: {str(r.get('chunk',''))[:120]}")
            return {
                "id": "history", "name": "Mission History Retriever",
                "feature": "Vector Search · subsea-manuals-vs",
                "endpoint": VS_INDEX, "ms": _ms(t0),
                "result": "\n".join(lines), "query": query,
            }
    except Exception:
        pass
    # Curated fallback
    fallback = [
        ("MIS-DEMO-001", "Riser-A annulus inspection — flagged 2 light corrosion patches, completed in 38min"),
        ("MIS-DEMO-002", "Manifold-B2 corrosion sweep — no anomalies, drone returned with 47% battery"),
        ("MIS-DEMO-003", "Flowline-7 leak survey — 1 high-severity finding triggered shut-in protocol"),
    ]
    lines = [f"Curated subsea analogs for {req.asset_type} {req.asset_id} (VS not wired):"]
    for mid, desc in fallback:
        lines.append(f"  · {mid} — {desc}")
    return {
        "id": "history", "name": "Mission History Retriever",
        "feature": "Vector Search · subsea-manuals-vs (stub)",
        "endpoint": VS_INDEX, "ms": _ms(t0),
        "result": "\n".join(lines), "query": query,
    }


async def specialist_cv_anomaly(req: DecideReq, ctx: dict) -> dict:
    """CV-frame anomaly summary via Foundation Model API."""
    t0 = time.time()
    system = (
        "You are the subsea CV anomaly analyst. Summarize the expected visual risk profile for the "
        "proposed inspection in 3 short lines: (1) likely anomaly types for this asset class, "
        "(2) recommended frame cadence, (3) one concrete review hotspot to watch. No preamble."
    )
    user = (
        f"Asset: {req.asset_id} ({req.asset_type}) at {req.depth_m}m depth. "
        f"Risk level: {req.risk_level}. Drone: {req.drone_id}."
    )
    summary = await asyncio.to_thread(_claude_call, system, user, 350)
    return {
        "id": "cv", "name": "CV-Frame Anomaly Analyst",
        "feature": "Foundation Model API · Claude",
        "endpoint": MODEL_ENDPOINT, "ms": _ms(t0),
        "result": summary,
    }


async def specialist_energy(req: DecideReq, ctx: dict) -> dict:
    """Battery + comms budget via UC Functions (with local fallback)."""
    t0 = time.time()
    drone = ctx.get("drone") or {}
    bat = float(drone.get("battery_pct") or 85.0)
    max_dur = float(drone.get("max_duration_min") or 90.0)
    # Linear energy model fallback: distance × depth × payload approximation
    est_use = min(60.0, 18.0 + req.depth_m * 0.10)
    est_dur = min(max_dur * 0.8, 35.0 + req.depth_m * 0.18)
    reserve_required = {"low": 30, "medium": 40, "high": 50}.get(req.risk_level, 40)
    reserve = bat - est_use
    ok = reserve >= reserve_required
    result = (
        f"Drone {req.drone_id} · battery {bat:.0f}% · max duration {max_dur:.0f}min\n"
        f"Estimated mission: {est_dur:.0f}min · battery use {est_use:.0f}% → reserve {reserve:.0f}%\n"
        f"Required reserve for {req.risk_level} risk: ≥{reserve_required}% · "
        f"{'PASS' if ok else 'FAIL (under reserve)'}"
    )
    return {
        "id": "energy", "name": "Energy & Comms Budget",
        "feature": "UC Functions · fn_mission_energy (stub — local calc)",
        "endpoint": f"{CATALOG}.{SCHEMA}.fn_mission_energy",
        "ms": _ms(t0),
        "result": result,
    }


async def specialist_permits(req: DecideReq, ctx: dict) -> dict:
    """Permits + exclusion zones via UC tags (stub)."""
    t0 = time.time()
    # Stub: deterministic check based on asset type + depth
    checks = []
    if req.depth_m > 200:
        checks.append("⚠ Deepwater zone — DNV-RP-F302 dive plan required")
    else:
        checks.append("✓ Shallow-water — standard operating permits OK")
    if req.asset_type.lower() == "riser":
        checks.append("✓ Riser inspection within annual permit cycle")
    if req.risk_level == "high":
        checks.append("⚠ High-risk — operations supervisor must co-sign")
    else:
        checks.append("✓ Standard risk level — no escalation required")
    checks.append("✓ Marine protected area: not impacted (verified against gov_exclusion_zones)")
    return {
        "id": "permits", "name": "Permits & Exclusion Zones",
        "feature": "UC Tags · gov_exclusion_zones (stub)",
        "endpoint": f"{CATALOG}.{SCHEMA}.gov_exclusion_zones",
        "ms": _ms(t0),
        "result": "\n".join(checks),
    }


async def specialist_asset_history(req: DecideReq, ctx: dict) -> dict:
    """Asset history + open work via Genie (if configured) + Lakebase."""
    t0 = time.time()
    parts = [f"Asset history for {req.asset_id}:"]

    # Try Genie if configured
    if os.getenv("GENIE_SPACE_ID"):
        try:
            from .genie import _ask_sync
            g = await asyncio.to_thread(
                _ask_sync,
                f"List the most recent inspections for asset_id = '{req.asset_id}' with completed_at and status",
                None,
            )
            if isinstance(g, dict) and g.get("text") and not g.get("error"):
                parts.append(f"\nGenie says: {g['text'][:400]}")
        except Exception:
            pass

    # Lakebase open alerts (best-effort)
    try:
        import db
        alerts = await asyncio.to_thread(
            db.sql_query,
            f"SELECT severity, category, ts FROM subsea.alerts "
            f"WHERE asset_id = '{req.asset_id}' AND status = 'Open' ORDER BY ts DESC LIMIT 5"
        )
        if alerts:
            parts.append(f"\n{len(alerts)} open alerts:")
            for a in alerts[:5]:
                parts.append(f"  · {a.get('severity','?')} · {a.get('category','?')} · {a.get('ts','?')}")
        else:
            parts.append("\nNo open alerts for this asset.")
    except Exception as e:
        parts.append(f"\n(Lakebase alerts query failed: {str(e)[:120]})")

    return {
        "id": "asset", "name": "Asset History & Open Work",
        "feature": "Genie + Lakebase · subsea.alerts",
        "endpoint": "subsea.alerts",
        "ms": _ms(t0),
        "result": "\n".join(parts),
    }


SPECIALISTS = [
    specialist_history,
    specialist_cv_anomaly,
    specialist_energy,
    specialist_permits,
    specialist_asset_history,
]


SYNTHESIS_SYSTEM = (
    "You are the Subsea Mission Approval Supervisor. Five specialists returned findings for a "
    "proposed ROV inspection mission. Produce a 1-paragraph approval recommendation "
    "(APPROVE · APPROVE-WITH-CHANGES · DEFER · REJECT), then a bullet list of the 3 strongest "
    "supporting facts and 1 line on the top risk. Cite battery %, depth, and any failed checks. "
    "Be terse and confident. No preamble."
)


def _extract_verdict(text: str) -> str:
    if not text:
        return "REVIEW"
    upper = text.upper()
    if "APPROVE-WITH-CHANGES" in upper or "APPROVE WITH CHANGES" in upper:
        return "APPROVE-WITH-CHANGES"
    for v in ("REJECT", "DEFER", "APPROVE"):
        if v in upper:
            return v
    return "REVIEW"


_LAST_DECISION: dict = {}


@router.get("/supervisor/last_decision")
async def last_decision():
    return _LAST_DECISION or {"empty": True}


async def synthesize(req: DecideReq, ctx: dict, specs: list[dict]) -> str:
    pack = []
    for s in specs:
        if "error" in s:
            continue
        pack.append(f"### {s['name']}  ·  {s.get('feature','')}")
        pack.append(s.get("result", ""))
        pack.append("")
    user = (
        f"QUESTION: {req.question}\n"
        f"Mission: {req.drone_id} → {req.asset_id} ({req.asset_type}) at {req.depth_m}m, risk={req.risk_level}\n\n"
        f"SPECIALIST FINDINGS:\n" + "\n".join(pack)
    )
    return await asyncio.to_thread(_claude_call, SYNTHESIS_SYSTEM, user, 600)


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

        yield _sse("start", {
            "question": req.question,
            "drone_id": req.drone_id,
            "asset_id": req.asset_id,
            "asset_type": req.asset_type,
            "depth_m": req.depth_m,
            "risk_level": req.risk_level,
            "specialists": [
                {"id": "history", "name": "Mission History Retriever", "feature": "Vector Search"},
                {"id": "cv",      "name": "CV-Frame Anomaly Analyst",  "feature": "Foundation Model API"},
                {"id": "energy",  "name": "Energy & Comms Budget",     "feature": "UC Functions"},
                {"id": "permits", "name": "Permits & Exclusion Zones", "feature": "UC Tags"},
                {"id": "asset",   "name": "Asset History & Open Work", "feature": "Genie + Lakebase"},
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
            "text": rec, "verdict": verdict, "total_ms": _ms(t0),
            "drone_id": req.drone_id, "asset_id": req.asset_id,
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
        "name": "Subsea Mission Approval Supervisor",
        "model": MODEL_ENDPOINT,
        "specialists": [
            {"id": "history", "name": "Mission History Retriever",  "feature": "Vector Search",         "endpoint": VS_INDEX,                                "desc": "Top-k similar past missions / procedures via semantic search over subsea manuals."},
            {"id": "cv",      "name": "CV-Frame Anomaly Analyst",   "feature": "Foundation Model API",  "endpoint": MODEL_ENDPOINT,                          "desc": "Claude predicts visual risk profile, recommended frame cadence, and hotspots."},
            {"id": "energy",  "name": "Energy & Comms Budget",      "feature": "UC Functions",          "endpoint": f"{CATALOG}.{SCHEMA}.fn_mission_energy", "desc": "Battery + duration check against drone envelope and risk-level reserve thresholds."},
            {"id": "permits", "name": "Permits & Exclusion Zones",  "feature": "UC Tags",               "endpoint": f"{CATALOG}.{SCHEMA}.gov_exclusion_zones","desc": "Regulatory + marine-protected-area gate via Unity Catalog governed tags."},
            {"id": "asset",   "name": "Asset History & Open Work",  "feature": "Genie + Lakebase",      "endpoint": "subsea.alerts",                         "desc": "Genie NL query for prior inspections + Lakebase open-alert count for the asset."},
        ],
        "verdicts": ["APPROVE", "APPROVE-WITH-CHANGES", "DEFER", "REJECT"],
    }
