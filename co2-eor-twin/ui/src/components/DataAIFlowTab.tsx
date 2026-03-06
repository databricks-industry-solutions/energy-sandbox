import { useState } from 'react';

/* ================================================================
   CO₂-EOR Digital Twin — Data & AI Flow Diagram
   3-row architecture: Sources → Platform (Medallion) → AI Agents → Serving
   Animated SVG edges with CSS dash animation.
   Detail cards below the diagram.
   ================================================================ */

/* ------------------------------------------------------------------ */
/*  Layout constants                                                   */
/* ------------------------------------------------------------------ */

const W = 1120;
const H = 540;

// Row Y positions
const SRC_Y = 60;
const BRONZE_Y = 170;
const SILVER_Y = 270;
const GOLD_Y = 370;
const AGENT_Y = 370;
const SERVE_Y = 470;

// Column regions
const DATA_X_START = 40;
const DATA_X_END = 620;
const AI_X_START = 660;
const AI_X_END = 1080;

/* ------------------------------------------------------------------ */
/*  Node definitions                                                   */
/* ------------------------------------------------------------------ */

interface Node {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  icon: string;
  detail: string;
}

interface Edge {
  from: string;
  to: string;
  color: string;
  dashed?: boolean;
}

const nodes: Node[] = [
  // --- Sources ---
  { id: 'scada', label: 'SCADA / RTU', x: 60, y: SRC_Y, w: 110, h: 38, color: '#3b82f6', icon: '📡', detail: 'Real-time well & facility telemetry — pressures, temperatures, flow rates, valve positions. 1-second polling via OPC-UA / Modbus TCP.' },
  { id: 'iot', label: 'IoT Sensors', x: 190, y: SRC_Y, w: 110, h: 38, color: '#06b6d4', icon: '🌡️', detail: 'Distributed fiber-optic DTS/DAS, downhole gauges, CO₂ concentration analyzers, soil-gas detectors. Streams via MQTT → Kafka.' },
  { id: 'co2meter', label: 'CO₂ Metering', x: 320, y: SRC_Y, w: 120, h: 38, color: '#00d4aa', icon: '⚗️', detail: 'Coriolis & ultrasonic flow meters on injection/production headers. Tracks purchased vs recycled CO₂ volumes for carbon accounting.' },
  { id: 'lab', label: 'Lab / PVT', x: 460, y: SRC_Y, w: 100, h: 38, color: '#f59e0b', icon: '🧪', detail: 'PVT studies, core analysis, water chemistry, CO₂-oil MMP tests. Uploaded as structured CSVs to Unity Catalog volumes.' },
  { id: 'market', label: 'Market Feeds', x: 580, y: SRC_Y, w: 110, h: 38, color: '#a855f7', icon: '📈', detail: 'WTI/Henry Hub spot & futures, CO₂ contract prices, 45Q credit valuations, carbon registry data. REST API ingestion every 15 min.' },
  { id: 'geo', label: 'Seismic / DAS', x: 710, y: SRC_Y, w: 120, h: 38, color: '#ef4444', icon: '🌍', detail: '4D seismic surveys, microseismic monitoring, DAS fiber acoustic sensing for CO₂ plume tracking and caprock integrity.' },
  { id: 'fleet', label: 'Fleet GPS', x: 850, y: SRC_Y, w: 100, h: 38, color: '#8b5cf6', icon: '🚛', detail: 'Real-time GPS tracking for trucks, rigs, wireline, coiled tubing units. Geofence alerts and ETA calculations.' },
  { id: 'permits', label: 'EPA / Permits', x: 970, y: SRC_Y, w: 110, h: 38, color: '#ec4899', icon: '📋', detail: 'EPA Class VI well permits, UIC monitoring reports, state regulatory filings, MRV (Monitoring, Reporting & Verification) data.' },

  // --- Bronze ---
  { id: 'bronze_ops', label: 'bronze.ops_raw', x: 100, y: BRONZE_Y, w: 150, h: 38, color: '#cd7f32', icon: '🥉', detail: 'Raw operational data — SCADA snapshots, IoT events, meter readings. Append-only Delta tables with schema evolution. Autoloader ingestion.' },
  { id: 'bronze_co2', label: 'bronze.co2_raw', x: 280, y: BRONZE_Y, w: 150, h: 38, color: '#cd7f32', icon: '🥉', detail: 'Raw CO₂ metering, injection volumes, recycled gas compositions. Immutable landing zone for carbon audit trail.' },
  { id: 'bronze_commercial', label: 'bronze.commercial', x: 460, y: BRONZE_Y, w: 160, h: 38, color: '#cd7f32', icon: '🥉', detail: 'Market prices, contract terms, 45Q credit data, transport tariffs. Daily batch + 15-min streaming for spot prices.' },
  { id: 'bronze_env', label: 'bronze.environ', x: 700, y: BRONZE_Y, w: 150, h: 38, color: '#cd7f32', icon: '🥉', detail: 'Seismic events, soil-gas readings, groundwater samples, flare metering, methane leak surveys. Raw sensor + lab data.' },
  { id: 'bronze_fleet', label: 'bronze.fleet', x: 880, y: BRONZE_Y, w: 140, h: 38, color: '#cd7f32', icon: '🥉', detail: 'Fleet GPS pings, maintenance logs, dispatch records, regulatory filings. 10-second position updates.' },

  // --- Silver ---
  { id: 'silver_wells', label: 'silver.wells', x: 80, y: SILVER_Y, w: 130, h: 38, color: '#c0c0c0', icon: '🥈', detail: 'Cleaned well-level production/injection allocations. Back-allocated rates, normalized pressures, validated test data. Hourly grain.' },
  { id: 'silver_patterns', label: 'silver.patterns', x: 230, y: SILVER_Y, w: 140, h: 38, color: '#c0c0c0', icon: '🥈', detail: 'Injection pattern aggregates — WAG cycle tracking, cumulative CO₂ slugs, pattern-level VRR, breakthrough indicators.' },
  { id: 'silver_facilities', label: 'silver.facilities', x: 390, y: SILVER_Y, w: 150, h: 38, color: '#c0c0c0', icon: '🥈', detail: 'Facility-level throughput, utilization by stream (oil/gas/water/CO₂), compression efficiency, flare volumes.' },
  { id: 'silver_carbon', label: 'silver.carbon', x: 560, y: SILVER_Y, w: 150, h: 38, color: '#c0c0c0', icon: '🥈', detail: 'CO₂ mass balance — purchased, injected, recycled, stored, emitted. MRV-ready calculations per EPA Subpart RR methodology.' },
  { id: 'silver_econ', label: 'silver.economics', x: 730, y: SILVER_Y, w: 150, h: 38, color: '#c0c0c0', icon: '🥈', detail: 'Well-level netback, LOE allocation, CO₂ cost per BOE, transport tariff application, 45Q credit accruals.' },
  { id: 'silver_env', label: 'silver.environ', x: 900, y: SILVER_Y, w: 140, h: 38, color: '#c0c0c0', icon: '🥈', detail: 'Processed seismic attributes, interpolated pressure maps, soil-gas anomaly detection, compliance scoring.' },

  // --- Gold / KPI ---
  { id: 'gold_twin', label: 'gold.digital_twin', x: 80, y: GOLD_Y, w: 160, h: 38, color: '#ffd700', icon: '🥇', detail: 'Unified digital twin state — real-time snapshot of all wells, patterns, facilities, pipelines. Materialized view refreshed every 30s.' },
  { id: 'gold_kpi', label: 'gold.kpi_daily', x: 260, y: GOLD_Y, w: 140, h: 38, color: '#ffd700', icon: '🥇', detail: 'Production, environmental & economic KPIs aggregated daily. Trend analysis, forecasts, anomaly flags. Powers the KPI ticker.' },
  { id: 'gold_carbon', label: 'gold.carbon_ledger', x: 420, y: GOLD_Y, w: 160, h: 38, color: '#ffd700', icon: '🥇', detail: 'Auditable CO₂ storage ledger for 45Q credit claims. Cumulative net storage, verification status, credit issuance tracking.' },

  // --- AI Agents ---
  { id: 'agent_monitor', label: 'Monitoring Agent', x: 660, y: AGENT_Y, w: 140, h: 38, color: '#3b82f6', icon: '👁️', detail: 'Watches real-time telemetry for anomalies — pressure excursions, flow deviations, equipment alarms. Triggers alerts and escalates to orchestrator.' },
  { id: 'agent_optimize', label: 'Optimization Agent', x: 820, y: AGENT_Y, w: 150, h: 38, color: '#00d4aa', icon: '⚡', detail: 'Proposes choke adjustments, WAG cycle changes, injection redistribution. Runs reservoir simulation proxies. Supervised mode requires human approval.' },
  { id: 'agent_maint', label: 'Maintenance Agent', x: 660, y: AGENT_Y + 55, w: 145, h: 38, color: '#f59e0b', icon: '🔧', detail: 'Predictive maintenance scheduling — ESP health, compressor vibration, pipeline corrosion. Dispatches fleet assets and creates work orders.' },
  { id: 'agent_commercial', label: 'Commercial Agent', x: 825, y: AGENT_Y + 55, w: 150, h: 38, color: '#a855f7', icon: '💰', detail: 'Monitors commodity prices, optimizes CO₂ purchase vs recycle decisions, tracks 45Q credit eligibility, flags contract take-or-pay risks.' },
  { id: 'agent_orchestrator', label: 'Orchestrator', x: 740, y: AGENT_Y + 115, w: 150, h: 38, color: '#ef4444', icon: '🎯', detail: 'Meta-agent coordinating all sub-agents. Resolves conflicts (e.g. production vs environmental), enforces guardrails, manages autonomy levels, routes approvals.' },

  // --- Serving ---
  { id: 'serve_api', label: 'REST API', x: 100, y: SERVE_Y, w: 110, h: 36, color: '#06b6d4', icon: '🔌', detail: 'Express.js API serving twin state, analytics, GeoJSON, agent queries. RBAC-protected endpoints. Powers the control room UI.' },
  { id: 'serve_ui', label: 'Control Room UI', x: 240, y: SERVE_Y, w: 140, h: 36, color: '#00d4aa', icon: '🖥️', detail: 'React dashboard — field map, KPI ticker, agent panel, shift log. Dark industrial theme. Real-time updates via polling.' },
  { id: 'serve_alerts', label: 'Alert System', x: 410, y: SERVE_Y, w: 120, h: 36, color: '#ef4444', icon: '🚨', detail: 'Multi-channel alerting — UI ticker, email, SMS, Slack. Severity-based routing. Acknowledgment tracking in shift log.' },
  { id: 'serve_shift', label: 'Shift Handoff', x: 560, y: SERVE_Y, w: 130, h: 36, color: '#f59e0b', icon: '📝', detail: 'Digital shift log with agent action audit trail. Structured handoff reports. Integrates with crew scheduling systems.' },
  { id: 'serve_report', label: 'Regulatory Reports', x: 720, y: SERVE_Y, w: 155, h: 36, color: '#ec4899', icon: '📊', detail: 'Automated EPA Subpart RR reports, state production filings, 45Q documentation. Gold-layer data ensures auditability.' },
  { id: 'serve_dash', label: 'AI/BI Dashboard', x: 905, y: SERVE_Y, w: 145, h: 36, color: '#8b5cf6', icon: '📉', detail: 'Databricks AI/BI dashboards for management — executive summaries, field comparisons, economic scenario modeling.' },
];

