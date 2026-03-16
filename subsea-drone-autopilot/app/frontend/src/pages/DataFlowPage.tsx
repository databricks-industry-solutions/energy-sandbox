import React from "react";

// Data Flow Diagram — scaled up, bigger boxes, larger text
// 3-row architecture: Sources | Platform/Medallion | Serving
// Unity Catalog governance box covers Bronze + Silver + Gold + VS + Lakebase

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
  <marker id="mp" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#7c3aed"/></marker>
  <marker id="mg" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#22c55e"/></marker>
  <marker id="mo" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#f97316"/></marker>
  <marker id="my" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#eab308"/></marker>
  <marker id="mi" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#6366f1"/></marker>
</defs>

<!-- Unity Catalog governance box — covers ALL platform tables including Bronze -->
<rect class="ucb" x="45" y="155" width="1000" height="240" rx="8"/>
<text class="ucl" x="545" y="175">Unity Catalog Governance</text>

<!-- Row labels + dividers -->
<text class="sl" x="690" y="24" text-anchor="middle">DATA SOURCES</text>
<line x1="10" y1="34" x2="1370" y2="34" class="sep"/>
<line x1="10" y1="165" x2="1370" y2="165" class="sep"/>
<text class="sl" x="690" y="188" text-anchor="middle">LAKEHOUSE PLATFORM</text>
<line x1="10" y1="400" x2="1370" y2="400" class="sep"/>
<text class="sl" x="690" y="420" text-anchor="middle">AI AGENTS &amp; SERVING</text>

<!-- ═══ ROW 1: Sources (y_center=95, box_h=66) ═══ -->
<g class="ng" id="n-telem" onclick="sel('telem')">
  <rect x="30" y="55" width="180" height="66" rx="8" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
  <text class="nl" x="120" y="82" text-anchor="middle">Drone Telemetry</text>
  <text class="ns" x="120" y="98" text-anchor="middle">5 ROVs / Streaming</text>
  <text class="ns" x="120" y="112" text-anchor="middle">IMU, Depth, Thrusters</text>
</g>

<g class="ng" id="n-camera" onclick="sel('camera')">
  <rect x="240" y="55" width="180" height="66" rx="8" fill="#1e3a5f" stroke="#3b82f6" stroke-width="2"/>
  <text class="nl" x="330" y="82" text-anchor="middle">Camera Frames</text>
  <text class="ns" x="330" y="98" text-anchor="middle">HD Subsea Images</text>
  <text class="ns" x="330" y="112" text-anchor="middle">4K @ 30fps per drone</text>
</g>

<g class="ng" id="n-ctrl" onclick="sel('ctrl')">
  <rect x="450" y="55" width="180" height="66" rx="8" fill="#1c1007" stroke="#f97316" stroke-width="2"/>
  <text class="nl" x="540" y="82" text-anchor="middle">Drone Control API</text>
  <text class="ns" x="540" y="98" text-anchor="middle">Route / Dispatch / Abort</text>
  <text class="ns" x="540" y="112" text-anchor="middle">REST Gateway</text>
</g>

<g class="ng" id="n-manuals" onclick="sel('manuals')">
  <rect x="660" y="55" width="180" height="66" rx="8" fill="#1a1507" stroke="#eab308" stroke-width="2"/>
  <text class="nl" x="750" y="82" text-anchor="middle">PDF Manuals</text>
  <text class="ns" x="750" y="98" text-anchor="middle">OEM / Procedures</text>
  <text class="ns" x="750" y="112" text-anchor="middle">UC Volumes</text>
</g>

<g class="ng" id="n-assets" onclick="sel('assets')">
  <rect x="870" y="55" width="180" height="66" rx="8" fill="#0d2e2e" stroke="#14b8a6" stroke-width="2"/>
  <text class="nl" x="960" y="82" text-anchor="middle">Asset Registry</text>
  <text class="ns" x="960" y="98" text-anchor="middle">Risers, Manifolds</text>
  <text class="ns" x="960" y="112" text-anchor="middle">FPSOs, Moorings</text>
</g>

<g class="ng" id="n-hist" onclick="sel('hist')">
  <rect x="1080" y="55" width="180" height="66" rx="8" fill="#1a0d4a" stroke="#8b5cf6" stroke-width="2"/>
  <text class="nl" x="1170" y="82" text-anchor="middle">Historical Reports</text>
  <text class="ns" x="1170" y="98" text-anchor="middle">Past Inspections</text>
  <text class="ns" x="1170" y="112" text-anchor="middle">Defect Database</text>
