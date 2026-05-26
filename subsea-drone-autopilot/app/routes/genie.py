"""Genie Conversation API proxy for Subsea Drone Autopilot.

Scoped to the demo's Genie Space (env: GENIE_SPACE_ID) covering the subsea
fleet's gold tables in Unity Catalog (drone_status, inspections, assets,
inspection_frames, autopilot_decisions, etc.).

Endpoints:
  POST /genie/ask         — blocking JSON response (used by supervisor specialists)
  POST /genie/ask_stream  — SSE stream with status updates, used by GenieSidebar
  GET  /genie/space       — Space metadata for the UI
"""
from __future__ import annotations

import asyncio
import collections
import json
import os
import time
import traceback
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "")


class GenieReq(BaseModel):
    question: str
    conversation_id: str | None = None


def _client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def _safe(obj, attr, default=None):
    """Safe attribute access. The Databricks SDK's response objects have a
    custom __getattr__ that raises KeyError (not AttributeError) for missing
    fields, which defeats the default arg in built-in getattr(). Wrap both."""
    if obj is None:
        return default
    try:
        v = getattr(obj, attr)
        return v if v is not None else default
    except (AttributeError, KeyError):
        return default


def _msg_id_of(obj) -> str | None:
    for attr in ("message_id", "id"):
        v = _safe(obj, attr)
        if v:
            return str(v)
    if isinstance(obj, dict):
        return obj.get("message_id") or obj.get("id")
    return None


def _conv_id_of(obj, fallback: str | None) -> str | None:
    v = _safe(obj, "conversation_id")
    if v:
        return str(v)
    if isinstance(obj, dict):
        return obj.get("conversation_id") or fallback
    return fallback


_CACHE: "collections.OrderedDict[str, tuple[float, dict]]" = collections.OrderedDict()
_CACHE_TTL_S = 90
_CACHE_MAX = 32


def _cache_get(question: str):
    key = question.strip().lower()
    e = _CACHE.get(key)
    if e and time.time() - e[0] < _CACHE_TTL_S:
        _CACHE.move_to_end(key)
        return e[1]
    return None


def _cache_set(question: str, val: dict):
    key = question.strip().lower()
    _CACHE[key] = (time.time(), val)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


POLL_SCHEDULE = [0.35] * 6 + [0.7] * 8 + [1.2] * 10 + [2.0] * 15


def _terminal(status: str) -> bool:
    s = (status or "").upper()
    return "COMPLETED" in s or "FAILED" in s or "CANCELLED" in s


def _ask_sync(question: str, conversation_id: str | None, status_cb=None):
    """Tight-polling Genie call. Uses _and_wait helpers if available (SDK>=0.34),
    else falls back to manual polling for SDK 0.30 compat."""
    if not GENIE_SPACE_ID:
        return {"error": "GENIE_SPACE_ID not configured."}

    cached = _cache_get(question) if not conversation_id else None
    if cached:
        if status_cb:
            status_cb({"stage": "cached", "msg": "Returning cached answer"})
        return dict(cached)

    w = _client()
    g = w.genie

    if status_cb:
        status_cb({"stage": "submitting", "msg": "Submitting question to Genie"})

    # Use _and_wait helpers if SDK supports them; otherwise fall through to manual polling
    has_wait = hasattr(g, "start_conversation_and_wait") and hasattr(g, "create_message_and_wait")
    if has_wait:
        if conversation_id:
            m = g.create_message_and_wait(space_id=GENIE_SPACE_ID, conversation_id=conversation_id, content=question)
            conv_id = _conv_id_of(m, conversation_id)
        else:
            m = g.start_conversation_and_wait(space_id=GENIE_SPACE_ID, content=question)
            conv_id = _conv_id_of(m, None)
        msg_id = _msg_id_of(m)
        final = m
    else:
        # Manual polling — works on SDK 0.30+
        if conversation_id:
            resp = g.create_message(space_id=GENIE_SPACE_ID, conversation_id=conversation_id, content=question)
            conv_id = _conv_id_of(resp, conversation_id)
        else:
            resp = g.start_conversation(space_id=GENIE_SPACE_ID, content=question)
            conv_id = _conv_id_of(resp, None)
        msg_id = _msg_id_of(resp)
        if not conv_id or not msg_id:
            raise RuntimeError(f"Genie did not return ids: conv={conv_id} msg={msg_id}")

        final, last_status = None, ""
        for delay in POLL_SCHEDULE:
            m = g.get_message(space_id=GENIE_SPACE_ID, conversation_id=conv_id, message_id=msg_id)
            final = m
            status = str(getattr(m, "status", "") or "").upper()
            if status and status != last_status:
                last_status = status
                if status_cb:
                    status_cb({"stage": status.lower(), "msg": _friendly_stage(status)})
            if _terminal(status):
                break
            time.sleep(delay)

    if status_cb:
        status_cb({"stage": "shaping", "msg": "Formatting result"})

    shaped = _shape(conv_id, msg_id, final, w)
    if not conversation_id and (shaped.get("rows") or shaped.get("sql") or (shaped.get("text") and shaped["text"] != "(Genie returned no text)")):
        _cache_set(question, shaped)
    return shaped


