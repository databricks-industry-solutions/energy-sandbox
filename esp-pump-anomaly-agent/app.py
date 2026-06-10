"""
ESP Fleet Operations Command Center
Streamlit · dark theme · BOP Guardian design patterns
"""
from __future__ import annotations
import asyncio, json, os
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

# ── Config ────────────────────────────────────────────────────────────────────
CATALOG  = "oil_pump_monitor_catalog"
SCHEMA   = "esp_hackathon"
TBL_T    = f"{CATALOG}.{SCHEMA}.pump_telemetry"
TBL_L    = f"{CATALOG}.{SCHEMA}.latest_reading_per_well"
TBL_P    = f"{CATALOG}.{SCHEMA}.pump_failure_predictions"
MODEL    = os.getenv("AGENT_MODEL", "databricks-claude-sonnet-4-6")
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID", "01f1647fb02a12d7ae6fa90c0378546d")
MAS_ENDPOINT   = os.getenv("MAS_ENDPOINT", "mas-5115482b-endpoint")
WAREHOUSE_ID   = os.getenv("DATABRICKS_WAREHOUSE_ID", "87e069097741b56c")

# ── Palette (BOP Guardian) ────────────────────────────────────────────────────
BG="#0B0F1A"; PANEL="#0f172a"; CARD="#1C2333"; BORDER="#1e293b"
TEXT="#e2e8f0"; MUTED="#64748b"
CYAN="#00D4FF"; GREEN="#22c55e"; YELLOW="#eab308"; RED="#ef4444"; ORANGE="#F97316"; PURPLE="#8B5CF6"
RC={"CRITICAL":RED,"HIGH":ORANGE,"MEDIUM":YELLOW,"LOW":GREEN}

# ── Plotly helpers ────────────────────────────────────────────────────────────
_B=dict(paper_bgcolor=BG,plot_bgcolor=PANEL,font_color=TEXT)
def _lay(h=300,**k):
    d=dict(**_B,height=h,margin=dict(l=10,r=10,t=36,b=24),
           xaxis=dict(gridcolor=BORDER),yaxis=dict(gridcolor=BORDER),
           legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(size=10)))
    d.update(k); return d
def _ef(m="No data",h=200):
    f=go.Figure(); f.add_annotation(text=m,xref="paper",yref="paper",x=.5,y=.5,showarrow=False,font=dict(color=MUTED,size=14))
    f.update_layout(**_B,height=h,xaxis=dict(visible=False),yaxis=dict(visible=False)); return f
def _rgba(hx,a):
    h=hx.lstrip("#"); return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"

# ── HTML helpers — Premium dark glassmorphism ────────────────────────────────
def _kpi(lbl,val,sub="",color=TEXT,crit=False):
    glow=f"animation:critGlow 2s infinite;border-color:{RED}77;" if crit else ""
    s=f"<div class='kpi-sub'>{sub}</div>" if sub else ""
    gtext=f"text-shadow:0 0 22px {color}77;" if color in (RED,ORANGE) else ""
    return (f"<div class='kpi-card {'crit' if crit else ''}' style='{glow}'>"
            f"<div class='kpi-label'>{lbl}</div>"
            f"<div class='kpi-value' style='color:{color};{gtext}'>{val}</div>{s}</div>")

def _badge(lbl,color):
    dot=f"display:inline-block;width:7px;height:7px;background:{color};border-radius:50%;margin-right:6px;{'animation:pulse 1.5s infinite;' if color==RED else ''}"
    return (f"<span style='display:inline-flex;align-items:center;background:{color}18;"
            f"border:1px solid {color}55;border-radius:20px;padding:4px 14px;font-size:12px;"
            f"color:{color};font-weight:700;letter-spacing:.04em;text-transform:uppercase'>"
            f"<span style='{dot}'></span>{lbl}</span>")

def _sec(title,sub=""):
    s=f"<span>{sub}</span>" if sub else ""
    return (f"<div class='section-hdr'><h2>{title}</h2>{s}</div>")

def _readout(title,value,mn,mx,warn,crit,unit,low_bad=False):
    color=(RED if value<=crit else(YELLOW if value<=warn else GREEN)) if low_bad else (RED if value>=crit else(YELLOW if value>=warn else GREEN))
    pct=max(0,min(100,(value-mn)/(mx-mn)*100))
    wp=max(0,min(100,(warn-mn)/(mx-mn)*100)); cp=max(0,min(100,(crit-mn)/(mx-mn)*100))
    if low_bad: zb=f"linear-gradient(to right,{RED}33 0%,{RED}33 {cp:.0f}%,{YELLOW}25 {cp:.0f}%,{YELLOW}25 {wp:.0f}%,{GREEN}18 {wp:.0f}%,{GREEN}18 100%)"
    else:       zb=f"linear-gradient(to right,{GREEN}18 0%,{GREEN}18 {wp:.0f}%,{YELLOW}25 {wp:.0f}%,{YELLOW}25 {cp:.0f}%,{RED}33 {cp:.0f}%,{RED}33 100%)"
    vs=f"{value:,.0f}" if abs(value)>=100 else(f"{value:.2f}" if abs(value)<10 else f"{value:.1f}")
    glow=f"text-shadow:0 0 20px {color}66;" if color in (RED,ORANGE) else ""
    return (f"<div class='readout-tile'>"
            f"<div class='readout-label'>{title}</div>"
            f"<div style='display:flex;align-items:baseline;gap:6px;margin-bottom:10px'>"
            f"<span class='readout-value' style='color:{color};{glow}'>{vs}</span>"
            f"<span class='readout-unit'>{unit}</span></div>"
            f"<div class='readout-bar' style='background:{zb}'>"
            f"<div class='readout-needle' style='left:{pct:.0f}%;background:{color};box-shadow:0 0 8px {color}'></div>"
            f"</div></div>")

def _gauge(title,value,mn,mx,warn,crit,unit,low_bad=False):
    if low_bad: steps=[{"range":[mn,crit],"color":_rgba(RED,.28)},{"range":[crit,warn],"color":_rgba(YELLOW,.20)},{"range":[warn,mx],"color":_rgba(GREEN,.14)}]
    else:       steps=[{"range":[mn,warn],"color":_rgba(GREEN,.14)},{"range":[warn,crit],"color":_rgba(YELLOW,.20)},{"range":[crit,mx],"color":_rgba(RED,.28)}]
    bar_col=(RED if (value<=crit if low_bad else value>=crit) else(YELLOW if (value<=warn if low_bad else value>=warn) else GREEN))
    fig=go.Figure(go.Indicator(mode="gauge+number",value=value,
        title={"text":f"<b>{title}</b><br><span style='font-size:.7em;color:{MUTED}'>{unit}</span>","font":{"color":TEXT,"size":13}},
        number={"font":{"color":bar_col,"size":30,"family":"JetBrains Mono, monospace"},"valueformat":".1f"},
        gauge={"axis":{"range":[mn,mx],"tickcolor":MUTED,"tickfont":{"color":MUTED,"size":10}},
               "bar":{"color":bar_col,"thickness":.32},
               "bgcolor":"rgba(0,0,0,0)","bordercolor":BORDER,"borderwidth":1,"steps":steps,
               "threshold":{"line":{"color":RED,"width":2},"thickness":.85,"value":crit}}))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=200,margin=dict(l=18,r=18,t=55,b=8))
    return fig

