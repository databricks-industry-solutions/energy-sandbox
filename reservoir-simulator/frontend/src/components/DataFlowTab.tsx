import { useState } from 'react'

interface NodeDef {
  id: string; label: string; sub: string
  x: number; y: number; w: number; h: number
  color: string; badge: string
  detail: string[]
}

// ── Data pipeline nodes ─────────────────────────────────────────────────────────────────────────────────────────────────
const PIPELINE: NodeDef[] = [
  {
    id: 'norne', label: 'Norne OPM Dataset', sub: 'github.com/OPM/opm-data',
    x: 30, y: 120, w: 150, h: 64,
    color: '#27AE60', badge: 'SOURCE',
    detail: [
      'NORNE_ATW2013.DATA (Eclipse deck)',
      'Grid: 46×112×22 = 113,344 cells',
      'Includes: GRID, PVT, RELPERM, VFP',
      'METRIC units · Start: Nov 1997',
      'Wells: B-2H, D-1H, E-3H, D-2H, C-4H',
    ],
  },
  {
    id: 'parser', label: 'Grid Parser', sub: 'Python · OPM deck reader',
    x: 255, y: 120, w: 140, h: 64,
    color: '#E67E22', badge: 'PARSE',
    detail: [
      'Reads DIMENS: 46×112×22',
      'Extracts ACTNUM (active cells)',
      'Parses COORD / ZCORN geometry',
      'Scales to 20×10×5 vis grid',
      'Well positions from WELSPECS',
    ],
  },
  {
    id: 'simulator', label: 'OPM Flow Engine', sub: 'Python simulator.py',
    x: 470, y: 120, w: 150, h: 64,
    color: '#2980B9', badge: 'SIMULATE',
    detail: [
      'Norne-calibrated physics:',
      'P₀ = 360 bar · φ = 25% · k = 120 mD',
      'Bubble point: 250 bar (DISGAS)',
      '40 timesteps × 91 days',
      'Sparse cell updates via WebSocket',
    ],
  },
  {
    id: 'sqlite', label: 'SQLite Database', sub: '/tmp/reservoir_sim.db',
    x: 695, y: 120, w: 140, h: 64,
    color: '#8E9AAF', badge: 'STORE',
    detail: [
      'Tables: scenarios, simulation_runs,',
      '  economics_results',
      'WAL mode + foreign keys ON',
      'In-memory grid snapshots (dict)',
      'Seeded: 3 Norne scenarios',
    ],
  },
  {
    id: 'unity', label: 'Unity Catalog', sub: 'oil_pump_monitor_catalog',
    x: 910, y: 120, w: 150, h: 64,
    color: '#F39C12', badge: 'CATALOG',
    detail: [
      'SQL Warehouse: 87e069097741b56c',
      'Schema: sim · econ',
      'Tables: sim_summary, sim_grid_cells',
      '  econ_cashflows, econ_assumptions',
      'Governed by Unity Catalog',
    ],
  },
]