def _friendly_stage(status: str) -> str:
    s = status.upper()
    if "FETCH" in s or "EXECUT" in s or "QUERY" in s: return "Running SQL on the warehouse"
    if "GEN" in s or "WRIT" in s: return "Writing SQL"
    if "PROC" in s or "WAIT" in s or "RUN" in s or "PEND" in s or "SUBMIT" in s: return "Genie is thinking"
    if "COMPLETED" in s: return "Done"
    if "FAILED" in s: return "Genie reported failure"
    if "CANCEL" in s: return "Cancelled"
    return status.lower().replace("_", " ") or "thinking"


def _shape(conv_id, msg_id, m, w):
    text, sql, rows, cols = "", None, [], []
    if m is None:
        return {"conversation_id": conv_id, "message_id": msg_id, "text": "(no response)", "sql": None, "columns": [], "rows": []}

    top_content = _safe(m, "content")
    if top_content and isinstance(top_content, str):
        text = top_content

    for att in (_safe(m, "attachments") or []):
        att_text = _safe(att, "text")
        if att_text and _safe(att_text, "content"):
            text = att_text.content
        att_query = _safe(att, "query")
        if att_query:
            sql = _safe(att_query, "query") or sql
            try:
                res = w.genie.get_message_query_result(
                    space_id=GENIE_SPACE_ID, conversation_id=conv_id, message_id=msg_id,
                )
                sr = _safe(res, "statement_response")
                if sr:
                    manifest = _safe(sr, "manifest")
                    schema = _safe(manifest, "schema") if manifest else None
                    if schema:
                        cols = [c.name for c in (_safe(schema, "columns") or [])]
                    result = _safe(sr, "result")
                    rows = (_safe(result, "data_array") or []) if result else []
            except Exception as e:
                print(f"Genie query result fetch failed: {e}")

    return {
        "conversation_id": conv_id, "message_id": msg_id,
        "text": text or "(Genie returned no text)",
        "sql": sql, "columns": cols, "rows": rows[:200],
    }


@router.post("/genie/ask")
async def ask(req: GenieReq):
    try:
        return await asyncio.to_thread(_ask_sync, req.question, req.conversation_id)
    except Exception as e:
        print(f"Genie error: {e}\n{traceback.format_exc()[-600:]}")
        return {"error": str(e)}


def _sse(event: str, data) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@router.post("/genie/ask_stream")
async def ask_stream(req: GenieReq):
    async def gen():
        t0 = time.time()
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def push_status(d: dict):
            loop.call_soon_threadsafe(queue.put_nowait, ("status", {**d, "elapsed_ms": round((time.time() - t0) * 1000)}))

        async def runner():
            try:
                shaped = await asyncio.to_thread(_ask_sync, req.question, req.conversation_id, push_status)
                await queue.put(("answer", shaped))
            except Exception as e:
                print(f"Genie stream error: {e}\n{traceback.format_exc()[-600:]}")
                await queue.put(("answer", {"error": str(e)}))
            finally:
                await queue.put(("done", {"total_ms": round((time.time() - t0) * 1000)}))

        task = asyncio.create_task(runner())
        yield _sse("start", {"question": req.question})
        try:
            while True:
                ev, payload = await queue.get()
                yield _sse(ev, payload)
                if ev == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@router.get("/genie/space")
async def space_info():
    return {
        "space_id": GENIE_SPACE_ID,
        "configured": bool(GENIE_SPACE_ID),
        "name": "Subsea Drone Autopilot — Fleet & Inspections Genie",
        "cache_entries": len(_CACHE),
    }