# ── Spark helpers ─────────────────────────────────────────────────────────────
def _bearer():
    from databricks.sdk import WorkspaceClient
    w=WorkspaceClient()
    host=(w.config.host or os.getenv("DATABRICKS_HOST","")).rstrip("/")
    tok=w.config.token or os.getenv("DATABRICKS_TOKEN","")
    if not tok:  # Databricks Apps use OAuth (SP), not a PAT — pull a bearer from the SDK
        try:
            _a=(w.config.authenticate() or {}).get("Authorization","")
            if _a.startswith("Bearer "): tok=_a[7:]
        except Exception: pass
    return host,tok

def spark():
    if "spark" not in st.session_state:
        from databricks.connect import DatabricksSession
        st.session_state.spark=DatabricksSession.builder.serverless(True).getOrCreate()
    return st.session_state.spark

def _wsc():
    if "wsc" not in st.session_state:
        from databricks.sdk import WorkspaceClient
        st.session_state.wsc=WorkspaceClient()
    return st.session_state.wsc

def qdf(sql):
    # Run on the serverless SQL warehouse via the SDK Statement Execution API.
    # Native app-OAuth auth, fast against the warm warehouse, no Spark cold start.
    import time
    w=_wsc()
    r=w.statement_execution.execute_statement(statement=sql,warehouse_id=WAREHOUSE_ID,wait_timeout="50s")
    def _state(x): return x.status.state.value if (x.status and x.status.state) else "SUCCEEDED"
    while _state(r) in ("PENDING","RUNNING"):
        time.sleep(0.7); r=w.statement_execution.get_statement(r.statement_id)
    if _state(r)!="SUCCEEDED":
        raise RuntimeError(getattr(getattr(r.status,"error",None),"message",None) or f"query {_state(r)}")
    cols=[c.name for c in r.manifest.schema.columns] if (r.manifest and r.manifest.schema) else []
    rows=[]; res=r.result
    while res is not None:
        rows.extend(res.data_array or [])
        nxt=getattr(res,"next_chunk_index",None)
        if nxt is None: break
        res=w.statement_execution.get_statement_result_chunk_n(r.statement_id,nxt)
    df=pd.DataFrame(rows,columns=cols)
    for c in df.columns:
        try: df[c]=pd.to_numeric(df[c])
        except (ValueError,TypeError): pass
    return df
def san(v): return (v or "").replace("'","''")
def rjson(df):
    if df.empty: return "[]"
    out=df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]): out[c]=out[c].astype(str)
    return out.to_json(orient="records")

# ── Dashboard query ───────────────────────────────────────────────────────────
FLEET_SQL=f"""
WITH lp AS(SELECT well_id,predicted_failure FROM(
  SELECT well_id,predicted_failure,ROW_NUMBER()OVER(PARTITION BY well_id ORDER BY window_hour DESC)rn
  FROM {TBL_P})WHERE rn=1)
SELECT l.well_id,l.event_ts,ROUND(l.motor_temp_f,1)motor_temp_f,
  ROUND(l.intake_pressure_psi,1)intake_pressure_psi,ROUND(l.vibration_g,3)vibration_g,
  ROUND(l.flow_rate_bpd,1)flow_rate_bpd,COALESCE(l.failure_flag,0)failure_flag,
  ROUND(COALESCE(lp.predicted_failure,0),4)ml_prob,
  CASE WHEN COALESCE(l.failure_flag,0)=1 OR COALESCE(lp.predicted_failure,0)>=.7 OR COALESCE(l.motor_temp_f,0)>250 THEN 'CRITICAL'
       WHEN COALESCE(lp.predicted_failure,0)>=.4 OR COALESCE(l.intake_pressure_psi,1800)<1200 OR COALESCE(l.intake_pressure_psi,1800)>2400 THEN 'HIGH'
       WHEN COALESCE(lp.predicted_failure,0)>=.15 OR COALESCE(l.vibration_g,0)>=2.5 THEN 'MEDIUM'
       ELSE 'LOW' END risk_tier
FROM {TBL_L} l LEFT JOIN lp ON l.well_id=lp.well_id
ORDER BY CASE WHEN COALESCE(l.failure_flag,0)=1 OR COALESCE(lp.predicted_failure,0)>=.7 OR COALESCE(l.motor_temp_f,0)>250 THEN 1
              WHEN COALESCE(lp.predicted_failure,0)>=.4 THEN 2 WHEN COALESCE(lp.predicted_failure,0)>=.15 THEN 3 ELSE 4 END,
         COALESCE(lp.predicted_failure,0)DESC
"""

