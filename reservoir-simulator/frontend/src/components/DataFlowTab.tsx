import { useState } from 'react'

interface NodeDef {
  id: string; label: string; sub: string
  x: number; y: number; w: number; h: number
  color: string; badge: string
  detail: string[]
}

// ── Data pipeline nodes ───────────────────────────────────────────────────
const PIPELINE: NodeDef[] = [
  {
    id: 'norne', label: 'Norne Field Dataset', sub: 'North Sea benchmark model',
    x: 20, y: 130, w: 175, h: 76,
    color: '#27AE60', badge: 'SOURCE',
    detail: [
      'NORNE_ATW2013.DATA (Eclipse deck)',
      'Grid: 46x112x22 = 113,344 cells',
      'Includes: GRID, PVT, RELPERM, VFP',
      'METRIC units · Start: Nov 1997',
      'Wells: B-2H, D-1H, E-3H, D-2H, C-4H',
    ],
  },
  {
    id: 'simulator', label: 'Res Flow Engine', sub: 'Python simulator.py',
    x: 225, y: 130, w: 180, h: 76,
    color: '#2980B9', badge: 'SIMULATE',
    detail: [
      'Norne-calibrated physics:',
      'P0 = 360 bar · phi = 25% · k = 120 mD',
      'Bubble point: 250 bar (DISGAS)',
      '40 timesteps x 91 days',
      'Post-sim: ops derivation + cost estimation',
    ],
  },
  {
    id: 'ops_engine', label: 'Operations Engine', sub: 'operations.py + costs.py',
    x: 435, y: 130, w: 180, h: 76,
    color: '#E67E22', badge: 'OPS',
    detail: [
      'Derives well activities from sim results:',
      'Drilling, completions, ESP, workovers',
      'Full-cycle cost estimation per activity',
      'SAP material + service pricing lookup',
      'Lifting cost $/BOE per well',
    ],
  },
  {
    id: 'sqlite', label: 'SQLite + Snapshots', sub: '/tmp/reservoir_sim.db',
    x: 645, y: 130, w: 175, h: 76,
    color: '#8E9AAF', badge: 'STORE',
    detail: [
      'Tables: scenarios, simulation_runs,',
      '  economics_results, run_operations,',
      '  run_costs, delta_sharing_log',
      'In-memory: grid snapshots, well series',
      'WAL mode + foreign keys',
    ],
  },
  {
    id: 'unity', label: 'Unity Catalog', sub: 'norne_digital_twin',
    x: 855, y: 130, w: 180, h: 76,
    color: '#F39C12', badge: 'CATALOG',
    detail: [
      'Catalog: norne_digital_twin',
      'Schemas: sap_supply_chain, ops_forecast,',
      '  sim_results',
      'Row-level security + audit logging',
      'Governs all Delta Sharing tables',
    ],
  },
]