const edges: Edge[] = [
  // Sources → Bronze
  { from: 'scada', to: 'bronze_ops', color: '#3b82f6' },
  { from: 'iot', to: 'bronze_ops', color: '#06b6d4' },
  { from: 'co2meter', to: 'bronze_co2', color: '#00d4aa' },
  { from: 'lab', to: 'bronze_co2', color: '#f59e0b' },
  { from: 'market', to: 'bronze_commercial', color: '#a855f7' },
  { from: 'geo', to: 'bronze_env', color: '#ef4444' },
  { from: 'fleet', to: 'bronze_fleet', color: '#8b5cf6' },
  { from: 'permits', to: 'bronze_env', color: '#ec4899' },

  // Bronze → Silver
  { from: 'bronze_ops', to: 'silver_wells', color: '#cd7f32' },
  { from: 'bronze_ops', to: 'silver_patterns', color: '#cd7f32' },
  { from: 'bronze_ops', to: 'silver_facilities', color: '#cd7f32' },
  { from: 'bronze_co2', to: 'silver_carbon', color: '#cd7f32' },
  { from: 'bronze_co2', to: 'silver_patterns', color: '#cd7f32' },
  { from: 'bronze_commercial', to: 'silver_econ', color: '#cd7f32' },
  { from: 'bronze_env', to: 'silver_env', color: '#cd7f32' },
  { from: 'bronze_fleet', to: 'silver_facilities', color: '#cd7f32' },

  // Silver → Gold
  { from: 'silver_wells', to: 'gold_twin', color: '#c0c0c0' },
  { from: 'silver_patterns', to: 'gold_twin', color: '#c0c0c0' },
  { from: 'silver_facilities', to: 'gold_twin', color: '#c0c0c0' },
  { from: 'silver_wells', to: 'gold_kpi', color: '#c0c0c0' },
  { from: 'silver_carbon', to: 'gold_carbon', color: '#c0c0c0' },
  { from: 'silver_carbon', to: 'gold_kpi', color: '#c0c0c0' },
  { from: 'silver_econ', to: 'gold_kpi', color: '#c0c0c0' },

  // Gold → Agents
  { from: 'gold_twin', to: 'agent_monitor', color: '#ffd700', dashed: true },
  { from: 'gold_twin', to: 'agent_optimize', color: '#ffd700', dashed: true },
  { from: 'gold_kpi', to: 'agent_maint', color: '#ffd700', dashed: true },
  { from: 'gold_kpi', to: 'agent_commercial', color: '#ffd700', dashed: true },
  { from: 'gold_carbon', to: 'agent_commercial', color: '#ffd700', dashed: true },

  // Agent → Orchestrator
  { from: 'agent_monitor', to: 'agent_orchestrator', color: '#3b82f6', dashed: true },
  { from: 'agent_optimize', to: 'agent_orchestrator', color: '#00d4aa', dashed: true },
  { from: 'agent_maint', to: 'agent_orchestrator', color: '#f59e0b', dashed: true },
  { from: 'agent_commercial', to: 'agent_orchestrator', color: '#a855f7', dashed: true },

  // Gold → Serving
  { from: 'gold_twin', to: 'serve_api', color: '#ffd700' },
  { from: 'gold_kpi', to: 'serve_ui', color: '#ffd700' },
  { from: 'gold_kpi', to: 'serve_dash', color: '#ffd700' },
  { from: 'gold_carbon', to: 'serve_report', color: '#ffd700' },

  // Agents → Serving
  { from: 'agent_orchestrator', to: 'serve_alerts', color: '#ef4444', dashed: true },
  { from: 'agent_orchestrator', to: 'serve_shift', color: '#ef4444', dashed: true },
  { from: 'agent_orchestrator', to: 'serve_api', color: '#ef4444', dashed: true },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const nodeMap = new Map(nodes.map((n) => [n.id, n]));

function getEdgePath(e: Edge): string {
  const from = nodeMap.get(e.from);
  const to = nodeMap.get(e.to);
  if (!from || !to) return '';

  const x1 = from.x + from.w / 2;
  const y1 = from.y + from.h;
  const x2 = to.x + to.w / 2;
  const y2 = to.y;

  const midY = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function DataAIFlowTab() {
  const [selected, setSelected] = useState<Node | null>(null);

  return (
    <div className="flow-tab-layout">
      {/* ---------- SVG Diagram ---------- */}
      <div className="flow-svg-container">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="flow-svg"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Animated dash pattern */}
            <style>{`
              .flow-edge {
                fill: none;
                stroke-width: 1.2;
                opacity: 0.35;
              }
              .flow-edge-anim {
                fill: none;
                stroke-width: 1.6;
                stroke-dasharray: 6 4;
                animation: fd 1.8s linear infinite;
              }
              .flow-edge-dashed {
                stroke-dasharray: 4 3;
              }
              @keyframes fd {
                to { stroke-dashoffset: -20; }
              }
            `}</style>
          </defs>

          {/* --- Row Labels --- */}
          <text x="14" y={SRC_Y - 8} className="flow-row-label">SOURCES</text>
          <text x="14" y={BRONZE_Y - 8} className="flow-row-label">BRONZE</text>
          <text x="14" y={SILVER_Y - 8} className="flow-row-label">SILVER</text>
          <text x="14" y={GOLD_Y - 8} className="flow-row-label">GOLD / AI AGENTS</text>
          <text x="14" y={SERVE_Y - 8} className="flow-row-label">SERVING</text>

          {/* --- Unity Catalog Governance Box --- */}
          <rect
            x={DATA_X_START - 10}
            y={BRONZE_Y - 22}
            width={AI_X_END - DATA_X_START + 20}
            height={GOLD_Y + 56 - BRONZE_Y + 22}
            rx="8"
            fill="none"
            stroke="#f97316"
            strokeWidth="1.5"
            strokeDasharray="6 4"
            opacity="0.35"
          />
          <text
            x={AI_X_END + 4}
            y={BRONZE_Y - 4}
            fill="#f97316"
            fontSize="9"
            fontWeight="600"
            opacity="0.6"
            style={{ fontFamily: 'monospace' }}
          >
            Unity
          </text>
          <text
            x={AI_X_END + 4}
            y={BRONZE_Y + 8}
            fill="#f97316"
            fontSize="9"
            fontWeight="600"
            opacity="0.6"
            style={{ fontFamily: 'monospace' }}
          >
            Catalog
          </text>

          {/* --- Edges (static faint track) --- */}
          {edges.map((e, i) => (
            <path
              key={`bg-${i}`}
              d={getEdgePath(e)}
              className={`flow-edge ${e.dashed ? 'flow-edge-dashed' : ''}`}
              stroke={e.color}
            />
          ))}

          {/* --- Edges (animated bright dash) --- */}
          {edges.map((e, i) => (
            <path
              key={`fg-${i}`}
              d={getEdgePath(e)}
              className="flow-edge-anim"
              stroke={e.color}
              opacity="0.7"
            />
          ))}

          {/* --- Nodes --- */}
          {nodes.map((n) => {
            const isSelected = selected?.id === n.id;
            return (
              <g
                key={n.id}
                onClick={() => setSelected(isSelected ? null : n)}
                style={{ cursor: 'pointer' }}
              >
                <rect
                  x={n.x}
                  y={n.y}
                  width={n.w}
                  height={n.h}
                  rx="6"
                  fill={isSelected ? n.color : '#161b22'}
                  stroke={n.color}
                  strokeWidth={isSelected ? 2 : 1.2}
                  opacity={isSelected ? 1 : 0.9}
                />
                <text
                  x={n.x + 8}
                  y={n.y + n.h / 2 + 1}
                  fill={isSelected ? '#0f1117' : '#e6edf3'}
                  fontSize="10.5"
                  fontWeight="500"
                  dominantBaseline="middle"
                  style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}
                >
                  {n.icon} {n.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* ---------- Detail Panel ---------- */}
      <div className="flow-detail-panel">
        {selected ? (
          <div className="flow-detail-card">
            <div className="flow-detail-header">
              <span className="flow-detail-icon">{selected.icon}</span>
              <span className="flow-detail-title">{selected.label}</span>
              <span
                className="flow-detail-badge"
                style={{ background: selected.color + '22', color: selected.color, borderColor: selected.color + '44' }}
              >
                {selected.y === SRC_Y ? 'Source' :
                 selected.y === BRONZE_Y ? 'Bronze' :
                 selected.y === SILVER_Y ? 'Silver' :
                 selected.id.startsWith('gold') ? 'Gold' :
                 selected.id.startsWith('agent') ? 'AI Agent' :
                 'Serving'}
              </span>
            </div>
            <div className="flow-detail-body">{selected.detail}</div>
          </div>
        ) : (
          <div className="flow-how-it-works">
            <div className="flow-how-header">How It Works</div>
            <div className="flow-how-cards">
              <HowCard
                icon="📡"
                title="Ingest"
                text="SCADA, IoT, CO₂ meters, market feeds, and seismic data stream into Bronze Delta tables via Autoloader and Kafka."
                color="#3b82f6"
              />
              <HowCard
                icon="⚙️"
                title="Refine"
                text="DLT pipelines clean, validate, and aggregate data through Silver (well/pattern/facility-level) to Gold (digital twin, KPIs, carbon ledger)."
                color="#c0c0c0"
              />
              <HowCard
                icon="🤖"
                title="Agent AI"
                text="Five specialized agents monitor, optimize, maintain, trade, and orchestrate — reading Gold tables and proposing actions with human-in-the-loop approval."
                color="#00d4aa"
              />
              <HowCard
                icon="🖥️"
                title="Serve"
                text="REST API serves the control room UI, alert system, shift handoffs, regulatory reports, and AI/BI dashboards in real time."
                color="#06b6d4"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HowCard({ icon, title, text, color }: { icon: string; title: string; text: string; color: string }) {
  return (
    <div className="flow-how-card" style={{ borderTopColor: color }}>
      <div className="flow-how-card-icon">{icon}</div>
      <div className="flow-how-card-title">{title}</div>
      <div className="flow-how-card-text">{text}</div>
    </div>
  );
}