@st.cache_data(ttl=60,show_spinner=False)
def load_fleet():
    df=qdf(FLEET_SQL)
    df["event_ts"]=pd.to_datetime(df["event_ts"],errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    df["ml_prob"]=pd.to_numeric(df["ml_prob"],errors="coerce").fillna(0.0)
    df["failure_flag"]=pd.to_numeric(df["failure_flag"],errors="coerce").fillna(0).astype(int)
    return df.fillna("")

@st.cache_data(ttl=60,show_spinner=False)
def load_well_hist(well_id):
    s=san(well_id)
    return qdf(f"SELECT event_ts,motor_temp_f,intake_pressure_psi,vibration_g,flow_rate_bpd FROM {TBL_T} WHERE well_id='{s}' AND event_ts>=current_timestamp()-INTERVAL 24 HOURS ORDER BY event_ts LIMIT 400")

# ── Charts ────────────────────────────────────────────────────────────────────
def ch_donut(df):
    c=df["risk_tier"].value_counts().reindex(["CRITICAL","HIGH","MEDIUM","LOW"],fill_value=0)
    fig=go.Figure(go.Pie(labels=c.index,values=c.values,hole=.6,marker_colors=[RED,ORANGE,YELLOW,GREEN],
        textinfo="value+percent",textfont_size=11,hovertemplate="<b>%{label}</b><br>%{value} wells (%{percent})<extra></extra>"))
    fig.update_layout(**_B,height=270,title=dict(text="Risk Distribution",font=dict(size=13,color=TEXT)),
        margin=dict(t=44,b=24,l=20,r=20),legend=dict(orientation="h",y=-.1,x=.5,xanchor="center",font=dict(color=TEXT,size=11)))
    return fig

def ch_prob(df):
    if df.empty: return _ef("No data",340)
    top=df.sort_values("ml_prob",ascending=True).tail(15)
    fig=go.Figure(go.Bar(y=top["well_id"],x=top["ml_prob"]*100,orientation="h",
        marker=dict(color=[RC.get(r,GREEN) for r in top["risk_tier"]],opacity=.85),
        text=[f"{v:.0f}%" for v in top["ml_prob"]*100],textposition="outside",textfont=dict(color=TEXT,size=11),
        hovertemplate="<b>%{y}</b><br>Failure Prob: %{x:.1f}%<extra></extra>"))
    _l=_lay(360,title=dict(text="ML Failure Probability",font=dict(size=13,color=TEXT)))
    _l["xaxis"]=dict(range=[0,105],gridcolor=BORDER,tickfont=dict(color=MUTED))
    _l["yaxis"]=dict(tickfont=dict(color=TEXT,size=11))
    fig.update_layout(**_l)
    return fig

def ch_ts(df,wid):
    if df.empty: return _ef(f"No 24h data for {wid}",420)
    fig=make_subplots(rows=2,cols=2,vertical_spacing=.14,horizontal_spacing=.10,
        subplot_titles=("Motor Temp (°F)","Intake Pressure (psi)","Vibration (g)","Flow Rate (bpd)"))
    ts=pd.to_datetime(df["event_ts"],errors="coerce")
    def _a(r,c,col,color,hl=None):
        fig.add_trace(go.Scatter(x=ts,y=df[col],mode="lines",line=dict(color=color,width=2),showlegend=False),row=r,col=c)
        if hl:
            for y,d in hl: fig.add_hline(y=y,line_dash=d,line_color=_rgba(RED,.7),line_width=1.2,row=r,col=c)
    _a(1,1,"motor_temp_f",RED,[(250,"dash")])
    _a(1,2,"intake_pressure_psi",CYAN,[(1200,"dot"),(2400,"dot")])
    _a(2,1,"vibration_g",PURPLE,[(2.5,"dash")])
    _a(2,2,"flow_rate_bpd",GREEN)
    fig.update_layout(**_B,height=430,showlegend=False,
        title=dict(text=f"24-Hour Telemetry — {wid}",font=dict(size=14,color=TEXT)),
        margin=dict(t=60,b=30,l=50,r=20))
    for ax in fig.select_xaxes(): ax.update(gridcolor=BORDER,tickfont=dict(color=MUTED,size=9))
    for ay in fig.select_yaxes(): ay.update(gridcolor=BORDER,tickfont=dict(color=MUTED,size=9))
    for an in fig.layout.annotations: an.font.color=MUTED; an.font.size=11
    return fig

# ── Agent ─────────────────────────────────────────────────────────────────────
SYS="""You are an expert ESP (Electric Submersible Pump) production engineering AI.
Identify at-risk wells using live telemetry, threshold breaches, 3σ anomalies, and ML predictions.
Healthy: intake_pressure 1200-2400 psi, motor_temp <250°F, low vibration.
failure_flag=1 = failure event. Prioritise CRITICAL→HIGH→MEDIUM→LOW.
Be concise, cite well IDs, explain sensor values, recommend actions."""

def _tools():
    from agents import function_tool
    @function_tool
    def get_well_ids()->str:
        """All ESP well IDs."""
        try: return json.dumps(qdf(f"SELECT DISTINCT well_id FROM {TBL_T} ORDER BY well_id")["well_id"].tolist())
        except Exception as e: return json.dumps({"error":str(e)})
    @function_tool
    def get_fleet_health_summary()->str:
        """Fleet-wide health summary with risk tiers."""
        try:
            df=qdf(f"""WITH lp AS(SELECT well_id,predicted_failure FROM(SELECT well_id,predicted_failure,ROW_NUMBER()OVER(PARTITION BY well_id ORDER BY window_hour DESC)rn FROM {TBL_P})WHERE rn=1)
            SELECT t.well_id,COUNT(*)readings,SUM(CASE WHEN intake_pressure_psi<1200 OR intake_pressure_psi>2400 THEN 1 ELSE 0 END)psi_viol,
              SUM(CASE WHEN motor_temp_f>250 THEN 1 ELSE 0 END)temp_viol,SUM(CASE WHEN failure_flag=1 THEN 1 ELSE 0 END)failures,
              ROUND(COALESCE(lp.predicted_failure,0),4)ml_prob,
              CASE WHEN SUM(CASE WHEN failure_flag=1 THEN 1 ELSE 0 END)>0 OR COALESCE(lp.predicted_failure,0)>=.7 THEN 'CRITICAL'
                   WHEN COALESCE(lp.predicted_failure,0)>=.4 THEN 'HIGH' WHEN COALESCE(lp.predicted_failure,0)>=.15 THEN 'MEDIUM' ELSE 'LOW' END risk_tier
            FROM {TBL_T} t LEFT JOIN lp ON t.well_id=lp.well_id
            WHERE t.event_ts>=current_timestamp()-INTERVAL 24 HOURS
            GROUP BY t.well_id,lp.predicted_failure ORDER BY risk_tier,ml_prob DESC""")
            return rjson(df)
        except Exception as e: return json.dumps({"error":str(e)})
    @function_tool
    def get_latest_readings(well_id:str)->str:
        """Last 24h telemetry for a well."""
        try:
            s=san(well_id); df=qdf(f"SELECT well_id,event_ts,motor_temp_f,intake_pressure_psi,vibration_g,flow_rate_bpd,failure_flag FROM {TBL_T} WHERE well_id='{s}' AND event_ts>=current_timestamp()-INTERVAL 24 HOURS ORDER BY event_ts DESC LIMIT 100")
            return rjson(df) if not df.empty else json.dumps({"message":"No data"})
        except Exception as e: return json.dumps({"error":str(e)})
    @function_tool
    def check_threshold_violations(well_id:str)->str:
        """Hard-threshold breaches for a well, last 24h."""
        try:
            s=san(well_id); df=qdf(f"SELECT well_id,event_ts,motor_temp_f,intake_pressure_psi,vibration_g,failure_flag FROM {TBL_T} WHERE well_id='{s}' AND event_ts>=current_timestamp()-INTERVAL 24 HOURS AND(intake_pressure_psi<1200 OR intake_pressure_psi>2400 OR motor_temp_f>250 OR failure_flag=1) ORDER BY event_ts DESC")
            return rjson(df) if not df.empty else json.dumps({"message":"No violations"})
        except Exception as e: return json.dumps({"error":str(e)})
    @function_tool
    def detect_statistical_anomalies(well_id:str)->str:
        """3σ anomalies vs 7-day baseline."""
        try:
            s=san(well_id); df=qdf(f"""WITH base AS(SELECT AVG(motor_temp_f)mu_mt,STDDEV(motor_temp_f)sd_mt,AVG(intake_pressure_psi)mu_ip,STDDEV(intake_pressure_psi)sd_ip,AVG(vibration_g)mu_vg,STDDEV(vibration_g)sd_vg FROM {TBL_T} WHERE well_id='{s}' AND event_ts>=current_timestamp()-INTERVAL 7 DAYS),
            recent AS(SELECT*FROM {TBL_T} WHERE well_id='{s}' AND event_ts>=current_timestamp()-INTERVAL 24 HOURS),
            scored AS(SELECT r.well_id,r.event_ts,r.motor_temp_f,r.intake_pressure_psi,r.vibration_g,ROUND(ABS(r.motor_temp_f-b.mu_mt)/NULLIF(b.sd_mt,0),2)z_mt,ROUND(ABS(r.intake_pressure_psi-b.mu_ip)/NULLIF(b.sd_ip,0),2)z_ip,ROUND(ABS(r.vibration_g-b.mu_vg)/NULLIF(b.sd_vg,0),2)z_vg FROM recent r CROSS JOIN base b)
            SELECT*FROM scored WHERE GREATEST(COALESCE(z_mt,0),COALESCE(z_ip,0),COALESCE(z_vg,0))>3 ORDER BY event_ts DESC LIMIT 50""")
            return rjson(df) if not df.empty else json.dumps({"message":"No 3σ anomalies"})
        except Exception as e: return json.dumps({"error":str(e)})
    @function_tool
    def get_failure_probability(well_id:str)->str:
        """Weighted heuristic + ML failure probability."""
        try:
            s=san(well_id); df=qdf(f"""WITH sig AS(SELECT AVG(CASE WHEN failure_flag=1 THEN 1.0 ELSE 0.0 END)fr7,AVG(CASE WHEN event_ts>=current_timestamp()-INTERVAL 24 HOURS AND(intake_pressure_psi<1200 OR intake_pressure_psi>2400 OR motor_temp_f>250)THEN 1.0 ELSE 0.0 END)vr24,AVG(CASE WHEN motor_temp_f>200 THEN(motor_temp_f-200)/100.0 ELSE 0.0 END)mts,AVG(ABS(intake_pressure_psi-1800)/600.0)ps FROM {TBL_T} WHERE well_id='{s}' AND event_ts>=current_timestamp()-INTERVAL 7 DAYS),
            lp AS(SELECT predicted_failure FROM(SELECT predicted_failure,ROW_NUMBER()OVER(ORDER BY window_hour DESC)rn FROM {TBL_P} WHERE well_id='{s}')WHERE rn=1),
            sc AS(SELECT LEAST(.99,GREATEST(.01,.45*COALESCE(fr7,0)+.30*COALESCE(vr24,0)+.15*COALESCE(mts,0)+.10*COALESCE(ps,0)))ws FROM sig)
            SELECT ROUND(ws*100,1)weighted_prob_pct,ROUND(COALESCE(lp.predicted_failure,0)*100,1)ml_prob_pct,
              CASE WHEN GREATEST(ws,COALESCE(lp.predicted_failure,0))>=.7 THEN 'CRITICAL' WHEN GREATEST(ws,COALESCE(lp.predicted_failure,0))>=.4 THEN 'HIGH' WHEN GREATEST(ws,COALESCE(lp.predicted_failure,0))>=.15 THEN 'MEDIUM' ELSE 'LOW' END risk_tier
            FROM sc LEFT JOIN lp ON TRUE""")
            return json.dumps(df.iloc[0].to_dict()) if not df.empty else json.dumps({"message":"No data"})
        except Exception as e: return json.dumps({"error":str(e)})
    return [get_well_ids,get_fleet_health_summary,get_latest_readings,check_threshold_violations,detect_statistical_anomalies,get_failure_probability]

def agent():
    if "agent" not in st.session_state:
        from agents import Agent,set_default_openai_api,set_default_openai_client
        from databricks.sdk import WorkspaceClient
        from openai import AsyncOpenAI
        try: from agents import set_tracing_disabled; set_tracing_disabled(True)
        except: pass
        ws=WorkspaceClient(); host=(ws.config.host or os.getenv("DATABRICKS_HOST","")).rstrip("/")
        token=ws.config.token or os.getenv("DATABRICKS_TOKEN","")
        if not token:  # Databricks Apps auth is OAuth (SP), not a PAT — pull a bearer from the SDK
            try:
                _a=(ws.config.authenticate() or {}).get("Authorization","")
                if _a.startswith("Bearer "): token=_a[7:]
            except Exception: pass
        set_default_openai_client(AsyncOpenAI(api_key=token or "no-token",base_url=f"{host}/serving-endpoints"))
        set_default_openai_api("chat_completions")
        st.session_state.agent=Agent(name="ESP Agent",model=MODEL,instructions=SYS,tools=_tools())
    return st.session_state.agent

async def _run(q):
    from agents import Runner
    return (await Runner.run(agent(),q,max_turns=6)).final_output

def ask(q):
    try:
        try: return asyncio.run(_run(q))
        except RuntimeError:
            loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop); return loop.run_until_complete(_run(q))
    except Exception as e:
        return f"⚠️ AI investigator error: {e}"

