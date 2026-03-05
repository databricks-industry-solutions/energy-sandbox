"""
Pipeline Command Center — Midstream Pipeline Command Center UI
8-tab Streamlit dashboard with digital twin, dark HMI theme, live refresh.
"""

from __future__ import annotations

import re, html as _html
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from simulator import simulate_tick
from agent import PipelineGuardian, Recommendation
from mock_data import (
    ASSETS, SENSOR_DEFS, RUL_PREDICTIONS, FAILURE_PATTERNS,
    WORK_ORDERS, SPARE_PARTS, CREW, OPERATIONS_CYCLE,
)

# ── Colour Palette (Dark HMI) ─────────────────────────────────────
BG       = "#0B0F1A"
PANEL    = "#0f172a"
CARD     = "#1C2333"
BORDER   = "#1e293b"
TXT      = "#e2e8f0"
MUTED    = "#64748b"
CYAN     = "#00D4FF"
GREEN    = "#22c55e"
YELLOW   = "#eab308"
RED      = "#ef4444"
ORANGE   = "#f97316"
PURPLE   = "#a855f7"

NAV_ITEMS = [
    ("\U0001F6E2\uFE0F  Pipeline Overview",   "pipeline"),
    ("\U0001F50D  Diagnostics",               "diag"),
    ("\u2699\uFE0F  Predictive Maint.",        "rul"),
    ("\u26A0\uFE0F  Events & Alarms",          "events"),
    ("\U0001F4E1  SCADA / ERP",               "scada"),
    ("\U0001F477  Crew & Ops",                "crew"),
    ("\U0001F4CA  Data & AI Flow",            "dataflow"),
    ("\U0001F916  Pipeline Advisor",          "advisor"),
]

# ── CSS Injection ──────────────────────────────────────────────────

