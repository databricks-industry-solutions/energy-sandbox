"""
BOP Guardian -- Command Center UI
Dark-themed Streamlit dashboard with 8 tabs: BOP Status, Diagnostics,
Predictive Maintenance, Events & Anomalies, SAP ERP, Crew & Ops,
Data & AI Flow, Guardian Advisor.
Uses ESP PM design patterns: @st.fragment(run_every=3), card layouts, gauges.
Includes live agentic AI monitoring and chat interface.
"""
from __future__ import annotations

import html as _html
import re
import time
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as _components
from pathlib import Path

from app.simulator import (
    simulate_tick, get_telemetry_history, get_events, get_anomalies,
    COMPONENTS, RIG_NAME, WELL_NAME, SENSOR_DEFS,
)
from app.mock_data import (
    RUL_PREDICTIONS, FAILURE_PATTERNS, SAP_WORK_ORDERS, SAP_SPARES,
    CREW, get_qualified_bop_crew, get_intervention_eta, get_sap_kpis,
    INTERVENTION_ETA,
)
from app.agent import GuardianAgent, SEV_LABEL

# ── Color palette (ESP PM) ──────────────────────────────────────────────────
BG = "#0B0F1A"; PANEL = "#0f172a"; CARD = "#1C2333"; BORDER = "#1e293b"
TEXT = "#e2e8f0"; MUTED = "#64748b"
MONO = "JetBrains Mono, Consolas, monospace"
CYAN = "#00D4FF"; GREEN = "#22c55e"; YELLOW = "#eab308"; RED = "#ef4444"
ORANGE = "#F97316"; PURPLE = "#8B5CF6"; AMBER = "#ffa940"; TEAL = "#36cfc9"
STATUS_COLORS = {"NORMAL": GREEN, "WATCH": YELLOW, "ACT_NOW": RED}
WO_COLORS = {"OPEN": AMBER, "IN_PROGRESS": CYAN, "PLANNED": PURPLE, "COMPLETED": GREEN}

# ── Plotly layout helpers ────────────────────────────────────────────────────
_BASE = dict(paper_bgcolor=BG, plot_bgcolor=PANEL, font_color=TEXT)

def _legend():
    return dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10))

def _layout(height=280, **kw):
    d = dict(**_BASE, height=height, margin=dict(l=10, r=10, t=30, b=30),
             xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
             legend=_legend())
    d.update(kw)
    return d

def _empty_fig(msg="No data"):
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(color=MUTED, size=14))
    fig.update_layout(**_BASE, height=200, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig

# ── HTML helpers (ESP PM patterns) ──────────────────────────────────────────

def _kpi(label: str, value: str, sub: str = "", color: str = TEXT) -> str:
    sub_html = f"<div style='font-size:11px;color:{MUTED};margin-top:2px'>{sub}</div>" if sub else ""
    return (
        f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
        f"padding:10px 12px'>"
        f"<div style='font-size:11px;color:{MUTED};text-transform:uppercase;"
        f"letter-spacing:.06em;margin-bottom:3px'>{label}</div>"
        f"<div style='font-size:25px;font-weight:700;color:{color}'>{value}</div>"
        f"{sub_html}</div>"
    )

def _badge(label: str, color: str) -> str:
    return (
        f"<span style='display:inline-block;background:{color}22;border:1px solid {color}55;"
        f"border-radius:10px;padding:2px 10px;font-size:18px;color:{color};"
        f"font-weight:700;margin:1px 3px'>{label}</span>"
    )

def _section(title: str, sub: str = "") -> str:
    s = f"<span style='color:{MUTED};font-size:20px;margin-left:10px'>{sub}</span>" if sub else ""
    return (
        f"<div style='border-bottom:1px solid {BORDER};padding-bottom:8px;margin:18px 0 12px'>"
        f"<span style='font-size:26px;font-weight:700;color:{TEXT}'>{title}</span>{s}</div>"
    )

def _mtile(label: str, value: str, unit: str, color: str) -> str:
    return (
        f"<div class='mtile'><div class='mtile-lbl'>{label}</div>"
        f"<div class='mtile-val' style='color:{color}'>{value}"
        f"<span class='mtile-unit'>{unit}</span></div></div>"
    )

def _rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB hex to rgba() string for Plotly gauge steps."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _md_to_html(text: str) -> str:
    """Convert basic markdown to safe HTML for chat bubbles."""
    t = _html.escape(text)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = t.replace('\n', '<br>')
    return t

# ── Gauge chart ──────────────────────────────────────────────────────────────

def _gauge(title: str, value: float, min_v: float, max_v: float,
           warn: float, crit: float, unit: str, low_is_bad: bool = False):
    if low_is_bad:
        steps = [
            {"range": [min_v, crit], "color": _rgba(RED, 0.25)},
            {"range": [crit, warn],  "color": _rgba(YELLOW, 0.18)},
            {"range": [warn, max_v], "color": _rgba(GREEN, 0.13)},
        ]
    else:
        steps = [
            {"range": [min_v, warn], "color": _rgba(GREEN, 0.13)},
            {"range": [warn, crit],  "color": _rgba(YELLOW, 0.18)},
            {"range": [crit, max_v], "color": _rgba(RED, 0.25)},
        ]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        title={"text": f"{title}<br><span style='font-size:0.7em;color:{MUTED}'>{unit}</span>",
               "font": {"color": TEXT, "size": 12}},
        number={"font": {"color": CYAN, "size": 22}},
        gauge={
            "axis": {"range": [min_v, max_v], "tickcolor": MUTED,
                     "tickfont": {"color": MUTED, "size": 9}},
            "bar": {"color": CYAN, "thickness": 0.25},
            "bgcolor": PANEL, "bordercolor": BORDER, "steps": steps,
        },
    ))
    fig.update_layout(paper_bgcolor=BG, font_color=TEXT, height=190,
                      margin=dict(l=18, r=18, t=48, b=8))
    return fig

# ── Digital readout tile (replaces gauges on BOP Status) ─────────────────────

def _readout_tile(title: str, value: float, min_v: float, max_v: float,
                  warn: float, crit: float, unit: str,
                  low_is_bad: bool = False) -> str:
    """LED-style digital readout with horizontal range bar."""
    if low_is_bad:
        color = RED if value <= crit else (YELLOW if value <= warn else GREEN)
    else:
        color = RED if value >= crit else (YELLOW if value >= warn else GREEN)
    pct = max(0, min(100, (value - min_v) / (max_v - min_v) * 100))
    # Zone markers on the bar track
    warn_pct = max(0, min(100, (warn - min_v) / (max_v - min_v) * 100))
    crit_pct = max(0, min(100, (crit - min_v) / (max_v - min_v) * 100))
    if low_is_bad:
        zone_bg = (f"linear-gradient(to right, {RED}30 0%, {RED}30 {crit_pct:.0f}%, "
                   f"{YELLOW}20 {crit_pct:.0f}%, {YELLOW}20 {warn_pct:.0f}%, "
                   f"{GREEN}15 {warn_pct:.0f}%, {GREEN}15 100%)")
    else:
        zone_bg = (f"linear-gradient(to right, {GREEN}15 0%, {GREEN}15 {warn_pct:.0f}%, "
                   f"{YELLOW}20 {warn_pct:.0f}%, {YELLOW}20 {crit_pct:.0f}%, "
                   f"{RED}30 {crit_pct:.0f}%, {RED}30 100%)")
    # Format value
    if abs(value) >= 100:
        val_str = f"{value:,.0f}"
    else:
        val_str = f"{value:.1f}"
    return (
        f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:8px;"
        f"padding:10px 14px;margin-bottom:8px'>"
        f"<div style='font-size:11px;color:{MUTED};text-transform:uppercase;"
        f"letter-spacing:.06em;margin-bottom:5px'>{title}</div>"
        f"<div style='display:flex;align-items:baseline;gap:6px;margin-bottom:8px'>"
        f"<span style='font-size:30px;font-weight:700;color:{color};"
        f"font-family:JetBrains Mono,Consolas,monospace;line-height:1'>{val_str}</span>"
        f"<span style='font-size:14px;color:{MUTED};font-weight:600'>{unit}</span>"
        f"</div>"
        f"<div style='position:relative;height:6px;background:{zone_bg};"
        f"border-radius:3px;overflow:visible'>"
        f"<div style='position:absolute;left:{pct:.0f}%;top:-2px;width:3px;height:10px;"
        f"background:{color};border-radius:1px;transform:translateX(-1px);"
        f"box-shadow:0 0 4px {color}80'></div>"
        f"</div></div>"
    )

# ── CSS injection (ESP PM dark theme) ───────────────────────────────────────

def _inject_css():
    st.markdown(f"""<style>
body, .stApp {{ background-color: {BG}; color: {TEXT}; font-size: 22px; }}
.block-container {{ padding-top: 0.8rem !important; }}
.stTabs [data-baseweb="tab-list"] {{ background-color: {PANEL}; border-radius: 8px; padding: 4px; }}
.stTabs [data-baseweb="tab"] {{ color: #6B7A99; font-weight: 600; font-size: 22px; padding: 15px 24px; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ color: {CYAN}; border-bottom: 2px solid {CYAN}; }}
/* Left sidebar nav */
section[data-testid="stSidebar"] {{ background: {BG} !important; min-width:250px !important; max-width:250px !important; }}
section[data-testid="stSidebar"] > div:first-child {{ background: {BG} !important; padding-top:1rem !important; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 4px !important; }}
section[data-testid="stSidebar"] .stButton > button {{
  background: transparent !important; border: none !important;
  border-left: 3px solid transparent !important; border-radius: 0 8px 8px 0 !important;
  text-align: left !important; justify-content: flex-start !important;
  padding: 14px 18px !important; font-size: 20px !important; font-weight: 600 !important;
  color: #6B7A99 !important; min-height: 55px !important; transition: all 0.15s;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
  background: {PANEL} !important; color: {TEXT} !important; border-left-color: #334155 !important;
}}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
  border-left-color: {CYAN} !important; background: {CYAN}0A !important; color: {CYAN} !important;
}}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
  background: {CYAN}18 !important;
}}
.stButton>button {{ background:{PANEL}; color:#94a3b8; border:1px solid {BORDER};
  border-radius:8px; font-size:21px; font-weight:600; padding:12px 27px; min-height:63px; }}
.stButton>button:hover {{ background:#1e3a5f; color:{TEXT}; border-color:#38bdf8; }}
hr {{ border-color: #1E2D4F; }}
@keyframes livepulse {{ 0%,100%{{opacity:1;box-shadow:0 0 4px {RED};}} 50%{{opacity:.4;box-shadow:0 0 10px {RED};}} }}
.live-dot {{ display:inline-block;width:8px;height:8px;background:{RED};border-radius:50%;
  animation:livepulse 1.1s ease-in-out infinite;vertical-align:middle;margin-right:5px; }}
.live-badge {{ display:inline-flex;align-items:center;background:{RED}22;border:1px solid {RED}55;
  border-radius:5px;padding:2px 9px 2px 6px;font-size:1.27rem;font-weight:700;color:{RED};letter-spacing:.8px; }}
.stDataFrame {{ background: {PANEL} !important; }}
.stSelectbox label, .stTextInput label {{ color: #6B7A99; font-size: 21px; }}
.stSelectbox div[data-baseweb="select"] {{ font-size: 21px; }}
.stRadio label {{ font-size: 21px !important; }}
.stRadio div[role="radiogroup"] label {{ font-size: 20px !important; }}
[data-testid="stHeader"] {{ display: none !important; }}
#MainMenu {{ visibility: hidden !important; }}
footer {{ visibility: hidden !important; }}
.stChatMessage {{ font-size: 21px; }}
[data-testid="stChatInput"] input {{ font-size: 21px; }}
.stExpander {{ font-size: 21px; }}
.mtile {{ background:{PANEL};border:1px solid {BORDER};border-radius:8px;padding:14px 16px; }}
.mtile-lbl {{ font-size:16px;color:{MUTED};text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px; }}
.mtile-val {{ font-size:39px;font-weight:700;line-height:1; }}
.mtile-unit {{ font-size:20px;color:{MUTED};font-weight:400;margin-left:3px; }}
</style>""", unsafe_allow_html=True)

# ── Sensor reading helper ────────────────────────────────────────────────────

def _reading_val(readings: list, asset_id: str, tag: str) -> float:
    for r in readings:
        if r["asset_id"] == asset_id and r["tag"] == tag:
            return r["value"]
    return 0.0

# ── BOP Stack SVG schematic ─────────────────────────────────────────────────

