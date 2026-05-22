import { useState } from 'react';

/* ================================================================
   Production Optimizer — Data & AI Flow Diagram
   Matches the REAL Databricks architecture:
   Sources → SDP Pipeline (Medallion) → MLflow + Physics → Lakebase → App
   ================================================================ */

const W = 1120;
const H = 560;

const SRC_Y = 55;
const BRONZE_Y = 155;
const SILVER_Y = 250;
const GOLD_Y = 345;
const SERVE_Y = 460;

interface Node {
  id: string; label: string; x: number; y: number;
  w: number; h: number; color: string; icon: string; detail: string;
}

interface Edge {
  from: string; to: string; color: string; dashed?: boolean;
}

const nodes: Node[] = [
  // --- Sources ---
  { id: 'scada', label: 'SCADA / RTU', x: 60, y: SRC_Y, w: 120, h: 38, color: '#3b82f6', icon: '📡',
    detail: 'Real-time well & facility telemetry — pressures, temperatures, flow rates, valve positions. OPC-UA / Modbus TCP polling.' },
  { id: 'iot', label: 'IoT Sensors', x: 200, y: SRC_Y, w: 120, h: 38, color: '#06b6d4', icon: '🌡️',
    detail: 'Downhole gauges, fiber-optic DTS/DAS, CO₂ analyzers, vibration sensors. MQTT → Kafka ingestion.' },
  { id: 'co2meter', label: 'CO₂ Metering', x: 340, y: SRC_Y, w: 130, h: 38, color: '#00d4aa', icon: '⚗️',
    detail: 'Coriolis & ultrasonic meters on injection/production headers. Tracks purchased vs recycled CO₂ for carbon accounting.' },
  { id: 'market', label: 'Market / Pricing', x: 490, y: SRC_Y, w: 130, h: 38, color: '#a855f7', icon: '📈',
    detail: 'WTI/Henry Hub spot prices ($72/bbl, $3.20/Mcf), CO₂ contract rates ($1.05/Mcf), 45Q credit valuations. REST API every 15 min.' },
  { id: 'lab', label: 'Lab / PVT', x: 640, y: SRC_Y, w: 110, h: 38, color: '#f59e0b', icon: '🧪',
    detail: 'PVT studies, core analysis, relative permeability, CO₂-oil MMP tests. Structured CSVs to Unity Catalog volumes.' },
  { id: 'hist', label: 'Production History', x: 770, y: SRC_Y, w: 150, h: 38, color: '#ef4444', icon: '📊',
    detail: '760 monthly production records across 16 producer wells. Oil, gas, water, pressures, CO₂ concentration, GOR, water cut.' },

  // --- Bronze (SDP Pipeline) ---
  { id: 'bronze_wells', label: 'bronze_wells', x: 100, y: BRONZE_Y, w: 140, h: 38, color: '#cd7f32', icon: '🥉',
    detail: '20 wells (16 producers, 4 injectors) — Delaware Basin Wolfcamp. Real rates, pressures, compositions. Delta table with CDF enabled. Loaded via SDP pipeline.' },
  { id: 'bronze_patterns', label: 'bronze_patterns', x: 280, y: BRONZE_Y, w: 160, h: 38, color: '#cd7f32', icon: '🥉',
    detail: '4 CO₂-EOR injection patterns (Apache, Bravo, Charlie, Delta). 5-spot and inverted 5-spot. WAG cycles, pressure targets, breakthrough estimates.' },
  { id: 'bronze_market', label: 'bronze.market', x: 480, y: BRONZE_Y, w: 140, h: 38, color: '#cd7f32', icon: '🥉',
    detail: 'Commodity prices, CO₂ contracts, transport tariffs. WTI $72/bbl, HH $3.20/Mcf, CO₂ $1.05/Mcf.' },
  { id: 'bronze_prod', label: 'bronze.production', x: 660, y: BRONZE_Y, w: 160, h: 38, color: '#cd7f32', icon: '🥉',
    detail: 'Historical production records, well test data, lab results. 760 rows partitioned by well_id.' },
  { id: 'sdp', label: 'SDP Pipeline', x: 870, y: BRONZE_Y, w: 140, h: 38, color: '#f97316', icon: '🔄',
    detail: 'Lakeflow Spark Declarative Pipeline (serverless). Materialized views with quality expectations: positive oil rate, valid water cut. Refreshes Bronze → Silver → Gold.' },

  // --- Silver (SDP Pipeline) ---
  { id: 'silver_history', label: 'silver_production_history', x: 60, y: SILVER_Y, w: 210, h: 38, color: '#c0c0c0', icon: '🥈',
    detail: '760 quality-checked monthly records. Enriched with well type, pattern, pad, reservoir zone. Partitioned by well_id. Expectations: oil_rate ≥ 0, 0 ≤ water_cut ≤ 1.' },
  { id: 'silver_econ', label: 'silver_economics', x: 310, y: SILVER_Y, w: 170, h: 38, color: '#c0c0c0', icon: '🥈',
    detail: '16 well-level economics: oil revenue, gas revenue, CO₂ cost allocation, LOE ($18/BOE), transport ($4.50/bbl), netback. Computed from current rates × pricing.' },
  { id: 'silver_carbon', label: 'silver.carbon', x: 520, y: SILVER_Y, w: 150, h: 38, color: '#c0c0c0', icon: '🥈',
    detail: 'CO₂ mass balance — purchased, injected, recycled, stored. MRV-ready per EPA Subpart RR. Net storage: 185 tCO₂/d.' },

  // --- Gold: MLflow + Physics ---
  { id: 'mlflow', label: 'MLflow Model', x: 60, y: GOLD_Y, w: 150, h: 38, color: '#00d4aa', icon: '🧠',
    detail: 'Arps Decline Curve PyFunc registered in Unity Catalog: oil_pump_monitor_catalog.production_optimizer.decline_curve_model. Scipy curve_fit optimization. Predicts rate & cumulative for any well at any future month.' },
  { id: 'gold_decline', label: 'gold_decline_curves', x: 240, y: GOLD_Y, w: 180, h: 38, color: '#ffd700', icon: '🥇',
    detail: '16 fitted decline curves: qi, Di, b-factor, R², EUR, remaining reserves, health score, performance gap, water cut/CO₂/pressure trends. Written by MLflow notebook with scipy fits.' },
  { id: 'gold_recs', label: 'gold_recommendations', x: 460, y: GOLD_Y, w: 190, h: 38, color: '#ffd700', icon: '🥇',
    detail: 'Physics-driven optimization actions: choke optimization, water shutoff, CO₂ injection adjustments. Each with $ impact, physics rationale, and risk assessment.' },
  { id: 'gold_econ', label: 'gold_field_economics', x: 690, y: GOLD_Y, w: 180, h: 38, color: '#ffd700', icon: '🥇',
    detail: 'Aggregated field economics: $260K/d revenue, $32K/d opex, $10K/d CO₂ cost, $45/boe netback, $38/bbl breakeven, $5K/d carbon credits.' },
  { id: 'lakebase', label: 'Lakebase (Postgres)', x: 910, y: GOLD_Y, w: 170, h: 38, color: '#06b6d4', icon: '🐘',
    detail: 'Managed PostgreSQL for mutable operational state: well_state (real-time SCADA), recommendations (status tracking: pending/accepted/rejected), shift_handover (operator logs). OAuth-authenticated.' },

  // --- Serving ---
  { id: 'serve_field', label: 'Field Overview', x: 60, y: SERVE_Y, w: 130, h: 36, color: '#3b82f6', icon: '🗺️',
    detail: 'Geospatial map — 20 wells, 4 facilities, 6 pipelines color-coded by status. Canvas renderer with pan/zoom and layer toggles.' },
  { id: 'serve_twin', label: 'Digital Twin', x: 220, y: SERVE_Y, w: 130, h: 36, color: '#06b6d4', icon: '🏭',
    detail: 'P&ID schematic — interactive SVG with live equipment status, flow readouts, health indicators. Clickable wells and facilities.' },
  { id: 'serve_actions', label: 'Actions', x: 380, y: SERVE_Y, w: 110, h: 36, color: '#00d4aa', icon: '⚡',
    detail: 'Agent-generated recommendations from gold_recommendations. Ranked by $ impact. Physics rationale expandable. Feeds into Scenario tab.' },
  { id: 'serve_deepdive', label: 'Deep Dive', x: 520, y: SERVE_Y, w: 120, h: 36, color: '#f59e0b', icon: '🔬',
    detail: 'Full well analytics from gold_decline_curves + silver_production_history. Oil/gas/water/pressure/CO₂ charts, health scores, Arps parameters.' },
  { id: 'serve_scenario', label: 'Scenario', x: 670, y: SERVE_Y, w: 120, h: 36, color: '#a855f7', icon: '🎛️',
    detail: 'What-if simulator. Pick a recommendation → auto-run Darcy flow + material balance → see per-well production & economic impact. Tunable sliders.' },
  { id: 'serve_app', label: 'Databricks App', x: 820, y: SERVE_Y, w: 140, h: 36, color: '#8b5cf6', icon: '🔌',
    detail: 'Express.js + React deployed as Databricks App. OAuth via SP client credentials. Queries SQL Warehouse for Delta tables, Lakebase for operational state.' },
];