def _inject_css():
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"],
    .stApp, .main .block-container {{background-color:{BG}!important;color:{TXT}!important;}}
    [data-testid="stSidebar"] {{background-color:{PANEL}!important;border-right:1px solid {BORDER}!important;}}
    [data-testid="stSidebar"] * {{color:{TXT}!important;}}
    h1,h2,h3,h4,h5,h6 {{color:{TXT}!important;font-family:'JetBrains Mono',monospace!important;}}
    .stMarkdown, .stText, p, span, label, li {{color:{TXT}!important;}}
    .stButton > button {{background:{CARD}!important;color:{CYAN}!important;border:1px solid {BORDER}!important;
        font-family:'JetBrains Mono',monospace!important;border-radius:6px!important;}}
    .stButton > button:hover {{border-color:{CYAN}!important;}}
    .stTextInput > div > div > input, .stSelectbox > div > div,
    .stMultiSelect > div > div {{background:{CARD}!important;color:{TXT}!important;border-color:{BORDER}!important;}}
    .stChatMessage {{background:{CARD}!important;border:1px solid {BORDER}!important;border-radius:8px!important;}}
    div[data-testid="stMetric"] {{background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:12px 16px;}}
    div[data-testid="stMetric"] label {{color:{MUTED}!important;font-size:13px!important;}}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {{color:{TXT}!important;font-family:'JetBrains Mono',monospace!important;}}
    .kpi-card {{background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:14px 18px;text-align:center;}}
    .kpi-title {{color:{MUTED};font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}}
    .kpi-value {{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;}}
    .kpi-sub {{color:{MUTED};font-size:12px;margin-top:2px;}}
    .badge {{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;
        font-family:'JetBrains Mono',monospace;letter-spacing:0.5px;}}
    .badge-critical {{background:rgba(239,68,68,0.15);color:{RED};border:1px solid rgba(239,68,68,0.3);}}
    .badge-warning  {{background:rgba(234,179,8,0.15);color:{YELLOW};border:1px solid rgba(234,179,8,0.3);}}
    .badge-info     {{background:rgba(0,212,255,0.15);color:{CYAN};border:1px solid rgba(0,212,255,0.3);}}
    .badge-agent    {{background:rgba(168,85,247,0.15);color:{PURPLE};border:1px solid rgba(168,85,247,0.3);}}
    .rec-card {{background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:14px;margin-bottom:10px;}}
    .rec-title {{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:600;color:{TXT};margin:6px 0 4px;}}
    .rec-detail {{color:{MUTED};font-size:13px;}}
    .rec-actions {{margin-top:6px;padding-left:16px;}}
    .rec-actions li {{color:{TXT};font-size:13px;margin-bottom:2px;}}
    .crew-tag {{display:inline-block;background:rgba(34,197,94,0.12);color:{GREEN};border:1px solid rgba(34,197,94,0.3);
        border-radius:4px;padding:1px 6px;font-size:11px;margin-top:4px;margin-right:4px;}}
    .led-tile {{background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:10px 14px;}}
    .led-label {{color:{MUTED};font-size:11px;text-transform:uppercase;letter-spacing:0.8px;}}
    .led-value {{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;}}
    .led-bar {{height:4px;border-radius:2px;margin-top:4px;}}
    </style>""", unsafe_allow_html=True)


# ── Helper Components ──────────────────────────────────────────────

def _kpi(title: str, value: str, sub: str = "", color: str = CYAN):
    return f"""<div class="kpi-card">
        <div class="kpi-title">{_html.escape(title)}</div>
        <div class="kpi-value" style="color:{color}">{_html.escape(str(value))}</div>
        <div class="kpi-sub">{_html.escape(sub)}</div></div>"""


def _badge(label: str, kind: str = "info"):
    return f'<span class="badge badge-{kind}">{_html.escape(label)}</span>'


def _readout_tile(label: str, value: float, unit: str, lo: float, hi: float, color: str = CYAN):
    pct = max(0, min(100, (value - lo) / (hi - lo) * 100)) if hi != lo else 50
    bar_color = GREEN if pct < 70 else (YELLOW if pct < 90 else RED)
    return f"""<div class="led-tile">
        <div class="led-label">{_html.escape(label)}</div>
        <div class="led-value" style="color:{color}">{value:,.1f} <span style="font-size:12px;color:{MUTED}">{_html.escape(unit)}</span></div>
        <div class="led-bar" style="background:linear-gradient(90deg,{bar_color} {pct:.0f}%,{BORDER} {pct:.0f}%)"></div>
    </div>"""


def _gauge(title: str, value: float, lo: float, hi: float, unit: str = ""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 13, "color": MUTED}},
        number={"suffix": f" {unit}", "font": {"size": 20, "color": TXT}},
        gauge={
            "axis": {"range": [lo, hi], "tickcolor": MUTED, "tickfont": {"color": MUTED, "size": 10}},
            "bar": {"color": CYAN, "thickness": 0.3},
            "bgcolor": CARD,
            "bordercolor": BORDER,
            "steps": [
                {"range": [lo, lo + (hi - lo) * 0.6], "color": "rgba(34,197,94,0.10)"},
                {"range": [lo + (hi - lo) * 0.6, lo + (hi - lo) * 0.85], "color": "rgba(234,179,8,0.10)"},
                {"range": [lo + (hi - lo) * 0.85, hi], "color": "rgba(239,68,68,0.10)"},
            ],
        },
    ))
    fig.update_layout(
        height=160, margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)", font={"color": TXT},
    )
    return fig


def _health_color(h: float) -> str:
    if h >= 0.8:
        return GREEN
    if h >= 0.6:
        return YELLOW
    return RED


def _md_to_html(md: str) -> str:
    """Minimal markdown → HTML for chat bubbles."""
    t = _html.escape(md)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"^## (.+)$", r"<h4 style='color:#e2e8f0;margin:8px 0 4px'>\1</h4>", t, flags=re.M)
    t = re.sub(r"^### (.+)$", r"<h5 style='color:#e2e8f0;margin:6px 0 2px'>\1</h5>", t, flags=re.M)
    t = re.sub(r"^- (.+)$", r"<li style='margin-left:16px;color:#e2e8f0'>\1</li>", t, flags=re.M)
    t = t.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return t


# ── Digital Twin: Pipeline Schematic SVG ───────────────────────────

def _pipeline_svg(components: list[dict]) -> str:
    """Generate an industry-style pipeline schematic with live status."""
    comp_map = {c["asset_id"]: c for c in components}

    def _dot(aid: str) -> str:
        h = comp_map.get(aid, {}).get("health", 1.0)
        c = _health_color(h)
        pulse = ' class="pulse"' if h < 0.6 else ""
        return f'<circle r="6" fill="{c}"{pulse}><title>{aid} — {h:.0%}</title></circle>'

    def _press_label(aid: str, tag: str) -> str:
        r = comp_map.get(aid, {}).get("readings", {})
        v = r.get(tag, 0)
        return f'<text font-size="9" fill="{MUTED}" font-family="JetBrains Mono,monospace">{v:,.0f}</text>'

    def _health_bar(aid: str, x: int, y: int, w: int = 50) -> str:
        h = comp_map.get(aid, {}).get("health", 1.0)
        c = _health_color(h)
        fw = int(w * h)
        return (f'<rect x="{x}" y="{y}" width="{w}" height="5" rx="2" fill="{BORDER}"/>'
                f'<rect x="{x}" y="{y}" width="{fw}" height="5" rx="2" fill="{c}"/>')

    svg = f"""<svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
        style="width:100%;background:{PANEL};border-radius:10px;border:1px solid {BORDER};">
    <defs>
        <style>
            .pulse {{animation: glow 1.5s ease-in-out infinite alternate;}}
            @keyframes glow {{0%{{opacity:1}} 100%{{opacity:0.3}}}}
            .pipe {{stroke:{CYAN};stroke-width:4;fill:none;stroke-linecap:round;}}
            .pipe-bg {{stroke:{BORDER};stroke-width:6;fill:none;stroke-linecap:round;}}
            .flow-arrow {{fill:{CYAN};opacity:0.7;}}
            .label {{fill:{TXT};font-family:JetBrains Mono,monospace;font-size:11px;font-weight:600;}}
            .sub-label {{fill:{MUTED};font-family:JetBrains Mono,monospace;font-size:9px;}}
            .station-box {{fill:{CARD};stroke:{BORDER};stroke-width:1;rx:6;}}
            .station-box-alert {{fill:{CARD};stroke:{YELLOW};stroke-width:1.5;rx:6;}}
            .station-box-crit {{fill:{CARD};stroke:{RED};stroke-width:2;rx:6;}}
            .ico {{fill:none;stroke:{CYAN};stroke-width:1.2;stroke-linecap:round;stroke-linejoin:round;opacity:0.8;}}
            .ico-fill {{fill:{CYAN};opacity:0.15;stroke:{CYAN};stroke-width:1;}}
        </style>
        <!-- Pump icon: circle with impeller blades -->
        <symbol id="ico-pump" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="8" class="ico-fill"/>
            <circle cx="10" cy="10" r="8" class="ico"/>
            <line x1="10" y1="2" x2="10" y2="18" class="ico"/>
            <line x1="2" y1="10" x2="18" y2="10" class="ico"/>
            <line x1="4.3" y1="4.3" x2="15.7" y2="15.7" class="ico"/>
            <line x1="15.7" y1="4.3" x2="4.3" y2="15.7" class="ico"/>
        </symbol>
        <!-- Compressor icon: turbine fan -->
        <symbol id="ico-comp" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="8" class="ico-fill"/>
            <circle cx="10" cy="10" r="8" class="ico"/>
            <circle cx="10" cy="10" r="2.5" class="ico"/>
            <path d="M10 2 C12 6,14 8,10 10" class="ico"/>
            <path d="M18 10 C14 12,12 14,10 10" class="ico"/>
            <path d="M10 18 C8 14,6 12,10 10" class="ico"/>
            <path d="M2 10 C6 8,8 6,10 10" class="ico"/>
        </symbol>
        <!-- Meter icon: gauge dial -->
        <symbol id="ico-meter" viewBox="0 0 20 20">
            <path d="M3 14 A8 8 0 0 1 17 14" class="ico-fill"/>
            <path d="M3 14 A8 8 0 0 1 17 14" class="ico"/>
            <line x1="10" y1="14" x2="14" y2="6" class="ico" stroke-width="1.5"/>
            <circle cx="10" cy="14" r="1.5" class="ico"/>
            <line x1="3" y1="14" x2="17" y2="14" class="ico" stroke-dasharray="1,2"/>
        </symbol>
        <!-- Pig icon: bullet/capsule shape -->
        <symbol id="ico-pig" viewBox="0 0 20 20">
            <rect x="3" y="6" width="14" height="8" rx="4" class="ico-fill"/>
            <rect x="3" y="6" width="14" height="8" rx="4" class="ico"/>
            <line x1="8" y1="6" x2="8" y2="14" class="ico" stroke-dasharray="1.5,1.5"/>
            <line x1="12" y1="6" x2="12" y2="14" class="ico" stroke-dasharray="1.5,1.5"/>
            <polygon points="17,10 20,8 20,12" class="ico"/>
        </symbol>
        <!-- Valve icon: bowtie -->
        <symbol id="ico-valve" viewBox="0 0 20 20">
            <polygon points="2,4 10,10 2,16" class="ico-fill"/>
            <polygon points="18,4 10,10 18,16" class="ico-fill"/>
            <polygon points="2,4 10,10 2,16" class="ico"/>
            <polygon points="18,4 10,10 18,16" class="ico"/>
            <line x1="10" y1="10" x2="10" y2="2" class="ico" stroke-width="1.5"/>
            <line x1="7" y1="2" x2="13" y2="2" class="ico" stroke-width="1.5"/>
        </symbol>
        <!-- RTU/SCADA icon: antenna tower -->
        <symbol id="ico-rtu" viewBox="0 0 20 20">
            <line x1="10" y1="2" x2="10" y2="18" class="ico" stroke-width="1.5"/>
            <line x1="5" y1="18" x2="15" y2="18" class="ico"/>
            <line x1="6" y1="18" x2="10" y2="8" class="ico"/>
            <line x1="14" y1="18" x2="10" y2="8" class="ico"/>
            <path d="M5 5 A6 6 0 0 1 10 2" class="ico"/>
            <path d="M15 5 A6 6 0 0 0 10 2" class="ico"/>
            <path d="M7 7 A4 4 0 0 1 10 5" class="ico"/>
            <path d="M13 7 A4 4 0 0 0 10 5" class="ico"/>
        </symbol>
        <!-- CP icon: shield with lightning bolt -->
        <symbol id="ico-cp" viewBox="0 0 20 20">
            <path d="M10 1 L3 4 L3 10 C3 15,10 19,10 19 C10 19,17 15,17 10 L17 4 Z" class="ico-fill"/>
            <path d="M10 1 L3 4 L3 10 C3 15,10 19,10 19 C10 19,17 15,17 10 L17 4 Z" class="ico"/>
            <polyline points="11,5 8,11 12,11 9,17" class="ico" stroke-width="1.5" fill="none"/>
        </symbol>
        <!-- Pipeline segment icon: pipe cross-section -->
        <symbol id="ico-pipe" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="8" class="ico-fill"/>
            <circle cx="10" cy="10" r="8" class="ico"/>
            <circle cx="10" cy="10" r="5" class="ico" stroke-dasharray="2,2"/>
            <path d="M10 2 L10 5 M10 15 L10 18 M2 10 L5 10 M15 10 L18 10" class="ico"/>
        </symbol>
    </defs>

    <!-- Title -->
    <text x="480" y="28" text-anchor="middle" class="label" font-size="14" fill="{CYAN}">
        EAGLE FORD MIDSTREAM TRUNK — 87.3 mi — DIGITAL TWIN
    </text>
    <text x="480" y="42" text-anchor="middle" class="sub-label">
        Karnes County TX → Corpus Christi Terminal  |  24″ OD × 0.500″ WT — API 5L X65
    </text>

    <!-- ── MAIN PIPELINE (horizontal trunk) ── -->
    <line x1="60" y1="260" x2="900" y2="260" class="pipe-bg"/>
    <line x1="60" y1="260" x2="900" y2="260" class="pipe" stroke-dasharray="12,4">
        <animate attributeName="stroke-dashoffset" from="32" to="0" dur="2s" repeatCount="indefinite"/>
    </line>

    <!-- Flow arrows -->
    <polygon points="240,253 252,260 240,267" class="flow-arrow"/>
    <polygon points="480,253 492,260 480,267" class="flow-arrow"/>
    <polygon points="720,253 732,260 720,267" class="flow-arrow"/>

    <!-- Mile markers -->
    <text x="60"  y="280" class="sub-label" text-anchor="middle">MP 0</text>
    <text x="260" y="280" class="sub-label" text-anchor="middle">MP 18.5</text>
    <text x="540" y="280" class="sub-label" text-anchor="middle">MP 52</text>
    <text x="900" y="280" class="sub-label" text-anchor="middle">MP 87.3</text>

    <!-- ── INLET TERMINAL (left) ── -->
    <rect x="20" y="70" width="120" height="160" class="{"station-box-crit" if comp_map.get("PS-01",{}).get("health",1)<0.6 else "station-box"}"/>
    <text x="80" y="88" text-anchor="middle" class="label" fill="{CYAN}">INLET TERMINAL</text>

    <!-- Pig Launcher -->
    <rect x="32" y="96" width="96" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-pig" x="34" y="100" width="14" height="14"/>
    <text x="84" y="114" text-anchor="middle" class="sub-label">PIG-01 Launcher</text>
    <g transform="translate(110,108)">{_dot("PIG-01")}</g>

    <!-- Pump Station 1 -->
    <rect x="32" y="130" width="96" height="36" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-pump" x="34" y="134" width="16" height="16"/>
    <text x="84" y="146" text-anchor="middle" class="sub-label">PS-01 Booster</text>
    <g transform="translate(110,152)">{_dot("PS-01")}</g>
    {_health_bar("PS-01", 36, 158, 88)}

    <!-- Meter Inlet -->
    <rect x="32" y="172" width="96" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-meter" x="34" y="174" width="14" height="14"/>
    <text x="84" y="190" text-anchor="middle" class="sub-label">MET-01 Custody</text>
    <g transform="translate(110,186)">{_dot("MET-01")}</g>

    <!-- RTU-01 -->
    <rect x="32" y="206" width="96" height="20" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-rtu" x="34" y="207" width="12" height="12"/>
    <text x="84" y="220" text-anchor="middle" class="sub-label">RTU-01 SCADA</text>
    <g transform="translate(110,216)">{_dot("RTU-01")}</g>

    <!-- Connector to trunk -->
    <line x1="80" y1="230" x2="80" y2="260" class="pipe" stroke-width="2"/>

    <!-- ── SEGMENT 1 ── -->
    <rect x="155" y="290" width="100" height="50" class="{"station-box-alert" if comp_map.get("SEG-01",{}).get("health",1)<0.8 else "station-box"}"/>
    <use href="#ico-pipe" x="157" y="294" width="14" height="14"/>
    <text x="210" y="308" text-anchor="middle" class="label" font-size="10">SEG-01</text>
    <text x="205" y="320" text-anchor="middle" class="sub-label">Gathering 16″</text>
    <g transform="translate(205,335)">{_dot("SEG-01")}</g>
    {_health_bar("SEG-01", 165, 340, 80)}

    <!-- ── COMPRESSOR STATION ALPHA (top) ── -->
    <rect x="210" y="70" width="130" height="140" class="{"station-box-crit" if comp_map.get("CS-01",{}).get("health",1)<0.6 else "station-box"}"/>
    <text x="275" y="88" text-anchor="middle" class="label" fill="{CYAN}">CS ALPHA</text>

    <rect x="222" y="96" width="106" height="36" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-comp" x="224" y="100" width="16" height="16"/>
    <text x="280" y="112" text-anchor="middle" class="sub-label">CS-01 Compressor</text>
    <g transform="translate(312,118)">{_dot("CS-01")}</g>
    {_health_bar("CS-01", 226, 126, 98)}

    <!-- VLV-01 -->
    <rect x="222" y="140" width="106" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-valve" x="224" y="143" width="14" height="14"/>
    <text x="280" y="158" text-anchor="middle" class="sub-label">VLV-01 Block Valve</text>
    <g transform="translate(312,154)">{_dot("VLV-01")}</g>

    <!-- CP System -->
    <rect x="222" y="174" width="106" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-cp" x="224" y="176" width="14" height="14"/>
    <text x="280" y="192" text-anchor="middle" class="sub-label">CP-01 Cathodic Prot.</text>
    <g transform="translate(312,188)">{_dot("CP-01")}</g>

    <!-- Connector -->
    <line x1="275" y1="210" x2="275" y2="260" class="pipe" stroke-width="2"/>

    <!-- ── SEGMENT 2 ── -->
    <rect x="365" y="290" width="100" height="50" class="{"station-box-crit" if comp_map.get("SEG-02",{}).get("health",1)<0.6 else ("station-box-alert" if comp_map.get("SEG-02",{}).get("health",1)<0.8 else "station-box")}"/>
    <use href="#ico-pipe" x="367" y="294" width="14" height="14"/>
    <text x="420" y="308" text-anchor="middle" class="label" font-size="10">SEG-02</text>
    <text x="415" y="320" text-anchor="middle" class="sub-label">Trunk 24″ (33.5 mi)</text>
    <g transform="translate(415,335)">{_dot("SEG-02")}</g>
    {_health_bar("SEG-02", 375, 340, 80)}

    <!-- ── MIDPOINT STATION ── -->
    <rect x="470" y="70" width="140" height="160" class="{"station-box-crit" if comp_map.get("PS-02",{}).get("health",1)<0.6 else "station-box"}"/>
    <text x="540" y="88" text-anchor="middle" class="label" fill="{CYAN}">MIDPOINT STATION</text>

    <rect x="482" y="96" width="116" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-comp" x="484" y="100" width="14" height="14"/>
    <text x="545" y="114" text-anchor="middle" class="sub-label">CS-02 Compressor</text>
    <g transform="translate(582,108)">{_dot("CS-02")}</g>

    <rect x="482" y="130" width="116" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-pump" x="484" y="133" width="14" height="14"/>
    <text x="545" y="148" text-anchor="middle" class="sub-label">PS-02 Mainline Pump</text>
    <g transform="translate(582,144)">{_dot("PS-02")}</g>
    {_health_bar("PS-02", 486, 152, 108)}

    <rect x="482" y="164" width="116" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-valve" x="484" y="167" width="14" height="14"/>
    <text x="545" y="182" text-anchor="middle" class="sub-label">VLV-02 Block Valve</text>
    <g transform="translate(582,178)">{_dot("VLV-02")}</g>

    <rect x="482" y="198" width="116" height="24" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-rtu" x="484" y="200" width="12" height="12"/>
    <text x="545" y="214" text-anchor="middle" class="sub-label">RTU-02 SCADA</text>
    <g transform="translate(582,210)">{_dot("RTU-02")}</g>

    <!-- Connector -->
    <line x1="540" y1="228" x2="540" y2="260" class="pipe" stroke-width="2"/>

    <!-- ── SEGMENT 3 ── -->
    <rect x="640" y="290" width="100" height="50" class="{"station-box-alert" if comp_map.get("SEG-03",{}).get("health",1)<0.8 else "station-box"}"/>
    <use href="#ico-pipe" x="642" y="294" width="14" height="14"/>
    <text x="695" y="308" text-anchor="middle" class="label" font-size="10">SEG-03</text>
    <text x="690" y="320" text-anchor="middle" class="sub-label">Trunk 24″ (35.3 mi)</text>
    <g transform="translate(690,335)">{_dot("SEG-03")}</g>
    {_health_bar("SEG-03", 650, 340, 80)}

    <!-- ── DELIVERY TERMINAL (right) ── -->
    <rect x="810" y="70" width="130" height="160" class="station-box"/>
    <text x="875" y="88" text-anchor="middle" class="label" fill="{CYAN}">DELIVERY TERMINAL</text>

    <!-- VLV-03 -->
    <rect x="822" y="96" width="106" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-valve" x="824" y="99" width="14" height="14"/>
    <text x="880" y="114" text-anchor="middle" class="sub-label">VLV-03 Block Valve</text>
    <g transform="translate(912,108)">{_dot("VLV-03")}</g>

    <!-- Meter Delivery -->
    <rect x="822" y="130" width="106" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-meter" x="824" y="132" width="14" height="14"/>
    <text x="880" y="148" text-anchor="middle" class="sub-label">MET-02 Custody</text>
    <g transform="translate(912,144)">{_dot("MET-02")}</g>

    <!-- Pig Receiver -->
    <rect x="822" y="164" width="106" height="28" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-pig" x="824" y="167" width="14" height="14"/>
    <text x="880" y="182" text-anchor="middle" class="sub-label">PIG-02 Receiver</text>
    <g transform="translate(912,178)">{_dot("PIG-02")}</g>

    <!-- RTU-03 -->
    <rect x="822" y="198" width="106" height="24" rx="4" fill="{PANEL}" stroke="{BORDER}"/>
    <use href="#ico-rtu" x="824" y="200" width="12" height="12"/>
    <text x="880" y="214" text-anchor="middle" class="sub-label">RTU-03 SCADA</text>
    <g transform="translate(912,210)">{_dot("RTU-03")}</g>

    <!-- Connector -->
    <line x1="875" y1="228" x2="875" y2="260" class="pipe" stroke-width="2"/>

    <!-- ── Legend ── -->
    <g transform="translate(60,400)">
        <text class="label" font-size="11" fill="{CYAN}">LEGEND</text>
        <circle cx="10" cy="20" r="5" fill="{GREEN}"/><text x="20" y="24" class="sub-label">Health ≥ 80%</text>
        <circle cx="110" cy="20" r="5" fill="{YELLOW}"/><text x="120" y="24" class="sub-label">Health 60-80%</text>
        <circle cx="230" cy="20" r="5" fill="{RED}"/><text x="240" y="24" class="sub-label">Health &lt; 60%</text>
        <line x1="320" y1="20" x2="370" y2="20" class="pipe" stroke-width="3"/>
        <text x="380" y="24" class="sub-label">Flow direction →</text>
        <!-- Asset type icons -->
        <use href="#ico-pump" x="2" y="32" width="12" height="12"/><text x="18" y="42" class="sub-label">Pump</text>
        <use href="#ico-comp" x="62" y="32" width="12" height="12"/><text x="78" y="42" class="sub-label">Compressor</text>
        <use href="#ico-valve" x="152" y="32" width="12" height="12"/><text x="168" y="42" class="sub-label">Valve</text>
        <use href="#ico-meter" x="212" y="32" width="12" height="12"/><text x="228" y="42" class="sub-label">Meter</text>
        <use href="#ico-pig" x="272" y="32" width="12" height="12"/><text x="288" y="42" class="sub-label">Pig Tool</text>
        <use href="#ico-rtu" x="342" y="32" width="12" height="12"/><text x="358" y="42" class="sub-label">SCADA RTU</text>
        <use href="#ico-cp" x="422" y="32" width="12" height="12"/><text x="438" y="42" class="sub-label">Cathodic Prot.</text>
        <use href="#ico-pipe" x="522" y="32" width="12" height="12"/><text x="538" y="42" class="sub-label">Pipe Segment</text>
    </g>

    <!-- Throughput readout -->
    <g transform="translate(650,400)">
        <rect width="240" height="45" rx="6" fill="{PANEL}" stroke="{BORDER}"/>
        <text x="120" y="18" text-anchor="middle" class="sub-label">THROUGHPUT</text>
        <text x="120" y="37" text-anchor="middle" class="label" font-size="18" fill="{CYAN}">
            {comp_map.get("MET-01",{}).get("readings",{}).get("FLOW",8500):,.0f} bbl/h
        </text>
    </g>

    <!-- Pipeline status badge -->
    <g transform="translate(60,460)">
        <rect width="840" height="30" rx="6" fill="{PANEL}" stroke="{BORDER}"/>
        <text x="420" y="20" text-anchor="middle" class="label" font-size="11">
            STATUS: {comp_map.get("SEG-01",{}).get("health",1) + comp_map.get("SEG-02",{}).get("health",1) + comp_map.get("SEG-03",{}).get("health",1) > 2.4 and "NORMAL" or (comp_map.get("SEG-01",{}).get("health",1) + comp_map.get("SEG-02",{}).get("health",1) + comp_map.get("SEG-03",{}).get("health",1) > 1.8 and "WATCH" or "ACT NOW")}
            — 18 assets monitored — {sum(1 for c in components if c.get("health",1)<0.8)} assets with alerts
        </text>
    </g>

    </svg>"""
    return svg


# ── Data & AI Flow Diagram ─────────────────────────────────────────

def _dataflow_html() -> str:
    return r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html{background:#0B0F1A}
body{background:#0B0F1A;margin:0 auto;max-width:960px;padding:4px}
@keyframes fd{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}
.fd{animation:fd 1.6s linear infinite}
</style></head><body>
<svg viewBox="0 0 860 430" style="width:100%;height:auto;display:block" xmlns="http://www.w3.org/2000/svg">
<defs>
  <!-- Lakeflow-style gradient fills -->
  <linearGradient id="gBlue" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#3b82f6" stop-opacity=".22"/>
    <stop offset="100%" stop-color="#3b82f6" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gOrange" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#f97316" stop-opacity=".22"/>
    <stop offset="100%" stop-color="#f97316" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gTeal" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#14b8a6" stop-opacity=".22"/>
    <stop offset="100%" stop-color="#14b8a6" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gPurple" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#8b5cf6" stop-opacity=".22"/>
    <stop offset="100%" stop-color="#8b5cf6" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gBronze" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#cd7f32" stop-opacity=".25"/>
    <stop offset="100%" stop-color="#cd7f32" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gSilver" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#c0c0c0" stop-opacity=".2"/>
    <stop offset="100%" stop-color="#c0c0c0" stop-opacity=".06"/>
  </linearGradient>
  <linearGradient id="gGold" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#ffd700" stop-opacity=".22"/>
    <stop offset="100%" stop-color="#ffd700" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gGreen" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#22c55e" stop-opacity=".22"/>
    <stop offset="100%" stop-color="#22c55e" stop-opacity=".08"/>
  </linearGradient>
  <linearGradient id="gCyan" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#00d4ff" stop-opacity=".2"/>
    <stop offset="100%" stop-color="#00d4ff" stop-opacity=".06"/>
  </linearGradient>
  <!-- Arrow markers -->
  <marker id="a1" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3z" fill="#3b82f6"/></marker>
  <marker id="a3" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3z" fill="#14b8a6"/></marker>
  <marker id="a4" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3z" fill="#8b5cf6"/></marker>
  <marker id="a5" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3z" fill="#22c55e"/></marker>
  <!-- Drop shadow filter -->
  <filter id="ds" x="-4%" y="-4%" width="108%" height="116%">
    <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000" flood-opacity=".35"/>
  </filter>
</defs>

<!-- Row labels -->
<text x="12" y="22" fill="#64748b" font-size="11" font-weight="700" font-family="sans-serif" letter-spacing=".5">SOURCES</text>
<text x="12" y="150" fill="#64748b" font-size="11" font-weight="700" font-family="sans-serif" letter-spacing=".5">PLATFORM / MEDALLION</text>
<text x="12" y="335" fill="#64748b" font-size="11" font-weight="700" font-family="sans-serif" letter-spacing=".5">SERVING / AGENTS</text>

<!-- SDP wrapper -->
<rect x="200" y="138" width="530" height="36" rx="6" fill="none" stroke="#FF6B35" stroke-width="1" stroke-dasharray="5 3" stroke-opacity=".5"/>
<rect x="206" y="131" width="195" height="14" rx="3" fill="#0B0F1A"/>
<text x="210" y="141" fill="#FF6B35" font-size="10" font-weight="700" font-family="sans-serif">Spark Declarative Pipelines (SDP)</text>

<!-- Unity Catalog governance box -->
<rect x="190" y="128" width="660" height="155" rx="8" fill="none" stroke="#f97316" stroke-width="1" stroke-dasharray="5 3" stroke-opacity=".35"/>
<rect x="680" y="121" width="164" height="14" rx="3" fill="#0B0F1A"/>
<text x="684" y="131" fill="#f97316" font-size="10" font-weight="700" font-family="sans-serif">Unity Catalog Governance</text>

<!-- ═══ SOURCE NODES (Lakeflow filled style) ═══ -->
<g filter="url(#ds)">
  <rect x="15" y="34" width="150" height="48" rx="8" fill="url(#gBlue)" stroke="#3b82f6" stroke-width="1.5"/>
  <rect x="15" y="34" width="150" height="4" rx="8" fill="#3b82f6" opacity=".6"/>
  <text x="90" y="55" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">SCADA / OPC-UA</text>
  <text x="90" y="70" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">18 assets · 65+ tags</text>
</g>

<g filter="url(#ds)">
  <rect x="180" y="34" width="130" height="48" rx="8" fill="url(#gOrange)" stroke="#f97316" stroke-width="1.5"/>
  <rect x="180" y="34" width="130" height="4" rx="8" fill="#f97316" opacity=".6"/>
  <text x="245" y="55" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">SAP PM / CMMS</text>
  <text x="245" y="70" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">Work orders · spares</text>
</g>

<g filter="url(#ds)">
  <rect x="325" y="34" width="130" height="48" rx="8" fill="url(#gTeal)" stroke="#14b8a6" stroke-width="1.5"/>
  <rect x="325" y="34" width="130" height="4" rx="8" fill="#14b8a6" opacity=".6"/>
  <text x="390" y="55" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">Crew Systems</text>
  <text x="390" y="70" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">Certs · zones · shifts</text>
</g>

<g filter="url(#ds)">
  <rect x="470" y="34" width="130" height="48" rx="8" fill="url(#gPurple)" stroke="#8b5cf6" stroke-width="1.5"/>
  <rect x="470" y="34" width="130" height="4" rx="8" fill="#8b5cf6" opacity=".6"/>
  <text x="535" y="55" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">ILI / CP Surveys</text>
  <text x="535" y="70" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">Corrosion · cathodic</text>
</g>

<!-- ═══ MEDALLION NODES ═══ -->
<g filter="url(#ds)">
  <rect x="220" y="180" width="110" height="46" rx="8" fill="url(#gBronze)" stroke="#cd7f32" stroke-width="1.5"/>
  <rect x="220" y="180" width="110" height="4" rx="8" fill="#cd7f32" opacity=".6"/>
  <text x="275" y="201" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">Bronze</text>
  <text x="275" y="215" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">Raw ingest</text>
</g>

<g filter="url(#ds)">
  <rect x="365" y="180" width="110" height="46" rx="8" fill="url(#gSilver)" stroke="#c0c0c0" stroke-width="1.5"/>
  <rect x="365" y="180" width="110" height="4" rx="8" fill="#c0c0c0" opacity=".5"/>
  <text x="420" y="201" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">Silver</text>
  <text x="420" y="215" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">Cleaned · enriched</text>
</g>

<g filter="url(#ds)">
  <rect x="510" y="180" width="110" height="46" rx="8" fill="url(#gGold)" stroke="#ffd700" stroke-width="1.5"/>
  <rect x="510" y="180" width="110" height="4" rx="8" fill="#ffd700" opacity=".5"/>
  <text x="565" y="201" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">Gold</text>
  <text x="565" y="215" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">KPIs · features</text>
</g>

<!-- ML Node -->
<g filter="url(#ds)">
  <rect x="670" y="180" width="140" height="46" rx="8" fill="url(#gPurple)" stroke="#8b5cf6" stroke-width="1.5"/>
  <rect x="670" y="180" width="140" height="4" rx="8" fill="#8b5cf6" opacity=".6"/>
  <text x="740" y="201" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700" font-family="sans-serif">ML / MLflow</text>
  <text x="740" y="215" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="sans-serif">Anomaly + RUL</text>
</g>

<!-- ═══ SERVING NODES ═══ -->
<g filter="url(#ds)">
  <rect x="220" y="244" width="110" height="36" rx="8" fill="url(#gTeal)" stroke="#14b8a6" stroke-width="1.5"/>
  <rect x="220" y="244" width="110" height="4" rx="8" fill="#14b8a6" opacity=".6"/>
  <text x="275" y="267" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="700" font-family="sans-serif">Lakebase</text>
</g>

<g filter="url(#ds)">
  <rect x="365" y="244" width="130" height="36" rx="8" fill="url(#gGreen)" stroke="#22c55e" stroke-width="1.5"/>
  <rect x="365" y="244" width="130" height="4" rx="8" fill="#22c55e" opacity=".5"/>
  <text x="430" y="267" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="700" font-family="sans-serif">Streamlit App</text>
</g>

<!-- ═══ AGENT LAYER ═══ -->
<g filter="url(#ds)">
  <rect x="20" y="352" width="120" height="42" rx="8" fill="url(#gCyan)" stroke="#00d4ff" stroke-width="1.5"/>
  <rect x="20" y="352" width="120" height="4" rx="8" fill="#00d4ff" opacity=".5"/>
  <text x="80" y="372" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="700" font-family="sans-serif">Health Agent</text>
  <text x="80" y="385" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="sans-serif">Anomaly severity</text>
</g>

<g filter="url(#ds)">
  <rect x="155" y="352" width="130" height="42" rx="8" fill="url(#gCyan)" stroke="#00d4ff" stroke-width="1.5"/>
  <rect x="155" y="352" width="130" height="4" rx="8" fill="#00d4ff" opacity=".5"/>
  <text x="220" y="372" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="700" font-family="sans-serif">Integrity Agent</text>
  <text x="220" y="385" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="sans-serif">Corrosion + RUL</text>
</g>

<g filter="url(#ds)">
  <rect x="300" y="352" width="130" height="42" rx="8" fill="url(#gCyan)" stroke="#00d4ff" stroke-width="1.5"/>
  <rect x="300" y="352" width="130" height="4" rx="8" fill="#00d4ff" opacity=".5"/>
  <text x="365" y="372" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="700" font-family="sans-serif">Leak Detect</text>
  <text x="365" y="385" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="sans-serif">Flow imbalance</text>
</g>

<g filter="url(#ds)">
  <rect x="445" y="352" width="130" height="42" rx="8" fill="url(#gCyan)" stroke="#00d4ff" stroke-width="1.5"/>
  <rect x="445" y="352" width="130" height="4" rx="8" fill="#00d4ff" opacity=".5"/>
  <text x="510" y="372" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="700" font-family="sans-serif">Crew Allocator</text>
  <text x="510" y="385" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="sans-serif">Skill-based dispatch</text>
</g>

<g filter="url(#ds)">
  <rect x="590" y="352" width="130" height="42" rx="8" fill="url(#gCyan)" stroke="#00d4ff" stroke-width="1.5"/>
  <rect x="590" y="352" width="130" height="4" rx="8" fill="#00d4ff" opacity=".5"/>
  <text x="655" y="372" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="700" font-family="sans-serif">Compliance</text>
  <text x="655" y="385" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="sans-serif">PHMSA · NACE · DOT</text>
</g>

<!-- ═══ EDGES ═══ -->
<!-- Sources -> Bronze -->
<path d="M90,82 L90,118 L275,118 L275,180" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M90,82 L90,118 L275,118 L275,180" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:0s"/>
<path d="M245,82 L245,118 L280,118" fill="none" stroke="#f97316" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M245,82 L245,118 L280,118" fill="none" stroke="#f97316" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.2s"/>
<path d="M390,82 L390,118 L285,118 L285,180" fill="none" stroke="#14b8a6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M390,82 L390,118 L285,118 L285,180" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.4s"/>
<path d="M535,82 L535,118 L290,118 L290,180" fill="none" stroke="#8b5cf6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M535,82 L535,118 L290,118 L290,180" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.5s"/>

<!-- Bronze -> Silver -> Gold (SDP) -->
<path d="M330,203 L365,203" fill="none" stroke="#c0c0c0" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M330,203 L365,203" fill="none" stroke="#c0c0c0" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.6s"/>
<path d="M475,203 L510,203" fill="none" stroke="#ffd700" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M475,203 L510,203" fill="none" stroke="#ffd700" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.8s"/>

<!-- Gold -> ML -->
<path d="M620,203 L670,203" fill="none" stroke="#8b5cf6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M620,203 L670,203" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:1s"/>
<path d="M620,203 L670,203" fill="none" stroke="none" marker-end="url(#a4)"/>

<!-- Gold -> Lakebase -->
<path d="M565,226 L565,236 L275,236 L275,244" fill="none" stroke="#14b8a6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M565,226 L565,236 L275,236 L275,244" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.9s"/>
<path d="M565,226 L565,236 L275,236 L275,244" fill="none" stroke="none" marker-end="url(#a3)"/>

<!-- Lakebase -> Streamlit -->
<path d="M330,262 L365,262" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M330,262 L365,262" fill="none" stroke="#22c55e" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:1.1s"/>
<path d="M330,262 L365,262" fill="none" stroke="none" marker-end="url(#a5)"/>

<!-- Streamlit -> Agent Layer -->
<path d="M430,280 L430,325 L365,325 L365,352" fill="none" stroke="#00d4ff" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
<path d="M430,280 L430,325 L365,325 L365,352" fill="none" stroke="#00d4ff" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:1.2s"/>
<path d="M430,280 L430,325 L80,325 L80,352" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>
<path d="M430,280 L430,325 L220,325 L220,352" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>
<path d="M430,280 L430,325 L510,325 L510,352" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>
<path d="M430,280 L430,325 L655,325 L655,352" fill="none" stroke="#00d4ff" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".15"/>

<!-- Edge labels -->
<text x="160" y="112" text-anchor="middle" fill="#3b82f6" font-size="10" font-family="sans-serif">IoT stream</text>
<text x="348" y="197" text-anchor="middle" fill="#FF6B35" font-size="10" font-family="sans-serif">SDP</text>
<text x="492" y="197" text-anchor="middle" fill="#FF6B35" font-size="10" font-family="sans-serif">SDP</text>
<text x="645" y="197" text-anchor="middle" fill="#8b5cf6" font-size="10" font-family="sans-serif">features</text>
<text x="348" y="256" text-anchor="middle" fill="#22c55e" font-size="10" font-family="sans-serif">JDBC</text>

<!-- Divider -->
<line x1="12" y1="318" x2="848" y2="318" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
</svg>
</body></html>"""