</g>

<!-- ═══ ROW 2: Platform (inside UC box) ═══ -->
<g class="ng" id="n-bronze" onclick="sel('bronze')">
  <rect x="70" y="210" width="180" height="66" rx="8" fill="#1a1430" stroke="#4f46e5" stroke-width="2"/>
  <text class="nl" x="160" y="237" text-anchor="middle">Bronze Layer</text>
  <text class="ns" x="160" y="253" text-anchor="middle">telemetry_raw</text>
  <text class="ns" x="160" y="267" text-anchor="middle">inspection_frames</text>
</g>

<g class="ng" id="n-silver" onclick="sel('silver')">
  <rect x="310" y="210" width="180" height="66" rx="8" fill="#2d1b69" stroke="#7c3aed" stroke-width="2"/>
  <text class="nl" x="400" y="237" text-anchor="middle">Silver Layer</text>
  <text class="ns" x="400" y="253" text-anchor="middle">telemetry_features</text>
  <text class="ns" x="400" y="267" text-anchor="middle">anomaly_score</text>
</g>

<g class="ng" id="n-gold" onclick="sel('gold')">
  <rect x="550" y="210" width="180" height="66" rx="8" fill="#431407" stroke="#f97316" stroke-width="2"/>
  <text class="nl" x="640" y="237" text-anchor="middle">Gold Layer</text>
  <text class="ns" x="640" y="253" text-anchor="middle">inspections</text>
  <text class="ns" x="640" y="267" text-anchor="middle">autopilot_decisions</text>
</g>

<g class="ng" id="n-vs" onclick="sel('vs')">
  <rect x="850" y="210" width="180" height="66" rx="8" fill="#1e1040" stroke="#a78bfa" stroke-width="2"/>
  <text class="nl" x="940" y="237" text-anchor="middle">Vector Search</text>
  <text class="ns" x="940" y="253" text-anchor="middle">Manual Chunks</text>
  <text class="ns" x="940" y="267" text-anchor="middle">RAG Index</text>
</g>

<g class="ng" id="n-lb" onclick="sel('lb')">
  <rect x="550" y="310" width="180" height="66" rx="8" fill="#0d2e2e" stroke="#14b8a6" stroke-width="2"/>
  <text class="nl" x="640" y="337" text-anchor="middle">Lakebase</text>
  <text class="ns" x="640" y="353" text-anchor="middle">Operational State</text>
  <text class="ns" x="640" y="367" text-anchor="middle">PostgreSQL</text>
</g>

<g class="ng" id="n-ml" onclick="sel('ml')">
  <rect x="310" y="310" width="180" height="66" rx="8" fill="#1a0d4a" stroke="#8b5cf6" stroke-width="2"/>
  <text class="nl" x="400" y="337" text-anchor="middle">ML Models</text>
  <text class="ns" x="400" y="353" text-anchor="middle">Vision / Anomaly</text>
  <text class="ns" x="400" y="367" text-anchor="middle">Model Serving</text>
</g>

<!-- ═══ ROW 3: Agents & Serving ═══ -->
<g class="ng" id="n-autopilot" onclick="sel('autopilot')">
  <rect x="30" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="120" y="467" text-anchor="middle">Autopilot Agent</text>
  <text class="ns" x="120" y="483" text-anchor="middle">Mission Plan + Safety</text>
  <text class="ns" x="120" y="497" text-anchor="middle">Claude + Tools</text>
</g>

<g class="ng" id="n-inspect" onclick="sel('inspect')">
  <rect x="240" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="330" y="467" text-anchor="middle">Inspection Agent</text>
  <text class="ns" x="330" y="483" text-anchor="middle">Image + Telemetry</text>
  <text class="ns" x="330" y="497" text-anchor="middle">RAG Reports</text>
</g>

<g class="ng" id="n-maint" onclick="sel('maint')">
  <rect x="450" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="540" y="467" text-anchor="middle">Maintenance Agent</text>
  <text class="ns" x="540" y="483" text-anchor="middle">Fleet Health</text>
  <text class="ns" x="540" y="497" text-anchor="middle">Work Orders</text>
</g>

<g class="ng" id="n-knowl" onclick="sel('knowl')">
  <rect x="660" y="440" width="180" height="66" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
  <text class="nl" x="750" y="467" text-anchor="middle">Knowledge Agent</text>
  <text class="ns" x="750" y="483" text-anchor="middle">Operator Q&amp;A</text>
  <text class="ns" x="750" y="497" text-anchor="middle">Manual RAG</text>
</g>