// ── SAP / Delta Sharing / App nodes ───────────────────────────────────────
const V2_NODES: NodeDef[] = [
  {
    id: 'sap_bdc', label: 'SAP Business Data Cloud', sub: 'Supply Chain · Pricing · Inventory',
    x: 20, y: 330, w: 195, h: 76,
    color: '#0FAAFF', badge: 'SAP BDC',
    detail: [
      'Material pricing: 18 items (live)',
      'Service contracts: 10 vendors',
      'Equipment inventory: 8 assets',
      'Vendor lead times',
      'Bidirectional via Delta Sharing',
    ],
  },
  {
    id: 'delta_sharing', label: 'Delta Sharing', sub: 'Open protocol · Bidirectional',
    x: 255, y: 330, w: 180, h: 76,
    color: '#8E44AD', badge: 'SHARE',
    detail: [
      'INBOUND: material_pricing, equipment,',
      '  service_contracts, vendor_lead_times',
      'OUTBOUND: production_forecast,',
      '  material_requirements, cost_estimates,',
      '  procurement_triggers',
    ],
  },
  {
    id: 'fastapi', label: 'FastAPI Backend', sub: 'Python 3.11 · uvicorn',
    x: 500, y: 330, w: 180, h: 76,
    color: '#9B59B6', badge: 'API',
    detail: [
      'POST /api/simulate  (+ ops + costs)',
      'GET  /api/operations/{run_id}',
      'GET  /api/costs/{run_id}/lifting',
      'POST /api/compare',
      'GET  /api/delta-sharing/status',
      'GET  /api/sap/materials|services|equipment',
    ],
  },
  {
    id: 'react', label: 'React UI — 9 Tabs', sub: 'TypeScript · Three.js · Recharts',
    x: 500, y: 460, w: 180, h: 76,
    color: '#16A085', badge: 'UI',
    detail: [
      'Scenarios · 3D Reservoir · Well Results',
      'Operations (Gantt) · Cost Analysis',
      'Economics · Compare',
      'Agent · Data & AI Flow',
      'SAP material/service/equipment views',
    ],
  },
  {
    id: 'claude', label: 'Digital Twin Agent', sub: 'Databricks FMAPI · Sonnet 4.5',
    x: 740, y: 330, w: 180, h: 76,
    color: '#8E44AD', badge: 'LLM',
    detail: [
      'Endpoint: databricks-claude-sonnet-4-5',
      'Context: sim + ops + costs + SAP data',
      'Reservoir + operations expertise',
      'Full-cycle cost analysis guidance',
      'Scenario comparison insights',
    ],
  },
  {
    id: 'user', label: 'Reservoir Engineer', sub: 'Operations · Planning · Economics',
    x: 740, y: 460, w: 180, h: 76,
    color: '#2C3E50', badge: 'USER',
    detail: [
      'Runs simulations + views 3D reservoir',
      'Reviews operations timeline (Gantt)',
      'Analyzes SAP-sourced cost estimates',
      'Compares scenarios: NPV + lifting $/BOE',
      'Asks AI for optimization guidance',
    ],
  },
]

interface EdgeDef { from: string; to: string; label: string; color?: string; dashed?: boolean }

const EDGES: EdgeDef[] = [
  { from: 'norne',         to: 'simulator',     label: 'deck data',       color: '#27AE60' },
  { from: 'simulator',     to: 'ops_engine',    label: 'well series',     color: '#2980B9' },
  { from: 'ops_engine',    to: 'sqlite',        label: 'ops + costs',     color: '#E67E22' },
  { from: 'sqlite',        to: 'unity',         label: 'SQL Warehouse',   color: '#8E9AAF' },
  { from: 'sap_bdc',       to: 'delta_sharing', label: 'pricing / inventory', color: '#0FAAFF' },
  { from: 'delta_sharing', to: 'unity',         label: 'inbound tables',  color: '#8E44AD' },
  { from: 'unity',         to: 'delta_sharing', label: 'outbound tables', color: '#F39C12', dashed: true },
  { from: 'delta_sharing', to: 'sap_bdc',       label: 'forecasts / MRP', color: '#F39C12', dashed: true },
  { from: 'sqlite',        to: 'fastapi',       label: 'queries',         color: '#8E9AAF' },
  { from: 'fastapi',       to: 'react',         label: 'REST + WS',      color: '#9B59B6' },
  { from: 'react',         to: 'user',          label: 'browser',         color: '#16A085' },
  { from: 'fastapi',       to: 'claude',        label: 'FMAPI call',     color: '#8E44AD' },
  { from: 'claude',        to: 'fastapi',       label: 'AI response',    color: '#8E44AD', dashed: true },
]

function allNodes() { return [...PIPELINE, ...V2_NODES] }
function nodeById(id: string) { return allNodes().find(n => n.id === id) }
function cx(n: NodeDef) { return n.x + n.w / 2 }
function cy(n: NodeDef) { return n.y + n.h / 2 }

