"""
app/ui.py  — ESP PM-quality ROP Drilling & SAP ERP Dashboard
──────────────────────────────────────────────────────────────
Tabs
  ⚡ Drilling Command  — fleet overview, live KPIs, well cards
  🔬 Well Diagnostics  — single-well gauges, metrics, trends
  📊 Deep Analytics    — LAS 4-track, scatter, hazard, drift
  🚨 Live Alerts       — severity-filtered alert stream
  🔧 SAP ERP           — work orders, BOM, procurement, contracts
  🤖 Drilling Agent    — Claude auto-analysis + chat
  🗺️ Data & AI Flow    — architecture SVG diagram

Design  : ESP PM dark — #0B0F1A base, #00D4FF cyan accent
Refresh : @st.fragment(run_every=3) for live tabs
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as _components
from sqlalchemy import text

from app.config import config
from app.db import get_engine, health_check
from app.simulator import simulate_all_wells
from app.sap_drilling import (
    get_work_orders, get_equipment_bom, get_procurement,
    get_vendor_contracts, get_notifications, get_sap_kpis,
)

# ── ESP PM colour palette ──────────────────────────────────
BG       = "#0B0F1A"
PANEL    = "#0f172a"
CARD     = "#1C2333"
TRACK_BG = "#0D1321"
BORDER   = "#1e293b"
TEXT     = "#e2e8f0"
MUTED    = "#64748b"
MONO     = "JetBrains Mono, Consolas, monospace"
CYAN     = "#00D4FF"
GREEN    = "#22c55e"
YELLOW   = "#eab308"
RED      = "#ef4444"
ORANGE   = "#F97316"
PURPLE   = "#8B5CF6"
AMBER    = "#ffa940"
TEAL     = "#36cfc9"

SEV_COLOR = {"CRITICAL": RED, "WARNING": YELLOW, "INFO": GREEN}
HAZ_COLOR = {
    "NORMAL": GREEN, "OPTIMAL": CYAN,
    "INEFFICIENT_DRILLING": YELLOW, "HIGH_MSE": ORANGE, "STUCK_PIPE": RED,
}
STATUS_COLOR = {
    "DRILLING": GREEN, "TRIPPING": YELLOW,
    "CIRCULATING": CYAN, "CONNECTION": AMBER,
}

# ── Plotly base ────────────────────────────────────────────
_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=TRACK_BG,
    font=dict(family=MONO, size=10, color=TEXT),
    margin=dict(l=54, r=14, t=30, b=36),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, showgrid=True),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, showgrid=True),
    hoverlabel=dict(bgcolor=CARD, font_size=10, font_family=MONO),
)

def _legend(**kw) -> dict:
    base = dict(bgcolor="rgba(10,14,26,0.9)", bordercolor=BORDER,
                font=dict(size=9, family=MONO), orientation="h",
                yanchor="bottom", y=1.02)
    base.update(kw)
    return base

def _layout(*, legend_kw=None, strip=(), **extra):
    base = {k: v for k, v in _BASE.items() if k not in strip}
    result = {**base, **extra}
    if legend_kw is not None:
        result["legend"] = _legend(**legend_kw)
    return result

def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper",
                       x=.5, y=.5, showarrow=False,
                       font=dict(color=MUTED, size=12, family=MONO))
    fig.update_layout(**_layout())
    return fig

# ═══════════════════════════════════════════════════════════
# HTML HELPERS (ESP PM patterns)
# ═══════════════════════════════════════════════════════════

def _kpi(label, value, sub="", color=TEXT):
    return (f'<div class="kpi-card">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="color:{color};">{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')

def _badge(label, color):
    return (f'<span style="background:{color}22;border:1px solid {color}55;'
            f'border-radius:20px;padding:2px 9px;font-size:10px;'
            f'font-weight:700;color:{color};font-family:{MONO};">{label}</span>')

def _section(title, sub=""):
    st.markdown(
        f'<div class="section-head"><span class="section-title">{title}</span>'
        f'<span class="section-sub">{sub}</span></div>',
        unsafe_allow_html=True)

def _mtile(label, value, unit="", color=TEXT):
    return (f'<div style="background:{PANEL};border:1px solid {BORDER};'
            f'border-radius:8px;padding:10px 12px;text-align:center;">'
            f'<div style="font-size:9px;color:{MUTED};letter-spacing:.06em;'
            f'text-transform:uppercase;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:20px;font-weight:700;color:{color};'
            f'font-family:{MONO};">{value}'
            f'<span style="font-size:11px;color:{MUTED};font-weight:400;">'
            f' {unit}</span></div></div>')


# ═══════════════════════════════════════════════════════════
# DATA LAYER (Lakebase queries — kept from original)
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=config.auto_refresh_sec, show_spinner=False)
def load_wells() -> list[str]:
    try:
        with get_engine().connect() as conn:
            rows = conn.execute(text("SELECT well_id FROM wells ORDER BY well_id")).fetchall()
        return [r[0] for r in rows] or list(config.known_wells)
    except Exception:
        return list(config.known_wells)

@st.cache_data(ttl=config.auto_refresh_sec, show_spinner=False)
def load_predictions(well_id: str, window_min: int) -> pd.DataFrame:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(text("""
                SELECT ts, md, rop_actual, rop_pred, rop_gap, mse, hazard_flag
                FROM predictions WHERE well_id = :wid AND ts >= :cutoff
                ORDER BY ts DESC LIMIT :lim
            """), conn, params={"wid": well_id, "cutoff": cutoff, "lim": config.page_size})
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.sort_values("ts").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["ts","md","rop_actual","rop_pred","rop_gap","mse","hazard_flag"])

@st.cache_data(ttl=config.auto_refresh_sec, show_spinner=False)
def load_alerts(well_id: str, window_min: int, unacked_only: bool = False) -> pd.DataFrame:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    q = ("SELECT id, well_id, ts, alert_type, severity, message, acknowledged "
         "FROM alerts WHERE well_id = :wid AND ts >= :cutoff")
    if unacked_only:
        q += " AND acknowledged = false"
    q += " ORDER BY ts DESC LIMIT 200"
    try:
        with get_engine().connect() as conn:
            df = pd.read_sql(text(q), conn, params={"wid": well_id, "cutoff": cutoff})
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df
    except Exception:
        return pd.DataFrame(columns=["id","well_id","ts","alert_type","severity","message","acknowledged"])

@st.cache_data(ttl=config.auto_refresh_sec, show_spinner=False)
def load_stats(well_id: str) -> dict:
    try:
        with get_engine().connect() as conn:
            row = conn.execute(text("""
                SELECT count(*) as total, max(ts) as last_ts,
                count(*) FILTER (WHERE ts >= NOW() - INTERVAL '1 minute') as rpm
                FROM predictions WHERE well_id = :wid
            """), {"wid": well_id}).fetchone()
            a_row = conn.execute(text(
                "SELECT count(*) FROM alerts WHERE well_id = :wid AND acknowledged = false"
            ), {"wid": well_id}).fetchone()
            eg_row = conn.execute(text("""
                SELECT avg(rop_gap) FROM predictions WHERE well_id = :wid
                AND ts >= NOW() - INTERVAL '60 minutes' AND ts < NOW() - INTERVAL '30 minutes'
            """), {"wid": well_id}).fetchone()
            lg_row = conn.execute(text("""
                SELECT avg(rop_gap) FROM predictions WHERE well_id = :wid
                AND ts >= NOW() - INTERVAL '30 minutes'
            """), {"wid": well_id}).fetchone()
        return {"total": row[0], "last_ts": row[1], "rpm": row[2],
                "alerts": a_row[0] if a_row else 0,
                "early_gap": eg_row[0] if eg_row else None,
                "late_gap": lg_row[0] if lg_row else None}
    except Exception:
        return {"total": 0, "last_ts": None, "rpm": 0, "alerts": 0,
                "early_gap": None, "late_gap": None}

@st.cache_data(ttl=300, show_spinner=False)
def load_models() -> pd.DataFrame:
    try:
        with get_engine().connect() as conn:
            return pd.read_sql(text(
                "SELECT version, stage, rmse, r2, registered_at "
                "FROM model_versions ORDER BY registered_at DESC LIMIT 5"
            ), conn)
    except Exception:
        return pd.DataFrame(columns=["version","stage","rmse","r2","registered_at"])

def ack_alert(alert_id: int) -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("UPDATE alerts SET acknowledged=true, acknowledged_at=NOW() WHERE id=:id"),
                         {"id": alert_id})
            conn.commit()
        return True
    except Exception:
        return False

def _age_badge(ts):
    if ts is None:
        return _badge("NO DATA", RED)
    try:
        age = (datetime.now(timezone.utc) - pd.to_datetime(ts, utc=True)).total_seconds()
        if age < 120:
            return _badge(f"{int(age)}s ago", GREEN)
        if age < 3600:
            return _badge(f"{int(age/60)}m ago", YELLOW)
        return _badge(f"{age/3600:.1f}h ago", RED)
    except Exception:
        return _badge("—", MUTED)

# ═══════════════════════════════════════════════════════════
# CLAUDE AI HELPER
# ═══════════════════════════════════════════════════════════

def _claude(messages: list[dict], max_tokens: int = 700) -> str:
    try:
        import os
        host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        token = os.environ.get("DATABRICKS_TOKEN", os.environ.get("DATABRICKS_API_TOKEN", ""))
        if not token:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            token = w.config.token
            host = f"https://{w.config.host}"
        import urllib.request, json
        model = os.environ.get("CLAUDE_MODEL", "databricks-claude-sonnet-4-5")
        body = json.dumps({"model": model, "max_tokens": max_tokens, "messages": messages}).encode()
        req = urllib.request.Request(f"{host}/serving-endpoints/{model}/invocations",
                                     data=body, headers={"Authorization": f"Bearer {token}",
                                                          "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("choices", [{}])[0].get("message", {}).get("content", "No response")
    except Exception as e:
        return f"AI unavailable: {e}"

def _snapshot(well_id: str, window_min: int) -> str:
    df = load_predictions(well_id, window_min)
    stats = load_stats(well_id)
    if df.empty:
        return f"Well: {well_id}\nWindow: {window_min}min\nNo data available."
    latest = df.iloc[-1]
    lines = [f"Well: {well_id}  |  Window: {window_min}min  |  Rows: {len(df)}",
             f"Latest: ROP={latest.get('rop_actual',0):.1f} ft/hr  Pred={latest.get('rop_pred',0):.1f}  "
             f"Gap={latest.get('rop_gap',0):.1f}  MSE={latest.get('mse',0):.0f}  "
             f"Hazard={latest.get('hazard_flag','?')}  MD={latest.get('md',0):.0f} ft",
             f"Avg ROP: {df.rop_actual.mean():.1f}  Max: {df.rop_actual.max():.1f}  "
             f"Avg MSE: {df.mse.mean():.0f}",
             f"Hazards: {df.hazard_flag.value_counts().to_dict()}",
             f"Alerts (unacked): {stats.get('alerts',0)}"]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# CHART BUILDERS (kept from original + new)
# ═══════════════════════════════════════════════════════════

def chart_rop(df: pd.DataFrame) -> go.Figure:
    if df.empty: return _empty_fig("Waiting for data…")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.ts, y=df.rop_actual, name="Actual",
                             mode="lines", line=dict(color=GREEN, width=2)))
    fig.add_trace(go.Scatter(x=df.ts, y=df.rop_pred, name="Predicted",
                             mode="lines", line=dict(color=CYAN, width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=pd.concat([df.ts, df.ts[::-1]]),
                             y=pd.concat([df.rop_pred, df.rop_actual[::-1]]),
                             fill="toself", fillcolor="rgba(0,212,255,0.06)",
                             line=dict(color="rgba(0,0,0,0)"), name="Gap", hoverinfo="skip"))
    fig.update_layout(**_layout(legend_kw={},
        title=dict(text="RATE OF PENETRATION  ft/hr", font_size=10, x=0,
                   font_color=MUTED, font_family=MONO), yaxis_title="ft/hr"))
    return fig

def chart_mse(df: pd.DataFrame) -> go.Figure:
    if df.empty: return _empty_fig("Waiting for data…")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.ts, y=df.mse, name="MSE", mode="lines",
                             fill="tozeroy", fillcolor="rgba(249,115,22,0.07)",
                             line=dict(color=ORANGE, width=1.8)))
    fig.add_hline(y=config.mse_high_threshold, line_dash="dash", line_color=RED, line_width=1,
                  annotation_text="HIGH", annotation_font_size=8, annotation_font_color=RED)
    fig.add_hline(y=config.mse_optimal_threshold, line_dash="dot", line_color=GREEN, line_width=1,
                  annotation_text="OPT", annotation_font_size=8, annotation_font_color=GREEN)
    fig.update_layout(**_layout(legend_kw={},
        title=dict(text="MECHANICAL SPECIFIC ENERGY  psi", font_size=10, x=0,
                   font_color=MUTED, font_family=MONO), yaxis_title="psi"))
    return fig

def chart_gap(df: pd.DataFrame) -> go.Figure:
    if df.empty: return _empty_fig("Waiting for data…")
    colors = [RED if v > config.rop_gap_threshold else (YELLOW if v > 0 else GREEN)
              for v in df.rop_gap.fillna(0)]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df.ts, y=df.rop_gap, name="ROP Gap", marker_color=colors, opacity=.85))
    fig.add_hline(y=config.rop_gap_threshold, line_dash="dash", line_color=RED, line_width=1)
    fig.update_layout(**_layout(legend_kw={},
        title=dict(text="ROP GAP  ft/hr", font_size=10, x=0,
                   font_color=MUTED, font_family=MONO), yaxis_title="ft/hr"))
    return fig

def chart_hazard_timeline(df: pd.DataFrame) -> go.Figure:
    if df.empty: return _empty_fig("No hazard data")
    fig = go.Figure()
    for flag, color in HAZ_COLOR.items():
        sub = df[df.hazard_flag == flag]
        if sub.empty: continue
        fig.add_trace(go.Scatter(x=sub.ts, y=[flag]*len(sub), mode="markers",
                                 marker=dict(color=color, size=8, symbol="square"), name=flag))
    fig.update_layout(**_layout(strip=("yaxis",), legend_kw={},
        title=dict(text="HAZARD TIMELINE", font_size=10, x=0, font_color=MUTED, font_family=MONO),
        yaxis=dict(type="category", categoryorder="array",
                   categoryarray=list(HAZ_COLOR.keys()), gridcolor=BORDER)))
    return fig

def chart_las_tracks(df: pd.DataFrame, well_id: str, window_min: int) -> go.Figure:
    if df.empty: return _empty_fig("No stream data — check replay producer")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[.30,.25,.20,.25],
                        subplot_titles=["ROP  ft/hr","MSE  psi","Gap  ft/hr","Hazard"])
    fig.add_trace(go.Scatter(x=df.ts, y=df.rop_actual, name="ROP Actual",
                             mode="lines", line=dict(color=GREEN, width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.ts, y=df.rop_pred, name="ROP Pred",
                             mode="lines", line=dict(color=CYAN, width=1.4, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.ts, y=df.mse, name="MSE", mode="lines", fill="tozeroy",
                             fillcolor="rgba(249,115,22,0.08)",
                             line=dict(color=ORANGE, width=1.5)), row=2, col=1)
    for y_val, col in [(config.mse_high_threshold, RED), (config.mse_optimal_threshold, GREEN)]:
        fig.add_shape(type="line", x0=df.ts.iloc[0], x1=df.ts.iloc[-1], y0=y_val, y1=y_val,
                      line=dict(color=col, width=1, dash="dash"), row=2, col=1)
    gap_c = [RED if v > config.rop_gap_threshold else (YELLOW if v > 0 else GREEN)
             for v in df.rop_gap.fillna(0)]
    fig.add_trace(go.Bar(x=df.ts, y=df.rop_gap, name="Gap",
                         marker_color=gap_c, opacity=.8), row=3, col=1)
    for flag, color in HAZ_COLOR.items():
        sub = df[df.hazard_flag == flag]
        if sub.empty: continue
        fig.add_trace(go.Scatter(x=sub.ts, y=[flag]*len(sub), mode="markers",
                                 marker=dict(color=color, size=9, symbol="square"),
                                 name=flag), row=4, col=1)
    base = {k: v for k, v in _BASE.items() if k not in ("xaxis", "yaxis")}
    fig.update_layout(**base, legend=_legend(orientation="v", x=1.01, y=1, yanchor="top", xanchor="left"),
                      height=660, title=dict(text=f"{well_id}  ·  LAS Track View  ·  last {window_min} min",
                                             font_size=11, x=0, font_color=MUTED, font_family=MONO))
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, showgrid=True)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, showgrid=True)
    fig.update_yaxes(type="category", categoryorder="array",
                     categoryarray=list(HAZ_COLOR.keys()), row=4, col=1)
    return fig

def chart_scatter(df: pd.DataFrame) -> go.Figure:
    valid = df.dropna(subset=["rop_actual","rop_pred"])
    if valid.empty: return _empty_fig("No scatter data")
    lo = min(valid.rop_actual.min(), valid.rop_pred.min())
    hi = max(valid.rop_actual.max(), valid.rop_pred.max())
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=valid.rop_actual, y=valid.rop_pred, mode="markers",
        marker=dict(color=valid.rop_gap.abs(), colorscale="RdYlGn_r", size=4, opacity=.7,
                    colorbar=dict(title="Gap", thickness=10)), name="Predictions"))
    fig.add_shape(type="line", x0=lo, y0=lo, x1=hi, y1=hi,
                  line=dict(color=CYAN, dash="dash", width=1))
    fig.update_layout(**_layout(legend_kw={},
        title=dict(text="ACTUAL vs PREDICTED ROP", font_size=10, x=0,
                   font_color=MUTED, font_family=MONO),
        xaxis_title="Actual ROP (ft/hr)", yaxis_title="Predicted ROP (ft/hr)"))
    return fig

def chart_gap_hist(df: pd.DataFrame) -> go.Figure:
    gaps = df.rop_gap.dropna()
    if gaps.empty: return _empty_fig("No gap data")
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=gaps, nbinsx=40, marker_color=CYAN, opacity=.75, name="Gap dist"))
    fig.add_vline(x=config.rop_gap_threshold, line_dash="dash", line_color=RED, line_width=1.5,
                  annotation_text="Hazard", annotation_font_size=8, annotation_font_color=RED)
    fig.update_layout(**_layout(legend_kw={},
        title=dict(text="ROP GAP DISTRIBUTION  ft/hr", font_size=10, x=0,
                   font_color=MUTED, font_family=MONO),
        xaxis_title="rop_pred − rop_actual", yaxis_title="Count"))
    return fig

def chart_haz_pie(df: pd.DataFrame, well_id: str, window_min: int) -> go.Figure:
    if df.empty: return _empty_fig("No data")
    haz = df.hazard_flag.value_counts().reset_index()
    haz.columns = ["flag","count"]
    fig = go.Figure(go.Pie(labels=haz["flag"], values=haz["count"], hole=.45,
                           marker_colors=[HAZ_COLOR.get(f, MUTED) for f in haz["flag"]],
                           textfont=dict(size=10, family=MONO)))
    fig.update_layout(**_layout(strip=("xaxis","yaxis"), legend_kw={"orientation":"h"},
        title=dict(text=f"HAZARD MIX  {well_id}  last {window_min}min",
                   font_size=10, x=0, font_color=MUTED, font_family=MONO)))
    return fig

def _rgba(hex_color, alpha=0.13):
    """Convert #RRGGBB to rgba() for Plotly compatibility."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _gauge(title, value, min_v, max_v, warn, crit, unit="", low_is_bad=False):
    if low_is_bad:
        steps = [dict(range=[min_v, warn], color=_rgba(RED)),
                 dict(range=[warn, crit], color=_rgba(YELLOW)),
                 dict(range=[crit, max_v], color=_rgba(GREEN))]
    else:
        steps = [dict(range=[min_v, warn], color=_rgba(GREEN)),
                 dict(range=[warn, crit], color=_rgba(YELLOW)),
                 dict(range=[crit, max_v], color=_rgba(RED))]
    fig = go.Figure(go.Indicator(mode="gauge+number", value=value,
        number=dict(font=dict(size=22, color=CYAN, family=MONO), suffix=f" {unit}"),
        title=dict(text=title, font=dict(size=10, color=MUTED, family=MONO)),
        gauge=dict(axis=dict(range=[min_v, max_v], tickcolor=MUTED, tickfont=dict(size=8)),
                   bar=dict(color=CYAN, thickness=0.3),
                   bgcolor=PANEL, borderwidth=0,
                   steps=steps,
                   threshold=dict(line=dict(color=RED, width=2), thickness=0.8, value=crit))))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=180,
                      margin=dict(l=20, r=20, t=40, b=10))
    return fig


