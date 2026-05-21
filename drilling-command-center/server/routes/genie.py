"""Genie Conversation API proxy.

Two endpoints:
  POST /genie/ask         — blocking JSON response (compatibility / supervisor)
  POST /genie/ask_stream  — SSE stream with status updates, used by the UI
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

GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "01f13f7f8e201dc3bbf806bdba354f39")


class GenieReq(BaseModel):
    question: str
    conversation_id: str | None = None


def _client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def _msg_id_of(obj) -> str | None:
    """SDK shape varies between start_conversation (flat .message_id) and
    create_message (returns a GenieMessage with .id)."""
    for attr in ("message_id", "id"):
        v = getattr(obj, attr, None)
        if v:
            return str(v)
    if isinstance(obj, dict):
        return obj.get("message_id") or obj.get("id")
    return None


def _conv_id_of(obj, fallback: str | None) -> str | None:
    v = getattr(obj, "conversation_id", None)
    if v:
        return str(v)
    if isinstance(obj, dict):
        return obj.get("conversation_id") or fallback
    return fallback


# ─── Result cache ─────────────────────────────────────────────────────────────
# Keyed by question text (per-process). Speeds up demo flows where the same
# question is asked twice (e.g. operator clicks a sample chip, then the
# Decision Supervisor fires the same NL question from a specialist).
_CACHE: "collections.OrderedDict[str, tuple[float, dict]]" = collections.OrderedDict()
_CACHE_TTL_S = 90
_CACHE_MAX = 32


def _cache_key(question: str) -> str:
    return question.strip().lower()


def _cache_get(question: str):
    key = _cache_key(question)
    e = _CACHE.get(key)
    if e and time.time() - e[0] < _CACHE_TTL_S:
        _CACHE.move_to_end(key)
        return e[1]
    return None


def _cache_set(question: str, val: dict):
    key = _cache_key(question)
    _CACHE[key] = (time.time(), val)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


# ─── Polling with adaptive backoff ────────────────────────────────────────────
# Genie typically answers in 4-15s. Tight early polling wakes us within 0.4s
# of completion at the most common latencies, then backs off so we don't
# hammer the API for long-running queries.
POLL_SCHEDULE = [0.35] * 6 + [0.7] * 8 + [1.2] * 10 + [2.0] * 15  # ~50s total


def _terminal(status: str) -> bool:
    s = (status or "").upper()
    return "COMPLETED" in s or "FAILED" in s or "CANCELLED" in s


def _ask_sync(question: str, conversation_id: str | None, status_cb=None):
    cached = _cache_get(question) if not conversation_id else None
    if cached:
        if status_cb:
            status_cb({"stage": "cached", "msg": "Returning cached answer"})
        # Return cached but copy so callers can't mutate the cache
        return dict(cached)

    w = _client()
    g = w.genie

    if status_cb:
        status_cb({"stage": "submitting", "msg": "Submitting question to Genie"})

    if conversation_id:
        resp = g.create_message(
            space_id=GENIE_SPACE_ID,
            conversation_id=conversation_id,
            content=question,
        )
        conv_id = _conv_id_of(resp, conversation_id)
    else:
        resp = g.start_conversation(
            space_id=GENIE_SPACE_ID,
            content=question,
        )
        conv_id = _conv_id_of(resp, None)

    msg_id = _msg_id_of(resp)
    if not conv_id or not msg_id:
        raise RuntimeError(f"Genie did not return ids: conv={conv_id} msg={msg_id} obj={resp!r}")

    # Poll with adaptive backoff
    final = None
    last_status = ""
    for delay in POLL_SCHEDULE:
        m = g.get_message(
            space_id=GENIE_SPACE_ID,
            conversation_id=conv_id,
            message_id=msg_id,
        )
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
    # Only cache fresh conversations with real content
    if not conversation_id and (shaped.get("rows") or shaped.get("sql") or (shaped.get("text") and shaped["text"] != "(Genie returned no text)")):
        _cache_set(question, shaped)
    return shaped


def _friendly_stage(status: str) -> str:
    s = status.upper()
    if "FETCH" in s or "EXECUT" in s or "QUERY" in s:
        return "Running SQL on the warehouse"
    if "GEN" in s or "WRIT" in s:
        return "Writing SQL"
    if "PROC" in s or "WAIT" in s or "RUN" in s or "PEND" in s or "SUBMIT" in s:
        return "Genie is thinking"
    if "COMPLETED" in s:
        return "Done"
    if "FAILED" in s:
        return "Genie reported failure"
    if "CANCEL" in s:
        return "Cancelled"
    return status.lower().replace("_", " ") or "thinking"


def _shape(conv_id, msg_id, m, w):
    text = ""
    sql = None
    rows: list = []
    cols: list[str] = []
    if m is None:
        return {"conversation_id": conv_id, "message_id": msg_id, "text": "(no response)", "sql": None, "columns": [], "rows": []}

    top_content = getattr(m, "content", None)
    if top_content and isinstance(top_content, str):
        text = top_content

    for att in (getattr(m, "attachments", None) or []):
        att_text = getattr(att, "text", None)
        if att_text:
            c = getattr(att_text, "content", None)
            if c:
                text = c

        att_query = getattr(att, "query", None)
        if att_query:
            sql = getattr(att_query, "query", None) or sql
            try:
                res = w.genie.get_message_query_result(
                    space_id=GENIE_SPACE_ID,
                    conversation_id=conv_id,
                    message_id=msg_id,
                )
                sr = getattr(res, "statement_response", None)
                if sr:
                    manifest = getattr(sr, "manifest", None)
                    schema = getattr(manifest, "schema", None) if manifest else None
                    if schema:
                        cols = [c.name for c in (getattr(schema, "columns", None) or [])]
                    result = getattr(sr, "result", None)
                    data = getattr(result, "data_array", None) if result else None
                    rows = data or []
            except Exception as e:
                print(f"Genie query result fetch failed: {e}")

    return {
        "conversation_id": conv_id,
        "message_id":      msg_id,
        "text":            text or "(Genie returned no text)",
        "sql":             sql,
        "columns":         cols,
        "rows":            rows[:200],
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

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
    """SSE stream with status updates while Genie thinks. Final 'answer' event
    carries the full shaped response."""
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
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@router.get("/genie/space")
async def space_info():
    return {
        "space_id": GENIE_SPACE_ID,
        "url": f"https://adb-4173618801742158.18.azuredatabricks.net/genie/rooms/{GENIE_SPACE_ID}",
        "name": "Drilling Command Center — ADME Live",
        "cache_entries": len(_CACHE),
    }
