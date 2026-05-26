"""Genie chat panel for Streamlit demos.

Floating bottom-right button → opens a centered modal dialog with chat.
Streamlit equivalent of the React GenieSidebar floater.

Usage in your Streamlit app:

    from genie_panel import render_genie_floater
    render_genie_floater(
        sample_questions=["Q1?", "Q2?"],
        title="Ask Genie",
    )

That's it — the function injects the floating button CSS, holds chat state in
session_state, and opens the dialog when clicked.
"""
from __future__ import annotations

import os
import time
import streamlit as st


GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "")


def _client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def _shape_message(conv_id, msg_id, m, w):
    """Compose answer = Genie NL text + first 15 result rows as markdown table.

    Most analytical questions get a brief 'here are the results' text from
    Genie with the data in a query attachment. Without rendering the rows
    inline, the user sees a meaningless one-liner. We fold the table into the
    text so the message itself is a complete answer.
    """
    text = ""
    cols: list[str] = []
    rows: list = []
    if m is None:
        return {"conversation_id": conv_id, "message_id": msg_id, "text": "(no response)"}
    top = _safe(m, "content")
    if top and isinstance(top, str):
        text = top
    for att in (_safe(m, "attachments") or []):
        att_text = _safe(att, "text")
        if att_text and _safe(att_text, "content"):
            text = att_text.content
        att_query = _safe(att, "query")
        if att_query:
            try:
                res = w.genie.get_message_query_result(
                    space_id=GENIE_SPACE_ID, conversation_id=conv_id, message_id=msg_id,
                )
                sr = _safe(res, "statement_response")
                if sr:
                    manifest = _safe(sr, "manifest")
                    schema = _safe(manifest, "schema")
                    if schema:
                        cols = [c.name for c in (_safe(schema, "columns") or [])]
                    result = _safe(sr, "result")
                    rows = (_safe(result, "data_array") or []) if result else []
            except Exception:
                pass

    parts = []
    if text and text != "(Genie returned no text)":
        parts.append(text)
    if rows and cols:
        md = ["", "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for r in rows[:15]:
            md.append("| " + " | ".join("" if v is None else str(v)[:60] for v in r) + " |")
        if len(rows) > 15:
            md.append(f"_… {len(rows) - 15} more rows_")
        parts.append("\n".join(md))
    if not parts:
        parts.append("(Genie didn't return a usable answer — try rephrasing more specifically.)")
    return {
        "conversation_id": conv_id,
        "message_id": msg_id,
        "text": "\n\n".join(parts),
    }


_POLL_DELAYS = [0.4, 0.4, 0.7, 0.7, 1.2, 1.2, 1.8, 2.5, 3.0, 3.0, 3.0, 3.0, 3.0]
_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


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


def _status_str(m) -> str:
    s = _safe(m, "status")
    if s is None:
        return ""
    return str(s).rsplit(".", 1)[-1].upper()


def _poll_until_terminal(w, conv_id: str, msg_id: str):
    """Poll get_message until status is terminal."""
    last = w.genie.get_message(space_id=GENIE_SPACE_ID, conversation_id=conv_id, message_id=msg_id)
    for d in _POLL_DELAYS:
        if _status_str(last) in _TERMINAL:
            break
        time.sleep(d)
        last = w.genie.get_message(space_id=GENIE_SPACE_ID, conversation_id=conv_id, message_id=msg_id)
    return last


def _ask_genie(question: str, conversation_id: str | None = None) -> dict:
    """Start or continue a Genie conversation, poll explicitly, then shape the result."""
    w = _client()
    g = w.genie
    if conversation_id:
        m = g.create_message(space_id=GENIE_SPACE_ID, conversation_id=conversation_id, content=question)
        conv_id = conversation_id
        msg_id = _safe(m, "id") or _safe(m, "message_id")
    else:
        r = g.start_conversation(space_id=GENIE_SPACE_ID, content=question)
        conv_id = _safe(r, "conversation_id")
        msg_id = _safe(r, "message_id")
        if not msg_id:
            inner = _safe(r, "message")
            msg_id = _safe(inner, "message_id") or _safe(inner, "id")
    if not (conv_id and msg_id):
        return {"text": f"_(Genie returned no ids: conv={conv_id} msg={msg_id})_"}
    final = _poll_until_terminal(w, conv_id, msg_id)
    return _shape_message(conv_id, msg_id, final, w)


_FLOATER_CSS = """
<style>
/* Floating button — last secondary button with key=genie_floater becomes the floater */
div[data-testid="stApp"] button[kind="secondary"][data-genie-floater="true"],
button[data-testid="stBaseButton-secondary"][data-genie-floater="true"] {
    position: fixed !important;
    bottom: 24px !important;
    right: 24px !important;
    z-index: 999 !important;
    width: 56px !important;
    height: 56px !important;
    border-radius: 28px !important;
    background: linear-gradient(135deg, #00E5FF, #4dabf7) !important;
    color: #0d0e11 !important;
    border: none !important;
    box-shadow: 0 4px 24px rgba(0, 229, 255, 0.4) !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    padding: 0 !important;
    cursor: pointer !important;
    transition: transform 0.15s !important;
}
div[data-testid="stApp"] button[kind="secondary"][data-genie-floater="true"]:hover,
button[data-testid="stBaseButton-secondary"][data-genie-floater="true"]:hover {
    transform: scale(1.06) !important;
}
/* Fall back: target the button container by st.button key — works on Streamlit 1.30+ */
div[data-testid="stApp"] div[data-testid="element-container"]:has(> div > button[data-testid="stBaseButton-secondary"][title="genie-floater-marker"]),
div[data-testid="stApp"] div:has(> button:contains("✨ Ask Genie")) {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 999;
    width: 56px;
}
</style>
<script>
// Tag the Ask Genie button so the CSS above targets it specifically
(function() {
  function tag() {
    const btns = window.parent ? window.parent.document.querySelectorAll('button') : document.querySelectorAll('button');
    btns.forEach(b => {
      if (b.textContent && b.textContent.trim() === '✨ Ask Genie' && !b.dataset.genieFloater) {
        b.dataset.genieFloater = 'true';
        b.style.position = 'fixed';
        b.style.bottom = '24px';
        b.style.right = '24px';
        b.style.zIndex = '999';
        b.style.width = '56px';
        b.style.height = '56px';
        b.style.borderRadius = '28px';
        b.style.background = 'linear-gradient(135deg, #00E5FF, #4dabf7)';
        b.style.color = '#0d0e11';
        b.style.border = 'none';
        b.style.boxShadow = '0 4px 24px rgba(0, 229, 255, 0.4)';
        b.style.fontSize = '22px';
        b.style.fontWeight = '700';
        b.style.padding = '0';
        b.style.cursor = 'pointer';
      }
    });
  }
  tag();
  // Re-tag on every Streamlit re-render (Streamlit re-renders trigger DOM mutations)
  const obs = new MutationObserver(tag);
  obs.observe((window.parent || window).document.body, {childList: true, subtree: true});
})();
</script>
"""


def _render_chat_body(sample_questions: list[str] | None):
    """Render the chat history + input. Used inside st.dialog."""
    if not GENIE_SPACE_ID:
        st.error("`GENIE_SPACE_ID` not configured. Set it in app.yaml env.")
        return

    # Sample question chips (only show if no history yet)
    if sample_questions and not st.session_state.genie_msgs:
        st.caption("Try one of these:")
        cols = st.columns(min(len(sample_questions), 2))
        for i, q in enumerate(sample_questions):
            if cols[i % len(cols)].button(q, key=f"gq_{hash(q)}", use_container_width=True):
                st.session_state.genie_pending = q
                st.rerun()

    # Chat history
    for m in st.session_state.genie_msgs:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            if m["role"] == "user":
                st.write(m["text"])
            else:
                if m.get("error"):
                    st.error(m["error"])
                elif m.get("text"):
                    st.write(m["text"])

    # Input — chat_input must be at the top-level inside the dialog
    pending = st.session_state.pop("genie_pending", None)
    question = pending or st.chat_input("Ask a question…", key="genie_chat_input")

    if question and GENIE_SPACE_ID:
        st.session_state.genie_msgs.append({"role": "user", "text": question})
        with st.spinner("Genie is thinking…"):
            try:
                shaped = _ask_genie(question, st.session_state.genie_conv)
                st.session_state.genie_conv = shaped.get("conversation_id")
                st.session_state.genie_msgs.append({
                    "role": "genie",
                    "text": shaped.get("text"),
                })
            except Exception as e:
                err = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                st.session_state.genie_msgs.append({"role": "genie", "error": err})
        st.rerun()


def render_genie_floater(sample_questions: list[str] | None = None, title: str = "Ask Genie"):
    """Render the floating Genie chat button. Click to open chat dialog.

    Call this ONCE at the bottom of your main app — outside any st.fragment so
    state survives reruns.
    """
    if "genie_msgs" not in st.session_state:
        st.session_state.genie_msgs = []
    if "genie_conv" not in st.session_state:
        st.session_state.genie_conv = None

    # Inject CSS + JS to make the button float
    st.markdown(_FLOATER_CSS, unsafe_allow_html=True)

    # Define the dialog using Streamlit's @st.dialog (requires Streamlit 1.35+)
    @st.dialog(f"✨ {title} · Genie", width="large")
    def _genie_dialog():
        _render_chat_body(sample_questions)
        if st.button("Clear conversation", key="genie_clear"):
            st.session_state.genie_msgs = []
            st.session_state.genie_conv = None
            st.rerun()

    # Floating trigger button (JS in _FLOATER_CSS will position+style it)
    if st.button("✨ Ask Genie", key="genie_floater_btn", help="Ask Genie about the demo data"):
        _genie_dialog()


# Back-compat alias — old code that calls render_genie_sidebar() still works
def render_genie_sidebar(sample_questions: list[str] | None = None, title: str = "Ask Genie"):
    """DEPRECATED — use render_genie_floater(). Kept for backward compat."""
    render_genie_floater(sample_questions=sample_questions, title=title)


# Public — call Genie programmatically from inside any tab. Returns shaped dict
# {conversation_id, text, sql, columns, rows, error?}. Use this when you want
# Genie to power a custom UI (e.g., the existing ESP Advisor chat tab).
def ask_genie(question: str, conversation_id: str | None = None) -> dict:
    """Ask Genie a single question. Returns shaped result or {error: '...'} on failure."""
    if not GENIE_SPACE_ID:
        return {"error": "GENIE_SPACE_ID not configured. Set it in app.yaml env."}
    try:
        return _ask_genie(question, conversation_id)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Surface type + repr + last frame so we can see where it broke
        msg = f"{type(e).__name__}: {e!r}\n\n```\n{tb[-1500:]}\n```"
        return {"error": msg}