function arrowPath(e: EdgeDef): string {
  const a = nodeById(e.from)!, b = nodeById(e.to)!
  if (!a || !b) return ''
  const ax = cx(a), ay = cy(a), bx = cx(b), by = cy(b)

  // Same row — horizontal
  if (Math.abs(ay - by) < 15) {
    const fromRight = a.x + a.w
    return `M${fromRight},${ay} L${b.x},${by}`
  }

  // sqlite → fastapi (down then left to fastapi top)
  if (e.from === 'sqlite' && e.to === 'fastapi') {
    const sx = cx(a), sy = a.y + a.h, ex = cx(b), ey = b.y
    const mid = (sy + ey) / 2
    return `M${sx},${sy} L${sx},${mid} L${ex},${mid} L${ex},${ey}`
  }

  // delta_sharing → unity (up-right)
  if (e.from === 'delta_sharing' && e.to === 'unity') {
    const sx = cx(a), sy = a.y, ex = cx(b), ey = b.y + b.h
    const mid = (sy + ey) / 2
    return `M${sx},${sy} L${sx},${mid} L${ex},${mid} L${ex},${ey}`
  }

  // unity → delta_sharing (down-left)
  if (e.from === 'unity' && e.to === 'delta_sharing') {
    const sx = cx(a) - 20, sy = a.y + a.h, ex = cx(b) + 20, ey = b.y
    const mid = (sy + ey) / 2
    return `M${sx},${sy} L${sx},${mid} L${ex},${mid} L${ex},${ey}`
  }

  // fastapi → react (straight down)
  if (e.from === 'fastapi' && e.to === 'react') {
    return `M${cx(a)},${a.y + a.h} L${cx(b)},${b.y}`
  }

  // fastapi → claude (horizontal right)
  if (e.from === 'fastapi' && e.to === 'claude') {
    return `M${a.x + a.w},${cy(a)} L${b.x},${cy(b)}`
  }

  // claude → fastapi (horizontal left, offset down)
  if (e.from === 'claude' && e.to === 'fastapi') {
    const sx = b.x + b.w, sy = cy(b) + 12, ex = a.x, ey = cy(a) + 12
    return `M${ex},${ey} L${sx},${sy}`
  }

  // Generic vertical
  if (Math.abs(ax - bx) < 80) {
    return `M${ax},${a.y + a.h} L${bx},${b.y}`
  }

  return `M${ax},${ay} L${bx},${by}`
}

function FlowEdge({ e, idx }: { e: EdgeDef; idx: number }) {
  const d = arrowPath(e)
  const col = e.color ?? '#555'
  const markerId = `arr-${e.from}-${e.to}`
  return (
    <g>
      <defs>
        <marker id={markerId} markerWidth={8} markerHeight={8} refX={6} refY={3} orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill={col} />
        </marker>
      </defs>
      <path d={d} fill="none" stroke={col} strokeWidth={1.5}
        strokeDasharray={e.dashed ? '5 4' : '6 3'} strokeOpacity={0.22} />
      <path d={d} fill="none" stroke={col} strokeWidth={2}
        strokeDasharray="6 3"
        style={{ animation: `flow-dash 1.6s linear ${idx * 0.2}s infinite` }}
        markerEnd={`url(#${markerId})`} />
    </g>
  )
}

function FlowNode({ n, selected, onSelect }: { n: NodeDef; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <g onClick={() => onSelect(n.id)} style={{ cursor: 'pointer' }}>
      <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={8}
        fill="var(--bg-card)"
        stroke={selected ? n.color : 'var(--border)'}
        strokeWidth={selected ? 2 : 1}
        style={{ filter: selected ? `drop-shadow(0 0 8px ${n.color}99)` : 'none', transition: 'all 0.2s' }}
      />
      {/* Badge — top-right, small row */}
      <rect x={n.x + n.w - 66} y={n.y + 6} width={60} height={17} rx={3}
        fill={n.color + '30'} stroke={n.color} strokeWidth={0.8} />
      <text x={n.x + n.w - 36} y={n.y + 18} textAnchor="middle"
        fill={n.color} fontSize={9} fontFamily="monospace" fontWeight={700}>{n.badge}</text>
      {/* Label — below badge, full width */}
      <text x={n.x + 12} y={n.y + 40} fill="var(--text-primary)" fontSize={12.5}
        fontFamily="system-ui,sans-serif" fontWeight={700}>{n.label}</text>
      {/* Sub — bottom row */}
      <text x={n.x + 12} y={n.y + 58} fill="var(--text-muted)" fontSize={10.5}
        fontFamily="system-ui,sans-serif">{n.sub}</text>
    </g>
  )
}