const edges: Edge[] = [
  // Sources → Bronze
  { from: 'scada', to: 'bronze_wells', color: '#3b82f6' },
  { from: 'iot', to: 'bronze_wells', color: '#06b6d4' },
  { from: 'co2meter', to: 'bronze_patterns', color: '#00d4aa' },
  { from: 'market', to: 'bronze_market', color: '#a855f7' },
  { from: 'lab', to: 'bronze_prod', color: '#f59e0b' },
  { from: 'hist', to: 'bronze_prod', color: '#ef4444' },

  // SDP Pipeline orchestrates Bronze → Silver
  { from: 'sdp', to: 'bronze_wells', color: '#f97316', dashed: true },
  { from: 'sdp', to: 'bronze_patterns', color: '#f97316', dashed: true },

  // Bronze → Silver
  { from: 'bronze_wells', to: 'silver_history', color: '#cd7f32' },
  { from: 'bronze_wells', to: 'silver_econ', color: '#cd7f32' },
  { from: 'bronze_patterns', to: 'silver_history', color: '#cd7f32' },
  { from: 'bronze_prod', to: 'silver_history', color: '#cd7f32' },
  { from: 'bronze_market', to: 'silver_econ', color: '#cd7f32' },
  { from: 'bronze_patterns', to: 'silver_carbon', color: '#cd7f32' },

  // Silver → Gold (MLflow + aggregation)
  { from: 'silver_history', to: 'mlflow', color: '#c0c0c0' },
  { from: 'mlflow', to: 'gold_decline', color: '#00d4aa', dashed: true },
  { from: 'mlflow', to: 'gold_recs', color: '#00d4aa', dashed: true },
  { from: 'silver_econ', to: 'gold_econ', color: '#c0c0c0' },
  { from: 'silver_carbon', to: 'gold_econ', color: '#c0c0c0' },

  // Gold → Lakebase (operational state sync)
  { from: 'gold_recs', to: 'lakebase', color: '#ffd700', dashed: true },

  // Gold + Lakebase → Serving
  { from: 'gold_decline', to: 'serve_deepdive', color: '#ffd700' },
  { from: 'gold_decline', to: 'serve_actions', color: '#ffd700' },
  { from: 'gold_recs', to: 'serve_actions', color: '#ffd700' },
  { from: 'gold_recs', to: 'serve_scenario', color: '#ffd700' },
  { from: 'gold_econ', to: 'serve_scenario', color: '#ffd700' },
  { from: 'lakebase', to: 'serve_twin', color: '#06b6d4' },
  { from: 'lakebase', to: 'serve_field', color: '#06b6d4' },
  { from: 'bronze_wells', to: 'serve_field', color: '#cd7f32' },
  { from: 'gold_decline', to: 'serve_app', color: '#ffd700' },
  { from: 'lakebase', to: 'serve_app', color: '#06b6d4' },
];

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

