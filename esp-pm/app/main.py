"""
ESP Predictive Maintenance — Databricks App
7-tab Streamlit dashboard: Fleet Command · Well Diagnostics · Live Alerts
· SAP Maintenance · ESP Advisor · Data Flow · AI Scheduler
"""
from __future__ import annotations
import os
import sys
import time
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(__file__))
import simulator
import sap_data
import diagnostics
import scheduler_agent
from genie_panel import ask_genie

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ESP Predictive Maintenance",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS theme ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
body, .stApp { background-color: #0B0F1A; color: #E8EDF5; }
.block-container { padding-top: 0.8rem !important; }
.stTabs [data-baseweb="tab-list"] { background-color: #0f172a; border-radius: 8px; padding: 2px; overflow-x: auto !important; flex-wrap: nowrap !important; scrollbar-width: thin; }
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { height: 6px; }
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
.stTabs [data-baseweb="tab"] { color: #6B7A99; font-weight: 600; font-size: 13px; white-space: nowrap !important; flex-shrink: 0 !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: #FFB020; border-bottom: 2px solid #FFB020; }
.fault-badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; margin:2px; }
.stButton>button { background:#0f172a; color:#94a3b8; border:1px solid #1e293b; border-radius:6px; font-size:12px; }
.stButton>button:hover { background:#1e3a5f; color:#e2e8f0; border-color:#38bdf8; }
hr { border-color: #1E2D4F; }
@keyframes livepulse { 0%,100%{opacity:1;box-shadow:0 0 4px #FF4757;}50%{opacity:.4;box-shadow:0 0 10px #FF4757;} }
.live-dot { display:inline-block;width:8px;height:8px;background:#FF4757;border-radius:50%;animation:livepulse 1.1s ease-in-out infinite;vertical-align:middle;margin-right:5px; }
.live-badge { display:inline-flex;align-items:center;background:#FF475722;border:1px solid #FF475755;border-radius:5px;padding:2px 9px 2px 6px;font-size:0.78rem;font-weight:700;color:#FF4757;letter-spacing:.8px; }
.stDataFrame { background: #0f172a !important; }
.stSelectbox label, .stTextInput label, .stTextArea label { color: #6B7A99; }
[data-testid="stHeader"] { display: none !important; }
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
div[data-testid="stMetricValue"] { color: #FFB020; }
/* Metric tile style */
.mtile { background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:12px 14px; }
.mtile-lbl { font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px; }
.mtile-val { font-size:22px;font-weight:700;line-height:1; }
.mtile-unit { font-size:12px;color:#64748b;font-weight:400;margin-left:3px; }
/* Chat message text — match query font size, readable color */
[data-testid="stChatMessage"] p { color:#c8d6e8 !important; line-height:1.6; margin-bottom:6px; }
[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3 { font-size:1em !important; font-weight:700 !important; color:#f1f5f9 !important; margin:8px 0 4px; }
[data-testid="stChatMessage"] li { color:#c8d6e8 !important; line-height:1.6; }
[data-testid="stChatMessage"] strong { color:#f1f5f9 !important; font-weight:600; }
[data-testid="stChatMessage"] code { background:#1e293b; color:#38bdf8; padding:1px 5px; border-radius:3px; }
</style>
""", unsafe_allow_html=True)

COLORS = {
    "bg":     "#0B0F1A",
    "panel":  "#0f172a",
    "border": "#1e293b",
    "green":  "#22c55e",
    "amber":  "#eab308",
    "red":    "#ef4444",
    "text":   "#e2e8f0",
    "dim":    "#64748b",
}
STATUS_COLOR = {"RUNNING": "#22c55e", "WARNING": "#eab308", "CRITICAL": "#ef4444"}
RISK_COLOR   = {"LOW": "#22c55e",     "MEDIUM":  "#eab308", "HIGH":     "#ef4444"}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _generate_initial_alerts() -> list:
    alerts = []
    faulty = [w for w in simulator.WELLS if w["stage"] != "healthy"]
    statuses = ["NEW", "NEW", "ACK", "NEW", "ACK", "CLOSED", "NEW", "NEW", "ACK",
                "NEW", "ACK", "CLOSED", "NEW", "NEW", "ACK"]
    i = 0
    for w in faulty:
        params = simulator.simulate_all_wells(0)
        wdata  = next((p for p in params if p["esp_id"] == w["esp_id"]), {})
        diags  = diagnostics.diagnose(wdata) if wdata else []
        for d in diags:
            if d["severity"] in ("CRITICAL", "HIGH"):
                s = statuses[i % len(statuses)]
                alerts.append({
                    "id":          f"ALT-{1000 + i:04d}",
                    "esp_id":      w["esp_id"],
                    "well_name":   w["name"],
                    "field":       w["field"],
                    "fault_code":  d["fault_code"],
                    "severity":    d["severity"],
                    "description": d["description"][:120],
                    "status":      s,
                    "triggered_at": datetime.utcnow() - timedelta(minutes=5 * (i + 1)),
                    "ack_by":      ("ops@demo.com" if s != "NEW" else ""),
                })
                i += 1
                if i >= 15:
                    break
        if i >= 15:
            break
    return alerts


# ── Session state (runs once on page load) ────────────────────────────────────
if "tick" not in st.session_state:
    st.session_state.tick          = 0
    st.session_state.wells         = simulator.simulate_all_wells(0)
    st.session_state.alerts        = _generate_initial_alerts()
    st.session_state.chat_history  = []
    st.session_state.selected_well = "ESP-001"
    st.session_state.extra_wos     = []

_LIVE_EVENT_ALERTS = {
    0:  ("ESP-009", "Sunrise-2",   "Marcellus",    "HIGH_TEMP",           "CRITICAL", "Motor temperature spike — thermal runaway risk detected"),
    5:  ("ESP-007", "Redstone-4",  "Bakken",       "MOTOR_OVERLOAD",      "CRITICAL", "Motor current >112% — overload condition escalating"),
    10: ("ESP-003", "Crawford-1",  "Eagle Ford",   "BEARING_FAILURE_RISK","CRITICAL", "Vibration >5.0 mm/s — imminent bearing failure"),
    15: ("ESP-002", "Meridian-2B", "Permian Basin","GAS_INTERFERENCE",    "HIGH",     "Intake pressure collapse — gas interference surge"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# FRAGMENT: runs every 3 seconds — refreshes data + renders all tabs
# Tab selection is preserved across re-renders because this is a fragment
# (partial DOM update), not a full page rerun.
# ═══════════════════════════════════════════════════════════════════════════════
@st.fragment(run_every=3)
def _app():
    # ── Refresh data ───────────────────────────────────────────────────────────
    st.session_state.tick += 1
    st.session_state.wells = simulator.simulate_all_wells(st.session_state.tick)
    new_cycle = st.session_state.tick % 20
    if new_cycle in _LIVE_EVENT_ALERTS:
        eid, ename, efield, fcode, sev, desc = _LIVE_EVENT_ALERTS[new_cycle]
        st.session_state.alerts.insert(0, {
            "id":           f"ALT-{9000 + st.session_state.tick:04d}",
            "esp_id":       eid,
            "well_name":    ename,
            "field":        efield,
            "fault_code":   fcode,
            "severity":     sev,
            "description":  desc,
            "status":       "NEW",
            "triggered_at": datetime.utcnow(),
            "ack_by":       "",
        })
        if len(st.session_state.alerts) > 30:
            st.session_state.alerts = st.session_state.alerts[:30]

    wells = st.session_state.wells
    kpis  = simulator.get_fleet_kpis(wells)

    # ── Header ─────────────────────────────────────────────────────────────────
    h1, h2, h3 = st.columns([1, 7, 2])
    with h1:
        st.markdown("## ⚡")
    with h2:
        st.markdown("## ESP Predictive Maintenance")
    with h3:
        cycle_num = st.session_state.tick % 20
        st.markdown(
            f"<div style='text-align:right;padding-top:10px'>"
            f"<span class='live-badge'><span class='live-dot'></span>LIVE</span>"
            f"<span style='color:#64748b;font-size:0.78rem;margin-left:10px'>"
            f"{datetime.utcnow().strftime('%H:%M:%S UTC')} &nbsp;|&nbsp; "
            f"cycle {cycle_num}/20</span></div>",
            unsafe_allow_html=True,
        )
    st.divider()

    # ── Persistent tab nav: remember active tab across fragment reruns ─────────
    # State lives on window.parent (shared across all iframes, survives Streamlit
    # reruns, resets on page reload). MutationObserver re-applies it whenever
    # Streamlit re-renders the tab list.
    components.html("""<script>
    (function(){
      var p = window.parent;
      if (p.__espPmTabsInit) return;
      p.__espPmTabsInit = true;

      function tabs(){
        return p.document.querySelectorAll('[data-baseweb="tab"]');
      }
      function activeIdx(){
        var ts = tabs();
        for (var i=0; i<ts.length; i++){
          if (ts[i].getAttribute('aria-selected') === 'true') return i;
        }
        return -1;
      }
      function applyStored(){
        var idx = p.__espPmActiveTab;
        if (idx === undefined) return;
        var ts = tabs();
        if (ts[idx] && activeIdx() !== idx){
          ts[idx].click();
        }
      }

      // Capture manual tab clicks (only when the click matches an actual tab
      // element — avoids overwriting state when other buttons trigger clicks).
      p.document.addEventListener('click', function(e){
        if (!e.isTrusted) return;
        var tab = e.target && e.target.closest && e.target.closest('[data-baseweb="tab"]');
        if (!tab) return;
        var ts = tabs();
        var idx = Array.prototype.indexOf.call(ts, tab);
        if (idx >= 0) p.__espPmActiveTab = idx;
      }, true);

      // Re-apply active tab whenever Streamlit re-renders the DOM
      var mo = new MutationObserver(function(){ applyStored(); });
      mo.observe(p.document.body, {childList: true, subtree: true});

      setTimeout(applyStored, 200);
    })();
    </script>""", height=0)

    # Programmatic nav (e.g., Diagnose button): set the global + click
    if "_nav_tab" in st.session_state:
        _ti = st.session_state.pop("_nav_tab")
        components.html(f"""<script>
        window.parent.__espPmActiveTab = {_ti};
        var tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
        if (tabs[{_ti}]) setTimeout(function(){{ tabs[{_ti}].click(); }}, 100);
        </script>""", height=0)

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "⚙️ Fleet Command",
        "🔬 Well Diagnostics",
        "🚨 Live Alerts",
        "🔧 SAP Maintenance",
        "🤖 ESP Advisor",
        "🗺️ Data Flow",
        "🧠 AI Scheduler",
    ])


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1 — FLEET COMMAND CENTER (Oil Pump Monitor card style)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab1:
        # KPI stat bar
        k1, k2, k3, k4, k5 = st.columns(5)
        def _kpi(col, label, value, color="#e2e8f0"):
            col.markdown(
                f"<div style='background:#0f172a;border:1px solid #1e293b;border-radius:10px;"
                f"padding:10px 14px'>"
                f"<div style='font-size:9px;color:#64748b;text-transform:uppercase;"
                f"letter-spacing:.06em;margin-bottom:4px'>{label}</div>"
                f"<div style='font-size:20px;font-weight:700;color:{color}'>{value}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        crit_c = "#ef4444" if kpis["critical_count"] > 0 else "#22c55e"
        warn_c = "#eab308" if kpis["warning_count"] > 0 else "#22c55e"
        _kpi(k1, "Critical Wells",  kpis["critical_count"],          crit_c)
        _kpi(k2, "Warning Wells",   kpis["warning_count"],           warn_c)
        _kpi(k3, "Total Flow bpd",  f"{kpis['total_flow_bpd']:,.0f}", "#38bdf8")
        _kpi(k4, "Avg Efficiency",  f"{kpis['avg_efficiency']}%",    "#a78bfa")
        _kpi(k5, "Tick / Cycle",    f"{st.session_state.tick} / {st.session_state.tick%20}", "#64748b")

        st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

        # 4×3 well card grid — Oil Pump Monitor style
        for row_idx in range(3):
            cols = st.columns(4)
            for col_idx in range(4):
                wi = row_idx * 4 + col_idx
                if wi >= len(wells):
                    break
                w = wells[wi]
                sc  = STATUS_COLOR.get(w["run_status"], "#6B7A99")
                rc  = RISK_COLOR.get(w["risk_bucket"],  "#6B7A99")
                glow = f"box-shadow:0 0 8px {sc}88;" if w["run_status"] != "RUNNING" else ""
                tc   = "#ef4444" if w["motor_temp_f"] > 200 else ("#eab308" if w["motor_temp_f"] > 185 else "#38bdf8")
                vc   = "#ef4444" if w["vibration_mms"] > 5  else ("#eab308" if w["vibration_mms"] > 3.5 else "#a78bfa")

                fault_html = ""
                if w["fault_codes"]:
                    top = w["fault_codes"][0]
                    fc_color = "#ef4444" if top["severity"] == "CRITICAL" else "#eab308"
                    fault_html = (
                        f"<div style='margin-top:8px'>"
                        f"<span style='background:{fc_color}22;border:1px solid {fc_color}55;"
                        f"border-radius:3px;padding:1px 7px;font-size:9px;color:{fc_color};"
                        f"font-family:monospace;font-weight:700'>{top['code']}</span>"
                        f"</div>"
                    )

                with cols[col_idx]:
                    st.markdown(
                        f"<div style='background:#0f172a;border:1px solid #1e293b;"
                        f"border-radius:12px;padding:14px;margin-bottom:6px'>"
                        # Name + status badge
                        f"<div style='display:flex;justify-content:space-between;"
                        f"align-items:flex-start;margin-bottom:10px'>"
                        f"  <div>"
                        f"    <div style='font-weight:700;font-size:13px;color:#e2e8f0'>{w['name']}</div>"
                        f"    <div style='font-size:10px;color:#64748b;margin-top:2px'>{w['field']}</div>"
                        f"  </div>"
                        f"  <div style='display:flex;align-items:center;gap:4px;"
                        f"  background:{sc}22;border:1px solid {sc}44;"
                        f"  border-radius:20px;padding:2px 9px;font-size:10px;color:{sc};font-weight:700'>"
                        f"    <div style='width:6px;height:6px;border-radius:50%;background:{sc};{glow}'></div>"
                        f"    {w['run_status']}"
                        f"  </div>"
                        f"</div>"
                        # 3 metric tiles
                        f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-bottom:10px'>"
                        f"  <div style='background:#141B2D;border-radius:6px;padding:6px 8px'>"
                        f"    <div style='font-size:9px;color:#64748b;text-transform:uppercase'>Temp</div>"
                        f"    <div style='font-size:15px;font-weight:700;color:{tc}'>{w['motor_temp_f']:.0f}°</div>"
                        f"  </div>"
                        f"  <div style='background:#141B2D;border-radius:6px;padding:6px 8px'>"
                        f"    <div style='font-size:9px;color:#64748b;text-transform:uppercase'>Vib</div>"
                        f"    <div style='font-size:15px;font-weight:700;color:{vc}'>{w['vibration_mms']}</div>"
                        f"  </div>"
                        f"  <div style='background:#141B2D;border-radius:6px;padding:6px 8px'>"
                        f"    <div style='font-size:9px;color:#64748b;text-transform:uppercase'>Flow</div>"
                        f"    <div style='font-size:15px;font-weight:700;color:#38bdf8'>{w['flow_rate_bpd']:.0f}</div>"
                        f"  </div>"
                        f"</div>"
                        # Risk bar
                        f"<div style='background:#1e293b;border-radius:3px;height:3px;overflow:hidden'>"
                        f"  <div style='width:{w['risk_score']*100:.0f}%;height:100%;background:{rc}'></div>"
                        f"</div>"
                        f"<div style='display:flex;justify-content:space-between;margin-top:4px'>"
                        f"  <span style='font-size:9px;color:#64748b'>{w['esp_id']}</span>"
                        f"  <span style='font-size:9px;color:{rc};font-weight:700'>"
                        f"  RISK {w['risk_score']*100:.0f}%</span>"
                        f"</div>"
                        f"{fault_html}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("→ Diagnose", key=f"sel_{w['esp_id']}", use_container_width=True):
                        st.session_state.selected_well = w["esp_id"]
                        st.session_state._nav_tab = 1
                        st.rerun(scope="fragment")

        st.divider()

        # Scatter: risk vs temp
        df_scatter = pd.DataFrame([{
            "esp_id": w["esp_id"], "name": w["name"],
            "risk_score": w["risk_score"], "motor_temp_f": w["motor_temp_f"],
            "flow_rate_bpd": w["flow_rate_bpd"], "run_status": w["run_status"],
        } for w in wells])
        fig_scatter = px.scatter(
            df_scatter, x="risk_score", y="motor_temp_f",
            size="flow_rate_bpd", color="run_status",
            color_discrete_map=STATUS_COLOR,
            hover_name="name", text="esp_id", size_max=40,
            title="Fleet Risk vs Motor Temperature (bubble size = flow rate)",
        )
        fig_scatter.update_traces(textposition="top center", textfont=dict(size=9, color="#e2e8f0"))
        fig_scatter.update_layout(
            paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["panel"],
            font_color=COLORS["text"], height=320,
            xaxis=dict(gridcolor="#1e293b", title="Risk Score"),
            yaxis=dict(gridcolor="#1e293b", title="Motor Temp (°F)"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2 — WELL DIAGNOSTICS (LiveMetrics tile style)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab2:
        well_options = {w["esp_id"]: f"{w['esp_id']} — {w['name']} ({w['field']})" for w in wells}
        sel_id = st.selectbox(
            "Select Well",
            list(well_options.keys()),
            format_func=lambda x: well_options[x],
            index=list(well_options.keys()).index(st.session_state.selected_well)
            if st.session_state.selected_well in well_options else 0,
            key="diag_well_select",
        )
        st.session_state.selected_well = sel_id
        w    = next(x for x in wells if x["esp_id"] == sel_id)
        sap  = sap_data.get_sap_data(sel_id)
        diags = diagnostics.diagnose(w)

        # ── LiveMetrics header row ────────────────────────────────────────────
        level   = w["run_status"]
        lc_map  = {"RUNNING": "#22c55e", "WARNING": "#eab308", "CRITICAL": "#ef4444"}
        lc      = lc_map.get(level, "#64748b")
        lbg_map = {"RUNNING": "#0d2137", "WARNING": "#1a1400", "CRITICAL": "#1a0000"}
        lbg     = lbg_map.get(level, "#0f172a")
        lbdr_map= {"RUNNING": "#1a4a6e", "WARNING": "#78350f", "CRITICAL": "#7f1d1d"}
        lbdr    = lbdr_map.get(level, "#1e293b")

        st.markdown(
            f"<div style='background:{lbg};border:1px solid {lbdr};border-radius:12px;"
            f"padding:12px 16px;margin-bottom:12px;display:flex;align-items:center;"
            f"justify-content:space-between'>"
            f"  <div style='font-weight:600;font-size:14px;color:#e2e8f0'>"
            f"  ⚙️ {w['name']} &nbsp;<span style='font-size:11px;color:#64748b'>"
            f"  {w['field']} · {w['esp_id']} · {w['days_online']}d online</span></div>"
            f"  <div style='display:flex;align-items:center;gap:5px;background:{lc}22;"
            f"  border:1px solid {lc};border-radius:20px;padding:3px 12px;"
            f"  font-size:11px;color:{lc};font-weight:700'>{level}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── 5 metric tiles (LiveMetrics style) ───────────────────────────────
        tc = "#ef4444" if w["motor_temp_f"] > 200 else ("#eab308" if w["motor_temp_f"] > 185 else "#38bdf8")
        vc = "#ef4444" if w["vibration_mms"] > 5   else ("#eab308" if w["vibration_mms"] > 3.5 else "#a78bfa")
        cc = "#ef4444" if w["motor_current_pct"] > 112 else ("#eab308" if w["motor_current_pct"] > 105 else "#34d399")
        pc = "#ef4444" if w["intake_pressure_psi"] < 600 else ("#eab308" if w["intake_pressure_psi"] < 800 else "#f472b6")
        ec = "#ef4444" if w["pump_efficiency_pct"] < 40  else ("#eab308" if w["pump_efficiency_pct"] < 55  else "#a78bfa")

        m1, m2, m3, m4, m5 = st.columns(5)
        def _mtile(col, label, value, unit, color):
            col.markdown(
                f"<div class='mtile'><div class='mtile-lbl'>{label}</div>"
                f"<div class='mtile-val' style='color:{color}'>{value}"
                f"<span class='mtile-unit'>{unit}</span></div></div>",
                unsafe_allow_html=True,
            )
        _mtile(m1, "Motor Temp",   f"{w['motor_temp_f']:.1f}",        "°F",    tc)
        _mtile(m2, "Vibration",    f"{w['vibration_mms']:.2f}",       "mm/s",  vc)
        _mtile(m3, "Current",      f"{w['motor_current_pct']:.1f}",   "%",     cc)
        _mtile(m4, "Intake PSI",   f"{w['intake_pressure_psi']:.0f}", "psi",   pc)
        _mtile(m5, "Efficiency",   f"{w['pump_efficiency_pct']:.1f}", "%",     ec)

        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

        # ── Gauges ────────────────────────────────────────────────────────────
        def _gauge(val, title, min_v, max_v, warn, crit, unit, low_is_bad=False):
            if low_is_bad:
                color_steps = [
                    {"range": [min_v, crit], "color": "#ef4444"},
                    {"range": [crit, warn],  "color": "#eab308"},
                    {"range": [warn, max_v], "color": "#22c55e"},
                ]
            else:
                color_steps = [
                    {"range": [min_v, warn], "color": "#22c55e"},
                    {"range": [warn, crit],  "color": "#eab308"},
                    {"range": [crit, max_v], "color": "#ef4444"},
                ]
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=val,
                title={"text": f"{title}<br><span style='font-size:0.7em;color:#64748b'>{unit}</span>",
                       "font": {"color": "#e2e8f0", "size": 13}},
                number={"font": {"color": "#FFB020", "size": 24}},
                gauge={
                    "axis": {"range": [min_v, max_v], "tickcolor": "#64748b",
                             "tickfont": {"color": "#64748b", "size": 10}},
                    "bar": {"color": "#FFB020", "thickness": 0.25},
                    "bgcolor": "#0f172a",
                    "bordercolor": "#1e293b",
                    "steps": color_steps,
                },
            ))
            fig.update_layout(
                paper_bgcolor=COLORS["bg"], font_color=COLORS["text"],
                height=200, margin=dict(l=20, r=20, t=50, b=10),
            )
            return fig

        g1, g2, g3 = st.columns(3)
        with g1:
            st.plotly_chart(_gauge(w["motor_temp_f"], "Motor Temperature", 120, 240, 185, 200, "°F"), use_container_width=True)
        with g2:
            st.plotly_chart(_gauge(w["vibration_mms"], "Vibration", 0, 10, 3.5, 5.0, "mm/s"), use_container_width=True)
        with g3:
            st.plotly_chart(_gauge(w["motor_current_pct"], "Motor Current", 0, 130, 105, 112, "% nameplate"), use_container_width=True)

        g4, g5, g6 = st.columns(3)
        with g4:
            st.plotly_chart(_gauge(w["intake_pressure_psi"], "Pump Intake Pressure", 0, 2000, 800, 600, "psi", low_is_bad=True), use_container_width=True)
        with g5:
            st.plotly_chart(_gauge(w["flow_rate_bpd"], "Flow Rate", 0, 3000, 400, 200, "bpd", low_is_bad=True), use_container_width=True)
        with g6:
            st.plotly_chart(_gauge(w["pump_efficiency_pct"], "Pump Efficiency", 0, 100, 55, 40, "%", low_is_bad=True), use_container_width=True)

        # ── Trend chart ───────────────────────────────────────────────────────
        st.markdown("#### Live Trend — last 24 readings")
        hist = w.get("trend_history", {})
        if hist:
            ts_labels = [(datetime.utcnow() - timedelta(seconds=3*(23-h))).strftime('%H:%M:%S')
                         for h in range(24)]
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=ts_labels, y=hist.get("motor_temp_f", []), name="Motor Temp (°F)",
                                            line=dict(color="#ef4444", width=2)))
            fig_trend.add_trace(go.Scatter(x=ts_labels, y=[v * 10 for v in hist.get("vibration_mms", [])],
                                            name="Vibration ×10 (mm/s)", line=dict(color="#eab308", width=2)))
            fig_trend.add_trace(go.Scatter(x=ts_labels, y=hist.get("motor_current_pct", []), name="Current (%)",
                                            line=dict(color="#22c55e", width=2)))
            fig_trend.update_layout(
                paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["panel"],
                font_color=COLORS["text"], height=260,
                xaxis=dict(gridcolor="#1e293b", title="Time (UTC)", tickangle=-30, nticks=8),
                yaxis=dict(gridcolor="#1e293b"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=10, r=10, t=10, b=40),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # ── Active diagnostics (AlertPanel card style) ────────────────────────
        st.markdown("#### Active Diagnostics")
        sev_colors = {"CRITICAL": "#ef4444", "HIGH": "#eab308", "MEDIUM": "#3b82f6", "LOW": "#22c55e"}
        sev_bg     = {"CRITICAL": "#1a0000", "HIGH": "#1a1400", "MEDIUM": "#0d1f3c", "LOW": "#0a1a0a"}
        sev_bdr    = {"CRITICAL": "#7f1d1d", "HIGH": "#78350f", "MEDIUM": "#1e3a5f", "LOW": "#14532d"}

        for d in diags:
            col_card = sev_colors.get(d["severity"], "#64748b")
            d_bg     = sev_bg.get(d["severity"], "#0f172a")
            d_bdr    = sev_bdr.get(d["severity"], "#1e293b")
            st.markdown(
                f"<div style='background:{d_bg};border:1px solid {d_bdr};"
                f"border-radius:8px;padding:10px 14px;margin-bottom:6px'>"
                f"  <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>"
                f"    <div style='display:flex;align-items:center;gap:6px'>"
                f"      <span style='background:{col_card}22;border:1px solid {col_card}55;"
                f"      border-radius:10px;padding:1px 8px;font-size:10px;color:{col_card};"
                f"      font-weight:700'>{d['severity']}</span>"
                f"      <span style='font-size:12px;font-weight:700;color:#e2e8f0'>{d['fault_code']}</span>"
                f"    </div>"
                f"    <span style='font-size:10px;color:#eab308'>⏱ {d['estimated_hours_to_failure']}h to failure</span>"
                f"  </div>"
                f"  <div style='font-size:11px;color:#94a3b8;margin-bottom:4px'>{d['description']}</div>"
                f"  <div style='font-size:10px;color:#64748b'>Action: {d['recommended_action']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── SAP panel ─────────────────────────────────────────────────────────
        st.markdown("#### SAP PM Data")
        eq = sap.get("equipment", {})
        sc1, sc2, sc3 = st.columns(3)
        sc1.markdown(f"**Equipment:** {eq.get('EQUNR','—')} | {eq.get('HERST','—')}")
        sc2.markdown(f"**Serial:** {eq.get('SERGE','—')} | Built: {eq.get('BAUJJ','—')}")
        sc3.markdown(f"**Next PM:** {sap.get('pm_next_date','—')}")

        notifs = sap.get("notifications", [])
        if notifs:
            st.markdown("**Open Notifications:**")
            st.dataframe(pd.DataFrame(notifs), use_container_width=True, hide_index=True)
        hist_sap = sap.get("history", [])
        if hist_sap:
            st.markdown("**Last 5 Completed Orders:**")
            st.dataframe(pd.DataFrame(hist_sap), use_container_width=True, hide_index=True)


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 3 — LIVE ALERTS (AlertPanel style)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab3:
        # Alert panel header
        new_count = sum(1 for a in st.session_state.alerts if a["status"] == "NEW")
        new_badge = (
            f"<span style='background:#ef444422;border:1px solid #ef4444;border-radius:10px;"
            f"padding:1px 8px;font-size:11px;color:#f87171;margin-left:auto'>{new_count} NEW</span>"
            if new_count > 0 else ""
        )
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:12px'>"
            f"  <span style='font-size:14px;color:#64748b;text-transform:uppercase;"
            f"  letter-spacing:.05em'>Recent Alerts</span>"
            f"  {new_badge}"
            f"</div>",
            unsafe_allow_html=True,
        )

        f1, f2 = st.columns(2)
        with f1:
            sev_filter = st.radio("Severity", ["All", "CRITICAL", "HIGH", "MEDIUM"], horizontal=True, key="sev_filt")
        with f2:
            stat_filter = st.radio("Status", ["All", "Active", "Acknowledged"], horizontal=True, key="stat_filt")

        alerts   = st.session_state.alerts
        filtered = [a for a in alerts
                    if (sev_filter == "All" or a["severity"] == sev_filter)
                    and (stat_filter == "All"
                         or (stat_filter == "Active" and a["status"] == "NEW")
                         or (stat_filter == "Acknowledged" and a["status"] == "ACK"))]

        if not filtered:
            st.markdown(
                "<div style='text-align:center;padding:40px 0;color:#475569;font-size:13px'>"
                "<div style='font-size:28px;margin-bottom:8px'>✓</div>"
                "No alerts match the current filter</div>",
                unsafe_allow_html=True,
            )
        else:
            for a in sorted(filtered, key=lambda x: (x["severity"] not in ("CRITICAL","HIGH"), x["triggered_at"])):
                sev_c   = {"CRITICAL": "#ef4444", "HIGH": "#eab308", "MEDIUM": "#3b82f6", "LOW": "#22c55e"}.get(a["severity"], "#64748b")
                is_crit = a["severity"] == "CRITICAL"
                card_bg  = "#1a000022" if is_crit else ("#1a140022" if a["severity"] == "HIGH" else "#0d1f3c22")
                card_bdr = "#7f1d1d"   if is_crit else ("#78350f"   if a["severity"] == "HIGH" else "#1e3a5f")
                mins_ago = int((datetime.utcnow() - a["triggered_at"]).total_seconds() / 60)
                ack_color = "#22c55e" if a["status"] == "ACK" else "#64748b"

                ac1, ac2, ac3 = st.columns([7, 2, 2])
                with ac1:
                    st.markdown(
                        f"<div style='background:{card_bg};border:1px solid {card_bdr};"
                        f"border-radius:8px;padding:10px 14px;margin-bottom:4px'>"
                        f"  <div style='display:flex;justify-content:space-between;"
                        f"  align-items:center;margin-bottom:5px'>"
                        f"    <div style='display:flex;align-items:center;gap:6px'>"
                        f"      <span style='background:{sev_c}22;border:1px solid {sev_c}55;"
                        f"      border-radius:10px;padding:1px 8px;font-size:10px;color:{sev_c};"
                        f"      font-weight:700'>{a['severity']}</span>"
                        f"      <span style='font-size:12px;font-weight:600;color:#e2e8f0'>{a['well_name']}</span>"
                        f"      <span style='font-size:11px;color:#64748b'>({a['esp_id']})</span>"
                        f"    </div>"
                        f"    <span style='font-size:10px;color:#475569'>"
                        f"    {a['triggered_at'].strftime('%H:%M:%S')} · {mins_ago}m ago</span>"
                        f"  </div>"
                        f"  <div style='font-size:11px;color:#94a3b8;margin-bottom:4px'>"
                        f"  <b style='color:#e2e8f0'>{a['fault_code']}</b> — {a['description'][:100]}</div>"
                        f"  <div style='font-size:10px;color:#475569'>{a['field']} &nbsp;·&nbsp; "
                        f"  Status: <span style='color:{ack_color};font-weight:600'>{a['status']}</span>"
                        f"  {' · ' + a['ack_by'] if a['ack_by'] else ''}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with ac2:
                    if a["status"] == "NEW":
                        if st.button("✔ Ack", key=f"ack_{a['id']}", use_container_width=True):
                            a["status"] = "ACK"
                            a["ack_by"] = "ops@demo.com"
                            st.rerun(scope="fragment")
                with ac3:
                    if st.button("🔧 WO", key=f"wo_{a['id']}", use_container_width=True):
                        new_wo = {
                            "AUFNR": f"40002{len(st.session_state.extra_wos)+1:05d}",
                            "KTEXT": f"Auto WO: {a['fault_code']} on {a['well_name']}",
                            "AUART": "PM02",
                            "FTRMS": (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d"),
                            "STATU": "CRTD",
                            "GWLDT": (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d"),
                            "PRIOK": "1" if a["severity"] == "CRITICAL" else "2",
                            "TECH":  "Unassigned",
                            "esp_id":    a["esp_id"],
                            "well_name": a["well_name"],
                        }
                        st.session_state.extra_wos.append(new_wo)
                        st.success(f"Work order {new_wo['AUFNR']} created for {a['well_name']}")

        st.divider()
        st.markdown("#### Alert Statistics")
        as1, as2 = st.columns(2)
        df_alerts = pd.DataFrame(alerts)
        sev_badge_colors = {"CRITICAL": "#ef4444", "HIGH": "#eab308", "MEDIUM": "#3b82f6", "LOW": "#22c55e"}
        if not df_alerts.empty:
            with as1:
                cnts = df_alerts["severity"].value_counts().reset_index()
                cnts.columns = ["severity", "count"]
                fig_pie = px.pie(cnts, values="count", names="severity",
                                 color="severity", color_discrete_map=sev_badge_colors,
                                 title="Alerts by Severity", hole=0.4)
                fig_pie.update_layout(paper_bgcolor=COLORS["bg"], font_color=COLORS["text"], height=280)
                st.plotly_chart(fig_pie, use_container_width=True)
            with as2:
                if "field" in df_alerts.columns:
                    fcnts = df_alerts["field"].value_counts().reset_index()
                    fcnts.columns = ["field", "count"]
                    fig_field = px.bar(fcnts, x="field", y="count",
                                       title="Alerts by Field", color_discrete_sequence=["#eab308"])
                    fig_field.update_layout(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["panel"],
                                            font_color=COLORS["text"], height=280,
                                            xaxis=dict(gridcolor="#1e293b"),
                                            yaxis=dict(gridcolor="#1e293b"))
                    st.plotly_chart(fig_field, use_container_width=True)


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 4 — SAP MAINTENANCE
    # ═══════════════════════════════════════════════════════════════════════════
    with tab4:
        sap_tabs = st.tabs(["Open Work Orders", "PM Schedule", "Equipment Master", "Maintenance History"])

        all_wos = sap_data.get_all_open_work_orders() + st.session_state.extra_wos

        with sap_tabs[0]:
            st.markdown("#### Open Work Orders")
            if all_wos:
                df_wo = pd.DataFrame(all_wos)
                pri_colors = {"1": "#ef4444", "2": "#eab308", "3": "#3b82f6", "4": "#22c55e"}
                for _, row in df_wo.iterrows():
                    pc = pri_colors.get(str(row.get("PRIOK", "4")), "#64748b")
                    st.markdown(
                        f"<div style='background:#0f172a;border-left:4px solid {pc};"
                        f"border:1px solid #1e293b;border-radius:6px;padding:10px;margin-bottom:6px'>"
                        f"<span style='background:{pc}22;color:{pc};border:1px solid {pc}55;"
                        f"border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700'>"
                        f"P{row.get('PRIOK','?')}</span> "
                        f"<strong style='color:#e2e8f0'>{row.get('AUFNR','?')}</strong> · "
                        f"{row.get('well_name','?')} ({row.get('esp_id','?')})<br>"
                        f"<span style='color:#94a3b8;font-size:0.88rem'>{row.get('KTEXT','?')}</span><br>"
                        f"<span style='color:#64748b;font-size:0.80rem'>"
                        f"Type: {row.get('AUART','?')} · Due: {row.get('FTRMS','?')} · "
                        f"Status: {row.get('STATU','?')} · Tech: {row.get('TECH','?')}"
                        f"</span></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No open work orders.")

        with sap_tabs[1]:
            st.markdown("#### Planned Maintenance Schedule")
            pm_sched = sap_data.get_all_pm_schedule()
            df_pm = pd.DataFrame(pm_sched)
            df_pm["next_pm_date"] = pd.to_datetime(df_pm["next_pm_date"])
            df_pm = df_pm.sort_values("next_pm_date")
            today = datetime.utcnow()
            df_pm["days_until"] = (df_pm["next_pm_date"] - today).dt.days
            df_pm["color"] = df_pm["days_until"].apply(
                lambda d: "#ef4444" if d <= 3 else ("#eab308" if d <= 14 else "#22c55e")
            )
            fig_gantt = go.Figure()
            for _, row in df_pm.iterrows():
                fig_gantt.add_trace(go.Bar(
                    x=[row["days_until"]], y=[row["well_name"]], orientation="h",
                    marker_color=row["color"], name=row["well_name"],
                    hovertemplate=f"{row['well_name']}: {row['next_pm_date'].strftime('%Y-%m-%d')} ({row['days_until']}d)<extra></extra>",
                    showlegend=False,
                ))
            fig_gantt.add_vline(x=0, line_color="#64748b", line_dash="dash")
            fig_gantt.update_layout(
                paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["panel"],
                font_color=COLORS["text"], height=420,
                xaxis=dict(title="Days Until Next PM", gridcolor="#1e293b"),
                yaxis=dict(gridcolor="#1e293b"),
                barmode="overlay",
                margin=dict(l=10, r=10, t=20, b=30),
            )
            st.plotly_chart(fig_gantt, use_container_width=True)
            st.dataframe(df_pm[["well_name", "esp_id", "next_pm_date", "days_until"]], use_container_width=True, hide_index=True)

        with sap_tabs[2]:
            st.markdown("#### Equipment Master (SAP EQUI)")
            sap_eq_sel = st.selectbox("Select Well", [w["esp_id"] for w in simulator.WELLS],
                                       format_func=lambda x: f"{x} — {next(w['name'] for w in simulator.WELLS if w['esp_id']==x)}",
                                       key="sap_eq_select")
            eq_data = sap_data.get_sap_data(sap_eq_sel)
            eq = eq_data.get("equipment", {})
            if eq:
                eq_df = pd.DataFrame([
                    {"Field": "Equipment Number (EQUNR)", "Value": eq.get("EQUNR", "—")},
                    {"Field": "Description (EQKTX)",      "Value": eq.get("EQKTX", "—")},
                    {"Field": "Planning Group (INGRP)",   "Value": eq.get("INGRP", "—")},
                    {"Field": "Manufacturer (HERST)",     "Value": eq.get("HERST", "—")},
                    {"Field": "Serial Number (SERGE)",    "Value": eq.get("SERGE", "—")},
                    {"Field": "Construction Year (BAUJJ)","Value": eq.get("BAUJJ", "—")},
                    {"Field": "Asset Number (ANLNR)",     "Value": eq.get("ANLNR", "—")},
                ])
                st.dataframe(eq_df, use_container_width=True, hide_index=True)

        with sap_tabs[3]:
            st.markdown("#### Maintenance History")
            hist_sel = st.selectbox("Select Well", [w["esp_id"] for w in simulator.WELLS],
                                     format_func=lambda x: f"{x} — {next(w['name'] for w in simulator.WELLS if w['esp_id']==x)}",
                                     key="sap_hist_select")
            hist_data = sap_data.get_sap_data(hist_sel).get("history", [])
            if hist_data:
                st.dataframe(pd.DataFrame(hist_data), use_container_width=True, hide_index=True)
            else:
                st.info("No maintenance history found.")


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 5 — ESP ADVISOR  (Genie Operations AI style)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab5:
        st.markdown("""<style>
        .g-hdr{background:#0a0e1a;border:1px solid #1e293b;border-radius:12px;
               padding:12px 16px;display:flex;align-items:center;gap:12px;margin-bottom:10px}
        .g-av{width:36px;height:36px;min-width:36px;background:#1e1b3a;
              border:1.5px solid #7c3aed;border-radius:50%;display:flex;
              align-items:center;justify-content:center;font-size:18px;line-height:36px}
        .g-dot{display:inline-block;width:7px;height:7px;border-radius:50%;
               vertical-align:middle;margin-right:5px}
        .crit-banner{background:#1f000066;border:1px solid #ef4444;border-radius:8px;
                     padding:8px 14px;margin-bottom:10px;color:#f87171;font-size:11px;font-weight:600}
        [data-testid="stChatMessage"]{background:transparent!important;padding:4px 0!important}
        [data-testid="stChatMessageContent"]{font-size:12px!important;line-height:1.6!important}
        </style>""", unsafe_allow_html=True)

        critical_ws = [w for w in wells if w["run_status"] == "CRITICAL"]
        warn_ws     = [w for w in wells if w["run_status"] == "WARNING"]
        if critical_ws:
            hdr_color = "#ef4444"
            hdr_text  = f"⚠ {len(critical_ws)} CRITICAL · {len(warn_ws)} WARNING active"
        else:
            hdr_color = "#22c55e"
            hdr_text  = f"All systems nominal · {len(warn_ws)} warning{'s' if len(warn_ws)!=1 else ''}"

        _genie_space_id = os.getenv("GENIE_SPACE_ID", "")
        _workspace_host = os.getenv("DATABRICKS_HOST", "fevm-oil-pump-monitor.cloud.databricks.com").rstrip("/")
        if not _workspace_host.startswith("http"):
            _workspace_host = "https://" + _workspace_host
        _genie_url = f"{_workspace_host}/genie/rooms/{_genie_space_id}" if _genie_space_id else "#"
        st.markdown(f"""<div class="g-hdr">
          <div class="g-av">✨</div>
          <div style="flex:1">
            <div style="color:#e2e8f0;font-size:13px;font-weight:700;margin:0">ESP Operations AI · Genie</div>
            <div style="font-size:10px;color:#64748b;margin-top:2px">
              <span class="g-dot" style="background:{hdr_color}"></span>
              {hdr_text} &nbsp;·&nbsp; Databricks Genie · UC governed
            </div>
          </div>
          <a href="{_genie_url}" target="_blank" rel="noopener" style="
              background:#1e293b;border:1px solid #38bdf8;border-radius:6px;
              padding:4px 10px;font-size:10px;font-weight:600;color:#38bdf8;
              text-decoration:none;margin-right:10px;white-space:nowrap;">
            🔗 Open Genie Space ↗
          </a>
          <div style="font-size:10px;color:#475569">{datetime.utcnow().strftime('%H:%M:%S UTC')}</div>
        </div>""", unsafe_allow_html=True)

        if critical_ws:
            crit_names = ", ".join(f"{w['esp_id']} ({w['name']})" for w in critical_ws)
            st.markdown(
                f'<div class="crit-banner">⚠ CRITICAL: {crit_names} — immediate action required</div>',
                unsafe_allow_html=True)

        ctx_options = ["Analyze entire fleet"] + [f"{w['esp_id']} — {w['name']}" for w in simulator.WELLS]
        ctx_sel = st.selectbox("", ctx_options, key="advisor_ctx", label_visibility="collapsed")

        if not st.session_state.chat_history:
            st.markdown(
                "<div style='background:#0a0e1a;border:1px solid #1e293b;border-radius:12px;"
                "padding:40px 20px;text-align:center;color:#334155;font-size:12px;"
                "font-style:italic;margin-bottom:8px'>"
                "✨ Ask Genie about your ESP fleet — natural-language SQL over live telemetry, "
                "fault histories, work orders, and failure predictions in Unity Catalog.</div>",
                unsafe_allow_html=True)
        else:
            for msg in st.session_state.chat_history:
                avatar = "👤" if msg["role"] == "user" else "✨"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

        quick_qs = [
            "Top 5 wells by failure risk score",
            "Average MTTF by fault code",
            "Open work orders by priority",
            "Wells with vibration above 4 mm/s",
            "Health score distribution by zone",
            "ESPs failed in the last 30 days",
        ]
        st.markdown("<p style='font-size:10px;color:#475569;margin:8px 0 4px'>Quick prompts:</p>",
                    unsafe_allow_html=True)
        qcols = st.columns(6)
        for qi, (qc, q) in enumerate(zip(qcols, quick_qs)):
            with qc:
                if st.button(q, key=f"qq_{qi}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": quick_qs[qi]})
                    st.rerun(scope="fragment")

        if prompt := st.chat_input("Ask Genie about your ESP fleet…"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.rerun(scope="fragment")

        if st.button("↺ Clear chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.session_state.esp_genie_conv = None
            st.rerun(scope="fragment")

        if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
            last_user_msg = st.session_state.chat_history[-1]["content"]

            if "esp_genie_conv" not in st.session_state:
                st.session_state.esp_genie_conv = None

            with st.chat_message("assistant", avatar="✨"):
                with st.spinner("Genie is reasoning over the ESP data plane…"):
                    shaped = ask_genie(
                        question=last_user_msg,
                        conversation_id=st.session_state.esp_genie_conv,
                    )
                    if shaped.get("error"):
                        reply = (
                            f"**Genie unavailable:** {shaped['error']}\n\n"
                            "**Simulated response based on live fleet data:**\n"
                            + _simulated_advisor_response(last_user_msg, wells, kpis)
                        )
                    else:
                        st.session_state.esp_genie_conv = shaped.get("conversation_id")
                        reply = shaped.get("text") or "_(Genie returned no answer — try rephrasing.)_"
                    st.markdown(reply)

            st.session_state.chat_history.append({"role": "assistant", "content": reply})


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 6 — DATA FLOW
    # ═══════════════════════════════════════════════════════════════════════════
    with tab6:
        tick = st.session_state.tick
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("Active Wells",   "12 / 12",            "All Online")
        sc2.metric("Records / Min",  f"{12*60 + tick*3:,}", "")
        sc3.metric("Bronze Latency", "1.2 s",              "")
        sc4.metric("ML Inference",   "4.8 s",              "p95")
        sc5.metric("Alert Latency",  "2.1 s",              "")

        FLOW_HTML = r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;padding:6px 4px;max-width:1440px;margin:0 auto}
html{background:#0f172a}
@keyframes flow-dash{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}
.fd{animation:flow-dash 1.6s linear infinite}
.fn{cursor:pointer}
.fn>rect{transition:all .2s}
</style></head><body>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:8px 14px;flex:1;min-width:150px"><div style="font-size:9px;color:#64748b;letter-spacing:.06em;margin-bottom:4px">SAP INTEGRATION</div><div style="font-size:11px;font-weight:600;color:#f97316;font-family:monospace">S/4HANA · BDC · Delta Share</div></div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:8px 14px;flex:1;min-width:150px"><div style="font-size:9px;color:#64748b;letter-spacing:.06em;margin-bottom:4px">COMPUTE</div><div style="font-size:11px;font-weight:600;color:#7c3aed;font-family:monospace">Databricks Spark (Serverless)</div></div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:8px 14px;flex:1;min-width:150px"><div style="font-size:9px;color:#64748b;letter-spacing:.06em;margin-bottom:4px">AI / NL-SQL</div><div style="font-size:11px;font-weight:600;color:#6366f1;font-family:monospace">ESP Advisor · Databricks Genie</div></div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:8px 14px;flex:1;min-width:150px"><div style="font-size:9px;color:#64748b;letter-spacing:.06em;margin-bottom:4px">FRONTEND</div><div style="font-size:11px;font-weight:600;color:#22c55e;font-family:monospace">Streamlit · 7 tabs · live</div></div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:8px 14px;flex:1;min-width:150px"><div style="font-size:9px;color:#64748b;letter-spacing:.06em;margin-bottom:4px">GOVERNANCE</div><div style="font-size:11px;font-weight:600;color:#f97316;font-family:monospace">Unity Catalog</div></div>
</div>
<div style="display:flex;gap:16px;align-items:flex-start">
  <div style="flex:1;background:#0f172a;border:1px solid #1e293b;border-radius:12px;overflow:hidden">
    <div style="padding:10px 16px;border-bottom:1px solid #1e293b;display:flex;align-items:center;gap:8px">
      <span style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em">Data &amp; AI Flow Diagram</span>
      <span style="margin-left:auto;font-size:10px;color:#475569">Click any node for details</span>
    </div>
    <svg id="dg" viewBox="0 0 1120 590" style="width:100%;display:block" xmlns="http://www.w3.org/2000/svg">
    <style>@keyframes flow-dash{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}</style>
    <defs>
      <marker id="a1" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#3b82f6"/></marker>
      <marker id="a2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#f97316"/></marker>
      <marker id="a3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#4f46e5"/></marker>
      <marker id="a4" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#14b8a6"/></marker>
      <marker id="a5" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#7c3aed"/></marker>
      <marker id="a6" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#a78bfa"/></marker>
      <marker id="a7" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#8b5cf6"/></marker>
      <marker id="a8" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6366f1"/></marker>
      <marker id="a9" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#22c55e"/></marker>
      <marker id="a4b" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#14b8a6"/></marker>
    </defs>
    <!-- Unity Catalog box -->
    <rect x="450" y="104" width="630" height="82" rx="10" fill="none" stroke="#f97316" stroke-width="1" stroke-dasharray="6 3" stroke-opacity=".45"/>
    <rect x="460" y="96" width="162" height="16" rx="4" fill="#0f172a"/>
    <text x="466" y="107" fill="#f97316" font-size="10" font-family="Helvetica,Arial,sans-serif" font-weight="700">Unity Catalog Governance</text>
    <!-- Section labels -->
    <text x="20" y="104" fill="#64748b" font-size="10" font-family="Helvetica,Arial,sans-serif" font-weight="700">DATA PIPELINE</text>
    <text x="20" y="344" fill="#64748b" font-size="10" font-family="Helvetica,Arial,sans-serif" font-weight="700">ANALYSIS &amp; AI SERVING</text>
    <!-- Divider -->
    <line x1="20" y1="320" x2="1100" y2="320" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
    <!-- ESP Sources -> Unity Catalog / Bronze Ingest (right-angle routing above SAP) -->
    <path d="M175,120 L175,58 L527,58 L527,120" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M175,120 L175,58 L527,58 L527,120" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:0s"/>
    <path d="M175,120 L175,58 L527,58 L527,120" fill="none" stroke="none" marker-end="url(#a1)"/>
    <text x="351" y="50" text-anchor="middle" fill="#3b82f6" font-size="9" font-family="Helvetica,Arial,sans-serif" font-weight="600">IoT stream → UC</text>
    <!-- SAP Integration -> Bronze -->
    <path d="M390,152 L450,152" fill="none" stroke="#f97316" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M390,152 L450,152" fill="none" stroke="#f97316" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.3s"/>
    <path d="M390,152 L450,152" fill="none" stroke="none" marker-end="url(#a2)"/>
    <text x="420" y="141" text-anchor="middle" fill="#f97316" font-size="9" font-family="Helvetica,Arial,sans-serif" font-weight="600">Delta Share</text>
    <!-- Bronze -> Lakebase -->
    <path d="M605,152 L665,152" fill="none" stroke="#4f46e5" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M605,152 L665,152" fill="none" stroke="#4f46e5" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.6s"/>
    <path d="M605,152 L665,152" fill="none" stroke="none" marker-end="url(#a3)"/>
    <text x="635" y="141" text-anchor="middle" fill="#4f46e5" font-size="9" font-family="Helvetica,Arial,sans-serif" font-weight="600">JDBC</text>
    <!-- Lakebase -> Silver/Gold -->
    <path d="M820,152 L880,152" fill="none" stroke="#14b8a6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M820,152 L880,152" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.9s"/>
    <path d="M820,152 L880,152" fill="none" stroke="none" marker-end="url(#a4)"/>
    <text x="850" y="141" text-anchor="middle" fill="#14b8a6" font-size="9" font-family="Helvetica,Arial,sans-serif" font-weight="600">ML reads</text>
    <!-- Lakebase -> Ops Dashboard -->
    <path d="M742,184 C742,280 1007,280 1007,360" fill="none" stroke="#14b8a6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M742,184 C742,280 1007,280 1007,360" fill="none" stroke="#14b8a6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.45s"/>
    <path d="M742,184 C742,280 1007,280 1007,360" fill="none" stroke="none" marker-end="url(#a4b)"/>
    <text x="910" y="274" text-anchor="middle" fill="#14b8a6" font-size="9" font-family="Helvetica,Arial,sans-serif" font-weight="600">live ops data</text>
    <!-- Silver/Gold -> Diag Rules -->
    <path d="M950,184 L950,320 L97,320 L97,360" fill="none" stroke="#7c3aed" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M950,184 L950,320 L97,320 L97,360" fill="none" stroke="#7c3aed" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:0s"/>
    <path d="M950,184 L950,320 L97,320 L97,360" fill="none" stroke="none" marker-end="url(#a5)"/>
    <!-- Silver/Gold -> Anomaly Detect -->
    <path d="M980,184 L980,320 L317,320 L317,360" fill="none" stroke="#7c3aed" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M980,184 L980,320 L317,320 L317,360" fill="none" stroke="#7c3aed" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.12s"/>
    <path d="M980,184 L980,320 L317,320 L317,360" fill="none" stroke="none" marker-end="url(#a5)"/>
    <!-- Silver/Gold -> Predictive ML -->
    <path d="M1010,184 L1010,320 L537,320 L537,360" fill="none" stroke="#7c3aed" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M1010,184 L1010,320 L537,320 L537,360" fill="none" stroke="#7c3aed" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.24s"/>
    <path d="M1010,184 L1010,320 L537,320 L537,360" fill="none" stroke="none" marker-end="url(#a5)"/>
    <!-- Diag Rules -> ESP Advisor AI -->
    <path d="M175,392 C425,392 425,363 675,363" fill="none" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M175,392 C425,392 425,363 675,363" fill="none" stroke="#a78bfa" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.3s"/>
    <path d="M175,392 C425,392 425,363 675,363" fill="none" stroke="none" marker-end="url(#a6)"/>
    <!-- Anomaly Detect -> ESP Advisor AI -->
    <path d="M400,392 C537,392 537,390 675,390" fill="none" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M400,392 C537,392 537,390 675,390" fill="none" stroke="#a78bfa" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.6s"/>
    <path d="M400,392 C537,392 537,390 675,390" fill="none" stroke="none" marker-end="url(#a6)"/>
    <!-- Predictive ML -> ESP Advisor AI -->
    <path d="M615,392 C645,392 645,417 675,417" fill="none" stroke="#8b5cf6" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M615,392 C645,392 645,417 675,417" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:.9s"/>
    <path d="M615,392 C645,392 645,417 675,417" fill="none" stroke="none" marker-end="url(#a7)"/>
    <!-- ESP Advisor AI -> Ops Dashboard -->
    <path d="M870,390 L920,392" fill="none" stroke="#6366f1" stroke-width="1.5" stroke-dasharray="6 3" stroke-opacity=".2"/>
    <path d="M870,390 L920,392" fill="none" stroke="#6366f1" stroke-width="2" stroke-dasharray="6 3" class="fd" style="animation-delay:1.2s"/>
    <path d="M870,390 L920,392" fill="none" stroke="none" marker-end="url(#a8)"/>
    <text x="895" y="381" text-anchor="middle" fill="#6366f1" font-size="9" font-family="Helvetica,Arial,sans-serif" font-weight="600">alerts / actions</text>
    <!-- ROW 1 NODES -->
    <g class="fn" id="fn-esp_src" onclick="sel('esp_src')">
      <rect x="20" y="120" width="155" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="121" y="126" width="48" height="14" rx="3" fill="#3b82f633" stroke="#3b82f6" stroke-width=".8"/>
      <text x="145" y="136.5" text-anchor="middle" fill="#3b82f6" font-size="8" font-family="monospace" font-weight="700">SOURCE</text>
      <text x="30" y="146" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">ESP Sources</text>
      <text x="30" y="162" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">IoT Field Devices</text>
    </g>
    <g class="fn" id="fn-sap_int" onclick="sel('sap_int')">
      <rect x="235" y="120" width="155" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="336" y="126" width="48" height="14" rx="3" fill="#f9731633" stroke="#f97316" stroke-width=".8"/>
      <text x="360" y="136.5" text-anchor="middle" fill="#f97316" font-size="8" font-family="monospace" font-weight="700">SAP</text>
      <text x="245" y="146" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">SAP Integration</text>
      <text x="245" y="162" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">PM · BDC · Delta Share</text>
    </g>
    <g class="fn" id="fn-bronze" onclick="sel('bronze')">
      <rect x="450" y="120" width="155" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="551" y="126" width="48" height="14" rx="3" fill="#4f46e533" stroke="#4f46e5" stroke-width=".8"/>
      <text x="575" y="136.5" text-anchor="middle" fill="#4f46e5" font-size="8" font-family="monospace" font-weight="700">INGEST</text>
      <text x="460" y="146" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Bronze Ingest</text>
      <text x="460" y="162" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">Raw Delta · Append-only</text>
    </g>
    <g class="fn" id="fn-lakebase" onclick="sel('lakebase')">
      <rect x="665" y="120" width="155" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="766" y="126" width="48" height="14" rx="3" fill="#14b8a633" stroke="#14b8a6" stroke-width=".8"/>
      <text x="790" y="136.5" text-anchor="middle" fill="#14b8a6" font-size="8" font-family="monospace" font-weight="700">POSTGRES</text>
      <text x="675" y="146" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Lakebase DB</text>
      <text x="675" y="162" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">Managed PostgreSQL 16</text>
    </g>
    <g class="fn" id="fn-silver" onclick="sel('silver')">
      <rect x="880" y="120" width="200" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="1026" y="126" width="48" height="14" rx="3" fill="#7c3aed33" stroke="#7c3aed" stroke-width=".8"/>
      <text x="1050" y="136.5" text-anchor="middle" fill="#7c3aed" font-size="8" font-family="monospace" font-weight="700">COMPUTE</text>
      <text x="890" y="146" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Silver / Gold</text>
      <text x="890" y="162" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">Feature Eng · ML Pipelines</text>
    </g>
    <!-- ROW 2 NODES -->
    <g class="fn" id="fn-diag" onclick="sel('diag')">
      <rect x="20" y="360" width="155" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="121" y="366" width="48" height="14" rx="3" fill="#a78bfa33" stroke="#a78bfa" stroke-width=".8"/>
      <text x="145" y="376.5" text-anchor="middle" fill="#a78bfa" font-size="8" font-family="monospace" font-weight="700">RULES</text>
      <text x="30" y="386" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Diag Rules</text>
      <text x="30" y="402" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">SPE / API RP 11S</text>
    </g>
    <g class="fn" id="fn-anomaly" onclick="sel('anomaly')">
      <rect x="235" y="360" width="165" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="346" y="366" width="48" height="14" rx="3" fill="#a78bfa33" stroke="#a78bfa" stroke-width=".8"/>
      <text x="370" y="376.5" text-anchor="middle" fill="#a78bfa" font-size="8" font-family="monospace" font-weight="700">ML</text>
      <text x="245" y="386" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Anomaly Detect</text>
      <text x="245" y="402" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">Z-Score · 48h Window</text>
    </g>
    <g class="fn" id="fn-pred_ml" onclick="sel('pred_ml')">
      <rect x="460" y="360" width="155" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="561" y="366" width="48" height="14" rx="3" fill="#8b5cf633" stroke="#8b5cf6" stroke-width=".8"/>
      <text x="585" y="376.5" text-anchor="middle" fill="#8b5cf6" font-size="8" font-family="monospace" font-weight="700">MLFLOW</text>
      <text x="470" y="386" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Predictive ML</text>
      <text x="470" y="402" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">XGBoost · Failure Risk</text>
    </g>
    <g class="fn" id="fn-advisor" onclick="sel('advisor')">
      <rect x="675" y="350" width="195" height="80" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="816" y="356" width="48" height="14" rx="3" fill="#6366f133" stroke="#6366f1" stroke-width=".8"/>
      <text x="840" y="366.5" text-anchor="middle" fill="#6366f1" font-size="8" font-family="monospace" font-weight="700">GENIE</text>
      <text x="685" y="376" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">ESP Advisor · Genie</text>
      <text x="685" y="392" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">Databricks Genie Space</text>
      <text x="685" y="408" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">NL-to-SQL · UC governed</text>
    </g>
    <g class="fn" id="fn-ops" onclick="sel('ops')">
      <rect x="920" y="360" width="175" height="64" rx="8" fill="#0a0e1a" stroke="#1e293b" stroke-width="1"/>
      <rect x="1041" y="366" width="48" height="14" rx="3" fill="#22c55e33" stroke="#22c55e" stroke-width=".8"/>
      <text x="1065" y="376.5" text-anchor="middle" fill="#22c55e" font-size="8" font-family="monospace" font-weight="700">STRM</text>
      <text x="930" y="386" fill="#e2e8f0" font-size="11" font-family="Helvetica,Arial,sans-serif" font-weight="700">Ops Dashboard</text>
      <text x="930" y="402" fill="#64748b" font-size="9.5" font-family="Helvetica,Arial,sans-serif">Streamlit · 7 tabs</text>
    </g>
    <g transform="translate(20,556)">
      <rect x="0" y="0" width="12" height="12" rx="2" fill="#3b82f6"/><text x="16" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">Source / IoT</text>
      <rect x="110" y="0" width="12" height="12" rx="2" fill="#f97316"/><text x="126" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">SAP / ERP</text>
      <rect x="210" y="0" width="12" height="12" rx="2" fill="#4f46e5"/><text x="226" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">Ingest</text>
      <rect x="290" y="0" width="12" height="12" rx="2" fill="#14b8a6"/><text x="306" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">Lakebase</text>
      <rect x="390" y="0" width="12" height="12" rx="2" fill="#7c3aed"/><text x="406" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">Compute</text>
      <rect x="480" y="0" width="12" height="12" rx="2" fill="#a78bfa"/><text x="496" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">AI / ML</text>
      <rect x="560" y="0" width="12" height="12" rx="2" fill="#6366f1"/><text x="576" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">Genie · NL-SQL</text>
      <rect x="660" y="0" width="12" height="12" rx="2" fill="#22c55e"/><text x="676" y="10" fill="#64748b" font-size="9" font-family="Helvetica,Arial,sans-serif">Serving / UI</text>
    </g>
    </svg>
  </div>
  <div id="panel" style="width:240px;flex-shrink:0"></div>
</div>
<script>
const D={
  esp_src:{color:'#3b82f6',label:'ESP Sources',sub:'IoT Field Devices',badge:'SOURCE',detail:['12 active ESP wells','Pump speed, current, vibration','60-second reading interval','MQTT ingestion pipeline']},
  sap_int:{color:'#f97316',label:'SAP Integration',sub:'PM · BDC · Delta Share',badge:'SAP',detail:['SAP PM: EQUI / QMEL / AUFK','BDC: harmonized data layer','Delta Sharing protocol','Open table format export']},
  bronze:{color:'#4f46e5',label:'Bronze Ingest',sub:'Raw Delta · Append-only',badge:'INGEST',detail:['Raw sensor + SAP tables','Delta format, append-only','Schema enforcement','Autoloader streaming ingest']},
  lakebase:{color:'#14b8a6',label:'Lakebase DB',sub:'Managed PostgreSQL 16',badge:'POSTGRES',detail:['Instance: esp-pm-db','Tables: alerts, work_orders','OAuth token auth · SSL required','OLTP for operational data']},
  silver:{color:'#7c3aed',label:'Silver / Gold',sub:'Feature Eng · ML Pipelines',badge:'COMPUTE',detail:['Spark serverless pipelines','Feature engineering layer','ML training feature store','Gold: aggregated KPIs + UC']},
  diag:{color:'#a78bfa',label:'Diag Rules',sub:'SPE / API RP 11S',badge:'RULES',detail:['8 deterministic rules','SPE / API RP 11S standards','Threshold-based detection','Generates structured alerts']},
  anomaly:{color:'#a78bfa',label:'Anomaly Detect',sub:'Z-Score · 48h Window',badge:'ML',detail:['Z-Score outlier detection','IQR statistical bounds','48-hour rolling window','Multi-sensor correlation']},
  pred_ml:{color:'#8b5cf6',label:'Predictive ML',sub:'XGBoost · Failure Risk',badge:'MLFLOW',detail:['XGBoost / Random Forest','Failure probability 0-1','Logged in MLflow Registry','30/60/90-day forecasts']},
  advisor:{color:'#6366f1',label:'ESP Advisor · Genie',sub:'Databricks Genie Space',badge:'GENIE',detail:['Genie Conversation API','Natural-language → governed SQL','Reads UC tables: alerts, work orders, telemetry','Conversation memory across turns']},
  ops:{color:'#22c55e',label:'Ops Dashboard',sub:'Streamlit · 7 tabs',badge:'STRM',detail:['This application','6 tabs: Overview to Data Flow','Work order management','Real-time alert display']},
};
const HOW=[
  {c:'#3b82f6',t:'ESP sensors stream pump data every 60 seconds to the pipeline'},
  {c:'#f97316',t:'SAP PM exports equipment and work order data via Delta Share'},
  {c:'#4f46e5',t:'Bronze Ingest consolidates raw sensor and SAP data into Delta tables'},
  {c:'#14b8a6',t:'Lakebase PostgreSQL stores operational alerts and work orders (OLTP)'},
  {c:'#7c3aed',t:'Silver/Gold layer runs feature engineering and ML training pipelines'},
  {c:'#a78bfa',t:'Diagnostic rules and anomaly models score failure risk on every cycle'},
  {c:'#6366f1',t:'ESP Advisor (Databricks Genie) answers natural-language questions over UC tables with governed SQL'},
];
let cur=null;
function showHow(){
  document.getElementById('panel').innerHTML='<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:16px">'
    +'<div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px">How It Works</div>'
    +HOW.map((s,i)=>'<div style="display:flex;gap:10px;margin-bottom:10px;align-items:flex-start">'
      +'<div style="width:20px;height:20px;border-radius:50%;background:'+s.c+'33;border:1px solid '+s.c+';color:'+s.c+';font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0">'+(i+1)+'</div>'
      +'<div style="font-size:11px;color:#94a3b8;line-height:1.5">'+s.t+'</div></div>').join('')
    +'</div>';
}
function sel(id){
  if(cur){const r=document.querySelector('#fn-'+cur+'>rect');if(r){r.setAttribute('stroke','#1e293b');r.setAttribute('stroke-width','1');r.style.filter='none';}}
  if(cur===id){cur=null;showHow();return;}
  cur=id;
  const r=document.querySelector('#fn-'+id+'>rect');const d=D[id];
  if(r&&d){r.setAttribute('stroke',d.color);r.setAttribute('stroke-width','2');r.style.filter='drop-shadow(0 0 6px '+d.color+'88)';}
  if(!d)return;
  document.getElementById('panel').innerHTML='<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:16px">'
    +'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
    +'<div style="width:10px;height:10px;border-radius:2px;background:'+d.color+'"></div>'
    +'<div><div style="font-weight:700;font-size:13px;color:#e2e8f0">'+d.label+'</div>'
    +'<div style="font-size:10px;color:#64748b">'+d.sub+'</div></div></div>'
    +'<div style="display:inline-block;margin-bottom:10px;background:'+d.color+'22;color:'+d.color+';border:1px solid '+d.color+';border-radius:4px;padding:2px 8px;font-size:9px;font-weight:700;font-family:monospace">'+d.badge+'</div>'
    +'<div style="display:flex;flex-direction:column;gap:6px">'
    +d.detail.map(x=>'<div style="font-size:11px;color:#94a3b8;padding:5px 9px;background:#060b18;border-radius:5px;font-family:monospace;line-height:1.5">'+x+'</div>').join('')
    +'</div>'
    +'<button onclick="clr()" style="margin-top:12px;width:100%;background:transparent;border:1px solid #1e293b;border-radius:5px;color:#64748b;font-size:11px;padding:5px 0;cursor:pointer">Dismiss</button>'
    +'</div>';
}
function clr(){if(cur){const r=document.querySelector('#fn-'+cur+'>rect');if(r){r.setAttribute('stroke','#1e293b');r.setAttribute('stroke-width','1');r.style.filter='none';}cur=null;}showHow();}
showHow();
</script>
</body></html>"""
        components.html(FLOW_HTML, height=700, scrolling=True)


    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 7 — AI MAINTENANCE SCHEDULER (Agentic Perceive–Reason–Act)
    # ═══════════════════════════════════════════════════════════════════════════
    with tab7:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:10px;margin-bottom:6px'>"
            "<span style='font-size:18px'>🧠</span>"
            "<div>"
            "<div style='font-size:14px;font-weight:700;color:#e2e8f0'>Agentic AI Maintenance Scheduler</div>"
            "<div style='font-size:10px;color:#64748b'>Permian Basin EOR Facilities &nbsp;·&nbsp; "
            "Perceive → Reason → Act loop</div>"
            "</div></div>",
            unsafe_allow_html=True,
        )

        # Run the agent loop
        agent_out = scheduler_agent.run_agent_loop(wells)
        ag_wos    = agent_out["work_orders"]
        ag_sched  = agent_out["schedule"]
        ag_roster = agent_out["roster"]
        ag_summ   = agent_out["summary"]

        # ── Sub-tabs ────────────────────────────────────────────────────────
        ai_tabs = st.tabs([
            "Daily Summary",
            "AI Work Orders",
            "Technician Schedule",
            "Agent Reasoning",
            "API Endpoints",
        ])

        # ── SUB-TAB 1: Daily Summary (GET /agent/daily-summary) ────────────
        with ai_tabs[0]:
            st.markdown("#### Agent Daily Summary")
            st.markdown(
                f"<div style='font-size:10px;color:#475569;margin-bottom:12px'>"
                f"Generated: {ag_summ['generated_at']} &nbsp;·&nbsp; "
                f"Fleet avg risk: {ag_summ['fleet_avg_risk']}%</div>",
                unsafe_allow_html=True,
            )
            sk1, sk2, sk3, sk4, sk5 = st.columns(5)
            def _akpi(col, lbl, val, clr):
                col.markdown(
                    f"<div style='background:#0f172a;border:1px solid #1e293b;border-radius:10px;"
                    f"padding:10px 14px'>"
                    f"<div style='font-size:9px;color:#64748b;text-transform:uppercase;"
                    f"letter-spacing:.06em;margin-bottom:4px'>{lbl}</div>"
                    f"<div style='font-size:20px;font-weight:700;color:{clr}'>{val}</div>"
                    f"</div>", unsafe_allow_html=True)
            crit_clr = "#ef4444" if ag_summ["critical_count"] > 0 else "#22c55e"
            _akpi(sk1, "Work Orders",   ag_summ["total_wos"],       "#38bdf8")
            _akpi(sk2, "Critical",      ag_summ["critical_count"],  crit_clr)
            _akpi(sk3, "High Priority", ag_summ["high_count"],      "#eab308")
            _akpi(sk4, "Labor Hours",   ag_summ["total_labor_hrs"], "#a78bfa")
            _akpi(sk5, "Crew Util %",   f"{ag_summ['avg_utilization']}%", "#22c55e")

            st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
            st.markdown("##### Top Actions")
            for i, action in enumerate(ag_summ["top_actions"]):
                is_imm = action.startswith("IMMEDIATE")
                ac = "#ef4444" if is_imm else "#eab308"
                abg = "#1a0000" if is_imm else "#1a1400"
                st.markdown(
                    f"<div style='background:{abg};border:1px solid {ac}44;border-radius:6px;"
                    f"padding:8px 12px;margin-bottom:4px;font-size:11px;color:#e2e8f0'>"
                    f"<span style='color:{ac};font-weight:700'>{i+1}.</span> {action}</div>",
                    unsafe_allow_html=True,
                )

            # Fleet risk heatmap
            st.markdown("##### Fleet Risk Heatmap")
            risk_data = [{"Well": w["name"], "Risk %": round(w["risk_score"]*100),
                          "Status": w["run_status"], "Field": w["field"]}
                         for w in wells]
            df_risk = pd.DataFrame(risk_data).sort_values("Risk %", ascending=False)
            fig_risk = px.bar(df_risk, x="Well", y="Risk %", color="Risk %",
                              color_continuous_scale=["#22c55e", "#eab308", "#ef4444"],
                              range_color=[0, 100], text="Risk %")
            fig_risk.update_layout(
                paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["panel"],
                font_color=COLORS["text"], height=280,
                xaxis=dict(gridcolor="#1e293b", tickangle=-30),
                yaxis=dict(gridcolor="#1e293b"),
                margin=dict(l=10, r=10, t=10, b=40),
                coloraxis_showscale=False,
            )
            fig_risk.update_traces(textposition="outside", textfont_size=9)
            st.plotly_chart(fig_risk, use_container_width=True)

        # ── SUB-TAB 2: AI Work Orders (POST /workorders) ──────────────────
        with ai_tabs[1]:
            st.markdown("#### AI-Generated Work Orders")
            st.markdown(
                f"<div style='font-size:10px;color:#475569;margin-bottom:10px'>"
                f"{len(ag_wos)} work orders generated by agent loop</div>",
                unsafe_allow_html=True,
            )
            for wo in ag_wos:
                sev_c = {"CRITICAL": "#ef4444", "HIGH": "#eab308", "MEDIUM": "#3b82f6"}.get(wo["severity"], "#64748b")
                sev_bg = {"CRITICAL": "#1a0000", "HIGH": "#1a1400", "MEDIUM": "#0d1f3c"}.get(wo["severity"], "#0f172a")
                st.markdown(
                    f"<div style='background:{sev_bg};border:1px solid {sev_c}33;"
                    f"border-radius:8px;padding:12px;margin-bottom:8px'>"
                    # Header row
                    f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                    f"  <div style='display:flex;align-items:center;gap:8px'>"
                    f"    <span style='background:{sev_c}22;border:1px solid {sev_c};border-radius:10px;"
                    f"    padding:1px 8px;font-size:10px;color:{sev_c};font-weight:700'>{wo['severity']}</span>"
                    f"    <span style='font-size:13px;font-weight:700;color:#e2e8f0'>{wo['wo_id']}</span>"
                    f"    <span style='font-size:11px;color:#64748b'>·</span>"
                    f"    <span style='font-size:11px;color:#38bdf8;font-weight:600'>{wo['well_name']}</span>"
                    f"    <span style='font-size:10px;color:#475569'>{wo['esp_id']}</span>"
                    f"  </div>"
                    f"  <span style='background:#0f172a;border:1px solid #1e293b;border-radius:4px;"
                    f"  padding:2px 8px;font-size:9px;color:#a78bfa;font-family:monospace'>"
                    f"  {wo['status']}</span>"
                    f"</div>"
                    # Fault & risk
                    f"<div style='display:flex;gap:16px;margin-bottom:6px;font-size:11px'>"
                    f"  <span style='color:#94a3b8'>Fault: <b style=\"color:#e2e8f0\">{wo['fault_code']}</b></span>"
                    f"  <span style='color:#94a3b8'>Risk: <b style=\"color:{sev_c}\">{wo['risk_pct']}%</b></span>"
                    f"  <span style='color:#94a3b8'>Window: <b style=\"color:#eab308\">{wo['window']}</b></span>"
                    f"  <span style='color:#94a3b8'>Est: <b style=\"color:#a78bfa\">{wo['est_hours']}h</b></span>"
                    f"</div>"
                    # Assignment
                    f"<div style='font-size:11px;color:#64748b;margin-bottom:6px'>"
                    f"  Scheduled: {wo['scheduled']} &nbsp;·&nbsp; "
                    f"  Tech: <span style='color:#22c55e;font-weight:600'>{wo['tech_name']}</span> ({wo['tech_id']})"
                    f"</div>"
                    # Action
                    f"<div style='font-size:10px;color:#94a3b8;background:#060b18;"
                    f"border-radius:4px;padding:6px 10px;line-height:1.5'>"
                    f"  {wo['action'][:200]}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── SUB-TAB 3: Technician Schedule ─────────────────────────────────
        with ai_tabs[2]:
            st.markdown("#### Technician Schedule Board")
            for tech_id, sched_data in ag_sched.items():
                tech_rec = next((t for t in ag_roster if t["id"] == tech_id), None)
                booked = tech_rec["booked_hrs"] if tech_rec else 0
                cap = tech_rec["capacity_hrs"] if tech_rec else 8
                util_pct = round(booked / cap * 100) if cap > 0 else 0
                bar_color = "#ef4444" if util_pct > 90 else ("#eab308" if util_pct > 60 else "#22c55e")

                jobs_html = ""
                if sched_data["jobs"]:
                    for j in sched_data["jobs"]:
                        jc = {"CRITICAL":"#ef4444","HIGH":"#eab308","MEDIUM":"#3b82f6"}.get(j["severity"],"#64748b")
                        jobs_html += (
                            f"<div style='display:flex;align-items:center;gap:8px;padding:4px 0'>"
                            f"<span style='background:{jc}22;border:1px solid {jc};border-radius:3px;"
                            f"padding:0 6px;font-size:9px;color:{jc};font-weight:700'>{j['severity']}</span>"
                            f"<span style='font-size:11px;color:#e2e8f0'>{j['well']}</span>"
                            f"<span style='font-size:10px;color:#64748b'>{j['fault']} · {j['hours']}h</span>"
                            f"<span style='font-size:9px;color:#475569;margin-left:auto'>{j['window']}</span>"
                            f"</div>"
                        )
                else:
                    jobs_html = "<div style='font-size:11px;color:#334155;font-style:italic;padding:4px 0'>No jobs scheduled</div>"

                st.markdown(
                    f"<div style='background:#0f172a;border:1px solid #1e293b;border-radius:8px;"
                    f"padding:12px;margin-bottom:8px'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                    f"  <div>"
                    f"    <span style='font-size:12px;font-weight:700;color:#e2e8f0'>{sched_data['name']}</span>"
                    f"    <span style='font-size:10px;color:#64748b;margin-left:8px'>{tech_id} · {sched_data['zone']}</span>"
                    f"  </div>"
                    f"  <span style='font-size:11px;color:{bar_color};font-weight:700'>{util_pct}% utilized</span>"
                    f"</div>"
                    f"<div style='background:#1e293b;border-radius:3px;height:4px;overflow:hidden;margin-bottom:8px'>"
                    f"  <div style='width:{util_pct}%;height:100%;background:{bar_color}'></div>"
                    f"</div>"
                    f"<div style='font-size:10px;color:#64748b;margin-bottom:4px'>"
                    f"  {booked}/{cap}h booked · {len(sched_data['jobs'])} job(s)</div>"
                    f"{jobs_html}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── SUB-TAB 4: Agent Reasoning (Perceive–Reason–Act trace) ─────────
        with ai_tabs[3]:
            st.markdown("#### Agent Reasoning Trace")
            st.markdown(
                "<div style='font-size:10px;color:#475569;margin-bottom:12px'>"
                "Full perceive → reason → act chain for each maintenance decision</div>",
                unsafe_allow_html=True,
            )
            for wo in ag_wos:
                sev_c = {"CRITICAL":"#ef4444","HIGH":"#eab308","MEDIUM":"#3b82f6"}.get(wo["severity"],"#64748b")
                reasoning_lines = wo["reasoning"].split("\n")
                reason_html = ""
                for line in reasoning_lines:
                    if line.startswith("PERCEIVE:"):
                        badge_c, badge_lbl = "#3b82f6", "PERCEIVE"
                    elif line.startswith("REASON:"):
                        badge_c, badge_lbl = "#a78bfa", "REASON"
                    elif line.startswith("ACT:"):
                        badge_c, badge_lbl = "#22c55e", "ACT"
                    else:
                        badge_c, badge_lbl = "#64748b", ""
                    body = line.split(":", 1)[1].strip() if ":" in line and badge_lbl else line
                    reason_html += (
                        f"<div style='display:flex;gap:8px;margin-bottom:6px;align-items:flex-start'>"
                        f"<span style='background:{badge_c}22;border:1px solid {badge_c};border-radius:3px;"
                        f"padding:0 6px;font-size:9px;color:{badge_c};font-weight:700;white-space:nowrap;"
                        f"margin-top:2px'>{badge_lbl}</span>"
                        f"<span style='font-size:11px;color:#94a3b8;line-height:1.5'>{body}</span>"
                        f"</div>"
                    )
                st.markdown(
                    f"<div style='background:#0a0e1a;border:1px solid #1e293b;border-radius:8px;"
                    f"padding:12px;margin-bottom:8px'>"
                    f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'>"
                    f"  <span style='background:{sev_c}22;border:1px solid {sev_c};border-radius:10px;"
                    f"  padding:1px 8px;font-size:10px;color:{sev_c};font-weight:700'>{wo['severity']}</span>"
                    f"  <span style='font-size:12px;font-weight:700;color:#e2e8f0'>"
                    f"  {wo['wo_id']} — {wo['well_name']}</span>"
                    f"</div>"
                    f"{reason_html}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── SUB-TAB 5: API Endpoints Reference ────────────────────────────
        with ai_tabs[4]:
            st.markdown("#### API Endpoints")
            st.markdown(
                "<div style='font-size:10px;color:#475569;margin-bottom:14px'>"
                "REST endpoints exposed by the Maintenance Scheduler agent backend</div>",
                unsafe_allow_html=True,
            )
            # POST /workorders
            st.markdown(
                "<div style='background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px;margin-bottom:10px'>"
                "<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
                "  <span style='background:#22c55e22;border:1px solid #22c55e;border-radius:3px;"
                "  padding:1px 8px;font-size:10px;color:#22c55e;font-weight:700;font-family:monospace'>POST</span>"
                "  <span style='font-size:13px;font-weight:700;color:#e2e8f0;font-family:monospace'>/workorders</span>"
                "</div>"
                "<div style='font-size:11px;color:#94a3b8;margin-bottom:8px'>"
                "Trigger the agent to create or update work orders. The agent runs the full "
                "perceive-reason-act loop and returns generated work orders with AI reasoning.</div>"
                "<div style='font-size:10px;color:#64748b;margin-bottom:4px'>Request Body:</div>"
                "<pre style='background:#060b18;border-radius:4px;padding:10px;font-size:10px;"
                "color:#38bdf8;overflow-x:auto;border:1px solid #1e293b'>"
                '{\n'
                '  "esp_ids": ["ESP-003", "ESP-009"],  // optional filter\n'
                '  "severity_filter": "CRITICAL",       // optional\n'
                '  "auto_assign": true                  // assign technicians\n'
                '}'
                "</pre>"
                "<div style='font-size:10px;color:#64748b;margin-bottom:4px;margin-top:8px'>Response:</div>"
                "<pre style='background:#060b18;border-radius:4px;padding:10px;font-size:10px;"
                "color:#38bdf8;overflow-x:auto;border:1px solid #1e293b'>"
                '{\n'
                '  "work_orders": [\n'
                '    {\n'
                '      "wo_id": "AI-WO-5000",\n'
                '      "esp_id": "ESP-009",\n'
                '      "fault_code": "CRITICAL_TEMP",\n'
                '      "severity": "CRITICAL",\n'
                '      "reasoning": "PERCEIVE: ESP-009 shows ...",\n'
                '      "tech_id": "T-105",\n'
                '      "scheduled": "2026-03-09 14:00",\n'
                '      "status": "AI-GENERATED"\n'
                '    }\n'
                '  ],\n'
                '  "agent_run_id": "run-20260309-001"\n'
                '}'
                "</pre>"
                "</div>",
                unsafe_allow_html=True,
            )
            # GET /agent/daily-summary
            st.markdown(
                "<div style='background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px;margin-bottom:10px'>"
                "<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
                "  <span style='background:#3b82f622;border:1px solid #3b82f6;border-radius:3px;"
                "  padding:1px 8px;font-size:10px;color:#3b82f6;font-weight:700;font-family:monospace'>GET</span>"
                "  <span style='font-size:13px;font-weight:700;color:#e2e8f0;font-family:monospace'>/agent/daily-summary</span>"
                "</div>"
                "<div style='font-size:11px;color:#94a3b8;margin-bottom:8px'>"
                "Retrieve the agent's daily maintenance summary including prioritized actions, "
                "crew utilization, and fleet risk overview.</div>"
                "<div style='font-size:10px;color:#64748b;margin-bottom:4px'>Response:</div>"
                "<pre style='background:#060b18;border-radius:4px;padding:10px;font-size:10px;"
                "color:#38bdf8;overflow-x:auto;border:1px solid #1e293b'>"
                '{\n'
                f'  "generated_at": "{ag_summ["generated_at"]}",\n'
                f'  "total_wos": {ag_summ["total_wos"]},\n'
                f'  "critical_count": {ag_summ["critical_count"]},\n'
                f'  "high_count": {ag_summ["high_count"]},\n'
                f'  "total_labor_hrs": {ag_summ["total_labor_hrs"]},\n'
                f'  "techs_assigned": {ag_summ["techs_assigned"]},\n'
                f'  "avg_utilization": {ag_summ["avg_utilization"]},\n'
                f'  "fleet_avg_risk": {ag_summ["fleet_avg_risk"]},\n'
                '  "top_actions": [...]\n'
                '}'
                "</pre>"
                "</div>",
                unsafe_allow_html=True,
            )
            # Architecture note
            st.markdown(
                "<div style='background:#0a0e1a;border:1px solid #1e293b;border-radius:8px;padding:14px'>"
                "<div style='font-size:11px;font-weight:700;color:#e2e8f0;margin-bottom:6px'>"
                "Agent Architecture</div>"
                "<div style='font-size:11px;color:#94a3b8;line-height:1.6'>"
                "<b style='color:#3b82f6'>1. Perceive</b> — Pull asset telemetry (temp, vibration, current, PIP), "
                "diagnostic rule outputs, and SAP maintenance history for all 12 ESPs.<br>"
                "<b style='color:#a78bfa'>2. Reason</b> — Score failure urgency using risk model + TTF estimates. "
                "Rank by composite priority. Generate human-readable justification chain.<br>"
                "<b style='color:#22c55e'>3. Act</b> — Create work orders, match technicians by skill/zone/capacity, "
                "set maintenance windows (IMMEDIATE / URGENT / PLANNED / ROUTINE)."
                "</div></div>",
                unsafe_allow_html=True,
            )


# ── Simulated advisor fallback (defined before _app so fragment can call it) ───
def _simulated_advisor_response(question: str, ws: list, kp: dict) -> str:
    q_lower = question.lower()
    high_w = [w for w in ws if w["risk_bucket"] == "HIGH"]
    if "top 3" in q_lower or "at risk" in q_lower:
        top3 = sorted(ws, key=lambda x: x["risk_score"], reverse=True)[:3]
        return "\n".join(
            f"**{i+1}. {w['name']} ({w['esp_id']})** — Risk {w['risk_score']*100:.0f}%, "
            f"Status: {w['run_status']}, Faults: {', '.join(f['code'] for f in w['fault_codes'])}"
            for i, w in enumerate(top3)
        )
    if "gas" in q_lower:
        return ("Gas interference occurs when free gas enters the pump intake, causing cavitation. "
                "Key indicators: PIP < 800 psi, elevated vibration, erratic current. "
                "Mitigation: reduce drawdown, install gas separator, adjust VSD frequency.")
    if "bearing" in q_lower:
        return ("Bearing wear is characterized by progressive vibration increase (>3.5 mm/s) "
                "and elevated temperature. The wear pattern accelerates — plan replacement within 72h "
                "once vibration exceeds threshold. Metallic particle analysis of oil can confirm.")
    return (f"Fleet summary: {len(ws)} ESPs, {kp['critical_count']} critical, "
            f"{kp['warning_count']} warnings. Average efficiency: {kp['avg_efficiency']}%. "
            f"High-risk wells: {', '.join(w['esp_id'] for w in high_w) or 'None'}. "
            "Enable Claude AI for detailed analysis.")


# ── Launch fragment ────────────────────────────────────────────────────────────
_app()