// ── App / AI nodes ────────────────────────────────────────────────────────────────────────────────────────────────────────
const APP_NODES: NodeDef[] = [
  {
    id: 'fastapi', label: 'FastAPI Backend', sub: 'Python 3.11 · uvicorn',
    x: 270, y: 350, w: 155, h: 64,
    color: '#9B59B6', badge: 'API',
    detail: [
      'POST /api/simulate → starts run',
      'GET  /api/scenarios → list',
      'GET  /api/runs/{id}/grid/{ts}',
      'POST /api/economics',
      'POST /api/agent/chat',
      'WS   /ws/simulate/{run_id}',
    ],
  },
  {
    id: 'react', label: 'React UI', sub: 'TypeScript · Three.js · Vite',
    x: 510, y: 350, w: 155, h: 64,
    color: '#16A085', badge: 'UI',
    detail: [
      'Scenarios: run Norne simulations',
      '3D Reservoir: InstancedMesh 1000 cells',
      '  Jet colormap · WebSocket streaming',
      'Well Results: Recharts time-series',
      'Economics: NPV · IRR · DCF',
      'Agent: Claude chat with context',
    ],
  },
  {
    id: 'claude', label: 'claude-sonnet-4-6', sub: 'Databricks FMAPI',
    x: 270, y: 480, w: 155, h: 64,
    color: '#8E44AD', badge: 'LLM',
    detail: [
      'Endpoint: databricks-claude-sonnet-4-5',
      'System: Norne reservoir expert',
      'Context: scenario + rates + economics',
      'Tools: pressure analysis, NPV calc',
      'Fallback: offline heuristic answers',
    ],
  },
  {
    id: 'user', label: 'Reservoir Engineer', sub: 'Norne Field Operations',
    x: 760, y: 350, w: 155, h: 64,
    color: '#2C3E50', badge: 'USER',
    detail: [
      'Selects: Norne Base/GasInj/FullField',
      'Watches: 3D cell saturation evolve',
      'Analyzes: well rates & BHP decline',
      'Computes: NPV at $75/bbl Brent',
      'Asks: AI for recovery optimization',
    ],
  },
]

interface EdgeDef { from: string; to: string; label: string; color?: string; dashed?: boolean }

const PIPELINE_EDGES: EdgeDef[] = [
  { from: 'norne',     to: 'parser',    label: 'git clone',       color: '#27AE60' },
  { from: 'parser',    to: 'simulator', label: 'grid params',     color: '#E67E22' },
  { from: 'simulator', to: 'sqlite',    label: 'run results',     color: '#2980B9' },
  { from: 'sqlite',    to: 'unity',     label: 'SQL Warehouse',   color: '#8E9AAF' },
]
const APP_EDGES: EdgeDef[] = [
  { from: 'sqlite',  to: 'fastapi', label: 'asyncio queries',   color: '#8E9AAF' },
  { from: 'fastapi', to: 'react',   label: 'REST + WebSocket',  color: '#9B59B6' },
  { from: 'react',   to: 'user',    label: 'browser',           color: '#16A085' },
  { from: 'fastapi', to: 'claude',  label: 'FMAPI call',        color: '#8E44AD' },
  { from: 'claude',  to: 'fastapi', label: 'AI response',       color: '#8E44AD', dashed: true },
]

function allNodes() { return [...PIPELINE, ...APP_NODES] }
function nodeById(id: string) { return allNodes().find(n => n.id === id) }
function cx(n: NodeDef) { return n.x + n.w / 2 }
function cy(n: NodeDef) { return n.y + n.h / 2 }