# ── Supervisor agent (Genie + ESP procedures, routed) ─────────────────────────
def supervisor_ask(q):
    """Query the Multi-Agent Supervisor serving endpoint via ai_query."""
    try:
        return qdf(f"SELECT ai_query('{MAS_ENDPOINT}','{san(q)}') AS a").iloc[0]["a"]
    except Exception as e:
        return f"⚠️ Supervisor error: {e}"

def respond(q):
    """Route an AI Investigation question by the selected mode."""
    if str(st.session_state.get("ai_mode","")).startswith("🧠"):
        return supervisor_ask(q)
    return ask(q)

# ── Genie (natural-language data Q&A for the floating sidebar) ─────────────────
def genie_ask(q):
    """Ask the ESP Genie space. Returns (text_answer, generated_sql)."""
    from databricks.sdk import WorkspaceClient
    w=WorkspaceClient()
    msg=w.genie.start_conversation_and_wait(GENIE_SPACE_ID,q)
    text=""; sql=""
    for a in (getattr(msg,"attachments",None) or []):
        t=getattr(a,"text",None)
        if t is not None and getattr(t,"content",None): text+=t.content+"\n"
        qa=getattr(a,"query",None)
        if qa is not None and getattr(qa,"query",None): sql=qa.query
    return text.strip(), sql

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="ESP Fleet Command Center",page_icon="🛢️",layout="wide",initial_sidebar_state="expanded")
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
/* Animations */
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.7;transform:scale(1.08)}}}}
@keyframes critGlow{{0%,100%{{box-shadow:0 0 12px {RED}44,0 0 24px {RED}22}}50%{{box-shadow:0 0 28px {RED}88,0 0 50px {RED}44}}}}
@keyframes gradFlow{{0%{{background-position:0% 50%}}50%{{background-position:100% 50%}}100%{{background-position:0% 50%}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
/* Base */
html,body,[data-testid="stAppViewContainer"]{{background:linear-gradient(180deg,#010408 0%,{BG} 12%,{BG} 100%);color:{TEXT};font-family:'Inter',-apple-system,sans-serif;-webkit-font-smoothing:antialiased;}}
[data-testid="stHeader"]{{background:rgba(3,11,21,.85)!important;backdrop-filter:blur(12px);}}
::-webkit-scrollbar{{width:6px;height:6px}}::-webkit-scrollbar-track{{background:{BG}}}::-webkit-scrollbar-thumb{{background:{BORDER};border-radius:3px}}::-webkit-scrollbar-thumb:hover{{background:{CYAN}55}}
/* Tabs */
.stTabs [data-baseweb="tab-list"]{{background:linear-gradient(180deg,{PANEL}ee 0%,{BG}cc 100%);border:1px solid {BORDER};border-radius:16px;padding:5px;gap:4px;backdrop-filter:blur(10px);overflow-x:auto;flex-wrap:nowrap;}}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{{height:0}}
.stTabs [data-baseweb="tab"]{{background:transparent;color:{MUTED};border-radius:11px;padding:9px 16px;font-weight:600;font-size:13px;white-space:nowrap;transition:all .25s ease;}}
.stTabs [data-baseweb="tab"]:hover{{color:{TEXT};background:{CARD}55;}}
.stTabs [aria-selected="true"]{{background:linear-gradient(135deg,{CARD} 0%,{PANEL} 100%);color:{CYAN};box-shadow:0 4px 20px {CYAN}22,inset 0 1px 0 {CYAN}44;}}
/* Buttons */
.stButton>button{{background:linear-gradient(180deg,{CARD} 0%,#060e1c 100%);color:{TEXT};border:1px solid {BORDER};border-radius:12px;padding:12px 22px;font-weight:600;font-size:14px;transition:all .2s ease;box-shadow:0 4px 14px rgba(0,0,0,.35);}}
.stButton>button:hover{{border-color:{CYAN}88;color:{CYAN};box-shadow:0 8px 28px {CYAN}22;transform:translateY(-2px);}}
.stButton>button:active{{transform:translateY(0);}}
/* Inputs */
.stTextInput>div>div>input{{background:linear-gradient(180deg,{CARD} 0%,#060e1c 100%);color:{TEXT};border:1px solid {BORDER};border-radius:12px;padding:14px 18px;font-size:15px;transition:all .2s;}}
.stTextInput>div>div>input:focus{{border-color:{CYAN};box-shadow:0 0 0 3px {CYAN}22;}}
/* Chat */
[data-testid="stChatMessage"]{{background:linear-gradient(180deg,{PANEL} 0%,{BG} 100%);border:1px solid {BORDER};border-radius:16px;margin:8px 0;box-shadow:0 6px 24px rgba(0,0,0,.3);animation:fadeUp .3s ease;}}
/* Hero */
.hero{{background:linear-gradient(135deg,#010408 0%,#061a38 35%,#0a2850 65%,{PANEL} 100%);border:1px solid {BORDER};border-radius:24px;padding:36px 48px;margin-bottom:28px;position:relative;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.5),inset 0 1px 0 rgba(255,255,255,.04);}}
.hero::before{{content:'';position:absolute;top:-60%;right:-30%;width:100%;height:200%;background:radial-gradient(ellipse,{CYAN}0b 0%,transparent 55%);pointer-events:none;}}
.hero::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,{CYAN}55,transparent);}}
.hero h1{{margin:0 0 10px;font-size:34px;font-weight:800;background:linear-gradient(135deg,{TEXT} 0%,{CYAN} 45%,#60efff 60%,{TEXT} 100%);background-size:250% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:gradFlow 5s linear infinite;position:relative;z-index:1;}}
.hero p{{margin:0;font-size:14px;color:{MUTED};line-height:1.8;position:relative;z-index:1;}}
.hero .live{{display:inline-flex;align-items:center;gap:7px;background:{GREEN}18;border:1px solid {GREEN}44;border-radius:20px;padding:4px 14px;font-size:11px;font-weight:700;color:{GREEN};letter-spacing:.04em;margin-left:12px;}}
.hero .live::before{{content:'';width:7px;height:7px;background:{GREEN};border-radius:50%;animation:pulse 2s infinite;}}
/* KPI */
.kpi-card{{background:linear-gradient(160deg,rgba(13,31,54,.92) 0%,rgba(7,21,37,.96) 100%);backdrop-filter:blur(14px);border:1px solid {BORDER};border-radius:18px;padding:20px 24px;transition:all .3s ease;box-shadow:0 8px 32px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.03);}}
.kpi-card:hover{{border-color:{CYAN}55;transform:translateY(-3px);box-shadow:0 16px 48px {CYAN}0f;}}
.kpi-card.crit{{animation:critGlow 2s infinite;border-color:{RED}66;}}
.kpi-label{{font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.1em;font-weight:700;margin-bottom:10px;}}
.kpi-value{{font-size:44px;font-weight:800;line-height:1;font-family:'JetBrains Mono',monospace;}}
.kpi-sub{{font-size:12px;color:{MUTED};margin-top:7px;}}
/* Readout */
.readout-tile{{background:linear-gradient(180deg,{PANEL} 0%,{BG} 100%);border:1px solid {BORDER};border-radius:14px;padding:18px 20px;margin-bottom:12px;}}
.readout-label{{font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.07em;font-weight:700;margin-bottom:10px;}}
.readout-value{{font-size:38px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1;}}
.readout-unit{{font-size:14px;color:{MUTED};margin-left:6px;font-weight:600;}}
.readout-bar{{position:relative;height:8px;border-radius:4px;margin-top:14px;}}
.readout-needle{{position:absolute;width:3px;height:16px;top:-4px;border-radius:2px;transform:translateX(-50%);}}
/* Section dividers */
.section-hdr{{border-bottom:2px solid transparent;background:linear-gradient({BG},{BG}) padding-box,linear-gradient(90deg,{CYAN}44,{PURPLE}33,{CYAN}44) border-box;padding-bottom:12px;margin:28px 0 20px;}}
.section-hdr h2{{margin:0;font-size:20px;font-weight:700;color:{TEXT};display:inline;}}
.section-hdr span{{color:{MUTED};font-size:13px;margin-left:12px;}}
/* Step cards */
.step-card{{background:linear-gradient(180deg,{PANEL} 0%,{BG} 100%);border:1px solid {BORDER};border-radius:18px;padding:26px;margin-bottom:18px;transition:all .3s ease;}}
.step-card:hover{{border-color:{CYAN}44;box-shadow:0 12px 40px {CYAN}09;}}
.step-num{{display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;background:linear-gradient(135deg,{CYAN}22,{CYAN}0f);border:2px solid {CYAN};border-radius:50%;font-size:17px;font-weight:700;color:{CYAN};margin-bottom:14px;box-shadow:0 4px 18px {CYAN}33;}}
.step-title{{font-size:18px;font-weight:700;color:{TEXT};margin:0 0 9px;}}
.step-desc{{font-size:14px;color:{MUTED};line-height:1.7;margin:0;}}
.tip-box{{background:linear-gradient(90deg,#071a38 0%,{PANEL} 100%);border-left:3px solid {CYAN};border-radius:0 12px 12px 0;padding:12px 16px;margin-top:12px;font-size:13px;color:{MUTED};line-height:1.6;box-shadow:inset 4px 0 14px {CYAN}11;}}
.tip-box b{{color:{CYAN};}}
/* Table */
[data-testid="stDataFrame"]{{border-radius:16px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.28);}}
[data-testid="stDataFrame"] th{{background:linear-gradient(180deg,#1a2f4e 0%,{PANEL} 100%)!important;font-weight:700!important;text-transform:uppercase!important;letter-spacing:.05em!important;font-size:10px!important;}}
</style>""",unsafe_allow_html=True)

st.markdown(f"""<div class="hero">
  <h1>🛢️ ESP Fleet Operations Command Center</h1>
  <p>Real-time telemetry &nbsp;·&nbsp; ML failure prediction &nbsp;·&nbsp; AI-guided investigation &nbsp;·&nbsp; {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC</p>
</div>""",unsafe_allow_html=True)

# ── Floating Ask-Genie panel (sidebar, available on every tab) ────────────────
with st.sidebar:
    st.markdown(f"<div style='font-size:18px;font-weight:800;color:{CYAN}'>🧞 Ask Genie</div>"
                f"<div style='color:{MUTED};font-size:12px;margin-bottom:10px'>Natural-language questions over the ESP fleet</div>",unsafe_allow_html=True)
    if "genie_hist" not in st.session_state: st.session_state.genie_hist=[]
    gq=st.text_input("Ask Genie",key="genie_q",placeholder="e.g. Which wells are over 250 F?",label_visibility="collapsed")
    if st.button("Ask Genie",use_container_width=True,type="primary",key="genie_btn") and gq.strip():
        with st.spinner("Genie is thinking…"):
            try:
                _txt,_sql=genie_ask(gq.strip())
                st.session_state.genie_hist.insert(0,{"q":gq.strip(),"a":_txt or "(see results below)","sql":_sql})
            except Exception as e:
                st.session_state.genie_hist.insert(0,{"q":gq.strip(),"a":f"⚠️ Genie error: {e}","sql":""})
    for h in st.session_state.genie_hist[:5]:
        st.markdown(f"<div style='color:{CYAN};font-size:11px;font-weight:700;margin-top:8px'>YOU</div>"
                    f"<div style='color:{TEXT};font-size:13px'>{h['q']}</div>",unsafe_allow_html=True)
        if h.get('a'): st.markdown(h['a'])
        if h.get('sql'):
            with st.expander("SQL + results"):
                st.code(h['sql'],language="sql")
                try: st.dataframe(qdf(h['sql']),use_container_width=True,hide_index=True,height=200)
                except Exception as e: st.caption(f"(preview unavailable: {e})")
        st.markdown(f"<hr style='border-color:{BORDER};margin:8px 0'>",unsafe_allow_html=True)

tab_demo,tab_dash,tab_well,tab_chat,tab_data=st.tabs(["▶ Demo","📊 Fleet","🔬 Well","🤖 AI","🗄️ Data Flow"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — FLEET DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    c1,c2=st.columns([1,5])
    with c1:
        if st.button("⟳  Refresh",use_container_width=True):
            st.cache_data.clear(); st.rerun()
    try:
        df=load_fleet()
        nc=int((df["risk_tier"]=="CRITICAL").sum()); nh=int((df["risk_tier"]=="HIGH").sum())
        nm=int((df["risk_tier"]=="MEDIUM").sum()); nl=int((df["risk_tier"]=="LOW").sum())
        with c2:
            st.markdown(f"<div style='padding-top:8px;color:{MUTED};font-size:13px;'>Last refresh: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC &nbsp;·&nbsp; <b style='color:{TEXT}'>{len(df)}</b> wells monitored</div>",unsafe_allow_html=True)
        st.markdown(_sec("Fleet Posture"),unsafe_allow_html=True)
        k1,k2,k3,k4,k5=st.columns(5)
        k1.markdown(_kpi("Total Wells",str(len(df)),"live snapshot"),unsafe_allow_html=True)
        k2.markdown(_kpi("Critical",str(nc),"immediate action",RED),unsafe_allow_html=True)
        k3.markdown(_kpi("High Risk",str(nh),"priority review",ORANGE),unsafe_allow_html=True)
        k4.markdown(_kpi("Medium",str(nm),"monitor closely",YELLOW),unsafe_allow_html=True)
        k5.markdown(_kpi("Normal",str(nl),"operating well",GREEN),unsafe_allow_html=True)
        st.markdown(_sec("Fleet Sensor Averages"),unsafe_allow_html=True)
        g1,g2,g3,g4=st.columns(4)
        g1.plotly_chart(_gauge("Motor Temp",df["motor_temp_f"].mean(),150,300,220,250,"°F"),use_container_width=True)
        g2.plotly_chart(_gauge("Intake PSI",df["intake_pressure_psi"].mean(),800,2800,1200,2400,"psi",True),use_container_width=True)
        g3.plotly_chart(_gauge("Vibration",df["vibration_g"].mean(),0,5,1.5,2.5,"g"),use_container_width=True)
        g4.plotly_chart(_gauge("Flow Rate",df["flow_rate_bpd"].mean(),0,5000,1000,4000,"bpd",True),use_container_width=True)
        st.markdown(_sec("Risk Intelligence"),unsafe_allow_html=True)
        ch1,ch2=st.columns([3,2])
        ch1.plotly_chart(ch_prob(df),use_container_width=True)
        ch2.plotly_chart(ch_donut(df),use_container_width=True)
        st.markdown(_sec("Well Status Table","click a row to open detail view"),unsafe_allow_html=True)
        disp=df.copy(); disp["ml_prob"]=(disp["ml_prob"]*100).round(1).astype(str)+"%"
        ev=st.dataframe(disp,use_container_width=True,hide_index=True,on_select="rerun",selection_mode="single-row",
            column_config={"well_id":st.column_config.TextColumn("Well ID"),"event_ts":st.column_config.TextColumn("Timestamp"),
                "motor_temp_f":st.column_config.NumberColumn("Motor Temp °F",format="%.1f"),"intake_pressure_psi":st.column_config.NumberColumn("Intake PSI",format="%.1f"),
                "vibration_g":st.column_config.NumberColumn("Vibration g",format="%.3f"),"flow_rate_bpd":st.column_config.NumberColumn("Flow bpd",format="%.1f"),
                "failure_flag":st.column_config.NumberColumn("Failure"),"ml_prob":st.column_config.TextColumn("ML Prob"),"risk_tier":st.column_config.TextColumn("Risk")})
        sel=ev.selection.rows if ev.selection else []
        if sel:
            st.session_state["sel_well"]=df.iloc[sel[0]]["well_id"]
            st.info(f"Well **{st.session_state['sel_well']}** selected — switch to **Well Detail** tab to view telemetry charts.",icon="🔬")
    except Exception as e:
        st.error(f"Dashboard error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — WELL DETAIL
# ══════════════════════════════════════════════════════════════════════════════
with tab_well:
    st.markdown(_sec("Well Telemetry Deep-Dive"),unsafe_allow_html=True)
    try: _wells=sorted(load_fleet()["well_id"].astype(str).tolist())
    except Exception: _wells=[]
    _pre=str(st.session_state.get("sel_well",""))
    _opts=["— select a well —"]+_wells
    _idx=_opts.index(_pre) if _pre in _wells else 0
    wc1,_=st.columns([2,3])
    with wc1: _pick=st.selectbox("Well ID",options=_opts,index=_idx,label_visibility="collapsed")
    wid="" if _pick.startswith("—") else _pick
    if wid:
        try:
            try: row=load_fleet(); row=row[row["well_id"]==wid]
            except: row=pd.DataFrame()
            if not row.empty:
                r=row.iloc[0]; rc=RC.get(str(r["risk_tier"]),MUTED)
                st.markdown(f"<div style='display:flex;gap:8px;align-items:center;margin-bottom:12px'><span style='font-size:18px;font-weight:700;color:{TEXT}'>{wid}</span>{_badge(str(r['risk_tier']),rc)}<span style='color:{MUTED};font-size:13px'>· {r['event_ts']}</span></div>",unsafe_allow_html=True)
                r1,r2,r3,r4=st.columns(4)
                r1.markdown(_readout("Motor Temp",float(r["motor_temp_f"] or 0),150,300,220,250,"°F"),unsafe_allow_html=True)
                r2.markdown(_readout("Intake PSI",float(r["intake_pressure_psi"] or 0),800,2800,1200,2400,"psi",True),unsafe_allow_html=True)
                r3.markdown(_readout("Vibration",float(r["vibration_g"] or 0),0,5,1.5,2.5,"g"),unsafe_allow_html=True)
                r4.markdown(_readout("Flow Rate",float(r["flow_rate_bpd"] or 0),0,5000,1000,4000,"bpd",True),unsafe_allow_html=True)
            hist=load_well_hist(wid)
            st.plotly_chart(ch_ts(hist,wid),use_container_width=True)
            if st.button(f"🤖  Investigate {wid} with AI",type="secondary"):
                st.session_state.setdefault("chat_history",[])
                q=f"Investigate well {wid}. Show threshold violations, statistical anomalies, and failure probability. Recommend actions."
                st.session_state["chat_history"].append({"role":"user","content":q})
                st.session_state["pending"]=q
                st.rerun()
        except Exception as e: st.error(f"Well detail error: {e}")
    else:
        st.markdown(f"<div style='background:{PANEL};border:1px solid {BORDER};border-radius:12px;padding:32px;text-align:center;color:{MUTED}'><div style='font-size:40px;margin-bottom:12px'>🔬</div><div style='font-size:16px'>Select a well from the Fleet Dashboard or enter a Well ID above</div></div>",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — AI INVESTIGATION
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown(_sec("AI Anomaly Investigator"),unsafe_allow_html=True)
    st.radio("Engine",["🧠  Supervisor (Genie + ESP manuals)","🔧  Investigator (live SQL tools)"],
             horizontal=True,key="ai_mode",label_visibility="collapsed")
    if "chat_history" not in st.session_state: st.session_state.chat_history=[]
    qa1,qa2,qa3,qa4=st.columns(4)
    with qa1:
        if st.button("📊  Check all wells",use_container_width=True): st.session_state["pending"]="Check all wells for anomalies. List any CRITICAL or HIGH risk wells with explanations."
    with qa2:
        if st.button("🔴  Find critical",use_container_width=True): st.session_state["pending"]="Which wells are CRITICAL right now? Explain why and what actions to take."
    with qa3:
        if st.button("📈  Failure probs",use_container_width=True): st.session_state["pending"]="Show failure probabilities for all wells, sorted by risk level."
    with qa4:
        if st.button("🧹  Clear chat",use_container_width=True): st.session_state.chat_history=[]; st.rerun()
    for m in st.session_state.chat_history:
        with st.chat_message(m["role"],avatar="🧑‍🔧" if m["role"]=="user" else "🤖"): st.markdown(m["content"])
    if "pending" in st.session_state:
        q=st.session_state.pop("pending")
        st.session_state.chat_history.append({"role":"user","content":q})
        with st.chat_message("user",avatar="🧑‍🔧"): st.markdown(q)
        with st.chat_message("assistant",avatar="🤖"):
            with st.spinner("Analysing wells…"): ans=respond(q)
            st.markdown(ans)
        st.session_state.chat_history.append({"role":"assistant","content":ans})
        st.rerun()
    if prompt:=st.chat_input("Ask anything — e.g. 'Why is WELL_005 at risk?'"):
        st.session_state.chat_history.append({"role":"user","content":prompt})
        with st.chat_message("user",avatar="🧑‍🔧"): st.markdown(prompt)
        with st.chat_message("assistant",avatar="🤖"):
            with st.spinner("Analysing wells…"): ans=respond(prompt)
            st.markdown(ans)
        st.session_state.chat_history.append({"role":"assistant","content":ans})

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DEMO WALKTHROUGH
# ══════════════════════════════════════════════════════════════════════════════
with tab_demo:
    st.markdown(_sec("Demo Guide","run this story in about 5 minutes"),unsafe_allow_html=True)
    _frame=[
        ("🎬 Scene","An operator owns a fleet of 25 ESP wells. Failures are costly and hard to see coming in raw high-frequency telemetry."),
        ("💼 Business Case","Catch failures hours early to avoid lost production and emergency workovers, and give operators a single pane of glass instead of spreadsheets."),
        ("🎯 What We'll Prove","Live telemetry, threshold and anomaly detection, an ML failure score, and a natural-language assistant, all on one governed platform."),
        ("🧱 Databricks Story","Unity Catalog governs the data; serverless SQL serves it; AI/BI and Genie make it conversational; Mosaic AI agents turn signals into recommended actions."),
    ]
    fc=st.columns(4)
    for col,(t,b) in zip(fc,_frame):
        col.markdown(f"<div class='step-card' style='padding:16px;min-height:150px'>"
                     f"<div class='step-title' style='font-size:15px'>{t}</div>"
                     f"<div class='step-desc'>{b}</div></div>",unsafe_allow_html=True)
    st.markdown(_sec("Click-Through Script","follow these steps in order"),unsafe_allow_html=True)

    steps=[
        ("1","🛢️  Open the Fleet Dashboard",
         "Click the <b>📊 Fleet Dashboard</b> tab, then press <b>⟳ Refresh</b> to load live data from Unity Catalog. You'll see the full ESP fleet load in seconds.",
         [("What you'll see","4 fleet-wide sensor gauges — Motor Temp, Intake PSI, Vibration, Flow Rate — each with colour-coded zones (green=safe, yellow=warn, red=critical)"),
          ("KPI strip","5 cards showing total wells and breakdown by risk tier: CRITICAL, HIGH, MEDIUM, and Low/Normal"),
          ("Pro tip","Red gauges mean the fleet average is already in the danger zone — investigate immediately")]),
        ("2","📊  Read the Risk Charts",
         "Below the gauges you'll find two charts that tell you where to focus:",
         [("ML Failure Probability bar","Horizontal bars ranked by the model's predicted failure score. The longest red bars are your highest-priority wells"),
          ("Risk Distribution donut","Instant view of the fleet split across risk tiers. A large red slice means many wells need attention"),
          ("Pro tip","Sort your attention by the bar chart — tackle CRITICAL (red) first, then ORANGE (high)")]),
        ("3","🔍  Select a Well to Investigate",
         "In the <b>Well Status Table</b>, click any row. The row highlights and a banner appears with the selected well ID.",
         [("Colour-coded rows","Red = CRITICAL, Orange = HIGH, Yellow = MEDIUM, Green = LOW — you can scan risk at a glance"),
          ("ML Prob column","This is the model's latest predicted failure probability for that well — values above 70% are CRITICAL"),
          ("Next step","Switch to the <b>🔬 Well Detail</b> tab to see the telemetry deep-dive for that well")]),
        ("4","🔬  Deep-Dive into Well Detail",
         "Go to the <b>🔬 Well Detail</b> tab. The selected well ID is pre-filled — just press <b>Load Well</b>.",
         [("LED readout tiles","4 digital gauges with gradient bars: Motor Temp, Intake PSI, Vibration, Flow Rate — red value = threshold breach"),
          ("24h time series","4-panel chart showing all 4 sensors over the last 24 hours. Dashed red lines are the threshold boundaries"),
          ("Pro tip","Look for sudden spikes or sustained drift in motor temp or vibration — those are the early failure signatures")]),
        ("5","🤖  Ask the AI Investigator",
         "Switch to <b>🤖 AI Investigation</b>. You can use quick-action buttons or type your own question.",
         [("Quick actions","Try <b>Check all wells</b> first to get a prioritised fleet summary, then <b>Find critical</b> for immediate action items"),
          ("Well-specific query","Click <b>Investigate [WELL_ID] with AI</b> in the Well Detail tab to auto-send a structured investigation prompt"),
          ("What the AI does","It calls 6 live tools: get_fleet_health_summary → get_latest_readings → check_threshold_violations → detect_statistical_anomalies → get_failure_probability, then synthesises a recommendation")]),
        ("6","💡  Example Queries to Try",
         "Paste any of these into the AI chat to see its full capability:",
         [("Fleet triage","Check all wells for anomalies and give me a prioritised alert list with recommended actions"),
          ("Single well","Why is WELL_005 at risk? Show me the violations, 3-sigma anomalies, and both weighted and ML failure probabilities"),
          ("Operator handoff","Which wells should I dispatch a field crew to today, and in what order of priority?"),
          ("Threshold check","Which wells have had more than 10 pressure violations in the last 24 hours?")])
    ]

    for num,title,desc,bullets in steps:
        st.markdown(f"""
        <div class="step-card">
          <div class="step-num">{num}</div>
          <p class="step-title">{title}</p>
          <p class="step-desc">{desc}</p>
          {"".join(f'<div class="tip-box"><b>{b[0]}:</b> {b[1]}</div>' for b in bullets)}
        </div>""",unsafe_allow_html=True)

    # Architecture section
    st.markdown(_sec("How It Works","technical overview"),unsafe_allow_html=True)
    st.markdown(f"""
    <div style='background:{PANEL};border:1px solid {BORDER};border-radius:12px;padding:20px;'>
      <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;'>
        <div>
          <div style='color:{CYAN};font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px'>Data Layer</div>
          <div style='color:{TEXT};font-size:13px;line-height:1.8'>
            <b>pump_telemetry</b> — raw sensor readings<br>
            <b>latest_reading_per_well</b> — materialised view<br>
            <b>pump_failure_predictions</b> — ML model output<br>
            Unity Catalog · ESP Hackathon schema
          </div>
        </div>
        <div>
          <div style='color:{CYAN};font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px'>Intelligence Layer</div>
          <div style='color:{TEXT};font-size:13px;line-height:1.8'>
            Threshold rules — hard PSI / temp limits<br>
            3σ statistical anomaly detection<br>
            Weighted heuristic (45/30/15/10 weights)<br>
            ML predicted_failure score (0–100%)
          </div>
        </div>
        <div>
          <div style='color:{CYAN};font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px'>Agent Layer</div>
          <div style='color:{TEXT};font-size:13px;line-height:1.8'>
            Mosaic AI agent framework<br>
            6 live SQL tools, lazy-loaded<br>
            Mosaic AI Model Serving<br>
            All queries run on Databricks Serverless
          </div>
        </div>
      </div>
    </div>
    """,unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — DATA & AI FLOW
# ══════════════════════════════════════════════════════════════════════════════
with tab_data:
    st.markdown(_sec("Data &amp; AI Flow","how telemetry becomes a recommended action"),unsafe_allow_html=True)
    try:
        _flow=open(os.path.join(os.path.dirname(__file__),"esp_dataflow.html"),encoding="utf-8").read()
        components.html(_flow,height=620,scrolling=True)
    except Exception as e:
        st.error(f"Data & AI Flow error: {e}")