export default function DataAIFlowTab() {
  const [selected, setSelected] = useState<Node | null>(null);

  return (
    <div className="flow-tab-layout">
      <div className="flow-svg-container">
        <svg viewBox={`0 0 ${W} ${H}`} className="flow-svg" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <style>{`
              .flow-edge { fill: none; stroke-width: 1.2; opacity: 0.3; }
              .flow-edge-anim { fill: none; stroke-width: 1.6; stroke-dasharray: 6 4; animation: fd 1.8s linear infinite; }
              .flow-edge-dashed { stroke-dasharray: 4 3; }
              @keyframes fd { to { stroke-dashoffset: -20; } }
            `}</style>
          </defs>

          {/* Row Labels */}
          <text x="14" y={SRC_Y - 8} className="flow-row-label">SOURCES</text>
          <text x="14" y={BRONZE_Y - 8} className="flow-row-label">BRONZE · SDP PIPELINE</text>
          <text x="14" y={SILVER_Y - 8} className="flow-row-label">SILVER</text>
          <text x="14" y={GOLD_Y - 8} className="flow-row-label">GOLD · MLFLOW · LAKEBASE</text>
          <text x="14" y={SERVE_Y - 8} className="flow-row-label">SERVING · DATABRICKS APP</text>

          {/* Unity Catalog governance box */}
          <rect x="30" y={BRONZE_Y - 20} width={W - 60} height={GOLD_Y + 56 - BRONZE_Y + 20}
            rx="8" fill="none" stroke="#f97316" strokeWidth="1.5" strokeDasharray="6 4" opacity="0.3" />
          <text x={W - 30} y={BRONZE_Y - 4} fill="#f97316" fontSize="9" fontWeight="600"
            opacity="0.5" textAnchor="end" style={{ fontFamily: 'monospace' }}>Unity Catalog</text>

          {/* Edges (static) */}
          {edges.map((e, i) => (
            <path key={`bg-${i}`} d={getEdgePath(e)}
              className={`flow-edge ${e.dashed ? 'flow-edge-dashed' : ''}`} stroke={e.color} />
          ))}
          {/* Edges (animated) */}
          {edges.map((e, i) => (
            <path key={`fg-${i}`} d={getEdgePath(e)} className="flow-edge-anim" stroke={e.color} opacity="0.65" />
          ))}

          {/* Nodes */}
          {nodes.map((n) => {
            const isSel = selected?.id === n.id;
            return (
              <g key={n.id} onClick={() => setSelected(isSel ? null : n)} style={{ cursor: 'pointer' }}>
                <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6"
                  fill={isSel ? n.color : '#161b22'} stroke={n.color}
                  strokeWidth={isSel ? 2 : 1.2} opacity={isSel ? 1 : 0.9} />
                <text x={n.x + 8} y={n.y + n.h / 2 + 1}
                  fill={isSel ? '#0f1117' : '#e6edf3'} fontSize="10.5" fontWeight="500"
                  dominantBaseline="middle"
                  style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}>
                  {n.icon} {n.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Detail Panel */}
      <div className="flow-detail-panel">
        {selected ? (
          <div className="flow-detail-card">
            <div className="flow-detail-header">
              <span className="flow-detail-icon">{selected.icon}</span>
              <span className="flow-detail-title">{selected.label}</span>
              <span className="flow-detail-badge"
                style={{ background: selected.color + '22', color: selected.color, borderColor: selected.color + '44' }}>
                {selected.id === 'sdp' ? 'SDP Pipeline' :
                 selected.id === 'mlflow' ? 'MLflow Model' :
                 selected.id === 'lakebase' ? 'Lakebase' :
                 selected.y === SRC_Y ? 'Source' :
                 selected.y === BRONZE_Y ? 'Bronze' :
                 selected.y === SILVER_Y ? 'Silver' :
                 selected.id.startsWith('gold') ? 'Gold' : 'Serving'}
              </span>
            </div>
            <div className="flow-detail-body">{selected.detail}</div>
          </div>
        ) : (
          <div className="flow-how-it-works">
            <div className="flow-how-header">How It Works — All Real, All Databricks</div>
            <div className="flow-how-cards">
              <HowCard icon="📡" title="Ingest" color="#3b82f6"
                text="SCADA, IoT, CO₂ meters, market feeds stream into Bronze Delta tables. 20 wells, 4 patterns, 760 production records in Unity Catalog." />
              <HowCard icon="🔄" title="SDP Pipeline" color="#f97316"
                text="Lakeflow Spark Declarative Pipeline refines Bronze → Silver with quality expectations (oil_rate ≥ 0, valid water_cut). Serverless compute." />
              <HowCard icon="🧠" title="MLflow" color="#00d4aa"
                text="Scipy curve_fit optimizes Arps decline parameters per well. PyFunc model registered in Unity Catalog. Writes gold_decline_curves with R², EUR, health scores." />
              <HowCard icon="🐘" title="Lakebase" color="#06b6d4"
                text="Managed PostgreSQL for mutable state: well operations, recommendation tracking (pending → accepted → implemented), shift handover logs." />
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
