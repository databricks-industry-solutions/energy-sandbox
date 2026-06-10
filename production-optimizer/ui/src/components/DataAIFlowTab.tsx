/* Production Optimizer — Data & AI Flow Diagram
   3-row architecture: Sources | Lakehouse Platform | AI Agents & Serving
   Adapted from the subsea-drone-autopilot DataFlowPage template. */

const FLOW_HTML = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0B0F1A;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     padding:8px 6px;max-width:1400px;margin:0 auto}
html{background:#0B0F1A}
@keyframes fd{from{stroke-dashoffset:18}to{stroke-dashoffset:0}}
.fe{fill:none;stroke-dasharray:6 12;animation:fd 1.2s linear infinite}
.et{fill:none;stroke-opacity:.18}
.ng{cursor:pointer}
.ng rect{transition:filter .15s}
.ng:hover rect{filter:brightness(1.4)}
.ng.sel rect{stroke-width:3!important;filter:brightness(1.6)}
.nl{fill:#E8EDF5;font-size:14px;font-weight:600}
.ns{fill:#6B7A99;font-size:11px}
.sl{fill:#4B5563;font-size:12px;font-weight:700;letter-spacing:2px}
.sep{stroke:#1E2D4F;stroke-width:1}
.ucb{fill:none;stroke:#f97316;stroke-width:1.5;stroke-dasharray:6 4;opacity:.5}
.ucl{fill:#f97316;font-size:11px;font-weight:600;opacity:.7}
.lt{fill:#6B7A99;font-size:10px}
.info{background:#141B2D;border:1px solid #1E2D4F;border-radius:8px;padding:16px;margin-top:10px}
.hw{display:flex;gap:10px;flex-wrap:wrap}
.hc{flex:1;min-width:150px;background:#0e1624;border:1px solid #1E2D4F;border-radius:6px;padding:12px}
.hn{color:#FFB020;font-size:12px;font-weight:700;margin-bottom:6px}
.ht{color:#94A3B8;font-size:11px;line-height:1.6}
.db2{display:inline-block;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:700;margin-bottom:8px}
.dt2{font-size:16px;font-weight:700;color:#E8EDF5;margin-bottom:10px}
.dl2{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px}
.di{font-size:12px;color:#94A3B8;line-height:1.7}
</style></head><body>
<svg viewBox="0 0 1380 580" width="100%" style="display:block">
<defs>
  <marker id="mc" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#06b6d4"/></marker>
  <marker id="mp" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#a855f7"/></marker>
  <marker id="mg" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#22c55e"/></marker>
  <marker id="mo" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#f97316"/></marker>
  <marker id="my" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#eab308"/></marker>
  <marker id="mi" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#6366f1"/></marker>
  <marker id="mt" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#14b8a6"/></marker>
</defs>

<!-- Unity Catalog governance box -->
<rect class="ucb" x="45" y="155" width="1290" height="240" rx="8"/>
<text class="ucl" x="690" y="175" text-anchor="middle">Unity Catalog · oil_pump_monitor_catalog.production_optimizer</text>

<!-- Row labels + dividers -->
<text class="sl" x="690" y="24" text-anchor="middle">DATA SOURCES</text>
<line x1="10" y1="34" x2="1370" y2="34" class="sep"/>
<line x1="10" y1="165" x2="1370" y2="165" class="sep"/>
<text class="sl" x="690" y="188" text-anchor="middle">LAKEHOUSE PLATFORM</text>
<line x1="10" y1="400" x2="1370" y2="400" class="sep"/>
<text class="sl" x="690" y="420" text-anchor="middle">AI AGENTS &amp; SERVING</text>

<!-- ═══ ROW 1: Sources ═══ -->
<g class="ng" id="n-scada" onclick="sel('scada')">
  <rect x="30" y="55" width="180" height="66" rx="8" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
  <text class="nl" x="120" y="82" text-anchor="middle">SCADA / RTU</text>
  <text class="ns" x="120" y="98" text-anchor="middle">Wellhead telemetry</text>
  <text class="ns" x="120" y="112" text-anchor="middle">OPC-UA · Modbus TCP</text>
</g>

<g class="ng" id="n-iot" onclick="sel('iot')">
  <rect x="240" y="55" width="180" height="66" rx="8" fill="#0c3a3f" stroke="#06b6d4" stroke-width="2"/>
  <text class="nl" x="330" y="82" text-anchor="middle">IoT Sensors</text>
  <text class="ns" x="330" y="98" text-anchor="middle">Downhole · DTS / DAS</text>
  <text class="ns" x="330" y="112" text-anchor="middle">MQTT → Kafka</text>
</g>

<g class="ng" id="n-co2" onclick="sel('co2')">
  <rect x="450" y="55" width="180" height="66" rx="8" fill="#0a3526" stroke="#10b981" stroke-width="2"/>
  <text class="nl" x="540" y="82" text-anchor="middle">CO₂ Metering</text>
  <text class="ns" x="540" y="98" text-anchor="middle">Coriolis · ultrasonic</text>
  <text class="ns" x="540" y="112" text-anchor="middle">MRV-ready · 45Q</text>
</g>

<g class="ng" id="n-market" onclick="sel('market')">
  <rect x="660" y="55" width="180" height="66" rx="8" fill="#2a1a4a" stroke="#a855f7" stroke-width="2"/>
  <text class="nl" x="750" y="82" text-anchor="middle">Market / Pricing</text>
  <text class="ns" x="750" y="98" text-anchor="middle">WTI · Henry Hub · CO₂</text>
  <text class="ns" x="750" y="112" text-anchor="middle">REST API · 45Q credits</text>
</g>

<g class="ng" id="n-lab" onclick="sel('lab')">
  <rect x="870" y="55" width="180" height="66" rx="8" fill="#3a2407" stroke="#f59e0b" stroke-width="2"/>
  <text class="nl" x="960" y="82" text-anchor="middle">Lab / PVT</text>
  <text class="ns" x="960" y="98" text-anchor="middle">Core · rel-perm · MMP</text>
  <text class="ns" x="960" y="112" text-anchor="middle">UC Volumes</text>
</g>

<g class="ng" id="n-hist" onclick="sel('hist')">
  <rect x="1080" y="55" width="180" height="66" rx="8" fill="#3a0e12" stroke="#ef4444" stroke-width="2"/>
  <text class="nl" x="1170" y="82" text-anchor="middle">Field History</text>
  <text class="ns" x="1170" y="98" text-anchor="middle">Monthly production</text>
  <text class="ns" x="1170" y="112" text-anchor="middle">Well tests · interventions</text>
</g>

<!-- ═══ ROW 2: Lakehouse Platform (inside UC box) ═══ -->
<g class="ng" id="n-bronze" onclick="sel('bronze')">
  <rect x="70" y="210" width="180" height="66" rx="8" fill="#3d2614" stroke="#cd7f32" stroke-width="2"/>
  <text class="nl" x="160" y="237" text-anchor="middle">Bronze Layer</text>
  <text class="ns" x="160" y="253" text-anchor="middle">bronze_wells · 20 rows</text>
  <text class="ns" x="160" y="267" text-anchor="middle">bronze_patterns · 4 rows</text>
</g>

<g class="ng" id="n-silver" onclick="sel('silver')">
  <rect x="310" y="210" width="180" height="66" rx="8" fill="#2a2a2a" stroke="#c0c0c0" stroke-width="2"/>
  <text class="nl" x="400" y="237" text-anchor="middle">Silver Layer</text>
  <text class="ns" x="400" y="253" text-anchor="middle">silver_production_history</text>
  <text class="ns" x="400" y="267" text-anchor="middle">silver_economics · 760+16</text>
</g>

<g class="ng" id="n-gold" onclick="sel('gold')">
  <rect x="550" y="210" width="180" height="66" rx="8" fill="#3d2e07" stroke="#ffd700" stroke-width="2"/>
  <text class="nl" x="640" y="237" text-anchor="middle">Gold Layer</text>
  <text class="ns" x="640" y="253" text-anchor="middle">decline_curves · recs</text>
  <text class="ns" x="640" y="267" text-anchor="middle">field_economics · docs</text>
</g>

<g class="ng" id="n-genie" onclick="sel('genie')">
  <rect x="850" y="210" width="180" height="66" rx="8" fill="#2a1a4a" stroke="#a855f7" stroke-width="2"/>
  <text class="nl" x="940" y="237" text-anchor="middle">Genie Space</text>
  <text class="ns" x="940" y="253" text-anchor="middle">Gold-scoped NL → SQL</text>
  <text class="ns" x="940" y="267" text-anchor="middle">Conversation API</text>
</g>

<g class="ng" id="n-warehouse" onclick="sel('warehouse')">
  <rect x="1110" y="210" width="200" height="66" rx="8" fill="#3a2407" stroke="#f59e0b" stroke-width="2"/>
  <text class="nl" x="1210" y="237" text-anchor="middle">SQL Warehouse</text>
  <text class="ns" x="1210" y="253" text-anchor="middle">Serverless · 87e069...</text>
  <text class="ns" x="1210" y="267" text-anchor="middle">/api/2.0/sql/statements</text>
</g>

<g class="ng" id="n-fmapi" onclick="sel('fmapi')">
  <rect x="550" y="310" width="200" height="66" rx="8" fill="#0a3526" stroke="#10b981" stroke-width="2"/>
  <text class="nl" x="650" y="337" text-anchor="middle">Foundation Model API</text>
  <text class="ns" x="650" y="353" text-anchor="middle">databricks-claude-sonnet-4-5</text>
  <text class="ns" x="650" y="367" text-anchor="middle">/serving-endpoints</text>
</g>

<g class="ng" id="n-loader" onclick="sel('loader')">
  <rect x="70" y="310" width="180" height="66" rx="8" fill="#0c3a3f" stroke="#06b6d4" stroke-width="2"/>
  <text class="nl" x="160" y="337" text-anchor="middle">load_data.py</text>
  <text class="ns" x="160" y="353" text-anchor="middle">Arps decline physics</text>
  <text class="ns" x="160" y="367" text-anchor="middle">Python · INSERT path</text>
</g>

<g class="ng" id="n-uc" onclick="sel('uc')">
  <rect x="850" y="310" width="180" height="66" rx="8" fill="#3a2407" stroke="#f97316" stroke-width="2"/>
  <text class="nl" x="940" y="337" text-anchor="middle">Unity Catalog</text>
  <text class="ns" x="940" y="353" text-anchor="middle">Governance · grants</text>
  <text class="ns" x="940" y="367" text-anchor="middle">Lineage · audit</text>
</g>

<!-- ═══ ROW 3: AI Agents & Serving ═══ -->
<g class="ng" id="n-field-agent" onclick="sel('field-agent')">
  <rect x="30" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="120" y="467" text-anchor="middle">Field Overview Agent</text>
  <text class="ns" x="120" y="483" text-anchor="middle">Selected-asset context</text>
  <text class="ns" x="120" y="497" text-anchor="middle">Genie + map clicks</text>
</g>

<g class="ng" id="n-supervisor" onclick="sel('supervisor')">
  <rect x="240" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="330" y="467" text-anchor="middle">Approval Supervisor</text>
  <text class="ns" x="330" y="483" text-anchor="middle">5 specialists · parallel</text>
  <text class="ns" x="330" y="497" text-anchor="middle">Claude 4.5 synthesis</text>
</g>

<g class="ng" id="n-ask-genie" onclick="sel('ask-genie')">
  <rect x="450" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="540" y="467" text-anchor="middle">Ask Genie</text>
  <text class="ns" x="540" y="483" text-anchor="middle">Free-form NL → SQL</text>
  <text class="ns" x="540" y="497" text-anchor="middle">Returns text + rows</text>
</g>

<g class="ng" id="n-scenario" onclick="sel('scenario')">
  <rect x="660" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="750" y="467" text-anchor="middle">Scenario Engine</text>
  <text class="ns" x="750" y="483" text-anchor="middle">What-if physics</text>
  <text class="ns" x="750" y="497" text-anchor="middle">Per-well prediction</text>
</g>

<g class="ng" id="n-ui" onclick="sel('ui')">
  <rect x="930" y="440" width="180" height="66" rx="8" fill="#052e16" stroke="#22c55e" stroke-width="2"/>
  <text class="nl" x="1020" y="467" text-anchor="middle">Operator UI</text>
  <text class="ns" x="1020" y="483" text-anchor="middle">React + Vite · 6 tabs</text>
  <text class="ns" x="1020" y="497" text-anchor="middle">Field · Twin · Optimizer …</text>
</g>

<g class="ng" id="n-api" onclick="sel('api')">
  <rect x="1180" y="440" width="150" height="66" rx="8" fill="#052e16" stroke="#22c55e" stroke-width="2"/>
  <text class="nl" x="1255" y="467" text-anchor="middle">Express API</text>
  <text class="ns" x="1255" y="483" text-anchor="middle">Node · TypeScript</text>
  <text class="ns" x="1255" y="497" text-anchor="middle">Databricks App</text>
</g>

<!-- ═══ EDGES ═══ -->
<!-- Row 1 → Row 2 -->
<path class="et" d="M120,121 C120,165 160,165 160,210" stroke="#3b82f6" stroke-width="2.5"/>
<path class="fe" d="M120,121 C120,165 160,165 160,210" stroke="#3b82f6" stroke-width="3" marker-end="url(#mc)"/>

<path class="et" d="M330,121 C330,165 160,165 160,210" stroke="#06b6d4" stroke-width="2.5"/>
<path class="fe" d="M330,121 C330,165 160,165 160,210" stroke="#06b6d4" stroke-width="3" marker-end="url(#mc)" style="animation-delay:.2s"/>

<path class="et" d="M540,121 C540,165 160,165 160,210" stroke="#10b981" stroke-width="2.5"/>
<path class="fe" d="M540,121 C540,165 160,165 160,210" stroke="#10b981" stroke-width="3" marker-end="url(#mt)" style="animation-delay:.3s"/>

<path class="et" d="M750,121 C750,165 160,165 160,210" stroke="#a855f7" stroke-width="2.5"/>
<path class="fe" d="M750,121 C750,165 160,165 160,210" stroke="#a855f7" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.4s"/>

<path class="et" d="M960,121 C960,165 160,165 160,210" stroke="#f59e0b" stroke-width="2.5"/>
<path class="fe" d="M960,121 C960,165 160,165 160,210" stroke="#f59e0b" stroke-width="3" marker-end="url(#my)" style="animation-delay:.6s"/>

<path class="et" d="M1170,121 C1170,165 160,165 160,210" stroke="#ef4444" stroke-width="2.5"/>
<path class="fe" d="M1170,121 C1170,165 160,165 160,210" stroke="#ef4444" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.8s"/>

<!-- Row 2 internal: Bronze → Silver → Gold → Genie -->
<path class="et" d="M250,243 L310,243" stroke="#c0c0c0" stroke-width="2.5"/>
<path class="fe" d="M250,243 L310,243" stroke="#c0c0c0" stroke-width="3" marker-end="url(#mp)"/>

<path class="et" d="M490,243 L550,243" stroke="#ffd700" stroke-width="2.5"/>
<path class="fe" d="M490,243 L550,243" stroke="#ffd700" stroke-width="3" marker-end="url(#my)" style="animation-delay:.2s"/>

<path class="et" d="M730,243 L850,243" stroke="#a855f7" stroke-width="2.5"/>
<path class="fe" d="M730,243 L850,243" stroke="#a855f7" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.4s"/>

<!-- Loader → Bronze (writes) -->
<path class="et" d="M160,310 L160,276" stroke="#06b6d4" stroke-width="2.5"/>
<path class="fe" d="M160,310 L160,276" stroke="#06b6d4" stroke-width="3" marker-end="url(#mc)" style="animation-delay:.5s"/>

<!-- Gold → SQL Warehouse (read path) -->
<path class="et" d="M730,243 L1110,243" stroke="#f59e0b" stroke-width="2.5" stroke-dasharray="4 4"/>
<path class="fe" d="M730,243 L1110,243" stroke="#f59e0b" stroke-width="3" marker-end="url(#my)" style="animation-delay:.7s"/>

<!-- Row 2 → Row 3 -->
<path class="et" d="M940,276 C940,360 120,360 120,440" stroke="#a855f7" stroke-width="2.5"/>
<path class="fe" d="M940,276 C940,360 120,360 120,440" stroke="#a855f7" stroke-width="3" marker-end="url(#mi)"/>

<path class="et" d="M650,376 C650,410 330,410 330,440" stroke="#10b981" stroke-width="2.5"/>
<path class="fe" d="M650,376 C650,410 330,410 330,440" stroke="#10b981" stroke-width="3" marker-end="url(#mi)" style="animation-delay:.2s"/>

<path class="et" d="M940,276 C940,360 540,360 540,440" stroke="#a855f7" stroke-width="2.5"/>
<path class="fe" d="M940,276 C940,360 540,360 540,440" stroke="#a855f7" stroke-width="3" marker-end="url(#mi)" style="animation-delay:.4s"/>

<path class="et" d="M1210,276 C1210,410 750,410 750,440" stroke="#f59e0b" stroke-width="2.5"/>
<path class="fe" d="M1210,276 C1210,410 750,410 750,440" stroke="#f59e0b" stroke-width="3" marker-end="url(#mi)" style="animation-delay:.6s"/>

<path class="et" d="M1210,276 C1210,410 330,410 330,440" stroke="#f59e0b" stroke-width="2.5"/>
<path class="fe" d="M1210,276 C1210,410 330,410 330,440" stroke="#f59e0b" stroke-width="3" marker-end="url(#mi)" style="animation-delay:.5s"/>

<!-- Agents → UI / API -->
<path class="et" d="M840,473 L930,473" stroke="#22c55e" stroke-width="2.5"/>
<path class="fe" d="M840,473 L930,473" stroke="#22c55e" stroke-width="3" marker-end="url(#mg)" style="animation-delay:.8s"/>

<path class="et" d="M1110,473 L1180,473" stroke="#22c55e" stroke-width="2.5"/>
<path class="fe" d="M1110,473 L1180,473" stroke="#22c55e" stroke-width="3" marker-end="url(#mg)"/>

<!-- Legend -->
<circle cx="30" cy="565" r="5" fill="#3b82f6"/><text class="lt" x="40" y="569">Telemetry / Sources</text>
<circle cx="180" cy="565" r="5" fill="#c0c0c0"/><text class="lt" x="190" y="569">Medallion (Bronze/Silver/Gold)</text>
<circle cx="380" cy="565" r="5" fill="#a855f7"/><text class="lt" x="390" y="569">Genie</text>
<circle cx="440" cy="565" r="5" fill="#10b981"/><text class="lt" x="450" y="569">Claude FM API</text>
<circle cx="555" cy="565" r="5" fill="#f59e0b"/><text class="lt" x="565" y="569">SQL Warehouse</text>
<circle cx="685" cy="565" r="5" fill="#6366f1"/><text class="lt" x="695" y="569">AI Agents</text>
<circle cx="775" cy="565" r="5" fill="#22c55e"/><text class="lt" x="785" y="569">UI Serving</text>
</svg>

<!-- How It Works -->
<div id="howto" class="info">
  <div class="hw">
    <div class="hc"><div class="hn">1 - Ingest</div><div class="ht">SCADA, IoT, CO₂ meters, market feeds, lab/PVT, and field history flow into Bronze Delta tables via Auto Loader.</div></div>
    <div class="hc"><div class="hn">2 - Medallion</div><div class="ht">Bronze → Silver (quality + features: GOR, water cut, CO₂%) → Gold (decline curves, recommendations, field economics, petroleum docs).</div></div>
    <div class="hc"><div class="hn">3 - Physics</div><div class="ht">load_data.py runs Arps decline fits in Python and writes them as gold_decline_curves rows. Same code path also seeds field economics.</div></div>
    <div class="hc"><div class="hn">4 - Genie Space</div><div class="ht">Genie scoped to the gold_* tables answers NL→SQL questions for Ask Genie and the Field Overview agent.</div></div>
    <div class="hc"><div class="hn">5 - Claude 4.5</div><div class="ht">Foundation Model API endpoint databricks-claude-sonnet-4-5 powers the Approval Supervisor — 5 specialists then a synthesis verdict.</div></div>
    <div class="hc"><div class="hn">6 - Operator UI</div><div class="ht">React SPA served by Express on a Databricks App. 6 tabs · Field · Twin · Optimizer · Genie · Supervisor · this view.</div></div>
    <div class="hc"><div class="hn">7 - Governance</div><div class="ht">Every read goes through Unity Catalog grants. SP OAuth + Apps client_credentials grant; full lineage + audit.</div></div>
  </div>
  <div style="margin-top:8px;font-size:11px;color:#4B5563;text-align:center">Click any node for details</div>
</div>

<div id="detail" class="info" style="display:none">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <span class="db2" id="db2">TYPE</span>
    <button onclick="clr()" style="font-size:12px;background:#1E2D4F;color:#94A3B8;border:none;border-radius:4px;padding:4px 12px;cursor:pointer">Back</button>
  </div>
  <div class="dt2" id="dt2"></div>
  <div class="dl2" id="dl2"></div>
</div>

<script>
const D={
  scada:{b:"SOURCE",b_c:"#3b82f6",t:"SCADA / RTU Telemetry",l:["Wellhead + facility telemetry","BHP, tubing / casing pressure","Choke positions, valve states","Oil / gas / water flow rates","OPC-UA / Modbus TCP polling","Ingested via Auto Loader"]},
  iot:{b:"SOURCE",b_c:"#06b6d4",t:"IoT Sensors",l:["Downhole gauges","Fiber-optic DTS / DAS","CO₂ analyzers · vibration sensors","Drives GOR / water-cut / CO₂% columns","MQTT → Kafka → Auto Loader","Per-minute resolution"]},
  co2:{b:"SOURCE",b_c:"#10b981",t:"CO₂ Metering",l:["Coriolis + ultrasonic meters","Injection + production headers","Purchased vs recycled accounting","MRV-ready per EPA Subpart RR","Drives co2_inj_rate column","Feeds 45Q credit reconciliation"]},
  market:{b:"SOURCE",b_c:"#a855f7",t:"Market / Pricing",l:["WTI + Henry Hub spot","CO₂ contract rates","45Q credit valuations","REST API · 15-min cadence","Drives silver_economics revenue","Drives gold_field_economics netback"]},
  lab:{b:"SOURCE",b_c:"#f59e0b",t:"Lab / PVT",l:["PVT studies + core analysis","Relative permeability","CO₂-oil MMP tests","Structured CSVs in UC Volumes","Drives reservoir parameters","Feeds material-balance models"]},
  hist:{b:"SOURCE",b_c:"#ef4444",t:"Field History",l:["Monthly production records","Well tests + intervention logs","Historical batch load","760 monthly rows · 16 producers","Backfills silver_production_history","Feeds Arps decline fits"]},
  bronze:{b:"BRONZE",b_c:"#cd7f32",t:"Bronze Delta Tables",l:["bronze_wells · 20 rows","16 producers + 4 injectors","bronze_patterns · 4 EOR patterns","Apache · Bravo · Charlie · Delta","Append-only · CDF enabled","Source for feature pipelines"]},
  silver:{b:"SILVER",b_c:"#c0c0c0",t:"Silver Feature Tables",l:["silver_production_history · 760 rows","Oil / gas / water rates · BHP","GOR · water cut · CO₂ concentration","silver_economics · 16 wells","Revenue · LOE · transport · netback","Partitioned by well_id"]},
  gold:{b:"GOLD",b_c:"#ffd700",t:"Gold Analytics Tables",l:["gold_decline_curves · 16 Arps fits","qi / Di / b / R² / EUR · health","gold_recommendations · physics actions","gold_field_economics · aggregates","petroleum_documents · SPE references","Powers all UI + agent reads"]},
  genie:{b:"GENIE",b_c:"#a855f7",t:"Genie Space",l:["Space 01f1559bf0731e529a700d5509784968","Production Optimizer — Field Operations","Scoped to the gold_* tables","NL→SQL via Conversation API","Powers Ask Genie + Field Overview","Selected-asset context auto-prepended"]},
  warehouse:{b:"COMPUTE",b_c:"#f59e0b",t:"SQL Warehouse",l:["Serverless · id 87e069097741b56c","/api/2.0/sql/statements","Apps SP OAuth token","All UC reads + writes","Used by every tab and agent","Bound to app via resources"]},
  fmapi:{b:"MODEL",b_c:"#10b981",t:"Foundation Model API · Claude 4.5",l:["databricks-claude-sonnet-4-5","/serving-endpoints/{name}/invocations","Powers Approval Supervisor","Decline-curve specialist + synthesis","temperature = 0.2 · max_tokens 600","Same OAuth token as SQL"]},
  loader:{b:"LOADER",b_c:"#06b6d4",t:"load_data.py",l:["scripts/load_data.py","Arps decline physics in Python","INSERTs Bronze → Silver → Gold rows","Statement-execution API path","Production-grade equivalent:","Auto Loader + Spark Declarative Pipeline"]},
  uc:{b:"GOVERNANCE",b_c:"#f97316",t:"Unity Catalog",l:["oil_pump_monitor_catalog.production_optimizer","8 governed tables","Grants on SP + demo user","Lineage + column-level audit","Powers Genie scoping","Single source of truth"]},
  "field-agent":{b:"AGENT",b_c:"#6366f1",t:"Field Overview Agent",l:["/api/agent/query → Genie","Selected-asset props prepended","Map click drives context","Returns NL answer + SQL + rows","Side panel on Field Overview tab","Conversation IDs threaded forward"]},
  supervisor:{b:"AGENT",b_c:"#6366f1",t:"Approval Supervisor",l:["/api/supervisor/decide SSE","5 specialists run in parallel","Decline · Economics · Rec History","Analog · Operations","Claude 4.5 synthesis verdict","APPROVE / WITH-MODS / DEFER / REJECT"]},
  "ask-genie":{b:"AGENT",b_c:"#6366f1",t:"Ask Genie",l:["/api/genie/ask","Free-form NL → SQL chat","Returns text + SQL + result rows","Conversation persistence","Dedicated tab","Direct Genie Space access"]},
  scenario:{b:"AGENT",b_c:"#6366f1",t:"Scenario Engine",l:["/api/production/what-if","Per-well prediction via physics","Choke + injection + price sliders","Pre-populates from gold_recommendations","Field-economics context bar","Auto-runs on rec selection"]},
  ui:{b:"UI",b_c:"#22c55e",t:"Operator UI",l:["React + Vite SPA","6 tabs · Field · Twin · Optimizer","Ask Genie · Supervisor · Flow","Dark theme · canvas + SVG","SSE streaming for Supervisor","Built static, served by Express"]},
  api:{b:"API",b_c:"#22c55e",t:"Express API",l:["Node · TypeScript","Routes: production · commercial · twin","agent · genie · supervisor · map · shift","SSE for /api/supervisor/decide","Polled by all UI tabs","Deployed as Databricks App"]},
};
let s=null;
function sel(id){
  if(s)document.getElementById('n-'+s)?.classList.remove('sel');
  s=id;document.getElementById('n-'+id)?.classList.add('sel');
  const d=D[id];if(!d)return;
  const b=document.getElementById('db2');
  b.textContent=d.b;
  b.style.cssText='background:'+d.b_c+'22;color:'+d.b_c+';border:1px solid '+d.b_c+'55;display:inline-block;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:700;margin-bottom:8px';
  document.getElementById('dt2').textContent=d.t;
  document.getElementById('dl2').innerHTML=d.l.map(x=>'<div class="di">'+x+'</div>').join('');
  document.getElementById('howto').style.display='none';
  document.getElementById('detail').style.display='block';
}
function clr(){
  if(s){document.getElementById('n-'+s)?.classList.remove('sel');s=null;}
  document.getElementById('howto').style.display='block';
  document.getElementById('detail').style.display='none';
}
</script>
</body></html>`;

export default function DataAIFlowTab() {
  const iframeHtml = '<iframe srcdoc="' + FLOW_HTML.replace(/"/g, '&quot;') + '" style="width:100%;height:820px;border:none;border-radius:8px;background:#0B0F1A;" />';
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12, color: '#E8EDF5' }}>
        Data &amp; AI Flow
      </h2>
      <div dangerouslySetInnerHTML={{ __html: iframeHtml }} />
    </div>
  );
}