export default function DataFlowTab() {
  const [sel, setSel] = useState<string | null>(null)
  const selNode = sel ? nodeById(sel) : null
  const select = (id: string) => setSel(s => s === id ? null : id)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Stats strip */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {[
          { label: 'Simulation Engine',   val: 'Res Flow (Norne)',         color: 'var(--green)' },
          { label: 'Operations Engine',   val: 'D&C + ESP + Workover',     color: '#E67E22' },
          { label: 'Cost Engine',         val: 'SAP Material + Service',   color: 'var(--amber)' },
          { label: 'Delta Sharing',       val: 'SAP BDC \u2194 Databricks',    color: '#8E44AD' },
          { label: 'Unity Catalog',       val: 'norne_digital_twin',       color: '#F39C12' },
          { label: 'AI Agent',            val: 'claude-sonnet-4-6 (FMAPI)', color: 'var(--blue)' },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding: '8px 14px', flex: 1, minWidth: 140 }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 4 }}>
              {k.label.toUpperCase()}
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: k.color, fontFamily: 'monospace' }}>
              {k.val}
            </div>
          </div>
        ))}
      </div>

      {/* Diagram + detail */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        <div className="card" style={{ flex: 1, overflow: 'hidden', padding: 0 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="label">RES SIM V2 — DIGITAL TWIN DATA &amp; AI FLOW</span>
            <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>Click any node for details</span>
          </div>

          <svg viewBox="0 0 1180 600" style={{ width: '100%', display: 'block' }}>
            <style>{`
              @keyframes flow-dash {
                from { stroke-dashoffset: 18; }
                to   { stroke-dashoffset: 0; }
              }
            `}</style>

            {/* Section divider */}
            <line x1={20} y1={275} x2={1160} y2={275} stroke="var(--border)" strokeWidth={1} strokeDasharray="4 4" />

            {/* Section labels */}
            <text x={28} y={116} fill="var(--text-muted)" fontSize={12} fontFamily="system-ui" fontWeight={700} letterSpacing="0.07em">
              SIMULATION &amp; OPERATIONS PIPELINE
            </text>
            <text x={28} y={318} fill="var(--text-muted)" fontSize={12} fontFamily="system-ui" fontWeight={700} letterSpacing="0.07em">
              SAP INTEGRATION &amp; APP LAYER
            </text>

            {/* Unity Catalog governance band */}
            <rect x={200} y={112} width={860} height={108} rx={10}
              fill="none" stroke="#F39C12" strokeWidth={1} strokeDasharray="6 3" strokeOpacity={0.45} />
            <rect x={209} y={104} width={178} height={16} rx={4} fill="var(--bg-card)" />
            <text x={215} y={115} fill="#F39C12" fontSize={10.5} fontFamily="system-ui" fontWeight={700}>
              Unity Catalog Governance
            </text>

            {/* Edges */}
            {EDGES.map((e, i) => <FlowEdge key={`e${i}`} e={e} idx={i} />)}

            {/* Edge labels for horizontal pipeline */}
            {EDGES.slice(0, 4).map(e => {
              const a = nodeById(e.from)!, b = nodeById(e.to)!
              if (!a || !b) return null
              return (
                <text key={`lbl-${e.label}`} x={(a.x + a.w + b.x) / 2} y={cy(a) - 14}
                  textAnchor="middle" fill={e.color} fontSize={10.5} fontFamily="system-ui" fontWeight={600}
                  style={{ pointerEvents: 'none' }}>
                  {e.label}
                </text>
              )
            })}

            {/* All nodes */}
            {PIPELINE.map(n => <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />)}
            {V2_NODES.map(n => <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />)}

            {/* Legend — two rows */}
            <g transform="translate(28, 555)">
              {[
                { color: '#27AE60', label: 'Norne Source' },
                { color: '#2980B9', label: 'Simulator' },
                { color: '#E67E22', label: 'Ops Engine' },
                { color: '#8E9AAF', label: 'SQLite' },
                { color: '#F39C12', label: 'Unity Catalog' },
              ].map((l, i) => (
                <g key={l.label} transform={`translate(${i * 210}, 0)`}>
                  <rect x={0} y={0} width={12} height={12} rx={2} fill={l.color} />
                  <text x={17} y={10} fill="var(--text-muted)" fontSize={10.5} fontFamily="system-ui">{l.label}</text>
                </g>
              ))}
            </g>
            <g transform="translate(28, 575)">
              {[
                { color: '#0FAAFF', label: 'SAP BDC' },
                { color: '#8E44AD', label: 'Delta Sharing' },
                { color: '#9B59B6', label: 'FastAPI' },
                { color: '#16A085', label: 'React UI' },
              ].map((l, i) => (
                <g key={l.label} transform={`translate(${i * 210}, 0)`}>
                  <rect x={0} y={0} width={12} height={12} rx={2} fill={l.color} />
                  <text x={17} y={10} fill="var(--text-muted)" fontSize={10.5} fontFamily="system-ui">{l.label}</text>
                </g>
              ))}
            </g>
          </svg>
        </div>

        {/* Detail panel */}
        <div style={{ width: 250, flexShrink: 0 }}>
          {selNode ? (
            <div className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: selNode.color, flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>{selNode.label}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{selNode.sub}</div>
                </div>
              </div>
              <div style={{
                display: 'inline-block', marginBottom: 12,
                background: selNode.color + '22', color: selNode.color,
                border: `1px solid ${selNode.color}`, borderRadius: 4,
                padding: '2px 8px', fontSize: 9, fontWeight: 700, fontFamily: 'monospace',
              }}>
                {selNode.badge}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {selNode.detail.map((d, i) => (
                  <div key={i} style={{
                    fontSize: 11, color: 'var(--text-secondary)',
                    padding: '5px 9px', background: 'var(--bg-panel)',
                    borderRadius: 5, fontFamily: 'monospace', lineHeight: 1.5,
                  }}>{d}</div>
                ))}
              </div>
              <button onClick={() => setSel(null)} style={{
                marginTop: 12, width: '100%',
                background: 'transparent', border: '1px solid var(--border)',
                borderRadius: 5, color: 'var(--text-muted)', fontSize: 11, padding: '5px 0',
              }}>Dismiss</button>
            </div>
          ) : (
            <div className="card" style={{ padding: 16 }}>
              <div className="label" style={{ marginBottom: 12 }}>HOW IT WORKS — V2</div>
              {[
                { step: '1', color: '#27AE60', text: 'Norne field data — real North Sea benchmark field model' },
                { step: '2', color: '#2980B9', text: 'Simulator runs 40 timesteps with calibrated physics (360 bar, 25% porosity)' },
                { step: '3', color: '#E67E22', text: 'Operations engine derives D&C, ESP, chemical, workover activities per well' },
                { step: '4', color: '#F39C12', text: 'Cost engine estimates full-cycle costs using SAP material & service pricing' },
                { step: '5', color: '#0FAAFF', text: 'SAP BDC shares live supply chain data inbound via Delta Sharing' },
                { step: '6', color: '#8E44AD', text: 'Production forecasts & MRP triggers shared back to SAP BDC outbound' },
                { step: '7', color: '#F39C12', text: 'All data governed in Unity Catalog with row-level security' },
                { step: '8', color: '#16A085', text: 'Compare scenarios: production, NPV, and lifting cost in one interface' },
              ].map(s => (
                <div key={s.step} style={{ display: 'flex', gap: 10, marginBottom: 9, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                    background: s.color + '30', border: `1px solid ${s.color}`, color: s.color,
                    fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>{s.step}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
