"""
Shared LLM client for all agents.
Uses WorkspaceClient for OAuth inside Databricks Apps,
falls back to httpx with token for local development.
"""

import json
import logging
from typing import Generator

import httpx
from config import CLAUDE_MODEL

logger = logging.getLogger(__name__)

# ── Client initialization ───────────────────────────────────

_client = None

def _get_client():
    """Get HTTP client — tries WorkspaceClient OAuth first, falls back to env token."""
    global _client
    if _client is not None:
        return _client

    try:
        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()
        host = ws.config.host.rstrip("/")
        token = ws.config.token

        _client = {
            "base_url": host,
            "headers": {"Authorization": f"Bearer {token}"},
            "source": "workspace_client",
        }
        logger.info(f"LLM client initialized via WorkspaceClient → {host}")
    except Exception as e:
        logger.warning(f"WorkspaceClient failed ({e}), falling back to env vars")
        from config import DATABRICKS_HOST, DATABRICKS_TOKEN
        _client = {
            "base_url": DATABRICKS_HOST,
            "headers": {"Authorization": f"Bearer {DATABRICKS_TOKEN}"},
            "source": "env_vars",
        }

    return _client


def _refresh_token():
    """Refresh token if using WorkspaceClient (OAuth tokens expire)."""
    global _client
    try:
        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()
        _client["headers"]["Authorization"] = f"Bearer {ws.config.token}"
    except Exception:
        pass


# ── LLM Call ────────────────────────────────────────────────

def call_llm(messages: list, tools: list | None = None, max_tokens: int = 4096) -> dict:
    """Single LLM call via Databricks SDK serving endpoint client."""
    from databricks.sdk import WorkspaceClient

    body = {
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools

    try:
        ws = WorkspaceClient()
        # Use SDK's do() method for raw API calls with proper auth
        import io
        response = ws.api_client.do(
            "POST",
            f"/serving-endpoints/{CLAUDE_MODEL}/invocations",
            body=body,
        )
        result = response
    except Exception as e1:
        # Fallback: manual token extraction
        try:
            logger.info(f"SDK do() failed ({e1}), trying manual token")
            ws = WorkspaceClient()
            token = ws.config.token
            host = ws.config.host.rstrip("/")
            c = httpx.Client(base_url=host, headers={"Authorization": f"Bearer {token}"}, timeout=120)
            r = c.post(f"/serving-endpoints/{CLAUDE_MODEL}/invocations", json=body)
            r.raise_for_status()
            result = r.json()
        except Exception as e2:
            logger.error(f"LLM call failed both methods: {e1} | {e2}")
            raise

    if "choices" not in result:
        logger.error(f"LLM response missing 'choices': {json.dumps(result)[:300]}")
        raise ValueError(f"Invalid LLM response: {json.dumps(result)[:200]}")

    return result


# ── Agent Loop ──────────────────────────────────────────────

def run_agent_loop(
    system_prompt: str,
    user_prompt: str,
    tools_schema: list,
    tool_executor: callable,
    max_iterations: int = 10,
    max_tokens: int = 4096,
) -> dict:
    """Run a full agent loop synchronously. Returns final parsed JSON."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(max_iterations):
        try:
            resp = call_llm(messages, tools_schema, max_tokens)
        except Exception as e:
            return {"status": "error", "summary": f"LLM call failed: {str(e)[:200]}"}

        choice = resp["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                try:
                    result = tool_executor(fn["name"], json.loads(fn["arguments"]))
                except Exception as e:
                    result = json.dumps({"error": f"Tool failed: {str(e)[:100]}"})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            content = msg.get("content", "")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"status": "error", "summary": content}

    return {"status": "error", "summary": "Max iterations exceeded."}


def run_agent_loop_stream(
    system_prompt: str,
    user_prompt: str,
    tools_schema: list,
    tool_executor: callable,
    max_iterations: int = 10,
    max_tokens: int = 4096,
) -> Generator[dict, None, None]:
    """Run agent loop with streaming status events."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for iteration in range(max_iterations):
        yield {"event": "status", "data": {"message": f"Agent step {iteration + 1}…"}}

        try:
            resp = call_llm(messages, tools_schema, max_tokens)
        except Exception as e:
            logger.error(f"Agent LLM call failed: {e}")
            yield {"event": "final", "data": {"status": "error", "summary": f"LLM call failed: {str(e)[:200]}"}}
            return

        choice = resp["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                tool_name = fn["name"]
                yield {"event": "status", "data": {"message": f"Calling {tool_name}…"}}
                try:
                    result = tool_executor(tool_name, json.loads(fn["arguments"]))
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
                    result = json.dumps({"error": f"Tool failed: {str(e)[:100]}"})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            content = msg.get("content", "")
            try:
                final = json.loads(content)
            except json.JSONDecodeError:
                final = {"answer": content, "summary": content, "sources": [], "confidence": "medium", "follow_up_suggestions": []}
            yield {"event": "final", "data": final}
            return

    yield {"event": "final", "data": {"status": "error", "summary": "Max iterations exceeded."}}