def _bop_stack_svg(components: dict, readings: list | None = None) -> str:
    """BOP P&ID digital twin — clean HMI design with integrated status indicators."""
    if readings is None:
        readings = []

    def _hc(aid):
        h = components.get(aid, {}).get("health_score", 1.0)
        return GREEN if h >= 0.8 else (YELLOW if h >= 0.6 else RED)

    def _hp(aid):
        return components.get(aid, {}).get("health_score", 1.0)

    def _af(aid):
        return components.get(aid, {}).get("anomaly_flag", False)

    def _rv(aid, tag):
        for r in readings:
            if r["asset_id"] == aid and r["tag"] == tag:
                return r["value"]
        return 0.0

    def _dot(aid, x, y):
        """Status dot with pulse animation on anomaly and subtle glow."""
        c = _hc(aid)
        anim = ""
        if _af(aid):
            anim = ('<animate attributeName="opacity" values="1;0.3;1" '
                    'dur="0.8s" repeatCount="indefinite"/>')
        glow = f'<circle cx="{x}" cy="{y}" r="9" fill="{c}" opacity="0.12"/>' if _af(aid) else ""
        return (f'{glow}<circle cx="{x}" cy="{y}" r="5" fill="{c}" '
                f'stroke="{c}" stroke-width="0.8" opacity="0.9">{anim}</circle>')

    # ── Layout constants ─────────────────────────────────────
    CX = 350;  BW = 44;  WALL = 7;  SW = 210
    SL = CX - SW // 2;   SR = CX + SW // 2
    BL = CX - BW // 2;   BR = CX + BW // 2
    DR_X = SR + 36  # data readout x (clears BSR actuator at SR+27)

    svg = []
    a = svg.append
    deg = chr(176)

    def _bore(y, h):
        a(f'<rect x="{BL - WALL}" y="{y}" width="{WALL}" height="{h}" fill="#475569" opacity="0.5"/>')
        a(f'<rect x="{BR}" y="{y}" width="{WALL}" height="{h}" fill="#475569" opacity="0.5"/>')

    def _flange(y):
        fw = SW + 20; fx = SL - 10
        a(f'<rect x="{fx}" y="{y}" width="{fw}" height="7" rx="1" '
          f'fill="#0f172a" stroke="#334155" stroke-width="0.8"/>')
        _bore(y, 7)
        for bx in [fx + 6, fx + 18, fx + fw - 18, fx + fw - 6]:
            a(f'<circle cx="{bx}" cy="{y + 3.5}" r="2" fill="#475569"/>')

    # ═══ 1. FLEX JOINT ═══════════════════════════════════════
    fj_y = 10;  fj_h = 24
    a(f'<ellipse cx="{CX}" cy="{fj_y + fj_h // 2}" rx="{BW // 2 + 18}" ry="{fj_h // 2}" '
      f'fill="none" stroke="#475569" stroke-width="1.5"/>')
    a(f'<ellipse cx="{CX}" cy="{fj_y + fj_h // 2}" rx="{BW // 2 + 8}" ry="{fj_h // 2 - 4}" '
      f'fill="none" stroke="#475569" stroke-width="0.6" opacity="0.4"/>')
    a(f'<text x="{CX}" y="{fj_y + fj_h // 2 + 4}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="sans-serif">FLEX JOINT</text>')

    # ═══ 2. RISER ═════════════════════════════════════════════
    riser_y = fj_y + fj_h;  riser_h = 30
    _bore(riser_y, riser_h)
    a(f'<text x="{CX}" y="{riser_y + riser_h // 2 + 5}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="10" font-family="sans-serif" font-weight="700">RISER</text>')

    # ═══ 3. ANNULAR PREVENTER (LMRP) ═════════════════════════
    ann_y = riser_y + riser_h;  ann_h = 70
    ann_c = _hc("BOP-ANN-01")
    a(f'<text x="{SL - 22}" y="{ann_y + 6}" fill="#64748b" font-size="11" '
      f'font-family="sans-serif" text-anchor="end" font-weight="700" '
      f'letter-spacing="2">L M R P</text>')
    # Dome shape
    a(f'<path d="M{SL},{ann_y + 20} Q{SL},{ann_y} {CX},{ann_y - 3} Q{SR},{ann_y} {SR},{ann_y + 20} '
      f'L{SR},{ann_y + ann_h} L{SL},{ann_y + ann_h} Z" fill="{ann_c}" fill-opacity="0.06" '
      f'stroke="{ann_c}" stroke-width="1.8"/>')
    _bore(ann_y + 10, ann_h - 10)
    # Packer element
    pk_gap = 10 if not _af("BOP-ANN-01") else 28
    pk_y = ann_y + 22;  pk_h = 30
    a(f'<path d="M{BL - WALL},{pk_y} Q{CX - pk_gap // 2},{pk_y + pk_h // 2} {BL - WALL},{pk_y + pk_h}" '
      f'fill="none" stroke="{ann_c}" stroke-width="4" opacity="0.4"/>')
    a(f'<path d="M{BR + WALL},{pk_y} Q{CX + pk_gap // 2},{pk_y + pk_h // 2} {BR + WALL},{pk_y + pk_h}" '
      f'fill="none" stroke="{ann_c}" stroke-width="4" opacity="0.4"/>')
    # Status dot + label INSIDE box (top-left area)
    a(_dot("BOP-ANN-01", SL + 14, ann_y + 26))
    a(f'<text x="{SL + 24}" y="{ann_y + 30}" fill="{ann_c}" font-size="10" '
      f'font-weight="700" font-family="sans-serif">ANN</text>')
    # Data readouts (right side, outside box)
    press_ann = _rv("BOP-ANN-01", "ANN_CLOSE_PRESS")
    temp_ann = _rv("BOP-ANN-01", "ANN_TEMP")
    a(f'<text x="{DR_X}" y="{ann_y + ann_h // 2 - 4}" fill="{CYAN}" '
      f'font-size="13" font-weight="700" font-family="monospace">{press_ann:.0f} psi</text>')
    a(f'<text x="{DR_X}" y="{ann_y + ann_h // 2 + 14}" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{temp_ann:.0f}{deg}F</text>')

    # ═══ 4. LMRP CONNECTOR ══════════════════════════════════
    lmrp_y = ann_y + ann_h;  lmrp_h = 16
    a(f'<rect x="{SL - 14}" y="{lmrp_y}" width="{SW + 28}" height="{lmrp_h}" rx="2" '
      f'fill="#0B0F1A" stroke="#F97316" stroke-width="1.5" stroke-dasharray="5 2"/>')
    _bore(lmrp_y, lmrp_h)
    for bx in range(SL - 8, SR + 14, 20):
        a(f'<circle cx="{bx}" cy="{lmrp_y + lmrp_h // 2}" r="3" '
          f'fill="#1a2236" stroke="#F97316" stroke-width="0.7"/>')
    a(f'<text x="{CX}" y="{lmrp_y + lmrp_h // 2 + 4}" text-anchor="middle" fill="#F97316" '
      f'font-size="11" font-weight="700" font-family="sans-serif" letter-spacing="1">'
      f'LMRP CONNECTOR</text>')
    a(f'<text x="{SL - 22}" y="{lmrp_y + lmrp_h + 14}" fill="#64748b" font-size="11" '
      f'font-family="sans-serif" text-anchor="end" font-weight="700" '
      f'letter-spacing="2">S T A C K</text>')

    # ═══ 5. UPPER PIPE RAM ════════════════════════════════════
    act_w = 18;  ram_h = 24
    upr_y = lmrp_y + lmrp_h + 22;  upr_h = 56
    upr_c = _hc("BOP-UPR-01")
    act_h = upr_h - 14
    a(f'<rect x="{SL}" y="{upr_y}" width="{SW}" height="{upr_h}" rx="4" '
      f'fill="{upr_c}" fill-opacity="0.06" stroke="{upr_c}" stroke-width="1.5"/>')
    _bore(upr_y, upr_h)
    # Ram blocks
    ram_gap = 6 if not _af("BOP-UPR-01") else 22
    ram_y = upr_y + 16
    lrw = BL - WALL - SL - 10 - ram_gap // 2
    rrw = SR - BR - WALL - 10 - ram_gap // 2
    a(f'<rect x="{SL + 10}" y="{ram_y}" width="{lrw}" height="{ram_h}" '
      f'rx="3" fill="{upr_c}" fill-opacity="0.4" stroke="{upr_c}" stroke-width="0.8"/>')
    a(f'<rect x="{BR + WALL + ram_gap // 2}" y="{ram_y}" width="{rrw}" height="{ram_h}" '
      f'rx="3" fill="{upr_c}" fill-opacity="0.4" stroke="{upr_c}" stroke-width="0.8"/>')
    if ram_gap <= 8:
        a(f'<circle cx="{CX}" cy="{ram_y + ram_h // 2}" r="9" '
          f'fill="{BG}" stroke="{upr_c}" stroke-width="0.5" opacity="0.5"/>')
    # Actuator cylinders
    a(f'<rect x="{SL - act_w - 3}" y="{upr_y + 7}" width="{act_w}" height="{act_h}" rx="3" '
      f'fill="{upr_c}" fill-opacity="0.10" stroke="{upr_c}" stroke-width="0.8"/>')
    a(f'<line x1="{SL - act_w // 2 - 3}" y1="{upr_y + 10}" '
      f'x2="{SL - act_w // 2 - 3}" y2="{upr_y + act_h + 4}" '
      f'stroke="{upr_c}" stroke-width="1.2" opacity="0.3"/>')
    a(f'<rect x="{SR + 3}" y="{upr_y + 7}" width="{act_w}" height="{act_h}" rx="3" '
      f'fill="{upr_c}" fill-opacity="0.10" stroke="{upr_c}" stroke-width="0.8"/>')
    a(f'<line x1="{SR + act_w // 2 + 3}" y1="{upr_y + 10}" '
      f'x2="{SR + act_w // 2 + 3}" y2="{upr_y + act_h + 4}" '
      f'stroke="{upr_c}" stroke-width="1.2" opacity="0.3"/>')
    # Status dot + label inside box
    a(_dot("BOP-UPR-01", SL + 14, upr_y + 8))
    a(f'<text x="{SL + 24}" y="{upr_y + 11}" fill="{upr_c}" font-size="10" '
      f'font-weight="700" font-family="sans-serif">UPR</text>')
    # Data readouts
    press_upr = _rv("BOP-UPR-01", "UPR_CLOSE_PRESS")
    close_upr = _rv("BOP-UPR-01", "UPR_CLOSE_TIME")
    a(f'<text x="{DR_X}" y="{upr_y + upr_h // 2 - 4}" fill="{CYAN}" '
      f'font-size="13" font-weight="700" font-family="monospace">{press_upr:.0f} psi</text>')
    a(f'<text x="{DR_X}" y="{upr_y + upr_h // 2 + 14}" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{close_upr:.1f}s close</text>')
    _flange(upr_y + upr_h)

    # ═══ 6. LOWER PIPE RAM ════════════════════════════════════
    lpr_y = upr_y + upr_h + 18;  lpr_h = 56
    lpr_c = _hc("BOP-LPR-01")
    a(f'<rect x="{SL}" y="{lpr_y}" width="{SW}" height="{lpr_h}" rx="4" '
      f'fill="{lpr_c}" fill-opacity="0.06" stroke="{lpr_c}" stroke-width="1.5"/>')
    _bore(lpr_y, lpr_h)
    ram_gap_l = 6 if not _af("BOP-LPR-01") else 22
    ram_yl = lpr_y + 16
    lrw_l = BL - WALL - SL - 10 - ram_gap_l // 2
    rrw_l = SR - BR - WALL - 10 - ram_gap_l // 2
    a(f'<rect x="{SL + 10}" y="{ram_yl}" width="{lrw_l}" height="{ram_h}" '
      f'rx="3" fill="{lpr_c}" fill-opacity="0.4" stroke="{lpr_c}" stroke-width="0.8"/>')
    a(f'<rect x="{BR + WALL + ram_gap_l // 2}" y="{ram_yl}" width="{rrw_l}" height="{ram_h}" '
      f'rx="3" fill="{lpr_c}" fill-opacity="0.4" stroke="{lpr_c}" stroke-width="0.8"/>')
    if ram_gap_l <= 8:
        a(f'<circle cx="{CX}" cy="{ram_yl + ram_h // 2}" r="9" '
          f'fill="{BG}" stroke="{lpr_c}" stroke-width="0.5" opacity="0.5"/>')
    a(f'<rect x="{SL - act_w - 3}" y="{lpr_y + 7}" width="{act_w}" height="{act_h}" rx="3" '
      f'fill="{lpr_c}" fill-opacity="0.10" stroke="{lpr_c}" stroke-width="0.8"/>')
    a(f'<rect x="{SR + 3}" y="{lpr_y + 7}" width="{act_w}" height="{act_h}" rx="3" '
      f'fill="{lpr_c}" fill-opacity="0.10" stroke="{lpr_c}" stroke-width="0.8"/>')
    # Status dot + label inside
    a(_dot("BOP-LPR-01", SL + 14, lpr_y + 8))
    a(f'<text x="{SL + 24}" y="{lpr_y + 11}" fill="{lpr_c}" font-size="10" '
      f'font-weight="700" font-family="sans-serif">LPR</text>')
    # Data readouts
    press_lpr = _rv("BOP-LPR-01", "LPR_CLOSE_PRESS")
    close_lpr = _rv("BOP-LPR-01", "LPR_CLOSE_TIME")
    a(f'<text x="{DR_X}" y="{lpr_y + lpr_h // 2 - 4}" fill="{CYAN}" '
      f'font-size="13" font-weight="700" font-family="monospace">{press_lpr:.0f} psi</text>')
    a(f'<text x="{DR_X}" y="{lpr_y + lpr_h // 2 + 14}" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{close_lpr:.1f}s close</text>')
    _flange(lpr_y + lpr_h)

    # ═══ 7. KILL / CHOKE MANIFOLD ════════════════════════════
    kc_y = lpr_y + lpr_h + 18;  kc_h = 18
    a(f'<rect x="{SL}" y="{kc_y}" width="{SW}" height="{kc_h}" rx="3" '
      f'fill="#1a2236" stroke="#475569" stroke-width="1"/>')
    _bore(kc_y, kc_h)
    kill_len = 50;  kill_cy = kc_y + kc_h // 2;  gv_s = 6
    # Kill line (left)
    a(f'<line x1="{SL}" y1="{kill_cy}" x2="{SL - kill_len}" y2="{kill_cy}" '
      f'stroke="#475569" stroke-width="3.5"/>')
    gv_x = SL - kill_len // 2
    a(f'<polygon points="{gv_x - gv_s},{kill_cy - gv_s} {gv_x + gv_s},{kill_cy} '
      f'{gv_x - gv_s},{kill_cy + gv_s}" fill="{GREEN}" fill-opacity="0.25" '
      f'stroke="{GREEN}" stroke-width="0.8"/>')
    a(f'<polygon points="{gv_x + gv_s},{kill_cy - gv_s} {gv_x - gv_s},{kill_cy} '
      f'{gv_x + gv_s},{kill_cy + gv_s}" fill="{GREEN}" fill-opacity="0.25" '
      f'stroke="{GREEN}" stroke-width="0.8"/>')
    a(f'<text x="{SL - kill_len - 5}" y="{kill_cy + 4}" text-anchor="end" fill="{MUTED}" '
      f'font-size="13" font-weight="700" font-family="sans-serif">KILL</text>')
    # Choke line (right)
    a(f'<line x1="{SR}" y1="{kill_cy}" x2="{SR + kill_len}" y2="{kill_cy}" '
      f'stroke="#475569" stroke-width="3.5"/>')
    gv_xr = SR + kill_len // 2
    a(f'<polygon points="{gv_xr - gv_s},{kill_cy - gv_s} {gv_xr + gv_s},{kill_cy} '
      f'{gv_xr - gv_s},{kill_cy + gv_s}" fill="{GREEN}" fill-opacity="0.25" '
      f'stroke="{GREEN}" stroke-width="0.8"/>')
    a(f'<polygon points="{gv_xr + gv_s},{kill_cy - gv_s} {gv_xr - gv_s},{kill_cy} '
      f'{gv_xr + gv_s},{kill_cy + gv_s}" fill="{GREEN}" fill-opacity="0.25" '
      f'stroke="{GREEN}" stroke-width="0.8"/>')
    a(f'<text x="{SR + kill_len + 5}" y="{kill_cy + 4}" fill="{MUTED}" '
      f'font-size="13" font-weight="700" font-family="sans-serif">CHOKE</text>')

    # ═══ 8. BLIND SHEAR RAM ═════════════════════════════════
    bsr_y = kc_y + kc_h + 14;  bsr_h = 72
    bsr_c = _hc("BOP-BSR-01")
    bsr_act_w = 22;  bsr_act_h = bsr_h - 12
    # Double border (reinforced look)
    a(f'<rect x="{SL - 3}" y="{bsr_y}" width="{SW + 6}" height="{bsr_h}" rx="4" '
      f'fill="{bsr_c}" fill-opacity="0.08" stroke="{bsr_c}" stroke-width="2.5"/>')
    a(f'<rect x="{SL + 3}" y="{bsr_y + 3}" width="{SW - 6}" height="{bsr_h - 6}" rx="2" '
      f'fill="none" stroke="{bsr_c}" stroke-width="0.5" opacity="0.25"/>')
    _bore(bsr_y, bsr_h)
    # Shear blades (V-shape when closed, rects when anomaly/open)
    blade_y = bsr_y + 18;  blade_h = 36
    if not _af("BOP-BSR-01"):
        a(f'<polygon points="{SL + 10},{blade_y} {CX - 3},{blade_y + blade_h // 2} '
          f'{SL + 10},{blade_y + blade_h}" fill="{bsr_c}" fill-opacity="0.4" '
          f'stroke="{bsr_c}" stroke-width="1"/>')
        a(f'<polygon points="{SR - 10},{blade_y} {CX + 3},{blade_y + blade_h // 2} '
          f'{SR - 10},{blade_y + blade_h}" fill="{bsr_c}" fill-opacity="0.4" '
          f'stroke="{bsr_c}" stroke-width="1"/>')
    else:
        a(f'<rect x="{SL + 8}" y="{blade_y + 4}" width="{BL - WALL - SL - 12}" '
          f'height="{blade_h - 8}" rx="3" fill="{bsr_c}" fill-opacity="0.35" '
          f'stroke="{bsr_c}" stroke-width="0.8"/>')
        a(f'<rect x="{BR + WALL + 4}" y="{blade_y + 4}" width="{SR - BR - WALL - 12}" '
          f'height="{blade_h - 8}" rx="3" fill="{bsr_c}" fill-opacity="0.35" '
          f'stroke="{bsr_c}" stroke-width="0.8"/>')
    a(f'<text x="{CX}" y="{bsr_y + bsr_h - 8}" text-anchor="middle" fill="{bsr_c}" '
      f'font-size="8" font-weight="700" font-family="sans-serif" opacity="0.4">SHEAR</text>')
    # Actuator cylinders
    a(f'<rect x="{SL - bsr_act_w - 5}" y="{bsr_y + 6}" width="{bsr_act_w}" '
      f'height="{bsr_act_h}" rx="4" fill="{bsr_c}" fill-opacity="0.12" '
      f'stroke="{bsr_c}" stroke-width="1.2"/>')
    a(f'<line x1="{SL - bsr_act_w // 2 - 5}" y1="{bsr_y + 10}" '
      f'x2="{SL - bsr_act_w // 2 - 5}" y2="{bsr_y + bsr_act_h + 3}" '
      f'stroke="{bsr_c}" stroke-width="1.5" opacity="0.25"/>')
    a(f'<rect x="{SR + 5}" y="{bsr_y + 6}" width="{bsr_act_w}" '
      f'height="{bsr_act_h}" rx="4" fill="{bsr_c}" fill-opacity="0.12" '
      f'stroke="{bsr_c}" stroke-width="1.2"/>')
    a(f'<line x1="{SR + bsr_act_w // 2 + 5}" y1="{bsr_y + 10}" '
      f'x2="{SR + bsr_act_w // 2 + 5}" y2="{bsr_y + bsr_act_h + 3}" '
      f'stroke="{bsr_c}" stroke-width="1.5" opacity="0.25"/>')
    # Status dot + label inside
    a(_dot("BOP-BSR-01", SL + 14, bsr_y + 9))
    a(f'<text x="{SL + 24}" y="{bsr_y + 12}" fill="{bsr_c}" font-size="10" '
      f'font-weight="700" font-family="sans-serif">BSR</text>')
    # Data readouts (3 lines)
    press_bsr = _rv("BOP-BSR-01", "BSR_CLOSE_PRESS")
    close_bsr = _rv("BOP-BSR-01", "BSR_CLOSE_TIME")
    shear_bsr = _rv("BOP-BSR-01", "BSR_SHEAR_PRESS")
    a(f'<text x="{DR_X}" y="{bsr_y + bsr_h // 2 - 12}" fill="{CYAN}" '
      f'font-size="13" font-weight="700" font-family="monospace">{press_bsr:.0f} psi</text>')
    a(f'<text x="{DR_X}" y="{bsr_y + bsr_h // 2 + 6}" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{close_bsr:.1f}s close</text>')
    a(f'<text x="{DR_X}" y="{bsr_y + bsr_h // 2 + 22}" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{shear_bsr:.0f} shear</text>')
    _flange(bsr_y + bsr_h)

    # ═══ 9. WELLHEAD CONNECTOR ═══════════════════════════════
    wh_y = bsr_y + bsr_h + 18;  wh_h = 28
    a(f'<rect x="{SL - 16}" y="{wh_y}" width="{SW + 32}" height="{wh_h}" rx="4" '
      f'fill="#1a2236" stroke="#475569" stroke-width="1.5"/>')
    _bore(wh_y, wh_h)
    for bx in range(SL - 10, SR + 16, 16):
        a(f'<circle cx="{bx}" cy="{wh_y + wh_h // 2}" r="3" '
          f'fill="#0B0F1A" stroke="#475569" stroke-width="0.7"/>')
    a(f'<text x="{CX}" y="{wh_y + wh_h // 2 + 4}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-weight="700" font-family="sans-serif" letter-spacing="0.8">'
      f'WELLHEAD CONNECTOR</text>')
    wb_y = wh_y + wh_h;  wb_h = 20
    _bore(wb_y, wb_h)
    a(f'<polygon points="{CX - 6},{wb_y + 10} {CX},{wb_y + wb_h} {CX + 6},{wb_y + 10}" '
      f'fill="{MUTED}" opacity="0.35"/>')

    # ═══ 10. HYDRAULIC SUPPLY LINES ══════════════════════════
    hyd_x = SL - bsr_act_w - 44
    a(f'<line x1="{hyd_x}" y1="{upr_y}" x2="{hyd_x}" y2="{bsr_y + bsr_h}" '
      f'stroke="#00D4FF" stroke-width="2" opacity="0.15"/>')
    for by in [upr_y + upr_h // 2, lpr_y + lpr_h // 2, bsr_y + bsr_h // 2]:
        a(f'<line x1="{hyd_x}" y1="{by}" x2="{SL - bsr_act_w - 5}" y2="{by}" '
          f'stroke="#00D4FF" stroke-width="1" opacity="0.15"/>')
    a(f'<text x="{hyd_x}" y="{upr_y - 6}" text-anchor="middle" fill="#00D4FF" '
      f'font-size="10" font-family="sans-serif" opacity="0.35">HYD</text>')

    # ═══ 11. PODS (wide spacing from stack) ══════════════════
    pod_a_active = _hp("POD-A") >= _hp("POD-B")
    pa_c = _hc("POD-A")
    pa_w, pa_h = 80, 100
    pa_x = SL - pa_w - 100;  pa_y = ann_y + 4
    a(f'<rect x="{pa_x}" y="{pa_y}" width="{pa_w}" height="{pa_h}" rx="6" '
      f'fill="{pa_c}" fill-opacity="0.05" stroke="{pa_c}" stroke-width="1.2"/>')
    a(_dot("POD-A", pa_x + 14, pa_y + 14))
    act_lbl = "ACTIVE" if pod_a_active else ""
    a(f'<text x="{pa_x + pa_w // 2}" y="{pa_y + 18}" text-anchor="middle" fill="{pa_c}" '
      f'font-size="12" font-weight="700" font-family="sans-serif">POD A</text>')
    a(f'<text x="{pa_x + pa_w // 2}" y="{pa_y + 32}" text-anchor="middle" fill="#3b82f6" '
      f'font-size="9" font-family="sans-serif">Blue</text>')
    if act_lbl:
        a(f'<text x="{pa_x + pa_w // 2}" y="{pa_y + 44}" text-anchor="middle" fill="{pa_c}" '
          f'font-size="8" font-weight="700" font-family="sans-serif" opacity="0.6">{act_lbl}</text>')
    sig_a = _rv("POD-A", "PODA_SIGNAL_STR")
    volt_a = _rv("POD-A", "PODA_VOLTAGE")
    # Signal strength bar
    pa_bar_x = pa_x + 8; pa_bar_w = pa_w - 16; pa_bar_y = pa_y + 52; pa_bar_h = 5
    pa_fill_w = max(0, min(pa_bar_w, pa_bar_w * sig_a / 100))
    pa_bar_c = GREEN if sig_a >= 80 else (YELLOW if sig_a >= 50 else RED)
    a(f'<rect x="{pa_bar_x}" y="{pa_bar_y}" width="{pa_bar_w}" height="{pa_bar_h}" rx="2" '
      f'fill="{MUTED}" fill-opacity="0.15"/>')
    a(f'<rect x="{pa_bar_x}" y="{pa_bar_y}" width="{pa_fill_w:.0f}" height="{pa_bar_h}" rx="2" '
      f'fill="{pa_bar_c}" fill-opacity="0.6"/>')
    a(f'<text x="{pa_x + pa_w // 2}" y="{pa_y + pa_h - 24}" text-anchor="middle" fill="{CYAN}" '
      f'font-size="16" font-weight="700" font-family="monospace">{sig_a:.0f}%</text>')
    a(f'<text x="{pa_x + pa_w // 2}" y="{pa_y + pa_h - 10}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{volt_a:.1f}V</text>')
    # MUX cable
    a(f'<path d="M{pa_x + pa_w},{pa_y + pa_h // 2} '
      f'C{pa_x + pa_w + 30},{pa_y + pa_h // 2} {SL - 40},{ann_y + ann_h // 2} '
      f'{SL},{ann_y + ann_h // 2}" fill="none" stroke="{pa_c}" stroke-width="1.2" '
      f'stroke-dasharray="5 3" opacity="0.3"/>')
    a(f'<text x="{pa_x + pa_w + 6}" y="{pa_y + pa_h // 2 - 6}" fill="{pa_c}" '
      f'font-size="10" font-family="sans-serif" opacity="0.35">MUX</text>')

    # Pod B
    pb_c = _hc("POD-B")
    pb_w, pb_h = 80, 100
    pb_x = SR + 100;  pb_y = ann_y + 4
    a(f'<rect x="{pb_x}" y="{pb_y}" width="{pb_w}" height="{pb_h}" rx="6" '
      f'fill="{pb_c}" fill-opacity="0.05" stroke="{pb_c}" stroke-width="1.2"/>')
    a(_dot("POD-B", pb_x + 14, pb_y + 14))
    act_lbl_b = "ACTIVE" if not pod_a_active else ""
    a(f'<text x="{pb_x + pb_w // 2}" y="{pb_y + 18}" text-anchor="middle" fill="{pb_c}" '
      f'font-size="12" font-weight="700" font-family="sans-serif">POD B</text>')
    a(f'<text x="{pb_x + pb_w // 2}" y="{pb_y + 32}" text-anchor="middle" fill="#eab308" '
      f'font-size="9" font-family="sans-serif">Yellow</text>')
    if act_lbl_b:
        a(f'<text x="{pb_x + pb_w // 2}" y="{pb_y + 44}" text-anchor="middle" fill="{pb_c}" '
          f'font-size="8" font-weight="700" font-family="sans-serif" opacity="0.6">{act_lbl_b}</text>')
    sig_b = _rv("POD-B", "PODB_SIGNAL_STR")
    volt_b = _rv("POD-B", "PODB_VOLTAGE")
    # Signal strength bar
    pb_bar_x = pb_x + 8; pb_bar_w = pb_w - 16; pb_bar_y = pb_y + 52; pb_bar_h = 5
    pb_fill_w = max(0, min(pb_bar_w, pb_bar_w * sig_b / 100))
    pb_bar_c = GREEN if sig_b >= 80 else (YELLOW if sig_b >= 50 else RED)
    a(f'<rect x="{pb_bar_x}" y="{pb_bar_y}" width="{pb_bar_w}" height="{pb_bar_h}" rx="2" '
      f'fill="{MUTED}" fill-opacity="0.15"/>')
    a(f'<rect x="{pb_bar_x}" y="{pb_bar_y}" width="{pb_fill_w:.0f}" height="{pb_bar_h}" rx="2" '
      f'fill="{pb_bar_c}" fill-opacity="0.6"/>')
    a(f'<text x="{pb_x + pb_w // 2}" y="{pb_y + pb_h - 24}" text-anchor="middle" fill="{CYAN}" '
      f'font-size="16" font-weight="700" font-family="monospace">{sig_b:.0f}%</text>')
    a(f'<text x="{pb_x + pb_w // 2}" y="{pb_y + pb_h - 10}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="13" font-family="monospace">{volt_b:.1f}V</text>')
    a(f'<path d="M{pb_x},{pb_y + pb_h // 2} '
      f'C{pb_x - 30},{pb_y + pb_h // 2} {SR + 40},{ann_y + ann_h // 2} '
      f'{SR},{ann_y + ann_h // 2}" fill="none" stroke="{pb_c}" stroke-width="1.2" '
      f'stroke-dasharray="5 3" opacity="0.3"/>')
    a(f'<text x="{pb_x - 6}" y="{pb_y + pb_h // 2 - 6}" text-anchor="end" fill="{pb_c}" '
      f'font-size="10" font-family="sans-serif" opacity="0.35">MUX</text>')

    # ═══ 12. SUPPORT SYSTEMS (uniform height, symmetric spacing) ═══
    sys_y = wb_y + wb_h + 34
    bh = 82;  gap = 20  # uniform height + equal gap
    # Centered row: P1(100) + gap + ACC(160) + gap + PLC(100) + gap + P2(100) = 520
    row_w = 100 + gap + 160 + gap + 100 + gap + 100  # 520
    row_x0 = CX - row_w // 2  # left edge of row

    # Pump 1
    p1_c = _hc("PMP-01"); p1_x = row_x0; p1_w = 100
    a(f'<rect x="{p1_x}" y="{sys_y}" width="{p1_w}" height="{bh}" rx="6" fill="{p1_c}" '
      f'fill-opacity="0.05" stroke="{p1_c}" stroke-width="1"/>')
    a(_dot("PMP-01", p1_x + 14, sys_y + 14))
    a(f'<text x="{p1_x + p1_w // 2}" y="{sys_y + 18}" text-anchor="middle" fill="{p1_c}" '
      f'font-size="10" font-weight="700" font-family="sans-serif">KOOMEY P1</text>')
    p1_cur = _rv("PMP-01", "PUMP_CURRENT")
    p1_press = _rv("PMP-01", "PUMP_PRESS")
    p1_vib = _rv("PMP-01", "PUMP_VIBRATION")
    a(f'<text x="{p1_x + p1_w // 2}" y="{sys_y + 36}" text-anchor="middle" fill="{CYAN}" '
      f'font-size="14" font-weight="700" font-family="monospace">{p1_cur:.0f}A</text>')
    # Current draw bar (max 60A)
    p1b_x = p1_x + 8; p1b_w = p1_w - 16; p1b_y = sys_y + 41; p1b_h = 5
    p1_pct = min(100, p1_cur / 60 * 100)
    p1b_fill = max(0, min(p1b_w, p1b_w * p1_pct / 100))
    p1b_c = GREEN if p1_cur <= 50 else (YELLOW if p1_cur <= 58 else RED)
    a(f'<rect x="{p1b_x}" y="{p1b_y}" width="{p1b_w}" height="{p1b_h}" rx="2" '
      f'fill="{MUTED}" fill-opacity="0.15"/>')
    a(f'<rect x="{p1b_x}" y="{p1b_y}" width="{p1b_fill:.0f}" height="{p1b_h}" rx="2" '
      f'fill="{p1b_c}" fill-opacity="0.6"/>')
    a(f'<text x="{p1_x + p1_w // 2}" y="{sys_y + 58}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">{p1_press:.0f}psi</text>')
    a(f'<text x="{p1_x + p1_w // 2}" y="{sys_y + 72}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">{p1_vib:.1f}mm/s</text>')

    # Accumulator — clean layout matching other boxes, with fill-level bar
    acc_c = _hc("ACC-01"); acc_x = p1_x + p1_w + gap; acc_w = 160
    a(f'<rect x="{acc_x}" y="{sys_y}" width="{acc_w}" height="{bh}" rx="6" fill="{acc_c}" '
      f'fill-opacity="0.05" stroke="{acc_c}" stroke-width="1"/>')
    a(_dot("ACC-01", acc_x + 16, sys_y + 14))
    a(f'<text x="{acc_x + acc_w // 2}" y="{sys_y + 18}" text-anchor="middle" fill="{acc_c}" '
      f'font-size="10" font-weight="700" font-family="sans-serif">ACCUMULATOR</text>')
    acc_p = _rv("ACC-01", "ACC_PRESS")
    acc_v = _rv("ACC-01", "ACC_VOLUME")
    acc_pre = _rv("ACC-01", "ACC_PRECHARGE")
    a(f'<text x="{acc_x + acc_w // 2}" y="{sys_y + 38}" text-anchor="middle" fill="{CYAN}" '
      f'font-size="14" font-weight="700" font-family="monospace">{acc_p:.0f}psi</text>')
    # Volume fill-level bar
    bar_x = acc_x + 14; bar_w = acc_w - 28; bar_y = sys_y + 45; bar_h = 6
    fill_w = max(0, min(bar_w, bar_w * acc_v / 100))
    bar_c = GREEN if acc_v >= 70 else (YELLOW if acc_v >= 50 else RED)
    a(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="3" '
      f'fill="{MUTED}" fill-opacity="0.15"/>')
    a(f'<rect x="{bar_x}" y="{bar_y}" width="{fill_w:.0f}" height="{bar_h}" rx="3" '
      f'fill="{bar_c}" fill-opacity="0.6"/>')
    a(f'<text x="{acc_x + acc_w // 2}" y="{sys_y + 62}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">{acc_v:.0f}% vol</text>')
    a(f'<text x="{acc_x + acc_w // 2}" y="{sys_y + 76}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">pre {acc_pre:.0f}psi</text>')

    # PLC
    plc_c = _hc("PLC-01"); plc_x = acc_x + acc_w + gap; plc_w = 100
    a(f'<rect x="{plc_x}" y="{sys_y}" width="{plc_w}" height="{bh}" rx="6" fill="{plc_c}" '
      f'fill-opacity="0.05" stroke="{plc_c}" stroke-width="1"/>')
    a(_dot("PLC-01", plc_x + 14, sys_y + 14))
    a(f'<text x="{plc_x + plc_w // 2}" y="{sys_y + 18}" text-anchor="middle" fill="{plc_c}" '
      f'font-size="10" font-weight="700" font-family="sans-serif">BOP PLC</text>')
    plc_cpu = _rv("PLC-01", "PLC_CPU_LOAD")
    plc_mem = _rv("PLC-01", "PLC_MEMORY")
    plc_scan = _rv("PLC-01", "PLC_SCAN_TIME")
    a(f'<text x="{plc_x + plc_w // 2}" y="{sys_y + 36}" text-anchor="middle" fill="{CYAN}" '
      f'font-size="14" font-weight="700" font-family="monospace">{plc_cpu:.0f}%</text>')
    # CPU load bar
    plcb_x = plc_x + 8; plcb_w = plc_w - 16; plcb_y = sys_y + 41; plcb_h = 5
    plcb_fill = max(0, min(plcb_w, plcb_w * plc_cpu / 100))
    plcb_c = GREEN if plc_cpu <= 60 else (YELLOW if plc_cpu <= 80 else RED)
    a(f'<rect x="{plcb_x}" y="{plcb_y}" width="{plcb_w}" height="{plcb_h}" rx="2" '
      f'fill="{MUTED}" fill-opacity="0.15"/>')
    a(f'<rect x="{plcb_x}" y="{plcb_y}" width="{plcb_fill:.0f}" height="{plcb_h}" rx="2" '
      f'fill="{plcb_c}" fill-opacity="0.6"/>')
    a(f'<text x="{plc_x + plc_w // 2}" y="{sys_y + 58}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">MEM {plc_mem:.0f}%</text>')
    a(f'<text x="{plc_x + plc_w // 2}" y="{sys_y + 72}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">scan {plc_scan:.0f}ms</text>')

    # Pump 2
    p2_c = _hc("PMP-02"); p2_x = plc_x + plc_w + gap; p2_w = 100
    a(f'<rect x="{p2_x}" y="{sys_y}" width="{p2_w}" height="{bh}" rx="6" fill="{p2_c}" '
      f'fill-opacity="0.05" stroke="{p2_c}" stroke-width="1"/>')
    a(_dot("PMP-02", p2_x + 14, sys_y + 14))
    a(f'<text x="{p2_x + p2_w // 2}" y="{sys_y + 18}" text-anchor="middle" fill="{p2_c}" '
      f'font-size="10" font-weight="700" font-family="sans-serif">KOOMEY P2</text>')
    p2_cur = _rv("PMP-02", "PUMP_CURRENT")
    p2_press = _rv("PMP-02", "PUMP_PRESS")
    p2_vib = _rv("PMP-02", "PUMP_VIBRATION")
    a(f'<text x="{p2_x + p2_w // 2}" y="{sys_y + 36}" text-anchor="middle" fill="{CYAN}" '
      f'font-size="14" font-weight="700" font-family="monospace">{p2_cur:.0f}A</text>')
    # Current draw bar (max 60A)
    p2b_x = p2_x + 8; p2b_w = p2_w - 16; p2b_y = sys_y + 41; p2b_h = 5
    p2_pct = min(100, p2_cur / 60 * 100)
    p2b_fill = max(0, min(p2b_w, p2b_w * p2_pct / 100))
    p2b_c = GREEN if p2_cur <= 50 else (YELLOW if p2_cur <= 58 else RED)
    a(f'<rect x="{p2b_x}" y="{p2b_y}" width="{p2b_w}" height="{p2b_h}" rx="2" '
      f'fill="{MUTED}" fill-opacity="0.15"/>')
    a(f'<rect x="{p2b_x}" y="{p2b_y}" width="{p2b_fill:.0f}" height="{p2b_h}" rx="2" '
      f'fill="{p2b_c}" fill-opacity="0.6"/>')
    a(f'<text x="{p2_x + p2_w // 2}" y="{sys_y + 58}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">{p2_press:.0f}psi</text>')
    a(f'<text x="{p2_x + p2_w // 2}" y="{sys_y + 72}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="12" font-family="monospace">{p2_vib:.1f}mm/s</text>')

    # Connection lines from pumps/acc/plc to hydraulic main & stack
    a(f'<path d="M{p1_x + p1_w // 2},{sys_y} L{p1_x + p1_w // 2},{sys_y - 10} L{hyd_x},{bsr_y + bsr_h}" '
      f'fill="none" stroke="#00D4FF" stroke-width="1" stroke-dasharray="4 2" opacity="0.2"/>')
    a(f'<path d="M{acc_x + acc_w // 2},{sys_y} L{acc_x + acc_w // 2},{sys_y - 10} '
      f'L{hyd_x},{lpr_y + lpr_h}" fill="none" stroke="#00D4FF" stroke-width="1" '
      f'stroke-dasharray="4 2" opacity="0.2"/>')
    a(f'<path d="M{plc_x + plc_w // 2},{sys_y} L{plc_x + plc_w // 2},{sys_y - 10} '
      f'L{CX},{wb_y}" fill="none" stroke="#22d3ee" stroke-width="1" '
      f'stroke-dasharray="4 2" opacity="0.2"/>')
    a(f'<path d="M{p2_x + p2_w // 2},{sys_y} L{p2_x + p2_w // 2},{sys_y - 10} '
      f'L{SR + bsr_act_w + 44},{bsr_y + bsr_h}" fill="none" stroke="#00D4FF" stroke-width="1" '
      f'stroke-dasharray="4 2" opacity="0.2"/>')

    # ── Title ────────────────────────────────────────────────
    a(f'<text x="{CX}" y="{sys_y + bh + 22}" text-anchor="middle" fill="{MUTED}" '
      f'font-size="13" font-weight="700" font-family="sans-serif" letter-spacing="1">'
      f'18-3/4 in  15K  Ram / Annular  |  Deepwater Sentinel</text>')

    # ── Legend ───────────────────────────────────────────────
    leg_y = sys_y + bh + 42
    for i, (clr, lbl) in enumerate([(GREEN, "Functional + redundancy"),
                                     (YELLOW, "Operational / no redundancy"),
                                     (RED, "Impaired / action required")]):
        lx = CX - 220 + i * 200
        a(f'<circle cx="{lx}" cy="{leg_y}" r="7" fill="{clr}" opacity="0.8"/>')
        a(f'<text x="{lx + 12}" y="{leg_y + 5}" fill="{MUTED}" font-size="13.5" '
          f'font-family="sans-serif">{lbl}</text>')

    total_h = leg_y + 22
    body = "\n".join(svg)
    vb_w = 700
    vb_h = total_h
    return (
        f'<!DOCTYPE html><html><head><style>'
        f'*{{margin:0;padding:0;box-sizing:border-box}}'
        f'html,body{{background:{BG};height:100%}}'
        f'svg{{width:100%;height:auto;display:block}}'
        f'</style></head><body>'
        f'<svg viewBox="0 0 {vb_w} {vb_h}" '
        f'preserveAspectRatio="xMidYMin meet" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">'
        f'<path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" stroke-width="0.3"/>'
        f'</pattern></defs>'
        f'<rect width="{vb_w}" height="{vb_h}" fill="url(#g)" opacity="0.25"/>'
        f'{body}'
        f'</svg></body></html>'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 -- BOP STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def render_bop_status(state: dict):
    status = state["status"]
    sc = STATUS_COLORS.get(status, MUTED)
    reason = state["status_reason"]
    # Status strip
    st.markdown(
        f"<div style='background:{sc}15;border:1px solid {sc}44;border-radius:10px;"
        f"padding:10px 16px;margin-bottom:12px;display:flex;align-items:center;gap:10px'>"
        f"<div style='width:10px;height:10px;border-radius:50%;background:{sc}'></div>"
        f"<span style='font-size:14px;font-weight:700;color:{sc}'>{status.replace('_',' ')}</span>"
        f"<span style='font-size:12px;color:{MUTED};margin-left:8px'>{reason}</span>"
        f"</div>", unsafe_allow_html=True)

    kpis = state["kpis"]
    sap = get_sap_kpis()
    readings = state["readings"]

    # 2-column layout: all KPI tiles (left) | BOP schematic (right)
    left, right = st.columns([1, 2])

    with left:
        # Helper to build a sensor KPI tile
        def _stile(title, aid, tag, mn, mx, w, cr, unit, lib):
            val = _reading_val(readings, aid, tag)
            if lib:
                clr = RED if val <= cr else (YELLOW if val <= w else GREEN)
            else:
                clr = RED if val >= cr else (YELLOW if val >= w else GREEN)
            vs = f"{val:,.0f} {unit}" if abs(val) >= 100 else f"{val:.1f} {unit}"
            return _kpi(title, vs, color=clr)

        # All 10 tiles in 5 rows of 2, uniform size
        rows = [
            (_kpi("Min Health", f"{kpis['min_health']:.0%}",
                color=RED if kpis["min_health"] < 0.6 else (YELLOW if kpis["min_health"] < 0.8 else GREEN)),
             _kpi("Active Anomalies", str(kpis["active_anomalies"]),
                color=RED if kpis["active_anomalies"] > 0 else GREEN)),
            (_kpi("Current Op", state["current_op"]["op_code"], color=PURPLE),
             _kpi("Depth MD", f"{kpis['depth_md']:,.0f} ft", color=CYAN)),
            (_stile("BSR Close", "BOP-BSR-01", "BSR_CLOSE_PRESS", 2000, 7000, 5200, 6000, "psi", False),
             _stile("Pump 1 Current", "PMP-01", "PUMP_CURRENT", 0, 100, 55, 65, "A", False)),
            (_stile("Accum Press", "ACC-01", "ACC_PRESS", 1500, 4500, 2500, 2200, "psi", True),
             _stile("BSR Close Time", "BOP-BSR-01", "BSR_CLOSE_TIME", 0, 80, 45, 55, "sec", False)),
            (_kpi("Healthy", f"{kpis['healthy_components']}/{kpis['total_components']}", color=GREEN),
             _stile("Pod A Signal", "POD-A", "PODA_SIGNAL_STR", 0, 100, 70, 50, "%", True)),
            (_stile("Annular Close", "BOP-ANN-01", "ANN_CLOSE_PRESS", 1500, 4500, 2500, 2200, "psi", True),
             _kpi("Crew on Rig", str(sap["crew_on_rig"]), color=TEAL)),
        ]

        for html_l, html_r in rows:
            c1, c2 = st.columns(2)
            c1.markdown(html_l, unsafe_allow_html=True)
            c2.markdown(html_r, unsafe_allow_html=True)

    with right:
        _components.html(_bop_stack_svg(state["components"], readings), height=670, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 -- COMPONENT DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════════

def render_diagnostics(state: dict):
    comp_opts = {c["asset_id"]: f'{c["asset_id"]} -- {c["name"]}' for c in COMPONENTS}
    sel = st.selectbox("Select Component", list(comp_opts.keys()),
                       format_func=lambda x: comp_opts[x], key="diag_comp")
    c = state["components"].get(sel, {})
    if not c:
        st.warning("Component not found."); return

    hs = c["health_score"]
    hc = GREEN if hs >= 0.8 else (YELLOW if hs >= 0.6 else RED)
    type_badge = _badge(c["component_type"].replace("_", " "), PURPLE)
    health_badge = _badge(f"Health {hs:.0%}", hc)
    st.markdown(
        f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:12px;"
        f"padding:12px 16px;margin-bottom:12px;display:flex;align-items:center;gap:10px'>"
        f"<span style='font-weight:700;font-size:22px;color:{TEXT}'>{c['name']}</span>"
        f"{type_badge} {health_badge}"
        f"</div>", unsafe_allow_html=True)

    # Readings for this component
    readings = [r for r in state["readings"] if r["asset_id"] == sel]
    if readings:
        # Up to 4 gauges
        sensor_key = c["component_type"]
        defs = SENSOR_DEFS.get(sensor_key, [])
        gauge_readings = readings[:4]
        gcols = st.columns(len(gauge_readings))
        for gi, rd in enumerate(gauge_readings):
            sd = next((d for d in defs if d["tag"] == rd["tag"]), None)
            base = sd["base"] if sd else rd["value"]
            low = base * 0.5; high = base * 1.8
            warn = base * 1.15; crit = base * 1.35
            with gcols[gi]:
                st.plotly_chart(
                    _gauge(rd["tag"].replace("_", " "), rd["value"], low, high, warn, crit, rd["unit"]),
                    use_container_width=True)

    # Sensor history
    st.markdown(_section("Sensor History", f"{sel}"), unsafe_allow_html=True)
    hist = get_telemetry_history(asset_id=sel, limit=200)
    if hist:
        df = pd.DataFrame(hist)
        tags = df["tag"].unique()
        if len(tags) > 0:
            fig = make_subplots(rows=len(tags), cols=1, shared_xaxes=True,
                                subplot_titles=[t.replace("_", " ") for t in tags],
                                vertical_spacing=0.06)
            colors = [CYAN, GREEN, YELLOW, RED, ORANGE, PURPLE, TEAL, AMBER]
            for ti, tag in enumerate(tags):
                tdf = df[df["tag"] == tag].reset_index(drop=True)
                fig.add_trace(go.Scatter(
                    x=list(range(len(tdf))), y=tdf["value"],
                    name=tag.replace("_", " "), mode="lines",
                    line=dict(color=colors[ti % len(colors)], width=1.5),
                ), row=ti + 1, col=1)
            fig.update_layout(**_BASE, height=max(180 * len(tags), 300),
                              margin=dict(l=10, r=10, t=30, b=20), showlegend=False)
            for i in range(1, len(tags) + 1):
                fig.update_yaxes(gridcolor=BORDER, row=i, col=1)
                fig.update_xaxes(gridcolor=BORDER, row=i, col=1)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.plotly_chart(_empty_fig("Collecting sensor history..."), use_container_width=True)

    # Diagnostic assessment
    if c["anomaly_flag"] and c["anomaly_type"]:
        st.markdown(_section("Diagnostic Assessment"), unsafe_allow_html=True)
        pattern = next((fp for fp in FAILURE_PATTERNS
                        if fp["anomaly_pattern"] == c["anomaly_type"]), None)
        if pattern:
            st.markdown(
                f"<div style='background:#1a0000;border:1px solid #7f1d1d;border-radius:8px;"
                f"padding:12px 14px;margin-bottom:6px'>"
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
                f"  {_badge('WARNING', RED)} {_badge(c['anomaly_type'].replace('_',' '), ORANGE)}"
                f"</div>"
                f"<div style='font-size:18px;color:{TEXT};margin-bottom:6px'>"
                f"  <b>Failure Mode:</b> {pattern['failure_mode']}</div>"
                f"<div style='font-size:18px;color:{TEXT};margin-bottom:6px'>"
                f"  <b>Avg Time to Failure:</b> {pattern['avg_ttf_days']} days</div>"
                f"<div style='font-size:16px;color:{MUTED}'>"
                f"  <b>Recommended Action:</b> {pattern['fix_action']}</div>"
                f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 -- PREDICTIVE MAINTENANCE (RUL)
# ═══════════════════════════════════════════════════════════════════════════════

def render_rul():
    st.markdown(_section("Remaining Useful Life Predictions", "XGBoost v3.1"), unsafe_allow_html=True)

    sorted_rul = sorted(RUL_PREDICTIONS, key=lambda x: x["predicted_rul_days"])
    for row_start in range(0, len(sorted_rul), 2):
        cols = st.columns(2)
        for ci in range(2):
            idx = row_start + ci
            if idx >= len(sorted_rul):
                break
            r = sorted_rul[idx]
            rul = r["predicted_rul_days"]
            rc = RED if rul < 60 else (YELLOW if rul < 120 else GREEN)
            p7 = r["failure_prob_7d"]; p30 = r["failure_prob_30d"]
            bar7 = max(int(p7 * 100 * 3), 1); bar30 = max(int(p30 * 100 * 3), 1)
            with cols[ci]:
                st.markdown(
                    f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
                    f"padding:12px 14px;margin-bottom:6px'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                    f"  <div>"
                    f"    <div style='font-weight:700;font-size:20px;color:{TEXT}'>{r['asset_id']}</div>"
                    f"    <div style='font-size:15px;color:{MUTED}'>{r['component_type'].replace('_',' ')}</div>"
                    f"  </div>"
                    f"  <div style='text-align:right'>"
                    f"    <div style='font-size:33px;font-weight:700;color:{rc}'>{rul}</div>"
                    f"    <div style='font-size:14px;color:{MUTED}'>days RUL</div>"
                    f"  </div>"
                    f"</div>"
                    f"<div style='font-size:15px;color:{MUTED};margin-bottom:3px'>Fail prob 7d: {p7:.1%}</div>"
                    f"<div style='background:{BORDER};border-radius:2px;height:3px;overflow:hidden;margin-bottom:6px'>"
                    f"  <div style='width:{min(bar7,100)}%;height:100%;background:{RED}'></div></div>"
                    f"<div style='font-size:15px;color:{MUTED};margin-bottom:3px'>Fail prob 30d: {p30:.1%}</div>"
                    f"<div style='background:{BORDER};border-radius:2px;height:3px;overflow:hidden'>"
                    f"  <div style='width:{min(bar30,100)}%;height:100%;background:{ORANGE}'></div></div>"
                    f"</div>", unsafe_allow_html=True)

    # Risk bar chart
    st.markdown(_section("30-Day Failure Probability (sorted)"), unsafe_allow_html=True)
    df_rul = pd.DataFrame(sorted_rul)
    df_rul = df_rul.sort_values("failure_prob_30d", ascending=True)
    bar_colors = [RED if v >= 0.2 else (YELLOW if v >= 0.1 else GREEN) for v in df_rul["failure_prob_30d"]]
    fig = go.Figure(go.Bar(
        x=df_rul["failure_prob_30d"], y=df_rul["asset_id"], orientation="h",
        marker_color=bar_colors, text=[f"{v:.0%}" for v in df_rul["failure_prob_30d"]],
        textposition="outside", textfont=dict(color=TEXT, size=10),
    ))
    fig.update_layout(**_BASE, height=320,
                      xaxis=dict(title="Failure Probability (30d)", gridcolor=BORDER),
                      yaxis=dict(gridcolor=BORDER), margin=dict(l=10, r=40, t=10, b=30))
    st.plotly_chart(fig, use_container_width=True)

    # Failure patterns reference
    st.markdown(_section("Known Failure Patterns"), unsafe_allow_html=True)
    for fp in FAILURE_PATTERNS:
        st.markdown(
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:8px;"
            f"padding:10px 14px;margin-bottom:6px'>"
            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:6px'>"
            f"  {_badge(fp['component_type'].replace('_',' '), PURPLE)}"
            f"  {_badge(fp['anomaly_pattern'].replace('_',' '), ORANGE)}"
            f"  <span style='font-size:15px;color:{MUTED};margin-left:auto'>TTF ~{fp['avg_ttf_days']}d</span>"
            f"</div>"
            f"<div style='font-size:16px;color:{TEXT}'>{fp['failure_mode']}</div>"
            f"<div style='font-size:15px;color:{MUTED};margin-top:4px'>{fp['fix_action']}</div>"
            f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 -- EVENTS & ANOMALIES
# ═══════════════════════════════════════════════════════════════════════════════

def render_events():
    SEV_LABELS = {1: "INFO", 2: "WARNING", 3: "CRITICAL"}
    SEV_COLORS = {1: CYAN, 2: YELLOW, 3: RED}

    events = get_events(limit=30)
    anomalies = get_anomalies(limit=30)

    ev_count = len(events); an_count = len(anomalies)
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:12px'>"
        f"<span style='font-size:21px;color:{MUTED};text-transform:uppercase;"
        f"letter-spacing:.05em'>Event Stream</span>"
        f"{_badge(str(ev_count) + ' events', CYAN)} {_badge(str(an_count) + ' anomalies', RED)}"
        f"</div>", unsafe_allow_html=True)

    sev_filter = st.radio("Severity filter", ["All", "CRITICAL", "WARNING", "INFO"],
                          horizontal=True, key="ev_sev_filt")

    # Anomaly cards
    st.markdown(_section("Active Anomalies"), unsafe_allow_html=True)
    if not anomalies:
        st.markdown(
            f"<div style='text-align:center;padding:30px;color:{MUTED};font-size:20px'>"
            f"No anomalies detected</div>", unsafe_allow_html=True)
    else:
        for a in reversed(anomalies):
            sev = a.get("severity", 1)
            sev_label = SEV_LABELS.get(sev, "INFO")
            if sev_filter != "All" and sev_label != sev_filter:
                continue
            sc = SEV_COLORS.get(sev, MUTED)
            st.markdown(
                f"<div style='background:{PANEL};border-left:3px solid {sc};"
                f"border:1px solid {BORDER};border-radius:6px;padding:10px 14px;margin-bottom:5px'>"
                f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:4px'>"
                f"  {_badge(sev_label, sc)}"
                f"  {_badge(a.get('component_type','').replace('_',' '), PURPLE)}"
                f"  {_badge(a.get('anomaly_type','').replace('_',' '), ORANGE)}"
                f"</div>"
                f"<div style='font-size:15px;color:{MUTED}'>"
                f"  {a.get('asset_id','')} | {a.get('ts','')[:19]}</div>"
                f"</div>", unsafe_allow_html=True)

    # Events list
    st.markdown(_section("Recent Events"), unsafe_allow_html=True)
    if not events:
        st.markdown(
            f"<div style='text-align:center;padding:30px;color:{MUTED};font-size:20px'>"
            f"Collecting events...</div>", unsafe_allow_html=True)
    else:
        for ev in reversed(events):
            sev = ev.get("severity", 1)
            sev_label = SEV_LABELS.get(sev, "INFO")
            if sev_filter != "All" and sev_label != sev_filter:
                continue
            sc = SEV_COLORS.get(sev, MUTED)
            st.markdown(
                f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:6px;"
                f"padding:8px 12px;margin-bottom:4px;display:flex;align-items:center;gap:8px'>"
                f"{_badge(sev_label, sc)}"
                f"<span style='font-size:16px;color:{TEXT};flex:1'>{ev.get('message','')}</span>"
                f"<span style='font-size:14px;color:{MUTED}'>{ev.get('ts','')[:19]}</span>"
                f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 -- SAP ERP & SUPPLY CHAIN
# ═══════════════════════════════════════════════════════════════════════════════

def render_sap():
    kpis = get_sap_kpis()
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(_kpi("Open Work Orders", str(kpis["open_wos"]), color=AMBER), unsafe_allow_html=True)
    crit_c = RED if kpis["critical_wos"] > 0 else GREEN
    k2.markdown(_kpi("Critical WOs", str(kpis["critical_wos"]), color=crit_c), unsafe_allow_html=True)
    inv_str = f"${kpis['total_inventory_value']:,.0f}"
    k3.markdown(_kpi("Inventory Value", inv_str, color=CYAN), unsafe_allow_html=True)
    ls_c = RED if kpis["low_stock_items"] > 0 else GREEN
    k4.markdown(_kpi("Low Stock Items", str(kpis["low_stock_items"]), color=ls_c), unsafe_allow_html=True)

    # Initialize WO assignments in session state
    if "wo_assignments" not in st.session_state:
        st.session_state.wo_assignments = {}

    # Work Orders with crew assignment
    st.markdown(_section("Work Orders — Crew Assignment"), unsafe_allow_html=True)
    crew_names = ["Unassigned"] + [f"{c['name']} ({c['role']})" for c in CREW]
    for wo in SAP_WORK_ORDERS:
        wc = WO_COLORS.get(wo["status"], MUTED)
        pri_c = RED if wo["priority"] == 1 else (YELLOW if wo["priority"] == 2 else CYAN)
        assigned = st.session_state.wo_assignments.get(wo["wo_id"], "Unassigned")
        st.markdown(
            f"<div style='background:{PANEL};border-left:3px solid {wc};"
            f"border:1px solid {BORDER};border-radius:6px;padding:10px 14px;margin-bottom:2px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:5px'>"
            f"  <div style='display:flex;align-items:center;gap:6px'>"
            f"    {_badge('P' + str(wo['priority']), pri_c)}"
            f"    <span style='font-weight:700;font-size:18px;color:{TEXT}'>{wo['wo_id']}</span>"
            f"    {_badge(wo['status'].replace('_',' '), wc)}"
            f"  </div>"
            f"  <span style='font-size:15px;color:{MUTED}'>{wo['start_date']} - {wo['finish_date']}</span>"
            f"</div>"
            f"<div style='font-size:16px;color:{TEXT}'>{wo['description']}</div>"
            f"<div style='font-size:15px;color:{MUTED};margin-top:3px'>"
            f"  Equipment: {wo['equipment_id']} | Activity: {wo['maintenance_activity']}</div>"
            f"</div>", unsafe_allow_html=True)

        if wo["status"] in ("OPEN", "IN_PROGRESS", "PLANNED"):
            ac, bc, _ = st.columns([2, 1, 3])
            with ac:
                sel_idx = crew_names.index(assigned) if assigned in crew_names else 0
                pick = st.selectbox("Assign crew", crew_names, index=sel_idx,
                                    key=f"wo_assign_{wo['wo_id']}", label_visibility="collapsed")
                st.session_state.wo_assignments[wo["wo_id"]] = pick
            with bc:
                if pick != "Unassigned":
                    if st.button("Confirm", key=f"wo_confirm_{wo['wo_id']}", type="primary"):
                        st.toast(f"{pick} assigned to {wo['wo_id']}", icon="\u2705")

    # Spare Parts — Reserve for WO
    if "spare_reservations" not in st.session_state:
        st.session_state.spare_reservations = {}
    wo_ids = ["None"] + [wo["wo_id"] for wo in SAP_WORK_ORDERS if wo["status"] != "COMPLETED"]

    st.markdown(_section("Spare Parts Inventory (BOM)"), unsafe_allow_html=True)
    for sp in SAP_SPARES:
        qty = sp["available_qty"]; minq = sp["min_stock"]
        reserved_wo = st.session_state.spare_reservations.get(sp["material_id"], "None")
        stock_c = RED if qty <= minq else GREEN
        st.markdown(
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:6px;"
            f"padding:8px 12px;margin-bottom:2px;display:flex;align-items:center;gap:10px'>"
            f"<div style='flex:1'>"
            f"  <div style='font-size:18px;font-weight:600;color:{TEXT}'>{sp['description']}</div>"
            f"  <div style='font-size:15px;color:{MUTED}'>{sp['material_id']} | {sp['component_type']} | Lead: {sp['lead_time_days']}d</div>"
            f"</div>"
            f"<div style='text-align:right'>"
            f"  <div style='font-size:21px;font-weight:700;color:{stock_c}'>{qty}</div>"
            f"  <div style='font-size:14px;color:{MUTED}'>min {minq}</div>"
            f"</div>"
            f"<div style='text-align:right'>"
            f"  <div style='font-size:16px;color:{MUTED}'>${sp['unit_price']:,}</div>"
            f"</div>"
            f"</div>", unsafe_allow_html=True)
        rc, rb, _ = st.columns([2, 1, 3])
        with rc:
            sel_wo = wo_ids.index(reserved_wo) if reserved_wo in wo_ids else 0
            res_pick = st.selectbox("Reserve for WO", wo_ids, index=sel_wo,
                                    key=f"spare_res_{sp['material_id']}", label_visibility="collapsed")
            st.session_state.spare_reservations[sp["material_id"]] = res_pick
        with rb:
            if res_pick != "None":
                if st.button("Reserve", key=f"spare_conf_{sp['material_id']}", type="primary"):
                    st.toast(f"{sp['description']} reserved for {res_pick}", icon="\U0001f4e6")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 -- CREW & OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def render_crew(state: dict, agent=None):
    bop_crew = get_qualified_bop_crew()
    bop_ids = {c["crew_id"] for c in bop_crew}

    # Initialize crew assignments
    if "crew_task_assignments" not in st.session_state:
        st.session_state.crew_task_assignments = {}
    if "crew_zone_overrides" not in st.session_state:
        st.session_state.crew_zone_overrides = {}

    zones = list(INTERVENTION_ETA.keys())
    task_options = ["Available", "BOP Inspection", "Ram Seal Replacement", "Pod A Diagnostics",
                    "Pump Maintenance", "Accumulator Check", "PLC Troubleshooting",
                    "Wellhead Connector Inspection", "BOP Pressure Test"]

    # Build AI assignments lookup: crew_id -> CrewAssignment
    ai_assignments: dict[str, object] = {}
    if agent and agent.state.crew_assignments:
        # Use the most recent assignment per crew_id
        for ca in agent.state.crew_assignments:
            ai_assignments[ca.crew_id] = ca

    # Summary KPIs — count both AI and human assignments
    ai_count = 0
    human_count = 0
    for c in CREW:
        cid = c["crew_id"]
        human_task = st.session_state.crew_task_assignments.get(cid, "Available")
        if human_task != "Available":
            human_count += 1
        elif cid in ai_assignments:
            ai_count += 1
    total_assigned = ai_count + human_count
    available_count = len(CREW) - total_assigned
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(_kpi("Total Crew", str(len(CREW)), color=CYAN), unsafe_allow_html=True)
    k2.markdown(_kpi("AI Assigned", str(ai_count),
        color=CYAN if ai_count > 0 else MUTED), unsafe_allow_html=True)
    k3.markdown(_kpi("Human Assigned", str(human_count),
        color=AMBER if human_count > 0 else MUTED), unsafe_allow_html=True)
    k4.markdown(_kpi("Available", str(available_count), color=TEAL), unsafe_allow_html=True)
    k5.markdown(_kpi("BOP Qualified", str(len(bop_crew)), color=CYAN), unsafe_allow_html=True)

    st.markdown(_section("Crew on Rig — Task Assignment"), unsafe_allow_html=True)

    for cr in CREW:
        cid = cr["crew_id"]
        is_bop = cid in bop_ids
        human_task = st.session_state.crew_task_assignments.get(cid, "Available")
        ai_assign = ai_assignments.get(cid)
        cur_zone = st.session_state.crew_zone_overrides.get(cid, cr["zone"])
        eta = INTERVENTION_ETA.get(cur_zone, 20)
        eta_c = GREEN if eta <= 5 else (YELLOW if eta <= 10 else RED)
        shift_c = GREEN if cr["shift"] == "Day" else PURPLE

        # Determine assignment state: human override > AI > available
        if human_task != "Available":
            is_assigned = True
            assigned_by = "HUMAN"
            cur_task = human_task
            border_c = AMBER
        elif ai_assign:
            is_assigned = True
            assigned_by = "AI"
            cur_task = ai_assign.issue_type.replace("_", " ").title()
            border_c = CYAN
        else:
            is_assigned = False
            assigned_by = ""
            cur_task = "Available"
            border_c = CYAN if is_bop else BORDER

        # Status indicator
        if assigned_by == "AI":
            status_dot = f"<div style='width:10px;height:10px;border-radius:50%;background:{CYAN}'></div>"
            assignment_html = (
                f"<div style='display:flex;align-items:center;gap:6px;margin-top:6px'>"
                f"  {status_dot}"
                f"  <span style='font-size:15px;font-weight:700;color:{CYAN}'>GUARDIAN AI ASSIGNED:</span>"
                f"  <span style='font-size:15px;font-weight:600;color:{TEXT}'>"
                f"{cur_task} — {ai_assign.asset_id}</span>"
                f"  <span style='font-size:13px;color:{MUTED};margin-left:6px'>"
                f"({ai_assign.reason})</span>"
                f"</div>"
            )
        elif assigned_by == "HUMAN":
            status_dot = f"<div style='width:10px;height:10px;border-radius:50%;background:{AMBER}'></div>"
            assignment_html = (
                f"<div style='display:flex;align-items:center;gap:6px;margin-top:6px'>"
                f"  {status_dot}"
                f"  <span style='font-size:15px;font-weight:700;color:{AMBER}'>HUMAN ASSIGNED:</span>"
                f"  <span style='font-size:15px;font-weight:600;color:{TEXT}'>{cur_task}</span>"
                f"</div>"
            )
        else:
            status_dot = f"<div style='width:10px;height:10px;border-radius:50%;background:{GREEN};opacity:0.5'></div>"
            assignment_html = (
                f"<div style='display:flex;align-items:center;gap:6px;margin-top:6px'>"
                f"  {status_dot}"
                f"  <span style='font-size:15px;color:{MUTED}'>Available for assignment</span>"
                f"</div>"
            )

        bop_tag = _badge("BOP QUALIFIED", CYAN) if is_bop else ""
        cert_badges = " ".join(_badge(cert.replace("_", " "), TEAL) for cert in cr.get("certs", []))

        st.markdown(
            f"<div style='background:{PANEL};border:1px solid {border_c};border-left:3px solid {border_c};"
            f"border-radius:8px;padding:12px 16px;margin-bottom:4px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center'>"
            f"  <div>"
            f"    <div style='font-weight:700;font-size:20px;color:{TEXT}'>{cr['name']}</div>"
            f"    <div style='font-size:15px;color:{MUTED}'>{cr['role']} | {cr['company']}</div>"
            f"  </div>"
            f"  <div style='display:flex;align-items:center;gap:6px'>"
            f"    {_badge(cr['shift'] + ' Shift', shift_c)}"
            f"    {bop_tag}"
            f"  </div>"
            f"</div>"
            f"<div style='display:flex;gap:16px;margin-top:6px'>"
            f"  <div style='font-size:15px;color:{MUTED}'>Zone: "
            f"    <span style='color:{TEXT}'>{cur_zone.replace('_',' ')}</span></div>"
            f"  <div style='font-size:15px;color:{MUTED}'>ETA to BOP: "
            f"    <span style='color:{eta_c};font-weight:700'>{eta} min</span></div>"
            f"</div>"
            f"{assignment_html}"
            f"<div style='margin-top:6px'>{cert_badges}</div>"
            f"</div>", unsafe_allow_html=True)

        # Assignment controls — clear labels, spacious layout
        lbl1, dd1, lbl2, dd2, btn_col = st.columns([0.6, 2, 0.5, 1.5, 0.8])
        with lbl1:
            st.markdown(f"<div style='font-size:13px;color:{MUTED};padding-top:8px'>Task:</div>",
                        unsafe_allow_html=True)
        with dd1:
            t_idx = task_options.index(cur_task) if cur_task in task_options else 0
            task_pick = st.selectbox("Task", task_options, index=t_idx,
                                    key=f"crew_task_{cid}", label_visibility="collapsed")
        with lbl2:
            st.markdown(f"<div style='font-size:13px;color:{MUTED};padding-top:8px'>Zone:</div>",
                        unsafe_allow_html=True)
        with dd2:
            z_idx = zones.index(cur_zone) if cur_zone in zones else 0
            zone_pick = st.selectbox("Zone", zones, index=z_idx,
                                    key=f"crew_zone_{cid}", label_visibility="collapsed")
        with btn_col:
            if st.button("Assign", key=f"crew_assign_{cid}", type="primary"):
                st.session_state.crew_task_assignments[cid] = task_pick
                st.session_state.crew_zone_overrides[cid] = zone_pick
                st.toast(f"{cr['name']} assigned to {task_pick} at {zone_pick.replace('_',' ')}", icon="\u2705")
                st.rerun()

    # Intervention ETA table for BOP-qualified
    st.markdown(_section("BOP Intervention Response", f"{len(bop_crew)} qualified"), unsafe_allow_html=True)
    for cr in sorted(bop_crew, key=lambda x: INTERVENTION_ETA.get(
            st.session_state.crew_zone_overrides.get(x["crew_id"], x["zone"]), 20)):
        cur_zone = st.session_state.crew_zone_overrides.get(cr["crew_id"], cr["zone"])
        eta = INTERVENTION_ETA.get(cur_zone, 20)
        eta_c = GREEN if eta <= 5 else (YELLOW if eta <= 10 else RED)
        bar_w = min(int(eta * 5), 100)
        human_task = st.session_state.crew_task_assignments.get(cr["crew_id"], "Available")
        ai_assign = ai_assignments.get(cr["crew_id"])
        if human_task != "Available":
            task_lbl = f" | <span style='color:{AMBER};font-weight:600'>HUMAN: {human_task}</span>"
        elif ai_assign:
            task_lbl = f" | <span style='color:{CYAN};font-weight:600'>AI: {ai_assign.issue_type.replace('_',' ').title()}</span>"
        else:
            task_lbl = ""
        st.markdown(
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:6px;"
            f"padding:8px 12px;margin-bottom:4px;display:flex;align-items:center;gap:12px'>"
            f"<div style='width:160px;font-size:18px;font-weight:600;color:{TEXT}'>{cr['name']}</div>"
            f"<div style='width:200px;font-size:15px;color:{MUTED}'>{cur_zone.replace('_',' ')}{task_lbl}</div>"
            f"<div style='flex:1;background:{BORDER};border-radius:2px;height:4px;overflow:hidden'>"
            f"  <div style='width:{bar_w}%;height:100%;background:{eta_c}'></div></div>"
            f"<div style='font-size:21px;font-weight:700;color:{eta_c};width:50px;text-align:right'>"
            f"  {eta}m</div>"
            f"</div>", unsafe_allow_html=True)

    # Current op
    op = state["current_op"]
    lr_c = GREEN if op["is_low_risk"] else RED
    lr_txt = "LOW RISK -- maintenance window" if op["is_low_risk"] else "ACTIVE OP -- defer non-critical maintenance"
    st.markdown(_section("Current Drilling Operation"), unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
        f"padding:14px 16px'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
        f"  <span style='font-weight:700;font-size:21px;color:{TEXT}'>{op['description']}</span>"
        f"  {_badge(op['op_code'], CYAN)}"
        f"</div>"
        f"<div style='font-size:16px;color:{MUTED};margin-bottom:4px'>"
        f"  Section: {op['section']} | MD: {op['depth_md']:,.0f} ft | TVD: {op['depth_tvd']:,.0f} ft</div>"
        f"<div style='display:flex;align-items:center;gap:6px;margin-top:6px'>"
        f"  <div style='width:8px;height:8px;border-radius:50%;background:{lr_c}'></div>"
        f"  <span style='font-size:16px;color:{lr_c};font-weight:600'>{lr_txt}</span>"
        f"</div>"
        f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 -- DATA & AI FLOW
# ═══════════════════════════════════════════════════════════════════════════════

_FLOW_SVG = r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  padding:6px 4px;margin:0 auto}
html{background:#0f172a}
@keyframes fd{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}
.fd{animation:fd 1.6s linear infinite}
</style></head><body>
<svg viewBox="0 0 950 460" style="width:100%;display:block" xmlns="http://www.w3.org/2000/svg">
<style>@keyframes fd{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}</style>
<defs>
  <marker id="a1" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#3b82f6"/></marker>
  <marker id="a2" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#f97316"/></marker>
  <marker id="a3" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#14b8a6"/></marker>
  <marker id="a4" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#8b5cf6"/></marker>
  <marker id="a5" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#22c55e"/></marker>
  <marker id="a6" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#00d4ff"/></marker>
</defs>

<!-- Row labels -->
<text x="16" y="30" fill="#64748b" font-size="15" font-weight="700" font-family="sans-serif">SOURCES</text>
<text x="16" y="180" fill="#64748b" font-size="15" font-weight="700" font-family="sans-serif">PLATFORM / MEDALLION</text>
<text x="16" y="370" fill="#64748b" font-size="15" font-weight="700" font-family="sans-serif">SERVING / AGENTS</text>

<!-- Unity Catalog governance box -->
<rect x="280" y="165" width="660" height="150" rx="10" fill="none" stroke="#f97316" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".4"/>
<rect x="290" y="157" width="148" height="16" rx="4" fill="#0f172a"/>
<text x="296" y="168" fill="#f97316" font-size="14" font-weight="700" font-family="sans-serif">Unity Catalog Governance</text>

<!-- SOURCE NODES -->
<g><rect x="20" y="45" width="160" height="50" rx="8" fill="#0f172a" stroke="#3b82f6" stroke-width="1.2"/>
  <text x="100" y="66" text-anchor="middle" fill="#3b82f6" font-size="16" font-weight="700" font-family="sans-serif">BOP Stack / PLCs</text>
  <text x="100" y="82" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">Sensor telemetry stream</text></g>
<g><rect x="200" y="45" width="140" height="50" rx="8" fill="#0f172a" stroke="#f97316" stroke-width="1.2"/>
  <text x="270" y="66" text-anchor="middle" fill="#f97316" font-size="16" font-weight="700" font-family="sans-serif">SAP S/4HANA</text>
  <text x="270" y="82" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">Work orders, spares</text></g>
<g><rect x="360" y="45" width="140" height="50" rx="8" fill="#0f172a" stroke="#14b8a6" stroke-width="1.2"/>
  <text x="430" y="66" text-anchor="middle" fill="#14b8a6" font-size="16" font-weight="700" font-family="sans-serif">Crew Systems</text>
  <text x="430" y="82" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">POB, certs, zones</text></g>

<!-- MEDALLION NODES -->
<g><rect x="300" y="195" width="110" height="50" rx="8" fill="#0f172a" stroke="#cd7f32" stroke-width="1.2"/>
  <text x="355" y="216" text-anchor="middle" fill="#cd7f32" font-size="16" font-weight="700" font-family="sans-serif">Bronze</text>
  <text x="355" y="232" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">Raw ingest</text></g>
<g><rect x="450" y="195" width="110" height="50" rx="8" fill="#0f172a" stroke="#c0c0c0" stroke-width="1.2"/>
  <text x="505" y="216" text-anchor="middle" fill="#c0c0c0" font-size="16" font-weight="700" font-family="sans-serif">Silver</text>
  <text x="505" y="232" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">Cleaned, enriched</text></g>
<g><rect x="600" y="195" width="110" height="50" rx="8" fill="#0f172a" stroke="#ffd700" stroke-width="1.2"/>
  <text x="655" y="216" text-anchor="middle" fill="#ffd700" font-size="16" font-weight="700" font-family="sans-serif">Gold</text>
  <text x="655" y="232" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">KPIs, features</text></g>

<!-- ML NODES -->
<g><rect x="770" y="195" width="150" height="50" rx="8" fill="#0f172a" stroke="#8b5cf6" stroke-width="1.2"/>
  <text x="845" y="216" text-anchor="middle" fill="#8b5cf6" font-size="16" font-weight="700" font-family="sans-serif">ML / MLflow</text>
  <text x="845" y="232" text-anchor="middle" fill="#64748b" font-size="14" font-family="sans-serif">Anomaly + RUL models</text></g>

<!-- SERVING NODES -->
<g><rect x="300" y="270" width="110" height="40" rx="8" fill="#0f172a" stroke="#14b8a6" stroke-width="1.2"/>
  <text x="355" y="294" text-anchor="middle" fill="#14b8a6" font-size="15" font-weight="700" font-family="sans-serif">Lakebase</text></g>
<g><rect x="450" y="270" width="130" height="40" rx="8" fill="#0f172a" stroke="#22c55e" stroke-width="1.2"/>
  <text x="515" y="294" text-anchor="middle" fill="#22c55e" font-size="15" font-weight="700" font-family="sans-serif">Streamlit App</text></g>

<!-- AGENT LAYER -->
<g><rect x="60" y="390" width="130" height="44" rx="8" fill="#0f172a" stroke="#00d4ff" stroke-width="1.2"/>
  <text x="125" y="410" text-anchor="middle" fill="#00d4ff" font-size="15" font-weight="700" font-family="sans-serif">Health Agent</text>
  <text x="125" y="424" text-anchor="middle" fill="#64748b" font-size="12" font-family="sans-serif">Real-time monitoring</text></g>
<g><rect x="210" y="390" width="145" height="44" rx="8" fill="#0f172a" stroke="#00d4ff" stroke-width="1.2"/>
  <text x="282" y="410" text-anchor="middle" fill="#00d4ff" font-size="15" font-weight="700" font-family="sans-serif">Maintenance Agent</text>
  <text x="282" y="424" text-anchor="middle" fill="#64748b" font-size="12" font-family="sans-serif">RUL + work orders</text></g>
<g><rect x="375" y="390" width="145" height="44" rx="8" fill="#0f172a" stroke="#00d4ff" stroke-width="1.2"/>
  <text x="447" y="410" text-anchor="middle" fill="#00d4ff" font-size="15" font-weight="700" font-family="sans-serif">Supply Chain Agent</text>
  <text x="447" y="424" text-anchor="middle" fill="#64748b" font-size="12" font-family="sans-serif">SAP spares + BOM</text></g>
<g><rect x="540" y="390" width="130" height="44" rx="8" fill="#0f172a" stroke="#00d4ff" stroke-width="1.2"/>
  <text x="605" y="410" text-anchor="middle" fill="#00d4ff" font-size="15" font-weight="700" font-family="sans-serif">Crew Agent</text>
  <text x="605" y="424" text-anchor="middle" fill="#64748b" font-size="12" font-family="sans-serif">POB + intervention</text></g>
<g><rect x="690" y="390" width="135" height="44" rx="8" fill="#0f172a" stroke="#00d4ff" stroke-width="1.2"/>
  <text x="757" y="410" text-anchor="middle" fill="#00d4ff" font-size="15" font-weight="700" font-family="sans-serif">Drilling Agent</text>
  <text x="757" y="424" text-anchor="middle" fill="#64748b" font-size="12" font-family="sans-serif">Op context + risk</text></g>

<!-- EDGES: Sources -> Bronze -->
<path d="M100,95 L100,140 L355,140 L355,195" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M100,95 L100,140 L355,140 L355,195" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:0s"/>
<path d="M100,95 L100,140 L355,140 L355,195" fill="none" stroke="none" marker-end="url(#a1)"/>
<path d="M270,95 L270,140 L355,140" fill="none" stroke="#f97316" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M270,95 L270,140 L355,140" fill="none" stroke="#f97316" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.2s"/>
<path d="M430,95 L430,140 L370,140 L370,195" fill="none" stroke="#14b8a6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M430,95 L430,140 L370,140 L370,195" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.4s"/>

<!-- EDGES: Bronze -> Silver -> Gold -->
<path d="M410,220 L450,220" fill="none" stroke="#c0c0c0" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M410,220 L450,220" fill="none" stroke="#c0c0c0" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.5s"/>
<path d="M560,220 L600,220" fill="none" stroke="#ffd700" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M560,220 L600,220" fill="none" stroke="#ffd700" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.7s"/>
<!-- Gold -> ML -->
<path d="M710,220 L770,220" fill="none" stroke="#8b5cf6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M710,220 L770,220" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.9s"/>
<path d="M710,220 L770,220" fill="none" stroke="none" marker-end="url(#a4)"/>
<!-- Gold -> Lakebase -->
<path d="M655,245 L655,260 L355,260 L355,270" fill="none" stroke="#14b8a6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M655,245 L655,260 L355,260 L355,270" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.8s"/>
<path d="M655,245 L655,260 L355,260 L355,270" fill="none" stroke="none" marker-end="url(#a3)"/>
<!-- Lakebase -> Streamlit -->
<path d="M410,290 L450,290" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M410,290 L450,290" fill="none" stroke="#22c55e" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:1s"/>
<path d="M410,290 L450,290" fill="none" stroke="none" marker-end="url(#a5)"/>
<!-- Streamlit -> Agent Layer -->
<path d="M515,310 L515,360 L440,360 L440,390" fill="none" stroke="#00d4ff" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M515,310 L515,360 L440,360 L440,390" fill="none" stroke="#00d4ff" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:1.1s"/>
<path d="M515,310 L515,360 L125,360 L125,390" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>
<path d="M515,310 L515,360 L282,360 L282,390" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>
<path d="M515,310 L515,360 L605,360 L605,390" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>
<path d="M515,310 L515,360 L757,360 L757,390" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>

<!-- Pipeline labels on edges -->
<text x="200" y="133" text-anchor="middle" fill="#3b82f6" font-size="12" font-family="sans-serif">IoT stream</text>
<text x="430" y="213" text-anchor="middle" fill="#c0c0c0" font-size="12" font-family="sans-serif">DLT</text>
<text x="580" y="213" text-anchor="middle" fill="#ffd700" font-size="12" font-family="sans-serif">DLT</text>
<text x="740" y="213" text-anchor="middle" fill="#8b5cf6" font-size="12" font-family="sans-serif">features</text>
<text x="430" y="283" text-anchor="middle" fill="#22c55e" font-size="12" font-family="sans-serif">JDBC</text>

<!-- Divider -->
<line x1="16" y1="350" x2="930" y2="350" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
</svg>
</body></html>"""

def render_dataflow():
    # Summary tiles
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.markdown(_kpi("Components", "10 / 10", "All monitored", GREEN), unsafe_allow_html=True)
    sc2.markdown(_kpi("Bronze Latency", "1.2 s", "Auto Loader", CYAN), unsafe_allow_html=True)
    sc3.markdown(_kpi("ML Inference", "4.8 s", "p95 latency", PURPLE), unsafe_allow_html=True)
    sc4.markdown(_kpi("Agent Layer", "5 agents", "Agentic AI", TEAL), unsafe_allow_html=True)

    _components.html(_FLOW_SVG, height=500, scrolling=False)

    # How It Works cards
    st.markdown(_section("How It Works"), unsafe_allow_html=True)
    cards = [
        ("BOP Stack Sensors", "PLCs stream pressure, temperature, vibration, and timing data every second via OPC-UA.",
         "#3b82f6"),
        ("Medallion Architecture", "Bronze ingests raw, Silver cleans and enriches, Gold computes KPIs and ML features.",
         "#ffd700"),
        ("ML Models (MLflow)", "XGBoost anomaly detection and RUL regression models, tracked in MLflow with feature store.",
         PURPLE),
        ("Lakebase Serving", "Low-latency JDBC serving layer for the Streamlit app with row-level security.",
         TEAL),
        ("Agentic AI (LIVE)", "5 domain agents (Health, Maintenance, Supply Chain, Crew, Drilling) "
         "analyze every tick and auto-recommend actions. Use the Guardian Advisor tab to interact.",
         CYAN),
        ("Unity Catalog", "Governance layer: column masking, row filters, lineage tracking across the entire pipeline.",
         ORANGE),
    ]
    for row_start in range(0, len(cards), 3):
        cols = st.columns(3)
        for ci in range(3):
            idx = row_start + ci
            if idx >= len(cards):
                break
            title, desc, clr = cards[idx]
            with cols[ci]:
                st.markdown(
                    f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
                    f"padding:12px 14px;min-height:100px'>"
                    f"<div style='font-size:18px;font-weight:700;color:{clr};margin-bottom:6px'>{title}</div>"
                    f"<div style='font-size:16px;color:{MUTED};line-height:1.5'>{desc}</div>"
                    f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# AGENT BANNER (persistent above tabs)
# ═══════════════════════════════════════════════════════════════════════════════

def render_agent_banner(agent: GuardianAgent):
    critical = agent.get_critical_alerts()
    active = agent.get_active_recommendations()
    warnings = [r for r in active if r.severity == 2]
    assigns = agent.state.crew_assignments[-5:]

    if not critical and not warnings:
        st.markdown(
            f"<div style='background:{GREEN}10;border:1px solid {GREEN}30;border-radius:8px;"
            f"padding:8px 16px;margin-bottom:8px;display:flex;align-items:center;gap:10px'>"
            f"<span style='font-size:20px;font-weight:700;color:{GREEN}'>GUARDIAN AI</span>"
            f"<span style='font-size:20px;color:{MUTED}'>All systems nominal -- no recommendations</span>"
            f"</div>", unsafe_allow_html=True)
        return

    n_crit = len(critical)
    n_warn = len(warnings)
    banner_c = RED if n_crit > 0 else YELLOW
    st.markdown(
        f"<div style='background:{banner_c}10;border:1px solid {banner_c}30;border-radius:8px;"
        f"padding:8px 16px;margin-bottom:8px;display:flex;align-items:center;gap:10px'>"
        f"<span style='font-size:20px;font-weight:700;color:{banner_c}'>GUARDIAN AI</span>"
        f"{_badge(str(n_crit) + ' critical', RED) if n_crit else ''}"
        f"{_badge(str(n_warn) + ' warnings', YELLOW) if n_warn else ''}"
        f"{_badge(str(len(assigns)) + ' crew assigned', CYAN) if assigns else ''}"
        f"<span style='font-size:18px;color:{MUTED};margin-left:auto'>See Guardian Advisor tab for details</span>"
        f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8 -- GUARDIAN ADVISOR (Chat)
# ═══════════════════════════════════════════════════════════════════════════════

def render_advisor(state: dict, agent: GuardianAgent):
    """Guardian Advisor — 2-column layout: live BOP sidebar + styled chat panel."""

    quick = None
    left, right = st.columns([3, 7])

    with left:
        # ── LIVE BOP STATUS (KPI grid) ──
        kpis = state["kpis"]
        rig_status = state["status"]
        sc = STATUS_COLORS.get(rig_status, MUTED)
        min_h = kpis["min_health"]
        hc = GREEN if min_h >= 0.8 else (YELLOW if min_h >= 0.6 else RED)
        n_anom = kpis["active_anomalies"]

        kpi_items = [
            ("Status", rig_status, sc),
            ("Min Health", f"{min_h:.0%}", hc),
            ("Anomalies", str(n_anom), RED if n_anom > 0 else GREEN),
            ("Healthy", f"{kpis['healthy_components']}/{kpis['total_components']}", GREEN),
            ("Depth MD", f"{kpis['depth_md']:.0f}", CYAN),
            ("Cycle", str(state["tick"]), MUTED),
        ]
        grid = "".join(
            f"<div style='background:{BG};border-radius:5px;padding:7px 9px;"
            f"border:1px solid {BORDER}'>"
            f"<div style='font-size:21px;font-weight:700;color:{c};font-family:monospace'>"
            f"{v}</div>"
            f"<div style='font-size:15px;color:{MUTED}'>{l}</div></div>"
            for l, v, c in kpi_items
        )
        st.markdown(
            f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
            f"padding:13px;margin-bottom:10px'>"
            f"<div style='font-size:15px;color:{CYAN};font-weight:700;letter-spacing:.08em;"
            f"margin-bottom:10px'>LIVE BOP STATUS</div>"
            f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px'>{grid}</div>"
            f"</div>", unsafe_allow_html=True)

        # ── COMPONENT HEALTH BARS ──
        bars = ""
        for aid, h in state["components"].items():
            hs = h["health_score"]
            hcolor = GREEN if hs >= 0.8 else (YELLOW if hs >= 0.6 else RED)
            name = h["component_type"].replace("_", " ")
            if len(name) > 14:
                name = name[:13]
            pct = int(hs * 100)
            dot = (f"<span style='display:inline-block;width:6px;height:6px;"
                   f"background:{RED};border-radius:50%;margin-left:3px'></span>"
                   if h["anomaly_flag"] else "")
            bars += (
                f"<div style='display:flex;align-items:center;gap:6px'>"
                f"<span style='font-size:14px;font-family:monospace;color:{MUTED};width:85px;"
                f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{name}</span>"
                f"<div style='flex:1;height:4px;background:{BG};border-radius:2px'>"
                f"<div style='width:{pct}%;height:100%;background:{hcolor};"
                f"border-radius:2px'></div></div>"
                f"<span style='font-size:14px;color:{hcolor};width:24px;text-align:right;"
                f"font-family:monospace'>{pct}</span>{dot}</div>"
            )
        st.markdown(
            f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
            f"padding:13px;margin-bottom:10px'>"
            f"<div style='font-size:15px;color:{CYAN};font-weight:700;letter-spacing:.08em;"
            f"margin-bottom:8px'>COMPONENT HEALTH</div>"
            f"<div style='display:flex;flex-direction:column;gap:4px'>{bars}</div>"
            f"</div>", unsafe_allow_html=True)

        # ── ACTIVE ALERTS ──
        critical = agent.get_critical_alerts()
        active_recs = agent.get_active_recommendations()
        warnings = [r for r in active_recs if r.severity == 2]
        alerts = (critical + warnings)[:4]
        if alerts:
            alert_html = ""
            for r in alerts:
                ac = RED if r.severity == 3 else YELLOW
                icon = "&#x1f534;" if r.severity == 3 else "&#x1f7e1;"
                alert_html += (
                    f"<div style='padding:5px 8px;background:{ac}10;border:1px solid {ac}33;"
                    f"border-radius:5px;font-size:15px;color:{ac};line-height:1.4'>"
                    f"{icon} {_html.escape(r.title)}</div>"
                )
            st.markdown(
                f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:10px;"
                f"padding:13px;margin-bottom:10px'>"
                f"<div style='font-size:15px;color:{CYAN};font-weight:700;letter-spacing:.08em;"
                f"margin-bottom:8px'>ACTIVE ALERTS</div>"
                f"<div style='display:flex;flex-direction:column;gap:5px'>{alert_html}</div>"
                f"</div>", unsafe_allow_html=True)

        # ── QUICK QUESTIONS ──
        st.markdown(
            f"<div style='font-size:15px;color:{CYAN};font-weight:700;letter-spacing:.08em;"
            f"margin:8px 0 6px'>QUICK QUESTIONS</div>", unsafe_allow_html=True)
        quick_qs = [
            ("Situation Report", "Give me a full situation report"),
            ("Critical Alerts", "What are the critical alerts and recommendations?"),
            ("Crew Status", "Show me BOP-qualified crew availability"),
            ("Spare Parts", "What is the spare parts inventory status?"),
            ("RUL Risks", "What are the failure risk predictions?"),
        ]
        for label, query in quick_qs:
            if st.button(label, key=f"qq_{label}", use_container_width=True):
                quick = query

    # Process quick action before rendering chat
    if quick:
        agent.state.chat_history.append({"role": "user", "content": quick})
        resp = agent.handle_query(quick, state)
        agent.state.chat_history.append({"role": "assistant", "content": resp})

    with right:
        # ── CHAT HEADER ──
        st.markdown(
            f"<div style='background:{PANEL};border:1px solid {BORDER};"
            f"border-radius:10px 10px 0 0;padding:11px 16px;"
            f"display:flex;align-items:center;gap:10px'>"
            f"<div style='width:32px;height:32px;background:{CYAN}15;border:1px solid {CYAN}55;"
            f"border-radius:50%;display:flex;align-items:center;justify-content:center;"
            f"font-size:24px'>&#x1f916;</div>"
            f"<div>"
            f"<div style='font-weight:700;font-size:21px;color:{TEXT}'>Guardian AI</div>"
            f"<div style='font-size:15px;color:{CYAN}'>{RIG_NAME} &middot; 5 agents active</div>"
            f"</div>"
            f"<div style='margin-left:auto'>{_badge('LIVE', GREEN)}</div>"
            f"</div>", unsafe_allow_html=True)

        # ── CHAT MESSAGES (fixed-height scrollable) ──
        chat_box = st.container(height=480)
        with chat_box:
            # Welcome message when empty
            if not agent.state.chat_history:
                st.markdown(
                    f"<div style='display:flex;flex-direction:column;align-items:flex-start;"
                    f"margin:8px 0'>"
                    f"<div style='max-width:85%;background:{PANEL};border:1px solid {BORDER};"
                    f"border-radius:2px 12px 12px 12px;padding:10px 13px'>"
                    f"<div style='font-size:14px;color:{CYAN};margin-bottom:5px;font-weight:700'>"
                    f"GUARDIAN AI</div>"
                    f"<div style='font-size:20px;line-height:1.7;color:{TEXT}'>"
                    f"Hello! I'm your BOP Guardian AI &mdash; monitoring all 10 BOP stack "
                    f"components, crew readiness, spare parts, and maintenance schedules "
                    f"in real-time. Ask me anything about the current rig status.</div>"
                    f"</div></div>", unsafe_allow_html=True)

            for msg in agent.state.chat_history:
                content = _md_to_html(msg["content"])
                if msg["role"] == "user":
                    st.markdown(
                        f"<div style='display:flex;flex-direction:column;align-items:flex-end;"
                        f"margin:8px 0'>"
                        f"<div style='max-width:85%;background:{CYAN}18;border:1px solid {CYAN}44;"
                        f"border-radius:12px 12px 2px 12px;padding:10px 13px'>"
                        f"<div style='font-size:20px;line-height:1.7;color:{CYAN}'>"
                        f"{content}</div>"
                        f"</div></div>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div style='display:flex;flex-direction:column;align-items:flex-start;"
                        f"margin:8px 0'>"
                        f"<div style='max-width:85%;background:{PANEL};border:1px solid {BORDER};"
                        f"border-radius:2px 12px 12px 12px;padding:10px 13px'>"
                        f"<div style='font-size:14px;color:{CYAN};margin-bottom:5px;font-weight:700'>"
                        f"GUARDIAN AI</div>"
                        f"<div style='font-size:20px;line-height:1.7;color:{TEXT}'>"
                        f"{content}</div>"
                        f"</div></div>", unsafe_allow_html=True)

        # ── CHAT INPUT ──
        if prompt := st.chat_input("Ask about BOP systems, crew, parts, RUL...", key="advisor_chat"):
            agent.state.chat_history.append({"role": "user", "content": prompt})
            resp = agent.handle_query(prompt, state)
            agent.state.chat_history.append({"role": "assistant", "content": resp})
            st.rerun()

    # ── AGENT RECOMMENDATIONS (full-width below sidebar + chat) ──
    all_critical = agent.get_critical_alerts()
    all_active = agent.get_active_recommendations()
    all_warnings = [r for r in all_active if r.severity == 2]
    rec_items = (all_critical + all_warnings)[:8]
    if rec_items:
        n_c = len(all_critical)
        n_w = len(all_warnings)
        label = f"Agent Recommendations — {n_c} critical, {n_w} warnings"
        with st.expander(label, expanded=n_c > 0):
            # Render cards in 2-column grid
            for row_start in range(0, len(rec_items), 2):
                cols = st.columns(2)
                for ci in range(2):
                    idx = row_start + ci
                    if idx >= len(rec_items):
                        break
                    r = rec_items[idx]
                    sev_c = RED if r.severity == 3 else YELLOW
                    sev_lbl = SEV_LABEL.get(r.severity, "INFO")
                    crew_str = ""
                    if r.assigned_crew:
                        crew_str = (
                            f"<div style='font-size:18px;color:{CYAN};margin-top:8px;"
                            f"padding-top:8px;border-top:1px solid {BORDER}'>"
                            f"&#x1f477; Assigned: {', '.join(_html.escape(c) for c in r.assigned_crew)}"
                            f"</div>"
                        )
                    actions_str = "".join(
                        f"<li style='margin-bottom:2px'>{_html.escape(a)}</li>"
                        for a in r.actions
                    )
                    with cols[ci]:
                        st.markdown(
                            f"<div style='background:{CARD};border-left:3px solid {sev_c};"
                            f"border:1px solid {BORDER};border-radius:8px;"
                            f"padding:12px 14px;height:100%'>"
                            f"<div style='display:flex;align-items:center;gap:8px;"
                            f"margin-bottom:8px;flex-wrap:wrap'>"
                            f"  {_badge(sev_lbl, sev_c)} {_badge(r.agent, PURPLE)}"
                            f"  <span style='font-size:16px;color:{MUTED}'>"
                            f"{_html.escape(r.asset_id)}</span>"
                            f"</div>"
                            f"<div style='font-size:21px;font-weight:600;color:{TEXT};"
                            f"margin-bottom:6px'>{_html.escape(r.title)}</div>"
                            f"<div style='font-size:18px;color:#94a3b8;line-height:1.5;"
                            f"margin-bottom:6px'>{_html.escape(r.detail)}</div>"
                            f"<ul style='font-size:18px;color:{TEXT};margin:0 0 0 18px;"
                            f"padding:0;line-height:1.6'>{actions_str}</ul>"
                            f"{crew_str}"
                            f"</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def render_app():
    st.set_page_config(
        page_title="BOP Guardian \u2014 Command Center",
        page_icon=str(Path(__file__).parent / "bop_icon.svg"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()

    # Header
    h1, h2, h3 = st.columns([1, 7, 2])
    with h1:
        st.image(str(Path(__file__).parent / "bop_icon.svg"), width=48)
    with h2:
        st.markdown(
            f"<div style='padding-top:4px'>"
            f"<span style='font-size:33px;font-weight:700;color:{TEXT}'>BOP GUARDIAN</span>"
            f"<span style='font-size:18px;color:{MUTED};margin-left:10px'>"
            f"Offshore BOP Monitoring Command Center | {RIG_NAME} | {WELL_NAME}</span>"
            f"</div>", unsafe_allow_html=True)
    with h3:
        st.markdown(
            f"<div style='text-align:right;padding-top:10px'>"
            f"<span class='live-badge'><span class='live-dot'></span>LIVE</span>"
            f"<span style='color:{MUTED};font-size:1.17rem;margin-left:10px'>"
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</span>"
            f"</div>", unsafe_allow_html=True)
    st.divider()

    if "tick" not in st.session_state:
        st.session_state.tick = 0
    if "agent" not in st.session_state:
        st.session_state.agent = GuardianAgent()
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "BOP Status"

    # ── Left sidebar navigation ─────────────────────────────
    NAV = [
        ("\U0001f6e1\ufe0f  BOP Status", "BOP Status"),
        ("\U0001f52c  Diagnostics", "Diagnostics"),
        ("\U0001f4ca  Predictive Maint.", "Predictive"),
        ("\U0001f6a8  Events & Anomalies", "Events"),
        ("\U0001f527  SAP ERP", "SAP ERP"),
        ("\U0001f477  Crew & Ops", "Crew & Ops"),
        ("\U0001f5fa\ufe0f  Data & AI Flow", "Data Flow"),
        ("\U0001f916  Guardian Advisor", "Advisor"),
    ]
    with st.sidebar:
        st.markdown(
            f"<div style='font-size:13px;color:{MUTED};text-transform:uppercase;"
            f"letter-spacing:2px;padding:0 14px 10px;font-weight:700'>Navigation</div>",
            unsafe_allow_html=True)
        for label, key in NAV:
            is_active = st.session_state.nav_page == key
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type=btn_type):
                st.session_state.nav_page = key
                st.rerun()

    # ── Live content fragment ────────────────────────────────
    @st.fragment(run_every=3)
    def _live():
        st.session_state.tick += 1
        state = simulate_tick()
        agent: GuardianAgent = st.session_state.agent
        agent.analyze_tick(state)

        render_agent_banner(agent)

        page = st.session_state.nav_page
        if page == "BOP Status":
            render_bop_status(state)
        elif page == "Diagnostics":
            render_diagnostics(state)
        elif page == "Predictive":
            render_rul()
        elif page == "Events":
            render_events()
        elif page == "SAP ERP":
            render_sap()
        elif page == "Crew & Ops":
            render_crew(state, agent)
        elif page == "Data Flow":
            render_dataflow()
        elif page == "Advisor":
            render_advisor(state, agent)

    _live()