<g class="ng" id="n-ui" onclick="sel('ui')">
  <rect x="930" y="440" width="180" height="66" rx="8" fill="#052e16" stroke="#22c55e" stroke-width="2"/>
  <text class="nl" x="1020" y="467" text-anchor="middle">Operator UI</text>
  <text class="ns" x="1020" y="483" text-anchor="middle">React + FastAPI</text>
  <text class="ns" x="1020" y="497" text-anchor="middle">Databricks App</text>
</g>

<g class="ng" id="n-api" onclick="sel('api')">
  <rect x="1180" y="440" width="150" height="66" rx="8" fill="#052e16" stroke="#22c55e" stroke-width="2"/>
  <text class="nl" x="1255" y="467" text-anchor="middle">SSE API</text>
  <text class="ns" x="1255" y="483" text-anchor="middle">Streaming</text>
  <text class="ns" x="1255" y="497" text-anchor="middle">FastAPI</text>
</g>

<!-- ═══ EDGES ═══ -->
<!-- Row 1 → Row 2 -->
<path class="et" d="M120,121 C120,165 160,165 160,210" stroke="#3b82f6" stroke-width="2.5"/>
<path class="fe" d="M120,121 C120,165 160,165 160,210" stroke="#3b82f6" stroke-width="3" marker-end="url(#mc)"/>

<path class="et" d="M330,121 C330,165 160,165 160,210" stroke="#3b82f6" stroke-width="2.5"/>
<path class="fe" d="M330,121 C330,165 160,165 160,210" stroke="#3b82f6" stroke-width="3" marker-end="url(#mc)" style="animation-delay:.2s"/>

<path class="et" d="M120,121 C120,175 400,175 400,210" stroke="#4f46e5" stroke-width="2.5"/>
<path class="fe" d="M120,121 C120,175 400,175 400,210" stroke="#4f46e5" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.4s"/>

<path class="et" d="M750,121 C750,165 940,165 940,210" stroke="#eab308" stroke-width="2.5"/>
<path class="fe" d="M750,121 C750,165 940,165 940,210" stroke="#eab308" stroke-width="3" marker-end="url(#my)" style="animation-delay:.6s"/>

<path class="et" d="M1170,121 C1170,165 640,165 640,210" stroke="#8b5cf6" stroke-width="2.5"/>
<path class="fe" d="M1170,121 C1170,165 640,165 640,210" stroke="#8b5cf6" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.8s"/>

<!-- Row 2 internal -->
<path class="et" d="M250,243 L310,243" stroke="#7c3aed" stroke-width="2.5"/>
<path class="fe" d="M250,243 L310,243" stroke="#7c3aed" stroke-width="3" marker-end="url(#mp)"/>

<path class="et" d="M490,243 L550,243" stroke="#f97316" stroke-width="2.5"/>
<path class="fe" d="M490,243 L550,243" stroke="#f97316" stroke-width="3" marker-end="url(#mo)" style="animation-delay:.2s"/>

<path class="et" d="M400,276 L400,310" stroke="#8b5cf6" stroke-width="2.5"/>
<path class="fe" d="M400,276 L400,310" stroke="#8b5cf6" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.4s"/>

<path class="et" d="M640,276 L640,310" stroke="#14b8a6" stroke-width="2.5"/>
<path class="fe" d="M640,276 L640,310" stroke="#14b8a6" stroke-width="3" marker-end="url(#mc)" style="animation-delay:.6s"/>

<!-- Row 2 → Row 3 -->
<path class="et" d="M160,276 C160,360 120,360 120,440" stroke="#6366f1" stroke-width="2.5"/>
<path class="fe" d="M160,276 C160,360 120,360 120,440" stroke="#6366f1" stroke-width="3" marker-end="url(#mi)"/>

<path class="et" d="M400,376 C400,410 330,410 330,440" stroke="#6366f1" stroke-width="2.5"/>
<path class="fe" d="M400,376 C400,410 330,410 330,440" stroke="#6366f1" stroke-width="3" marker-end="url(#mi)" style="animation-delay:.2s"/>

<path class="et" d="M640,376 C640,410 540,410 540,440" stroke="#6366f1" stroke-width="2.5"/>
<path class="fe" d="M640,376 C640,410 540,410 540,440" stroke="#6366f1" stroke-width="3" marker-end="url(#mi)" style="animation-delay:.4s"/>

<path class="et" d="M940,276 C940,360 750,360 750,440" stroke="#a78bfa" stroke-width="2.5"/>
<path class="fe" d="M940,276 C940,360 750,360 750,440" stroke="#a78bfa" stroke-width="3" marker-end="url(#mp)" style="animation-delay:.6s"/>