# ── Recommendation Card Renderer ───────────────────────────────────

def _render_rec_card(rec: Recommendation):
    sev_badge = _badge(rec.severity_label, "critical" if rec.severity == 3 else "warning" if rec.severity == 2 else "info")
    agent_badge = _badge(rec.agent, "agent")
    crew_html = ""
    if rec.crew:
        crew_items = []
        for ca in rec.crew:
            role_tag = f'<span style="color:{ORANGE};font-size:10px;font-weight:600">[{_html.escape(ca.role)}]</span> ' if ca.role else ""
            score_tag = f' <span style="color:{MUTED};font-size:10px">score:{ca.skill_score}</span>' if ca.skill_score else ""
            reasoning_tag = (
                f'<br><span style="color:{MUTED};font-size:10px;font-style:italic;margin-left:4px">'
                f'{_html.escape(ca.reasoning)}</span>'
            ) if ca.reasoning else ""
            crew_items.append(
                f'<div style="margin-top:4px">'
                f'{role_tag}<span class="crew-tag">{_html.escape(ca.crew_name)}</span>'
                f' → {ca.eta_min}min ({_html.escape(ca.cert_reason)}){score_tag}'
                f'{reasoning_tag}</div>'
            )
        crew_html = (
            f'<div style="margin-top:6px;padding:6px 8px;background:rgba(0,212,255,0.06);'
            f'border-left:2px solid {CYAN};border-radius:0 4px 4px 0">'
            f'<span style="color:{CYAN};font-size:11px;font-weight:700">AI CREW DISPATCH</span>'
            + "".join(crew_items) + '</div>'
        )
    actions_html = "".join(f"<li>{_html.escape(a)}</li>" for a in rec.actions)
    st.markdown(f"""<div class="rec-card">
        {sev_badge} {agent_badge} <span style="color:{MUTED};font-size:11px;margin-left:8px">{_html.escape(rec.asset_id)}</span>
        <div class="rec-title">{_html.escape(rec.title)}</div>
        <div class="rec-detail">{_html.escape(rec.detail)}</div>
        <ul class="rec-actions">{actions_html}</ul>
        {crew_html}
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  PAGE RENDERERS
# ══════════════════════════════════════════════════════════════════

def _render_pipeline_overview(state: dict, agent_obj: PipelineGuardian):
    """Tab 1 — Pipeline Overview (Digital Twin)"""
    kpis = state["kpis"]
    cols = st.columns(6)
    items = [
        ("AVG HEALTH",       f"{kpis['avg_health']:.0%}",        "",               _health_color(kpis["avg_health"])),
        ("THROUGHPUT",       f"{kpis['throughput_bblh']:,}",      "bbl/h",          CYAN),
        ("UPTIME",           f"{kpis['uptime_pct']}%",           "",                GREEN),
        ("ANOMALIES",        str(kpis["active_anomalies"]),       "active",         YELLOW if kpis["active_anomalies"] else GREEN),
        ("WORK ORDERS",      str(kpis["open_work_orders"]),       "open",           ORANGE),
        ("OPERATION",        state["current_op"]["op"],           state["current_op"]["risk"], CYAN),
    ]
    for c, (t, v, s, clr) in zip(cols, items):
        c.markdown(_kpi(t, v, s, clr), unsafe_allow_html=True)

    # Digital Twin SVG
    svg = _pipeline_svg(state["components"])
    st.components.v1.html(
        f"<html><head><style>html{{background:{BG}}}body{{margin:0;width:100%}}</style></head>"
        f"<body>{svg}</body></html>",
        height=855, scrolling=False,
    )

    # Status bar with crew allocation
    status = state["status"]
    sc = GREEN if status == "NORMAL" else (YELLOW if status == "WATCH" else RED)
    border_clr = f"{sc}40" if status == "NORMAL" else (f"{YELLOW}50" if status == "WATCH" else f"{RED}60")

    # Build crew dispatch section for non-NORMAL status
    crew_html = ""
    if status != "NORMAL":
        recent_recs = agent_obj.state.recommendations[-10:]
        # Get critical/warning recs with crew
        active_crews: list[tuple] = []
        seen = set()
        for rec in reversed(recent_recs):
            if rec.crew and rec.severity >= 2:
                for ca in rec.crew:
                    key = f"{ca.crew_name}|{ca.asset_id}"
                    if key not in seen:
                        seen.add(key)
                        sev_clr = RED if rec.severity == 3 else YELLOW
                        active_crews.append((ca, rec.severity, sev_clr))
        if active_crews:
            crew_tags = []
            for ca, sev, sev_clr in active_crews[:5]:
                sev_dot = f'<span style="color:{sev_clr};font-size:10px">{"●" if sev == 3 else "▲"}</span>'
                role_str = f' [{ca.role}]' if ca.role else ''
                crew_tags.append(
                    f'<span style="display:inline-block;background:rgba(0,212,255,0.08);'
                    f'border:1px solid rgba(0,212,255,0.25);border-radius:4px;padding:2px 8px;'
                    f'margin:2px 3px;font-size:11px;color:{TXT}">'
                    f'{sev_dot} <b>{_html.escape(ca.crew_name)}</b>'
                    f'<span style="color:{CYAN}">{_html.escape(role_str)}</span>'
                    f' → <span style="color:{sev_clr};font-weight:600">{_html.escape(ca.asset_id)}</span>'
                    f' <span style="color:{MUTED}">ETA {ca.eta_min}min</span></span>'
                )
            crew_html = (
                f'<div style="margin-top:6px;padding-top:6px;border-top:1px solid {BORDER}">'
                f'<span style="color:{CYAN};font-size:10px;font-weight:700;letter-spacing:.5px">'
                f'AI CREW DISPATCH</span> '
                + "".join(crew_tags)
                + '</div>'
            )

    st.markdown(
        f'<div style="padding:8px 12px;background:{PANEL};border:1px solid {border_clr};border-radius:6px;'
        f'border-left:3px solid {sc}">'
        f'<div style="text-align:center">'
        f'<span style="color:{sc};font-family:JetBrains Mono,monospace;font-weight:700;font-size:14px">'
        f'STATUS: {status}</span> — '
        f'<span style="color:{MUTED};font-size:13px">{state["status_reason"]}</span></div>'
        f'{crew_html}</div>',
        unsafe_allow_html=True,
    )


def _render_diagnostics(state: dict):
    """Tab 2 — Sensor Diagnostics"""
    components = state["components"]
    comp_map = {c["asset_id"]: c for c in components}

    selected = st.selectbox("Select Asset", [c["asset_id"] + " — " + c["name"] for c in components])
    aid = selected.split(" — ")[0] if selected else components[0]["asset_id"]
    comp = comp_map.get(aid, components[0])

    st.markdown(f"### {comp['name']}")
    st.markdown(f"Health: **{comp['health']:.0%}** | Type: **{comp['type']}**")

    readings = comp.get("readings", {})
    defs = SENSOR_DEFS.get(comp["type"], [])

    cols = st.columns(min(len(defs), 3))
    for i, sd in enumerate(defs):
        tag = sd["tag"]
        val = readings.get(tag, sd["base"])
        lo = sd["base"] - sd["noise"] * 3
        hi = sd["base"] + sd["noise"] * 3
        with cols[i % len(cols)]:
            st.markdown(
                _readout_tile(sd["label"], val, sd["unit"], lo, hi, _health_color(comp["health"])),
                unsafe_allow_html=True,
            )

    if defs:
        st.markdown("#### Gauges")
        gcols = st.columns(min(len(defs), 4))
        for i, sd in enumerate(defs[:4]):
            val = readings.get(sd["tag"], sd["base"])
            lo = sd["base"] - sd["noise"] * 4
            hi = sd["base"] + sd["noise"] * 4
            with gcols[i]:
                st.plotly_chart(_gauge(sd["label"], val, lo, hi, sd["unit"]), use_container_width=True)


def _render_rul(state: dict):
    """Tab 3 — Predictive Maintenance / RUL"""
    st.markdown("### Remaining Useful Life Predictions")

    for pred in RUL_PREDICTIONS:
        aid = pred["asset_id"]
        asset = next((a for a in ASSETS if a["asset_id"] == aid), {})
        name = asset.get("name", aid)
        rul = pred["predicted_rul_days"]
        p7 = pred["failure_prob_7d"]
        p30 = pred["failure_prob_30d"]

        color = GREEN if rul > 300 else (YELLOW if rul > 100 else RED)
        st.markdown(
            f'<div class="rec-card">'
            f'<span class="label" style="color:{color};font-family:JetBrains Mono,monospace;font-size:18px;font-weight:700">'
            f'{rul} days</span> '
            f'<span style="color:{MUTED};font-size:12px">RUL</span><br>'
            f'<span style="color:{TXT};font-size:13px;font-weight:600">{aid}</span> — '
            f'<span style="color:{MUTED};font-size:13px">{name}</span><br>'
            f'<span style="color:{MUTED};font-size:12px">'
            f'7-day P(fail): {p7:.1%} | 30-day P(fail): {p30:.1%} | Model: {pred["model_version"]}'
            f'</span></div>',
            unsafe_allow_html=True,
        )

    # Failure patterns reference
    st.markdown("### Known Failure Patterns")
    for fp in FAILURE_PATTERNS:
        st.markdown(
            f'<div class="rec-card">'
            f'{_badge(fp["component_type"], "info")} {_badge(fp["failure_mode"], "warning")}<br>'
            f'<span style="color:{TXT};font-size:13px"><strong>Root Cause:</strong> {fp["root_cause"]}</span><br>'
            f'<span style="color:{MUTED};font-size:12px">Action: {fp["action"]} | '
            f'Downtime: {fp["downtime_hours"]}h | Avg TTF: {fp["avg_ttf_days"]}d</span></div>',
            unsafe_allow_html=True,
        )


def _render_events(state: dict):
    """Tab 4 — Events & Alarms"""
    st.markdown("### Event Log")

    severity_filter = st.multiselect("Filter by Severity", ["CRITICAL", "WARNING", "INFO"], default=["CRITICAL", "WARNING", "INFO"])

    events = state.get("events", [])
    filtered = [e for e in reversed(events) if e["severity"] in severity_filter]

    if not filtered:
        st.info("No events matching the selected filters.")
        return

    for ev in filtered[:50]:
        sev = ev["severity"]
        badge_cls = "critical" if sev == "CRITICAL" else ("warning" if sev == "WARNING" else "info")
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;padding:8px 12px;margin-bottom:4px;">'
            f'{_badge(sev, badge_cls)} '
            f'<span style="color:{MUTED};font-size:11px;font-family:JetBrains Mono,monospace">{ev["ts"]}</span> '
            f'<span style="color:{CYAN};font-size:11px;font-weight:600">[{ev["source"]}]</span> '
            f'<span style="color:{TXT};font-size:13px">{_html.escape(ev["message"])}</span></div>',
            unsafe_allow_html=True,
        )

    # Anomaly section
    anomalies = state.get("anomalies", [])
    if anomalies:
        st.markdown("### Active Anomalies")
        for an in reversed(anomalies[-20:]):
            sev = an["severity"]
            badge_cls = "critical" if sev == "CRITICAL" else ("warning" if sev == "WARNING" else "info")
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;padding:8px 12px;margin-bottom:4px;">'
                f'{_badge(sev, badge_cls)} '
                f'<span style="color:{CYAN};font-size:12px;font-weight:600">{an["asset_id"]}</span> '
                f'<span style="color:{MUTED};font-size:11px">{an["tag"]} = {an["value"]:.2f}</span> — '
                f'<span style="color:{TXT};font-size:13px">{_html.escape(an["message"])}</span></div>',
                unsafe_allow_html=True,
            )


def _render_scada(state: dict):
    """Tab 5 — SCADA / ERP Integration"""
    st.markdown("### Work Orders (SAP PM / CMMS)")

    for wo in WORK_ORDERS:
        status = wo["status"]
        icon_map = {"OPEN": CYAN, "IN_PROGRESS": ORANGE, "PLANNED": MUTED, "COMPLETED": GREEN}
        clr = icon_map.get(status, MUTED)
        st.markdown(
            f'<div class="rec-card">'
            f'<span style="color:{clr};font-family:JetBrains Mono,monospace;font-weight:700">{wo["wo_id"]}</span> '
            f'{_badge(wo["priority"], "warning")} {_badge(status, "info" if status != "COMPLETED" else "info")}<br>'
            f'<span style="color:{TXT};font-size:13px">{_html.escape(wo["title"])}</span><br>'
            f'<span style="color:{MUTED};font-size:12px">Asset: {wo["asset_id"]}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Spare Parts Inventory")
    for part in SPARE_PARTS:
        low = part["qty"] <= part["min_qty"]
        clr = RED if low else GREEN
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;padding:8px 12px;margin-bottom:4px;">'
            f'<span style="color:{clr};font-family:JetBrains Mono,monospace;font-weight:600">{part["part_id"]}</span> '
            f'<span style="color:{TXT};font-size:13px">{_html.escape(part["description"])}</span><br>'
            f'<span style="color:{MUTED};font-size:12px">'
            f'Qty: {part["qty"]} (min {part["min_qty"]}) | ${part["unit_cost"]:,} | Lead: {part["lead_days"]}d'
            f'{"  ⚠️ LOW STOCK" if low else ""}</span></div>',
            unsafe_allow_html=True,
        )

    # Maintenance KPIs
    st.markdown("### Maintenance KPIs")
    mcols = st.columns(4)
    open_ct = sum(1 for w in WORK_ORDERS if w["status"] == "OPEN")
    ip_ct = sum(1 for w in WORK_ORDERS if w["status"] == "IN_PROGRESS")
    planned_ct = sum(1 for w in WORK_ORDERS if w["status"] == "PLANNED")
    done_ct = sum(1 for w in WORK_ORDERS if w["status"] == "COMPLETED")
    mcols[0].markdown(_kpi("OPEN", str(open_ct), "", CYAN), unsafe_allow_html=True)
    mcols[1].markdown(_kpi("IN PROGRESS", str(ip_ct), "", ORANGE), unsafe_allow_html=True)
    mcols[2].markdown(_kpi("PLANNED", str(planned_ct), "", MUTED), unsafe_allow_html=True)
    mcols[3].markdown(_kpi("COMPLETED", str(done_ct), "", GREEN), unsafe_allow_html=True)


def _render_crew(state: dict, agent_obj: PipelineGuardian):
    """Tab 6 — Crew & Ops"""
    st.markdown("### Crew Roster")
    for m in CREW:
        certs = ", ".join(m["certs"])
        zone_clr = GREEN if m["shift"] == "Day" else YELLOW
        st.markdown(
            f'<div class="rec-card">'
            f'<span style="color:{TXT};font-family:JetBrains Mono,monospace;font-weight:700;font-size:14px">'
            f'{_html.escape(m["name"])}</span><br>'
            f'<span style="color:{CYAN};font-size:13px">{m["role"]}</span> | '
            f'<span style="color:{zone_clr};font-size:12px">{m["shift"]} Shift</span> | '
            f'<span style="color:{MUTED};font-size:12px">{m["zone"]}</span><br>'
            f'<span style="color:{MUTED};font-size:11px">Certs: {_html.escape(certs)}</span></div>',
            unsafe_allow_html=True,
        )

    # Skill-based auto-dispatch summary
    st.markdown("### AI Crew Allocation")
    st.markdown(
        f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;padding:10px 14px;margin-bottom:10px;">'
        f'<span style="color:{CYAN};font-weight:700;font-size:13px">Skill-Based Auto-Dispatch</span><br>'
        f'<span style="color:{MUTED};font-size:12px">'
        f'AI agents match crew to incidents by certification → asset type, then pick the closest '
        f'crew member by zone proximity with night-shift penalty (+25 min). '
        f'Certifications: Pipeline Tech → pipe segments, Compressor Mech → compressors, '
        f'Pump Tech → pump stations, I&E Tech → metering/valves/RTUs, CP Tech → cathodic protection.</span></div>',
        unsafe_allow_html=True,
    )

    # Active crew assignments
    assignments = agent_obj.state.crew_assignments
    if assignments:
        st.markdown(f'<span style="color:{GREEN};font-weight:600;font-size:14px">'
                    f'{len(assignments)} crew dispatched</span>', unsafe_allow_html=True)
        for ca in reversed(assignments[-10:]):
            role_tag = (f'<span style="background:rgba(249,115,22,0.15);color:{ORANGE};'
                        f'border:1px solid rgba(249,115,22,0.3);border-radius:4px;padding:1px 6px;'
                        f'font-size:10px;font-weight:600;margin-right:6px">{_html.escape(ca.role)}</span>'
                        ) if ca.role else ""
            score_html = (f'<span style="color:{CYAN};font-size:11px;float:right">Score: {ca.skill_score}</span>'
                          ) if ca.skill_score else ""
            reasoning_html = (
                f'<div style="color:{MUTED};font-size:10px;font-style:italic;margin-top:3px;'
                f'padding-left:4px;border-left:2px solid {BORDER}">{_html.escape(ca.reasoning)}</div>'
            ) if ca.reasoning else ""
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;padding:8px 12px;margin-bottom:4px;">'
                f'{score_html}'
                f'{role_tag}<span class="crew-tag">{_html.escape(ca.crew_name)}</span> → '
                f'<span style="color:{CYAN};font-weight:600">{ca.asset_id}</span> '
                f'<span style="color:{MUTED};font-size:12px">(ETA {ca.eta_min} min)</span><br>'
                f'<span style="color:{TXT};font-size:12px">{_html.escape(ca.issue_type)}</span><br>'
                f'<span style="color:{MUTED};font-size:11px">Cert: {_html.escape(ca.cert_reason)}</span>'
                f'{reasoning_html}</div>',
                unsafe_allow_html=True,
            )

    # Operations cycle
    st.markdown("### Pipeline Operations Schedule")
    for op in OPERATIONS_CYCLE:
        risk_clr = GREEN if op["risk"] == "LOW" else (YELLOW if op["risk"] == "MEDIUM" else RED)
        st.markdown(
            f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;padding:6px 12px;margin-bottom:4px;">'
            f'{_badge(op["op"], "info")} '
            f'<span style="color:{risk_clr};font-size:12px;font-weight:600">Risk: {op["risk"]}</span><br>'
            f'<span style="color:{MUTED};font-size:12px">{op["detail"]}</span></div>',
            unsafe_allow_html=True,
        )


def _render_dataflow():
    """Tab 7 — Data & AI Flow Diagram"""
    # KPI summary tiles
    kcols = st.columns(4)
    kpi_items = [
        ("Components", "18 / 18", "monitored", CYAN),
        ("Bronze Latency", "1.2 s", "avg ingest", GREEN),
        ("ML Inference", "4.8 s", "anomaly + RUL", PURPLE),
        ("Agent Layer", "5 agents", "per tick", ORANGE),
    ]
    for c, (t, v, s, clr) in zip(kcols, kpi_items):
        c.markdown(_kpi(t, v, s, clr), unsafe_allow_html=True)

    st.components.v1.html(_dataflow_html(), height=450, scrolling=False)

    # How It Works — 6 cards in 3-column grid (BOP Guardian style)
    st.markdown("### How It Works")
    cards = [
        ("Field Sources", "SCADA/OPC-UA telemetry from 18 assets (65+ tags), ILI corrosion surveys, "
         "SAP PM work orders, CP pipe-to-soil readings, and crew roster data."),
        ("SDP Medallion", "Spark Declarative Pipelines ingest into Bronze (raw), clean and score "
         "health in Silver, and aggregate KPIs + RUL predictions in Gold."),
        ("Lakebase Serving", "Gold-layer results sync to managed PostgreSQL via JDBC for sub-10ms "
         "indexed queries, connection pooling, and auto-scaling."),
        ("5 AI Agents", "Health, Integrity, Leak Detection, Operations, and Compliance agents run "
         "each tick — auto-dispatching crew by certification and zone proximity."),
        ("Digital Twin", "Live SVG schematic with health dots, flow animation, pressure readouts, "
         "and industry icons for every asset class on the 87-mile trunk line."),
        ("Pipeline Advisor", "Natural-language chat with 9 intent types and 10+ component aliases "
         "for instant insights on health, RUL, crew, compliance, and operations."),
    ]
    for row_start in range(0, len(cards), 3):
        cols = st.columns(3)
        for c, (title, desc) in zip(cols, cards[row_start:row_start + 3]):
            c.markdown(
                f'<div class="rec-card"><div class="rec-title" style="color:{CYAN}">{title}</div>'
                f'<div class="rec-detail">{desc}</div></div>',
                unsafe_allow_html=True,
            )


def _render_advisor(agent_obj: PipelineGuardian):
    """Tab 8 — Pipeline Advisor Chat"""
    st.markdown("### Pipeline Advisor")
    st.markdown(
        f'<span style="color:{MUTED};font-size:13px">'
        f'Ask about pipeline health, RUL predictions, crew, work orders, leak detection, compliance, operations, or spare parts.</span>',
        unsafe_allow_html=True,
    )

    # Display chat history
    for msg in agent_obj.state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            if role == "assistant":
                st.markdown(
                    f'<div style="color:{TXT};font-size:13px">{_md_to_html(msg["content"])}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask Pipeline Command Center...")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        response = agent_obj.handle_query(user_input)
        with st.chat_message("assistant"):
            st.markdown(
                f'<div style="color:{TXT};font-size:13px">{_md_to_html(response)}</div>',
                unsafe_allow_html=True,
            )

    # Quick action buttons
    st.markdown("---")
    st.markdown(f'<span style="color:{MUTED};font-size:12px">Quick Actions:</span>', unsafe_allow_html=True)
    qcols = st.columns(5)
    prompts = ["Pipeline summary", "Show RUL predictions", "Crew status", "Leak detection", "Compliance report"]
    for c, prompt in zip(qcols, prompts):
        if c.button(prompt, key=f"qa_{prompt}"):
            response = agent_obj.handle_query(prompt)
            st.rerun()

    # Recent recommendations banner
    recs = agent_obj.state.recommendations
    if recs:
        st.markdown("### Recent Agent Recommendations")
        cols = st.columns(2)
        for i, rec in enumerate(reversed(recs[-6:])):
            with cols[i % 2]:
                _render_rec_card(rec)


# ══════════════════════════════════════════════════════════════════
#  MAIN APP RENDER
# ══════════════════════════════════════════════════════════════════

def render_app():
    st.set_page_config(
        page_title="Pipeline Command Center",
        page_icon="🛢️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _inject_css()

    # ── Session State ──────────────────────────────────────────────
    if "tick" not in st.session_state:
        st.session_state.tick = 0
    if "agent" not in st.session_state:
        st.session_state.agent = PipelineGuardian()
    if "page" not in st.session_state:
        st.session_state.page = "pipeline"

    agent: PipelineGuardian = st.session_state.agent

    # ── Sidebar Navigation ─────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            f'<div style="text-align:center;padding:10px 0">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:20px;font-weight:700;color:{CYAN}">'
            f'PIPELINE<br>COMMAND CENTER</span><br>'
            f'<span style="color:{MUTED};font-size:11px">Midstream Digital Twin</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        for label, key in NAV_ITEMS:
            is_active = st.session_state.page == key
            btn_style = f"color:{CYAN};font-weight:700" if is_active else f"color:{MUTED}"
            if st.button(f"{'▸ ' if is_active else '  '}{label}", key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")
        st.markdown(
            f'<div style="color:{MUTED};font-size:11px;text-align:center">'
            f'Tick: {st.session_state.tick}<br>'
            f'Powered by Databricks</div>',
            unsafe_allow_html=True,
        )

    # ── Live Refresh Fragment ──────────────────────────────────────
    @st.fragment(run_every=3)
    def _live():
        st.session_state.tick += 1
        state = simulate_tick()
        agent.analyze_tick(state)

        page = st.session_state.page
        if page == "pipeline":
            _render_pipeline_overview(state, agent)
        elif page == "diag":
            _render_diagnostics(state)
        elif page == "rul":
            _render_rul(state)
        elif page == "events":
            _render_events(state)
        elif page == "scada":
            _render_scada(state)
        elif page == "crew":
            _render_crew(state, agent)
        elif page == "dataflow":
            _render_dataflow()
        elif page == "advisor":
            _render_advisor(agent)

    _live()