# ═══════════════════════════════════════════════════════════
# CSS (ESP PM-quality dark theme)
# ═══════════════════════════════════════════════════════════

def _inject_css():
    st.markdown(f"""<style>
html, body, [class*="css"] {{ font-family: Inter, system-ui, sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 0.75rem; padding-bottom: 0.5rem; }}
section[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab-list"] {{
  gap: 2px; background: {PANEL}; border-radius: 8px; padding: 2px;
  border: 1px solid {BORDER};
}}
.stTabs [data-baseweb="tab"] {{
  background: transparent; color: {MUTED};
  font-size: 11px; font-weight: 500; border-radius: 6px; padding: 6px 14px;
}}
.stTabs [aria-selected="true"] {{
  background: {CARD} !important; color: {CYAN} !important;
  font-weight: 700; border: 1px solid {BORDER};
}}
.kpi-card {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
  padding: 14px 18px; flex: 1; min-width: 120px;
}}
.kpi-label {{
  font-size: 9px; color: {MUTED}; letter-spacing: 0.08em;
  font-family: {MONO}; text-transform: uppercase; margin-bottom: 5px;
}}
.kpi-value {{ font-size: 22px; font-weight: 700; font-family: {MONO}; }}
.kpi-sub {{ font-size: 10px; color: {MUTED}; margin-top: 2px; font-family: {MONO}; }}
.section-head {{
  display: flex; align-items: baseline; gap: 10px;
  border-bottom: 1px solid {BORDER}; padding-bottom: 6px; margin: 16px 0 10px;
}}
.section-title {{ font-size: 11px; font-weight: 700; color: {TEXT}; letter-spacing: 0.06em; }}
.section-sub {{ font-size: 10px; color: {MUTED}; }}
.alert-row {{
  background: {CARD}; border-radius: 6px; padding: 8px 14px; margin-bottom: 5px;
  border-left: 3px solid {BORDER};
}}
.alert-row-critical {{ border-left-color: {RED}; }}
.alert-row-warning {{ border-left-color: {YELLOW}; }}
.alert-row-info {{ border-left-color: {GREEN}; }}
@keyframes livepulse {{
  0%,100% {{ opacity:1; box-shadow:0 0 4px {GREEN}; }}
  50% {{ opacity:.4; box-shadow:0 0 10px {GREEN}; }}
}}
.live-dot {{
  width:8px; height:8px; border-radius:50%; background:{GREEN};
  display:inline-block; animation: livepulse 1.1s ease-in-out infinite;
}}
[data-testid="stMetricValue"] {{ font-family: {MONO}; color: {CYAN}; }}
hr {{ border-color: {BORDER}; margin: 10px 0; }}
.stButton button {{
  background: {CARD}; border: 1px solid {BORDER}; color: {TEXT};
  font-size: 11px; border-radius: 5px; padding: 5px 16px;
}}
.stButton button:hover {{ background: {CYAN}22; border-color: {CYAN}; color: {CYAN}; }}
</style>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# TAB 1 — DRILLING COMMAND (ESP PM Fleet Command style)
# ═══════════════════════════════════════════════════════════

def render_drilling_command(wells_data):
    n_drilling = sum(1 for w in wells_data if w["status"] == "DRILLING")
    avg_rop = sum(w["rop_actual"] for w in wells_data) / max(len(wells_data), 1)
    avg_mse = sum(w["mse"] for w in wells_data) / max(len(wells_data), 1)
    n_haz = sum(1 for w in wells_data if w["hazard_flag"] not in ("NORMAL", "OPTIMAL"))
    avg_eff = sum(w["efficiency"] for w in wells_data) / max(len(wells_data), 1)

    # KPI row
    st.markdown(
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;">'
        f'{_kpi("Active Wells", f"{n_drilling}/{len(wells_data)}", "Currently drilling", GREEN)}'
        f'{_kpi("Avg ROP", f"{avg_rop:.0f} ft/hr", "Fleet average", CYAN)}'
        f'{_kpi("Avg MSE", f"{avg_mse/1000:.0f}K psi", "Mechanical specific energy", ORANGE)}'
        f'{_kpi("Hazards", str(n_haz), "Non-normal wells", RED if n_haz else GREEN)}'
        f'{_kpi("Efficiency", f"{avg_eff:.0f}%", "Actual / Predicted", GREEN if avg_eff >= 80 else YELLOW)}'
        f'</div>', unsafe_allow_html=True)

    # Well cards
    cols = st.columns(2)
    for i, w in enumerate(wells_data):
        with cols[i % 2]:
            sc = STATUS_COLOR.get(w["status"], MUTED)
            hc = HAZ_COLOR.get(w["hazard_flag"], MUTED)
            eff = w["efficiency"]
            eff_col = GREEN if eff >= 80 else (YELLOW if eff >= 60 else RED)
            eff_w = min(max(eff, 0), 100)
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:12px;'
                f'padding:16px;margin-bottom:10px;border-top:3px solid {sc};">'
                # Header
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<span class="live-dot"></span>'
                f'<span style="font-size:16px;font-weight:700;color:{TEXT};">{w["well_id"]}</span>'
                f'<span style="font-size:10px;color:{MUTED};">{w["name"]}  ·  {w["field"]}</span>'
                f'</div>'
                f'{_badge(w["status"], sc)}'
                f'</div>'
                # Metrics grid
                f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px;">'
                + _mtile("ROP", f'{w["rop_actual"]:.0f}', "ft/hr", GREEN)
                + _mtile("MSE", f'{w["mse"]/1000:.0f}K', "psi", ORANGE)
                + _mtile("WOB", f'{w["wob"]:.0f}', "klbs", CYAN)
                + _mtile("RPM", f'{w["rpm"]:.0f}', "", PURPLE)
                + f'</div>'
                # Efficiency bar
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">'
                f'<span style="font-size:9px;color:{MUTED};font-family:{MONO};width:70px;">EFFICIENCY</span>'
                f'<div style="flex:1;height:6px;background:{BORDER};border-radius:3px;">'
                f'<div style="width:{eff_w}%;height:100%;background:{eff_col};border-radius:3px;"></div></div>'
                f'<span style="font-size:11px;color:{eff_col};font-family:{MONO};font-weight:700;">{eff:.0f}%</span>'
                f'</div>'
                # Hazard + depth
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'{_badge(w["hazard_flag"], hc)}'
                f'<span style="font-size:10px;color:{MUTED};font-family:{MONO};">'
                f'MD {w["md"]:.0f} ft  ·  TVD {w["tvd"]:.0f} ft</span>'
                f'</div>'
                f'</div>', unsafe_allow_html=True)

    # ROP comparison chart
    _section("ROP COMPARISON", "Both wells overlaid")
    fig = go.Figure()
    for w in wells_data:
        fig.add_trace(go.Indicator(mode="number+delta", value=w["rop_actual"],
            delta=dict(reference=w["rop_pred"], valueformat=".1f", relative=False),
            title=dict(text=w["well_id"], font=dict(size=11, color=MUTED)),
            number=dict(font=dict(size=24, color=GREEN), suffix=" ft/hr"),
            domain=dict(x=[wells_data.index(w)/len(wells_data),
                           (wells_data.index(w)+1)/len(wells_data)], y=[0,1])))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=100,
                      margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# TAB 2 — WELL DIAGNOSTICS (ESP PM Well Diagnostics style)
# ═══════════════════════════════════════════════════════════

def render_well_diagnostics(wells_data):
    well_ids = [w["well_id"] for w in wells_data]
    sel = st.selectbox("Select Well", well_ids, key="diag_well")
    w = next((x for x in wells_data if x["well_id"] == sel), wells_data[0])

    sc = STATUS_COLOR.get(w["status"], MUTED)
    hc = HAZ_COLOR.get(w["hazard_flag"], MUTED)

    # Header
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'background:{PANEL};border:1px solid {BORDER};border-radius:8px;'
        f'padding:10px 18px;margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<span class="live-dot"></span>'
        f'<span style="font-size:17px;font-weight:700;color:{TEXT};">{w["well_id"]}</span>'
        f'<span style="font-size:10px;color:{MUTED};font-family:{MONO};">'
        f'{w["name"]} · {w["field"]} · MD {w["md"]:.0f} ft</span></div>'
        f'<div style="display:flex;gap:8px;">'
        f'{_badge(w["status"], sc)} {_badge(w["hazard_flag"], hc)}</div>'
        f'</div>', unsafe_allow_html=True)

    # Metric tiles row
    tiles = (
        _mtile("ROP Actual", f'{w["rop_actual"]:.1f}', "ft/hr", GREEN)
        + _mtile("ROP Predicted", f'{w["rop_pred"]:.1f}', "ft/hr", CYAN)
        + _mtile("MSE", f'{w["mse"]/1000:.0f}K', "psi", ORANGE)
        + _mtile("WOB", f'{w["wob"]:.1f}', "klbs", CYAN)
        + _mtile("Torque", f'{w["torque"]:,.0f}', "ft-lbs", PURPLE)
        + _mtile("SPP", f'{w["spp"]:,.0f}', "psi", TEAL)
    )
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:14px;">'
        + tiles + '</div>', unsafe_allow_html=True)

    # Gauge row
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        st.plotly_chart(_gauge("ROP", w["rop_actual"], 0, 150, 60, 100, "ft/hr", low_is_bad=True),
                        use_container_width=True)
    with g2:
        st.plotly_chart(_gauge("MSE", w["mse"]/1000, 0, 200, 80, 150, "K psi"),
                        use_container_width=True)
    with g3:
        st.plotly_chart(_gauge("WOB", w["wob"], 0, 60, 30, 45, "klbs"),
                        use_container_width=True)
    with g4:
        st.plotly_chart(_gauge("RPM", w["rpm"], 0, 220, 140, 180, ""),
                        use_container_width=True)

    # Diagnostics assessment
    _section("DIAGNOSTICS ASSESSMENT")
    diags = []
    if w["hazard_flag"] == "HIGH_MSE":
        diags.append(("HIGH MSE DETECTED", "MSE exceeds efficient drilling threshold. Check bit condition, reduce WOB, or increase RPM.", RED))
    if w["hazard_flag"] == "STUCK_PIPE":
        diags.append(("STUCK PIPE RISK", "Low ROP with high torque detected. Initiate jarring sequence or circulate.", RED))
    if w["hazard_flag"] == "INEFFICIENT_DRILLING":
        diags.append(("INEFFICIENT DRILLING", "ROP gap exceeds threshold. Optimize drilling parameters — consider WOB/RPM adjustment.", YELLOW))
    if w["mse"] > config.mse_high_threshold:
        diags.append(("BIT WEAR", "MSE trending high — likely bit dulling. Schedule bit trip.", ORANGE))
    if w["rop_actual"] < 40:
        diags.append(("LOW ROP", f"ROP at {w['rop_actual']:.0f} ft/hr below target. Check formation change or bit condition.", YELLOW))
    if not diags:
        diags.append(("ALL CLEAR", "Drilling parameters within normal operating envelope.", GREEN))

    for title, desc, color in diags:
        st.markdown(
            f'<div style="background:{color}12;border:1px solid {color}44;'
            f'border-radius:6px;padding:10px 14px;margin-bottom:6px;">'
            f'<div style="font-size:11px;font-weight:700;color:{color};">{title}</div>'
            f'<div style="font-size:10px;color:{TEXT};margin-top:3px;">{desc}</div>'
            f'</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# TAB 3 — DEEP ANALYTICS (kept from original)
# ═══════════════════════════════════════════════════════════

def render_analytics():
    _WIN_OPTS = {"30 min": 30, "1 hr": 60, "4 hr": 240, "12 hr": 720,
                 "1 day": 1440, "3 days": 4320, "7 days": 10080}
    c1, c2 = st.columns([1, 3])
    with c1:
        an_well = st.selectbox("Well", load_wells(), key="an_well")
    with c2:
        an_win = _WIN_OPTS[st.selectbox("Window", list(_WIN_OPTS.keys()),
                                         index=len(_WIN_OPTS)-1, key="an_win")]

    stats = load_stats(an_well)
    df = load_predictions(an_well, an_win)

    # Pipeline status strip
    _section("PIPELINE STATUS", "MSEEL → Lakehouse → Streaming → Lakebase")
    nodes = [("MSEEL CSV","Source",MUTED,"MIP_3H/4H"),("Bronze","Raw Delta",ORANGE,"Append-only"),
             ("Silver","Cleaned+MSE",CYAN,"Teale formula"),("Gold","ML Features",GREEN,"label_rop"),
             ("Streaming","Spark UDF",CYAN,f"{stats.get('rpm',0)}/min"),
             ("Lakebase","Postgres",GREEN,f"{stats.get('total',0):,} rows")]
    arrow = f'<span style="color:{BORDER};font-size:18px;align-self:center;">→</span>'
    nodes_html = arrow.join(
        f'<div style="background:{CARD};border:1px solid {c}44;border-radius:6px;'
        f'padding:7px 14px;text-align:center;min-width:90px;">'
        f'<div style="font-size:9px;font-weight:700;color:{c};font-family:{MONO};">{n}</div>'
        f'<div style="font-size:8px;color:{MUTED};margin-top:1px;">{s}</div>'
        f'<div style="font-size:9px;color:{CYAN};margin-top:3px;font-family:{MONO};">{v}</div>'
        f'</div>' for n, s, c, v in nodes)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;background:{TRACK_BG};'
        f'border:1px solid {BORDER};border-radius:8px;padding:12px 16px;overflow-x:auto;">'
        + nodes_html + f'</div><div style="margin-top:8px;">{_age_badge(stats.get("last_ts"))}'
        f'<span style="font-size:10px;color:{MUTED};margin-left:12px;">'
        f'{stats.get("alerts",0)} alerts · {stats.get("total",0):,} predictions</span></div>',
        unsafe_allow_html=True)

    # 4-track LAS chart
    _section("LAS TRACK VIEW", f"{an_well} · last {an_win} min · live stream")
    st.plotly_chart(chart_las_tracks(df, an_well, an_win), use_container_width=True)

    # Scatter + Histogram
    _section("MODEL PERFORMANCE")
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(chart_scatter(df), use_container_width=True)
    with c2: st.plotly_chart(chart_gap_hist(df), use_container_width=True)

    # Hazard pie + model registry
    c3, c4 = st.columns([1.2, 0.8])
    with c3:
        st.plotly_chart(chart_haz_pie(df, an_well, an_win), use_container_width=True)
    with c4:
        _section("MODEL REGISTRY")
        mv = load_models()
        if mv.empty:
            st.info("No model versions yet.")
        else:
            for _, row in mv.head(5).iterrows():
                sc = GREEN if row.get("stage") == "Production" else MUTED
                rmse = f"{row['rmse']:.3f}" if pd.notna(row.get("rmse")) else "—"
                r2 = f"{row['r2']:.4f}" if pd.notna(row.get("r2")) else "—"
                st.markdown(
                    f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:5px;'
                    f'padding:8px 12px;margin-bottom:5px;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<span style="font-size:10px;color:{TEXT};">v{row["version"]}</span>'
                    f'<span style="font-size:9px;color:{sc};">{row.get("stage","—")}</span></div>'
                    f'<div style="font-size:9px;color:{MUTED};margin-top:3px;">'
                    f'RMSE <span style="color:{CYAN};">{rmse}</span>&nbsp;&nbsp;'
                    f'R² <span style="color:{CYAN};">{r2}</span></div></div>',
                    unsafe_allow_html=True)

    # Drift indicator
    eg, rg = stats.get("early_gap"), stats.get("late_gap")
    if eg is not None and rg is not None:
        drift = rg - eg
        dcol = RED if drift > 5 else (GREEN if drift < -2 else YELLOW)
        drift_lbl = "⚠ MODEL DRIFT DETECTED" if drift > 5 else ("✓ Stable" if drift < 2 else "→ Watch")
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;'
            f'padding:10px 16px;font-family:{MONO};font-size:10px;margin-top:8px;">'
            f'<span style="color:{MUTED};">ROP GAP DRIFT</span>'
            f' · early <span style="color:{CYAN};">{eg:.1f}</span>'
            f' → recent <span style="color:{CYAN};">{rg:.1f}</span>'
            f' ft/hr · drift <span style="color:{dcol};">{drift:+.1f} ft/hr  {drift_lbl}</span>'
            f'</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# TAB 4 — LIVE ALERTS (ESP PM style)
# ═══════════════════════════════════════════════════════════

def render_alerts():
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        well_id = st.selectbox("Well", load_wells(), key="alert_well")
    with c2:
        sev_filter = st.radio("Severity", ["All","CRITICAL","WARNING","INFO"],
                              horizontal=True, key="sev_filter")
    with c3:
        unacked = st.checkbox("Unacked only", value=True, key="alert_unacked")

    df_alts = load_alerts(well_id, 10080, unacked_only=unacked)
    if sev_filter != "All":
        df_alts = df_alts[df_alts.severity == sev_filter]

    # Stats
    total = len(df_alts)
    crit = len(df_alts[df_alts.severity == "CRITICAL"]) if not df_alts.empty else 0
    warn = len(df_alts[df_alts.severity == "WARNING"]) if not df_alts.empty else 0
    info = len(df_alts[df_alts.severity == "INFO"]) if not df_alts.empty else 0

    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:14px;">'
        f'{_kpi("Total", str(total), "Alerts in window", TEXT)}'
        f'{_kpi("Critical", str(crit), "", RED)}'
        f'{_kpi("Warning", str(warn), "", YELLOW)}'
        f'{_kpi("Info", str(info), "", GREEN)}'
        f'</div>', unsafe_allow_html=True)

    if df_alts.empty:
        st.markdown(f'<div style="color:{MUTED};font-size:11px;padding:20px;text-align:center;">'
                    f'No alerts matching filters.</div>', unsafe_allow_html=True)
    else:
        for _, row in df_alts.head(30).iterrows():
            sc = SEV_COLOR.get(str(row.get("severity","")), TEXT)
            ts_s = pd.to_datetime(row["ts"]).strftime("%H:%M:%S") if pd.notna(row.get("ts")) else "—"
            sev_c = str(row.get("severity","")).lower()
            st.markdown(
                f'<div class="alert-row alert-row-{sev_c}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div style="display:flex;gap:8px;align-items:center;">'
                f'{_badge(str(row.get("severity","")), sc)}'
                f'<span style="font-size:10px;font-weight:600;color:{TEXT};">'
                f'{row.get("alert_type","")}</span></div>'
                f'<span style="font-size:9px;color:{MUTED};font-family:{MONO};">{ts_s}</span>'
                f'</div>'
                f'<div style="font-size:9.5px;color:{MUTED};margin-top:4px;">'
                f'{str(row.get("message",""))[:200]}</div></div>',
                unsafe_allow_html=True)
            if not row["acknowledged"]:
                if st.button("ACK", key=f"ack_{row['id']}"):
                    if ack_alert(int(row["id"])):
                        st.cache_data.clear(); st.rerun()


# ═══════════════════════════════════════════════════════════
# TAB 5 — SAP ERP (NEW — ESP PM SAP Maintenance style)
# ═══════════════════════════════════════════════════════════

def render_sap_erp():
    kpis = get_sap_kpis()
    mat_val = f'${kpis["total_material_value"]:,.0f}'
    overdue_col = RED if kpis["overdue_wos"] else GREEN
    st.markdown(
        '<div style="display:flex;gap:10px;margin-bottom:14px;">'
        + _kpi("Open WOs", str(kpis["open_wos"]), "Work orders", AMBER)
        + _kpi("Overdue", str(kpis["overdue_wos"]), "", overdue_col)
        + _kpi("Material Value", mat_val, "Inventory", CYAN)
        + _kpi("Active Contracts", str(kpis["active_contracts"]), "Vendors", PURPLE)
        + _kpi("Pending POs", str(kpis["pending_pos"]), "Procurement", ORANGE)
        + '</div>', unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs(["Work Orders", "Equipment & BOM", "Procurement", "Contracts"])

    with t1:
        wos = get_work_orders()
        for wo in wos:
            s = wo["status"]
            sc = {
                "OPEN": AMBER, "IN_PROGRESS": CYAN, "COMPLETED": GREEN, "CLOSED": MUTED
            }.get(s, MUTED)
            pc = {1: RED, 2: ORANGE, 3: YELLOW, 4: GREEN}.get(wo.get("priority", 4), MUTED)
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                f'padding:12px 16px;margin-bottom:6px;border-left:3px solid {sc};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div style="display:flex;gap:8px;align-items:center;">'
                f'<span style="font-size:12px;font-weight:700;color:{TEXT};font-family:{MONO};">'
                f'{wo["wo_id"]}</span>'
                f'{_badge(s, sc)}'
                + _badge(f'P{wo.get("priority", "-")}', pc) +
                f'</div>'
                f'<span style="font-size:9px;color:{MUTED};font-family:{MONO};">'
                f'{wo.get("well_id","")}</span>'
                f'</div>'
                f'<div style="font-size:11px;color:{TEXT};margin-top:6px;">{wo["description"]}</div>'
                f'<div style="font-size:9px;color:{MUTED};margin-top:4px;font-family:{MONO};">'
                f'Type: {wo.get("wo_type","")} · Assigned: {wo.get("assigned_to","—")} · '
                f'Due: {wo.get("due_date","—")} · Est: ${wo.get("cost_estimate",0):,.0f}</div>'
                f'</div>', unsafe_allow_html=True)

    with t2:
        bom = get_equipment_bom()
        st.markdown(
            f'<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:11px;">'
            f'<tr style="background:{PANEL};border-bottom:1px solid {BORDER};">'
            f'<th style="padding:8px 12px;text-align:left;color:{MUTED};font-size:9px;letter-spacing:.05em;">MATERIAL ID</th>'
            f'<th style="padding:8px 12px;text-align:left;color:{MUTED};font-size:9px;">DESCRIPTION</th>'
            f'<th style="padding:8px;text-align:center;color:{MUTED};font-size:9px;">STOCK</th>'
            f'<th style="padding:8px;text-align:center;color:{MUTED};font-size:9px;">MIN</th>'
            f'<th style="padding:8px;text-align:right;color:{MUTED};font-size:9px;">UNIT COST</th>'
            f'<th style="padding:8px;text-align:center;color:{MUTED};font-size:9px;">CONDITION</th>'
            f'</tr>', unsafe_allow_html=True)
        rows_html = ""
        for item in bom:
            cond = item.get("condition", "GOOD")
            cc = {"NEW": GREEN, "GOOD": GREEN, "FAIR": YELLOW, "REPLACE": RED}.get(cond, MUTED)
            stock = item.get("stock_qty", 0)
            min_s = item.get("min_stock", 0)
            stk_c = RED if stock <= min_s else (YELLOW if stock <= min_s * 1.5 else GREEN)
            rows_html += (
                f'<tr style="border-bottom:1px solid {BORDER}22;">'
                f'<td style="padding:7px 12px;font-family:{MONO};color:{CYAN};font-size:10px;">'
                f'{item["material_id"]}</td>'
                f'<td style="padding:7px 12px;color:{TEXT};">{item["description"]}</td>'
                f'<td style="padding:7px 8px;text-align:center;color:{stk_c};font-family:{MONO};font-weight:700;">'
                f'{stock}</td>'
                f'<td style="padding:7px 8px;text-align:center;color:{MUTED};font-family:{MONO};">{min_s}</td>'
                f'<td style="padding:7px 8px;text-align:right;color:{TEXT};font-family:{MONO};">'
                f'${item.get("unit_cost",0):,.0f}</td>'
                f'<td style="padding:7px 8px;text-align:center;">{_badge(cond, cc)}</td>'
                f'</tr>')
        st.markdown(rows_html + '</table></div>', unsafe_allow_html=True)

    with t3:
        pos = get_procurement()
        for po in pos:
            ps = po.get("status", "")
            pc = {"ORDERED": AMBER, "IN_TRANSIT": CYAN, "DELIVERED": GREEN, "INVOICED": MUTED}.get(ps, MUTED)
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                f'padding:12px 16px;margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><span style="font-size:12px;font-weight:700;color:{TEXT};font-family:{MONO};">'
                f'{po["po_id"]}</span>'
                f'<span style="font-size:10px;color:{MUTED};margin-left:10px;">{po["vendor"]}</span></div>'
                f'{_badge(ps, pc)}'
                f'</div>'
                f'<div style="font-size:10px;color:{TEXT};margin-top:6px;">'
                f'{po.get("material_desc","")} × {po.get("qty",0)}</div>'
                f'<div style="font-size:9px;color:{MUTED};margin-top:4px;font-family:{MONO};">'
                f'Total: ${po.get("total",0):,.0f} · ETA: {po.get("eta","—")} · '
                f'{po.get("delivery_location","")}</div>'
                f'</div>', unsafe_allow_html=True)

    with t4:
        contracts = get_vendor_contracts()
        for c in contracts:
            cs = c.get("status", "")
            cc = {"ACTIVE": GREEN, "PENDING": AMBER, "EXPIRED": RED}.get(cs, MUTED)
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
                f'padding:12px 16px;margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><span style="font-size:12px;font-weight:700;color:{TEXT};font-family:{MONO};">'
                f'{c["contract_id"]}</span>'
                f'<span style="font-size:10px;color:{MUTED};margin-left:10px;">{c["vendor"]}</span></div>'
                f'{_badge(cs, cc)}'
                f'</div>'
                f'<div style="font-size:11px;color:{TEXT};margin-top:6px;">{c["service"]}</div>'
                f'<div style="font-size:9px;color:{MUTED};margin-top:4px;font-family:{MONO};">'
                f'{c.get("start_date","")} → {c.get("end_date","")} · '
                f'${c.get("daily_rate",0):,.0f}/day · Total ${c.get("total_value",0):,.0f}</div>'
                f'</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# TAB 6 — DRILLING AGENT (ESP PM Advisor style)
# ═══════════════════════════════════════════════════════════

def render_agent():
    c1, c2 = st.columns([1, 3])
    with c1:
        ag_well = st.selectbox("Well", load_wells(), key="ag_well")
    with c2:
        _AG_OPTS = {"30 min": 30, "1 hr": 60, "4 hr": 240, "12 hr": 720,
                    "1 day": 1440, "7 days": 10080}
        ag_win = _AG_OPTS[st.selectbox("Window", list(_AG_OPTS.keys()),
                                        index=len(_AG_OPTS)-1, key="ag_win")]

    ctx = _snapshot(ag_well, ag_win)
    cache_key = f"ai_{ag_well}_{ag_win}"
    if cache_key not in st.session_state:
        with st.spinner("AI agent analysing drilling conditions…"):
            st.session_state[cache_key] = _claude([
                {"role": "system", "content":
                 "You are a senior drilling engineer AI assistant specialising in "
                 "ROP optimisation and hazard detection. Analyse the real-time data "
                 "and provide: (1) one-line status, (2) 3-4 bullet findings, "
                 "(3) 2-3 actionable recommendations. Be quantitative."},
                {"role": "user", "content": f"Analyse this live snapshot:\n\n{ctx}"},
            ], max_tokens=700)

    df_live = load_predictions(ag_well, ag_win)
    cur_flag = df_live.iloc[-1].get("hazard_flag", "NORMAL") if not df_live.empty else "NORMAL"
    flag_col = HAZ_COLOR.get(cur_flag, MUTED)

    if cur_flag not in ("NORMAL", "OPTIMAL"):
        st.markdown(
            f'<div style="background:{flag_col}18;border:1px solid {flag_col}66;'
            f'border-radius:8px;padding:12px 18px;margin-bottom:12px;">'
            f'<span style="font-size:13px;font-weight:700;color:{flag_col};">'
            f'⚠ HAZARD DETECTED — {cur_flag}</span>'
            f'<div style="font-size:10px;color:{TEXT};margin-top:4px;">'
            f'Immediate review recommended.</div></div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1])

    with col_left:
        # Agent header (ESP PM style)
        st.markdown(
            f'<div style="background:{PANEL};border:1px solid {BORDER};border-radius:12px;'
            f'padding:12px 16px;margin-bottom:12px;">'
            f'<div style="display:flex;align-items:center;gap:12px;">'
            f'<div style="width:36px;height:36px;background:#1e1b3a;'
            f'border:1.5px solid {PURPLE};border-radius:50%;display:flex;'
            f'align-items:center;justify-content:center;font-size:18px;">🤖</div>'
            f'<div><div style="font-size:13px;font-weight:700;color:{TEXT};">'
            f'Drilling AI Agent</div>'
            f'<div style="font-size:10px;color:{MUTED};">Claude Sonnet · ROP Optimization</div>'
            f'</div></div></div>', unsafe_allow_html=True)

        if st.button("↺ Re-analyse", key="reanalyse"):
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            st.rerun()

        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:8px;'
            f'padding:16px 18px;font-size:11px;color:{TEXT};line-height:1.8;'
            f'white-space:pre-wrap;min-height:160px;">'
            f'{st.session_state.get(cache_key, "Analysing…")}</div>',
            unsafe_allow_html=True)

    with col_right:
        st.markdown(f'<div style="font-size:11px;color:{MUTED};font-family:{MONO};'
                    f'letter-spacing:.07em;margin-bottom:8px;">CHAT WITH AGENT</div>',
                    unsafe_allow_html=True)

        if "chat_msgs" not in st.session_state:
            st.session_state.chat_msgs = []

        for m in st.session_state.chat_msgs[-16:]:
            rc = CYAN if m["role"] == "assistant" else GREEN
            rl = "AGENT" if m["role"] == "assistant" else "YOU"
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};'
                f'border-radius:6px;padding:8px 12px;margin-bottom:5px;">'
                f'<div style="font-size:8px;color:{rc};font-family:{MONO};'
                f'letter-spacing:.06em;margin-bottom:3px;">{rl}</div>'
                f'<div style="font-size:10.5px;color:{TEXT};line-height:1.65;">'
                f'{m["content"]}</div></div>', unsafe_allow_html=True)

        user_in = st.chat_input("Ask about ROP, MSE, hazards, bit parameters…",
                                key="agent_chat")
        if user_in:
            st.session_state.chat_msgs.append({"role": "user", "content": user_in})
            history = [{"role": m["role"], "content": m["content"]}
                       for m in st.session_state.chat_msgs]
            with st.spinner("Thinking…"):
                reply = _claude(
                    [{"role": "system", "content": f"Senior drilling engineer AI.\n\nSnapshot:\n{ctx}"}]
                    + history, max_tokens=500)
            st.session_state.chat_msgs.append({"role": "assistant", "content": reply})
            st.rerun()

        if st.button("Clear chat", key="clr_chat"):
            st.session_state.chat_msgs = []
            st.rerun()


# ═══════════════════════════════════════════════════════════
# TAB 7 — DATA & AI FLOW (ESP PM Data Flow style)
# ═══════════════════════════════════════════════════════════

def render_dataflow():
    svg = f'''<svg viewBox="0 0 1120 520" xmlns="http://www.w3.org/2000/svg">
<defs>
<style>
@keyframes fd {{ to {{ stroke-dashoffset: -18; }} }}
.edge {{ stroke-dasharray:6 3; animation:fd 1.6s linear infinite; }}
.track {{ stroke-opacity:0.12; }}
text {{ font-family: {MONO}; }}
</style>
</defs>
<rect width="1120" height="520" fill="{BG}" rx="8"/>

<!-- Sources -->
<rect x="30" y="40" width="160" height="70" rx="6" fill="{PANEL}" stroke="{GREEN}" stroke-width="1.5"/>
<text x="110" y="62" text-anchor="middle" fill="{GREEN}" font-size="9" font-weight="700">MSEEL CSV</text>
<text x="110" y="78" text-anchor="middle" fill="{MUTED}" font-size="8">MIP_3H / MIP_4H</text>
<text x="110" y="92" text-anchor="middle" fill="{MUTED}" font-size="7">Surface drilling data</text>

<rect x="30" y="140" width="160" height="70" rx="6" fill="{PANEL}" stroke="{AMBER}" stroke-width="1.5"/>
<text x="110" y="162" text-anchor="middle" fill="{AMBER}" font-size="9" font-weight="700">SAP ERP</text>
<text x="110" y="178" text-anchor="middle" fill="{MUTED}" font-size="8">Delta Sharing</text>
<text x="110" y="192" text-anchor="middle" fill="{MUTED}" font-size="7">WOs · BOM · Procurement</text>

<!-- Medallion -->
<rect x="240" y="40" width="120" height="70" rx="6" fill="{PANEL}" stroke="{ORANGE}" stroke-width="1.5"/>
<text x="300" y="62" text-anchor="middle" fill="{ORANGE}" font-size="9" font-weight="700">BRONZE</text>
<text x="300" y="78" text-anchor="middle" fill="{MUTED}" font-size="8">Raw Delta</text>

<rect x="400" y="40" width="120" height="70" rx="6" fill="{PANEL}" stroke="{CYAN}" stroke-width="1.5"/>
<text x="460" y="62" text-anchor="middle" fill="{CYAN}" font-size="9" font-weight="700">SILVER</text>
<text x="460" y="78" text-anchor="middle" fill="{MUTED}" font-size="8">MSE + Features</text>

<rect x="560" y="40" width="120" height="70" rx="6" fill="{PANEL}" stroke="{GREEN}" stroke-width="1.5"/>
<text x="620" y="62" text-anchor="middle" fill="{GREEN}" font-size="9" font-weight="700">GOLD</text>
<text x="620" y="78" text-anchor="middle" fill="{MUTED}" font-size="8">ML-Ready</text>

<!-- ML -->
<rect x="400" y="160" width="140" height="70" rx="6" fill="{PANEL}" stroke="{PURPLE}" stroke-width="1.5"/>
<text x="470" y="182" text-anchor="middle" fill="{PURPLE}" font-size="9" font-weight="700">XGBOOST</text>
<text x="470" y="198" text-anchor="middle" fill="{MUTED}" font-size="8">MLflow Registry</text>
<text x="470" y="212" text-anchor="middle" fill="{MUTED}" font-size="7">rop_xgb_mseel</text>

<rect x="600" y="160" width="160" height="70" rx="6" fill="{PANEL}" stroke="{CYAN}" stroke-width="1.5"/>
<text x="680" y="182" text-anchor="middle" fill="{CYAN}" font-size="9" font-weight="700">STREAMING</text>
<text x="680" y="198" text-anchor="middle" fill="{MUTED}" font-size="8">Spark Structured</text>
<text x="680" y="212" text-anchor="middle" fill="{MUTED}" font-size="7">Real-time UDF scoring</text>

<!-- Serving -->
<rect x="400" y="300" width="140" height="70" rx="6" fill="{PANEL}" stroke="{GREEN}" stroke-width="1.5"/>
<text x="470" y="322" text-anchor="middle" fill="{GREEN}" font-size="9" font-weight="700">LAKEBASE</text>
<text x="470" y="338" text-anchor="middle" fill="{MUTED}" font-size="8">PostgreSQL (OLTP)</text>
<text x="470" y="352" text-anchor="middle" fill="{MUTED}" font-size="7">predictions · alerts</text>

<rect x="600" y="300" width="160" height="70" rx="6" fill="{PANEL}" stroke="{CYAN}" stroke-width="1.5"/>
<text x="680" y="322" text-anchor="middle" fill="{CYAN}" font-size="9" font-weight="700">STREAMLIT APP</text>
<text x="680" y="338" text-anchor="middle" fill="{MUTED}" font-size="8">Databricks Apps</text>
<text x="680" y="352" text-anchor="middle" fill="{MUTED}" font-size="7">7 tabs · @fragment(3s)</text>

<!-- SAP outbound -->
<rect x="820" y="40" width="140" height="70" rx="6" fill="{PANEL}" stroke="{AMBER}" stroke-width="1.5"/>
<text x="890" y="62" text-anchor="middle" fill="{AMBER}" font-size="9" font-weight="700">SAP TABLES</text>
<text x="890" y="78" text-anchor="middle" fill="{MUTED}" font-size="8">Delta Sharing</text>
<text x="890" y="92" text-anchor="middle" fill="{MUTED}" font-size="7">WOs · BOM · Contracts</text>

<!-- Foundation Model -->
<rect x="820" y="160" width="140" height="70" rx="6" fill="{PANEL}" stroke="{PURPLE}" stroke-width="1.5"/>
<text x="890" y="182" text-anchor="middle" fill="{PURPLE}" font-size="9" font-weight="700">CLAUDE</text>
<text x="890" y="198" text-anchor="middle" fill="{MUTED}" font-size="8">Foundation Model API</text>
<text x="890" y="212" text-anchor="middle" fill="{MUTED}" font-size="7">Drilling AI Agent</text>

<!-- Edges (tracks behind + animated dash) -->
<!-- Sources → Bronze -->
<line x1="190" y1="75" x2="240" y2="75" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="190" y1="75" x2="240" y2="75" stroke="{GREEN}" stroke-width="1.5" class="edge"/>
<line x1="190" y1="175" x2="240" y2="75" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="190" y1="175" x2="240" y2="75" stroke="{AMBER}" stroke-width="1.5" class="edge"/>
<!-- Bronze → Silver → Gold -->
<line x1="360" y1="75" x2="400" y2="75" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="360" y1="75" x2="400" y2="75" stroke="{ORANGE}" stroke-width="1.5" class="edge"/>
<line x1="520" y1="75" x2="560" y2="75" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="520" y1="75" x2="560" y2="75" stroke="{CYAN}" stroke-width="1.5" class="edge"/>
<!-- Gold → ML + Streaming -->
<line x1="620" y1="110" x2="470" y2="160" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="620" y1="110" x2="470" y2="160" stroke="{PURPLE}" stroke-width="1.5" class="edge"/>
<line x1="680" y1="110" x2="680" y2="160" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="680" y1="110" x2="680" y2="160" stroke="{CYAN}" stroke-width="1.5" class="edge"/>
<!-- Streaming → Lakebase -->
<line x1="680" y1="230" x2="470" y2="300" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="680" y1="230" x2="470" y2="300" stroke="{GREEN}" stroke-width="1.5" class="edge"/>
<!-- Lakebase → App -->
<line x1="540" y1="335" x2="600" y2="335" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="540" y1="335" x2="600" y2="335" stroke="{GREEN}" stroke-width="1.5" class="edge"/>
<!-- Gold → SAP Tables -->
<line x1="680" y1="75" x2="820" y2="75" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="680" y1="75" x2="820" y2="75" stroke="{AMBER}" stroke-width="1.5" class="edge"/>
<!-- Claude → App -->
<line x1="890" y1="230" x2="760" y2="300" stroke="{BORDER}" stroke-width="3" class="track"/>
<line x1="890" y1="230" x2="760" y2="300" stroke="{PURPLE}" stroke-width="1.5" class="edge"/>

<!-- Unity Catalog governance box -->
<rect x="220" y="20" width="500" height="365" rx="10" fill="none"
      stroke="{ORANGE}" stroke-width="1" stroke-dasharray="6 4" opacity="0.4"/>
<text x="470" y="396" text-anchor="middle" fill="{ORANGE}" font-size="8" opacity="0.6">UNITY CATALOG — Governed Lakehouse</text>

<!-- Title -->
<text x="560" y="460" text-anchor="middle" fill="{MUTED}" font-size="10">ROP PREDICTION — DATA & AI FLOW</text>
<text x="560" y="480" text-anchor="middle" fill="{MUTED}" font-size="7">MSEEL Field · Databricks Lakehouse · SAP ERP · Claude AI</text>
</svg>'''

    _components.html(
        f'<html><head><style>'
        f'html {{ background:{BG}; }} body {{ max-width:1120px; margin:0 auto; }}'
        f'</style></head><body>{svg}</body></html>',
        height=580, scrolling=True)

    # How It Works cards
    _section("HOW IT WORKS")
    cards = [
        ("Ingestion", "MSEEL CSV data and SAP ERP tables ingested via Autoloader into Bronze Delta tables. Delta Sharing enables real-time SAP integration.", GREEN),
        ("Medallion ETL", "Bronze → Silver (MSE calculation via Teale equation, feature engineering) → Gold (ML-ready labels, sliding windows).", CYAN),
        ("ML Pipeline", "XGBoost model trained on Gold, registered in MLflow. Spark Structured Streaming scores live data via UDF.", PURPLE),
        ("Serving", "Predictions and alerts written to Lakebase PostgreSQL. Streamlit app reads via SQLAlchemy with 3-second live refresh.", GREEN),
        ("SAP Integration", "Work orders, equipment BOM, procurement, and vendor contracts surfaced alongside drilling analytics.", AMBER),
        ("AI Agent", "Claude Foundation Model API provides natural-language drilling analysis and chat-based diagnostic support.", PURPLE),
    ]
    cols = st.columns(3)
    for i, (title, desc, color) in enumerate(cards):
        with cols[i % 3]:
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {color}33;'
                f'border-radius:8px;padding:14px 16px;margin-bottom:8px;min-height:120px;">'
                f'<div style="font-size:10px;font-weight:700;color:{color};'
                f'letter-spacing:.06em;margin-bottom:6px;">{title.upper()}</div>'
                f'<div style="font-size:10px;color:{TEXT};line-height:1.6;">{desc}</div>'
                f'</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# ENTRY POINT — render_app()
# ═══════════════════════════════════════════════════════════

def render_app():
    st.set_page_config(
        page_title="ROP Prediction — Drilling & ERP",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_css()

    # Header
    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:4px 0 8px;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<span class="live-dot"></span>'
        f'<span style="font-size:18px;font-weight:700;color:{TEXT};">ROP PREDICTION</span>'
        f'<span style="font-size:10px;color:{MUTED};font-family:{MONO};">'
        f'Drilling & SAP ERP · MSEEL Field</span>'
        f'</div>'
        f'<span style="font-size:9px;color:{MUTED};font-family:{MONO};">'
        f'Databricks Lakehouse + Lakebase + Claude AI</span>'
        f'</div>', unsafe_allow_html=True)

    # Initialise simulator tick
    if "tick" not in st.session_state:
        st.session_state.tick = 0

    @st.fragment(run_every=3)
    def _live():
        st.session_state.tick += 1
        wells_data = simulate_all_wells(st.session_state.tick)

        tabs = st.tabs([
            "⚡ Drilling Command",
            "🔬 Well Diagnostics",
            "📊 Deep Analytics",
            "🚨 Live Alerts",
            "🔧 SAP ERP",
            "🤖 Drilling Agent",
            "🗺️ Data & AI Flow",
        ])

        with tabs[0]:
            render_drilling_command(wells_data)
        with tabs[1]:
            render_well_diagnostics(wells_data)
        with tabs[2]:
            render_analytics()
        with tabs[3]:
            render_alerts()
        with tabs[4]:
            render_sap_erp()
        with tabs[5]:
            render_agent()
        with tabs[6]:
            render_dataflow()

    _live()