<path class="et" d="M840,473 L930,473" stroke="#22c55e" stroke-width="2.5"/>
<path class="fe" d="M840,473 L930,473" stroke="#22c55e" stroke-width="3" marker-end="url(#mg)" style="animation-delay:.8s"/>

<path class="et" d="M1110,473 L1180,473" stroke="#22c55e" stroke-width="2.5"/>
<path class="fe" d="M1110,473 L1180,473" stroke="#22c55e" stroke-width="3" marker-end="url(#mg)"/>

<!-- Control API → Autopilot -->
<path class="et" d="M540,121 C540,280 120,280 120,440" stroke="#f97316" stroke-width="2.5"/>
<path class="fe" d="M540,121 C540,280 120,280 120,440" stroke="#f97316" stroke-width="3" marker-end="url(#mo)" style="animation-delay:.3s"/>

<!-- Legend -->
<circle cx="30" cy="565" r="5" fill="#3b82f6"/><text class="lt" x="40" y="569">Telemetry/Images</text>
<circle cx="170" cy="565" r="5" fill="#6366f1"/><text class="lt" x="180" y="569">Agent Calls</text>
<circle cx="290" cy="565" r="5" fill="#f97316"/><text class="lt" x="300" y="569">Drone Control</text>
<circle cx="420" cy="565" r="5" fill="#a78bfa"/><text class="lt" x="430" y="569">RAG/Vector</text>
<circle cx="530" cy="565" r="5" fill="#22c55e"/><text class="lt" x="540" y="569">UI Serving</text>
<circle cx="630" cy="565" r="5" fill="#14b8a6"/><text class="lt" x="640" y="569">Lakebase</text>
</svg>