function arrowPath(e: EdgeDef): string {
  const a = nodeById(e.from)!, b = nodeById(e.to)!
  if (!a || !b) return ''
  const ax = cx(a), ay = cy(a), bx = cx(b), by = cy(b)
  // Horizontal pipeline edges
  if (Math.abs(ay - by) < 15) {
    return `M${a.x + a.w},${ay} L${b.x},${by}`
  }
  // sqlite → fastapi (down then across)
  if (e.from === 'sqlite' && e.to === 'fastapi') {
    const sx = cx(a), sy = a.y + a.h, ex = b.x + b.w, ey = cy(b)
    const mid = sy + 35
    return `M${sx},${sy} L${sx},${mid} L${ex},${mid} L${ex},${ey}`
  }
  // fastapi → claude
  if (e.from === 'fastapi' && e.to === 'claude') {
    const sx = cx(a), sy = a.y + a.h, ex = cx(b), ey = b.y
    return `M${sx},${sy} L${sx},${(sy + ey) / 2} L${ex},${(sy + ey) / 2} L${ex},${ey}`
  }
  // claude → fastapi
  if (e.from === 'claude' && e.to === 'fastapi') {
    const sx = cx(a) + 22, sy = a.y, ex = cx(b) + 22, ey = b.y + b.h
    return `M${sx},${sy} L${sx},${(sy + ey) / 2} L${ex},${(sy + ey) / 2} L${ex},${ey}`
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
        style={{ animation: `flow-dash 1.6s linear ${idx * 0.28}s infinite` }} />
      <path d={d} fill="none" stroke="none" markerEnd={`url(#${markerId})`} />
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
      {/* Badge */}
      <rect x={n.x + n.w - 56} y={n.y + 6} width={50} height={15} rx={3}
        fill={n.color + '30'} stroke={n.color} strokeWidth={0.8} />
      <text x={n.x + n.w - 31} y={n.y + 17} textAnchor="middle"
        fill={n.color} fontSize={8} fontFamily="monospace" fontWeight={700}>{n.badge}</text>
      {/* Label */}
      <text x={n.x + 10} y={n.y + 26} fill="var(--text-primary)" fontSize={11}
        fontFamily="system-ui,sans-serif" fontWeight={700}>{n.label}</text>
      <text x={n.x + 10} y={n.y + 42} fill="var(--text-muted)" fontSize={9.5}
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

      {/* ── Stats strip ── */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {[
          { label: 'Simulation Engine',  val: 'OPM Flow (Norne benchmark)',   color: 'var(--green)' },
          { label: 'Dataset',            val: 'Norne ATW2013 · 46×112×22',    color: 'var(--blue)' },
          { label: 'Storage',            val: 'SQLite + Unity Catalog',        color: 'var(--amber)' },
          { label: 'AI Agent',           val: 'claude-sonnet-4-6 (FMAPI)',     color: '#8E44AD' },
          { label: '3D Rendering',       val: 'Three.js InstancedMesh',        color: 'var(--teal)' },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding: '8px 14px', flex: 1, minWidth: 160 }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 4 }}>
              {k.label.toUpperCase()}
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: k.color, fontFamily: 'monospace' }}>
              {k.val}
            </div>
          </div>
        ))}
      </div>

      {/* ── Main: diagram + detail ── */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        {/* SVG diagram */}
        <div className="card" style={{ flex: 1, overflow: 'hidden', padding: 0 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="label">RESERVOIR SIMULATOR — DATA &amp; AI FLOW</span>
            <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>
              Click any node for details
            </span>
          </div>

          <svg viewBox="0 0 1120 600" style={{ width: '100%', display: 'block' }}>
            <style>{`
              @keyframes flow-dash {
                from { stroke-dashoffset: 18; }
                to   { stroke-dashoffset: 0; }
              }
            `}</style>

            {/* Section divider */}
            <line x1={20} y1={305} x2={1100} y2={305} stroke="var(--border)" strokeWidth={1} strokeDasharray="4 4" />

            {/* Section labels */}
            <text x={28} y={108} fill="var(--text-muted)" fontSize={10} fontFamily="system-ui" fontWeight={700} letterSpacing="0.07em">
              DATA PIPELINE
            </text>
            <text x={28} y={335} fill="var(--text-muted)" fontSize={10} fontFamily="system-ui" fontWeight={700} letterSpacing="0.07em">
              APP &amp; AI LAYER
            </text>

            {/* Unity Catalog governance band */}
            <rect x={225} y={102} width={850} height={82} rx={10}
              fill="none" stroke="#F39C12" strokeWidth={1} strokeDasharray="6 3" strokeOpacity={0.45} />
            <rect x={234} y={94} width={162} height={16} rx={4} fill="var(--bg-card)" />
            <text x={240} y={106} fill="#F39C12" fontSize={10} fontFamily="system-ui" fontWeight={700}>
              Unity Catalog Governance
            </text>

            {/* Pipeline edges */}
            {PIPELINE_EDGES.map((e, i) => <FlowEdge key={`p${i}`} e={e} idx={i} />)}
            {/* App edges */}
            {APP_EDGES.map((e, i) => <FlowEdge key={`a${i}`} e={e} idx={i + 4} />)}

            {/* Pipeline edge labels */}
            {PIPELINE_EDGES.map(e => {
              const a = nodeById(e.from)!, b = nodeById(e.to)!
              if (!a || !b) return null
              const mx = (a.x + a.w + b.x) / 2
              const my = cy(a) - 12
              return (
                <text key={e.label} x={mx} y={my} textAnchor="middle"
                  fill={e.color} fontSize={9} fontFamily="system-ui" fontWeight={600}
                  style={{ pointerEvents: 'none' }}>
                  {e.label}
                </text>
              )
            })}

            {/* Pipeline nodes */}
            {PIPELINE.map(n => <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />)}
            {/* App nodes */}
            {APP_NODES.map(n => <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />)}

            {/* Inline labels for vertical edges */}
            <text x={247} y={305} fill="#8E9AAF" fontSize={9} fontFamily="system-ui" fontWeight={600}>SQLite reads</text>
            <text x={247} y={445} fill="#8E44AD" fontSize={9} fontFamily="system-ui" fontWeight={600}>FMAPI</text>
            <text x={265} y={462} fill="#8E44AD" fontSize={9} fontFamily="system-ui" fontWeight={600}>response</text>

            {/* Legend */}
            <g transform="translate(28, 562)">
              {[
                { color: '#27AE60', label: 'OPM Source' },
                { color: '#E67E22', label: 'Parser' },
                { color: '#2980B9', label: 'Simulator' },
                { color: '#8E9AAF', label: 'SQLite' },
                { color: '#F39C12', label: 'Unity Catalog' },
                { color: '#9B59B6', label: 'FastAPI' },
                { color: '#16A085', label: 'React UI' },
                { color: '#8E44AD', label: 'Claude AI' },
              ].map((l, i) => (
                <g key={l.label} transform={`translate(${i * 128}, 0)`}>
                  <rect x={0} y={0} width={11} height={11} rx={2} fill={l.color} />
                  <text x={15} y={9} fill="var(--text-muted)" fontSize={9} fontFamily="system-ui">{l.label}</text>
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
                  }}>
                    {d}
                  </div>
                ))}
              </div>
              <button onClick={() => setSel(null)} style={{
                marginTop: 12, width: '100%',
                background: 'transparent', border: '1px solid var(--border)',
                borderRadius: 5, color: 'var(--text-muted)', fontSize: 11, padding: '5px 0',
              }}>
                Dismiss
              </button>
            </div>
          ) : (
            <div className="card" style={{ padding: 16 }}>
              <div className="label" style={{ marginBottom: 12 }}>HOW IT WORKS</div>
              {[
                { step: '1', color: '#27AE60', text: 'Norne OPM data cloned from GitHub — real North Sea field deck' },
                { step: '2', color: '#E67E22', text: 'Parser reads DIMENS 46×112×22 and scales to 20×10×5 vis grid' },
                { step: '3', color: '#2980B9', text: 'Simulator runs 40 timesteps with Norne-calibrated physics (360 bar, φ=25%)' },
                { step: '4', color: '#8E9AAF', text: 'Run results stored in SQLite; grid snapshots streamed live via WebSocket' },
                { step: '5', color: '#F39C12', text: 'Unity Catalog holds sim & econ Delta tables for ad-hoc SQL' },
                { step: '6', color: '#9B59B6', text: 'FastAPI serves cells, scenarios, economics, and agent endpoints' },
                { step: '7', color: '#16A085', text: 'React renders 1000-cell 3D with jet colormap updating in real time' },
                { step: '8', color: '#8E44AD', text: 'Claude answers reservoir engineering questions with full simulation context' },
              ].map(s => (
                <div key={s.step} style={{ display: 'flex', gap: 10, marginBottom: 9, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                    background: s.color + '30', border: `1px solid ${s.color}`, color: s.color,
                    fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {s.step}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {s.text}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