<!-- How It Works -->
<div id="howto" class="info">
  <div class="hw">
    <div class="hc"><div class="hn">1 - Ingest</div><div class="ht">5 ROVs stream telemetry (depth, IMU, thruster currents) + HD camera frames into Bronze Delta tables via Auto Loader.</div></div>
    <div class="hc"><div class="hn">2 - Feature Engineering</div><div class="ht">Windowed aggregations compute anomaly scores, health labels, and peak metrics in Silver layer.</div></div>
    <div class="hc"><div class="hn">3 - ML Inference</div><div class="ht">Vision model detects corrosion, cracks, marine growth on frames. Isolation forest flags anomalous telemetry.</div></div>
    <div class="hc"><div class="hn">4 - RAG Index</div><div class="ht">PDF manuals chunked and embedded into Vector Search for procedure lookups by agents.</div></div>
    <div class="hc"><div class="hn">5 - AI Agents</div><div class="ht">4 agents (Autopilot, Inspection, Maintenance, Knowledge) use Claude tool-calling to query data and produce structured outputs.</div></div>
    <div class="hc"><div class="hn">6 - Operator UI</div><div class="ht">React SPA served by FastAPI with SSE streaming. Fleet twin, live viewer, mission planner, knowledge assistant.</div></div>
    <div class="hc"><div class="hn">7 - Audit Trail</div><div class="ht">Every agent decision logged to autopilot_decisions. Full traceability for safety compliance.</div></div>
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
  telem:{b:"SOURCE",b_c:"#3b82f6",t:"Drone Telemetry Stream",l:["5 ROV/AUV units","1 Hz sensor rate per drone","Depth, IMU (6-axis), Thruster currents","Internal temps, RSSI, Nav error","Streaming via Auto Loader","Partitioned by drone_id"]},
  camera:{b:"SOURCE",b_c:"#3b82f6",t:"Subsea Camera Frames",l:["4K resolution @ 30fps","Stored in UC Volumes","Frame metadata in Delta","Used by vision ML model","Supports forward + down cameras","Lighting conditions tracked"]},
  ctrl:{b:"CONTROL",b_c:"#f97316",t:"Drone Control API Gateway",l:["REST API for fleet control","plan_route / dispatch / abort","Real-time mission state queries","Waypoint-based navigation","Safety interlocks enforced","Accessed by Autopilot Agent"]},
  manuals:{b:"DOCUMENTS",b_c:"#eab308",t:"PDF Manuals & Procedures",l:["OEM drone/thruster manuals","Company inspection procedures","Asset integrity standards","Stored in /Volumes/subsea/manuals/","Chunked into Vector Search index","800-token chunks, 150 overlap"]},
  assets:{b:"REGISTRY",b_c:"#14b8a6",t:"Subsea Asset Registry",l:["Risers, moorings, manifolds","Flowlines, FPSO hulls","15 assets across 5 types","Integrity classification A/B/C","Linked to inspection records","Gulf Location, Block 42"]},
  hist:{b:"HISTORY",b_c:"#8b5cf6",t:"Historical Inspection Reports",l:["Past mission defect records","Severity trends over time","Used for baseline comparison","Feeds Gold layer analytics","Links to manual references","Training data for ML models"]},
  bronze:{b:"BRONZE",b_c:"#4f46e5",t:"Bronze Delta Tables (Unity Catalog)",l:["telemetry_raw: per-second data","inspection_frames: per-image records","Raw, append-only, immutable","Partitioned by drone_id / mission_id","Change Data Feed enabled","Source for feature pipelines"]},
  silver:{b:"SILVER",b_c:"#7c3aed",t:"Silver Feature Tables (Unity Catalog)",l:["telemetry_features: windowed aggs","5-min sliding windows","anomaly_score (isolation forest)","health_label: normal/warning/critical","Peak currents, max temps","Comms loss fraction"]},
  gold:{b:"GOLD",b_c:"#f97316",t:"Gold Analytics Tables (Unity Catalog)",l:["inspections: mission records","autopilot_decisions: audit trail","drone_status: live fleet state","drone_limits: safety envelopes","Queryable by all agents","Powers operator dashboards"]},
  vs:{b:"VECTOR",b_c:"#a78bfa",t:"Vector Search Index (Unity Catalog)",l:["subsea.manuals.chunk_index","Delta-sync with managed embeddings","databricks-bge-large-en model","doc_name, section, chunk_text","Top-k similarity search","Used by Inspection + Knowledge agents"]},
  lb:{b:"LAKEBASE",b_c:"#14b8a6",t:"Lakebase PostgreSQL (Unity Catalog)",l:["Operational state store","Real-time alert tracking","Chat session persistence","Low-latency OLTP queries","Auto-scaling PostgreSQL 16","Resource-bound via app.yaml"]},
  ml:{b:"ML",b_c:"#8b5cf6",t:"ML Model Serving",l:["Vision model: defect classification","Anomaly detection: isolation forest","Served via Model Serving endpoints","Batch + real-time inference","SHAP explanations available","MLflow tracked + versioned"]},
  autopilot:{b:"AGENT",b_c:"#6366f1",t:"Autopilot Agent",l:["Plans + validates + dispatches missions","6 tools: list_drones, plan_route, etc.","Safety rules: battery, depth, duration","Risk-weighted drone selection","Function-calling loop (max 10 iter)","Audit trail in autopilot_decisions"]},
  inspect:{b:"AGENT",b_c:"#6366f1",t:"Inspection Agent",l:["Analyzes frames + telemetry + manuals","5 tools: get_frames, query_manuals, etc.","Groups defects by asset_part + type","Conservative: never invents references","Structured report_json output","Writes back to inspections table"]},
  maint:{b:"AGENT",b_c:"#6366f1",t:"Maintenance Advisor Agent",l:["Condition-based maintenance planning","Fleet-wide health assessment","Risk-weighted prioritization","OEM interval lookup via RAG","Generates work order schedule","Categories: battery, thruster, sensor"]},
  knowl:{b:"AGENT",b_c:"#6366f1",t:"Knowledge Assistant Agent",l:["Operator Q&A via RAG","Searches manuals + procedures","Cites sources with confidence","Fleet status + inspection history","Follow-up suggestions","Safety disclaimers on critical Qs"]},
  ui:{b:"UI",b_c:"#22c55e",t:"Operator Dashboard",l:["React SPA + Vite","7 pages: Command, Fleet Twin, etc.","Dark theme (#0B0F1A)","SSE streaming for real-time","SVG digital twin per drone","CV defect annotations on frames"]},
  api:{b:"API",b_c:"#22c55e",t:"FastAPI SSE Backend",l:["uvicorn on port 8000","POST endpoints for each agent","Server-Sent Events streaming","status + final event pattern","Serves React static build","Databricks App deployment"]},
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

export default function DataFlowPage() {
  const iframeHtml = '<iframe srcdoc="' + FLOW_HTML.replace(/"/g, '&quot;') + '" style="width:100%;height:760px;border:none;border-radius:8px;" />';
  return (
    <div>
      <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>
        Data Flow Architecture
      </h2>
      <div dangerouslySetInnerHTML={{ __html: iframeHtml }} />
    </div>
  );
}
