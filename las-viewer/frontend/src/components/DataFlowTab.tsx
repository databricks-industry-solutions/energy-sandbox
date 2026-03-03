import { useState } from 'react'

/* ─── Node definitions ─────────────────────────────────────────────────── */
interface NodeDef {
  id: string; label: string; sub: string
  x: number; y: number; w: number; h: number
  color: string; badge?: string
  detail: string[]
}

const PIPELINE: NodeDef[] = [
  {
    id: 'las',   label: 'LAS / DLIS Files', sub: 'S3 Object Store',
    x: 30, y: 130, w: 130, h: 64,
    color: '#27AE60', badge: 'SOURCE',
    detail: ['Raw .las / .dlis well-log files', 'Uploaded by OFS field engineers', 'Partitioned by well & date', 'Supported: LAS 1.2, 2.0, 3.0, DLIS'],
  },
  {
    id: 'bronze', label: 'las_raw', sub: 'Bronze · Delta Lake',
    x: 240, y: 130, w: 140, h: 64,
    color: '#CD6116', badge: 'BRONZE',
    detail: ['Auto Loader ingestion (cloudFiles)', 'Schema inference + evolution', 'Raw curve preservation', 'Unity Catalog: las.bronze.depth_logs'],
  },
  {
    id: 'silver', label: 'las_curated', sub: 'Silver · DLT Pipeline',
    x: 460, y: 130, w: 140, h: 64,
    color: '#8E9AAF', badge: 'SILVER',
    detail: ['Depth alignment (±0.5 ft tolerance)', 'Despiking (z-score > 3.5)', 'Environmental corrections (Rxo, temp)', 'Gap filling via interpolation'],
  },
  {
    id: 'gold', label: 'las_gold', sub: 'Gold · ML-Derived',
    x: 680, y: 130, w: 140, h: 64,
    color: '#F39C12', badge: 'GOLD',
    detail: ['VCL from linear GR (Larionov)', 'φ_eff: RHOB–NPHI crossplot', 'Sw: Archie equation (m=2, n=2)', 'DT synthetic (ML regression model)'],
  },
  {
    id: 'lakebase', label: 'Lakebase', sub: 'Managed PostgreSQL 16',
    x: 900, y: 130, w: 150, h: 64,
    color: '#2980B9', badge: 'SERVING',
    detail: ['Instance: las-viewer-db', 'Tables: wells, depth_logs,', '  formation_tops, curve_quality,', '  qc_rules, recipes, anomalies'],
  },
]

const APP_NODES: NodeDef[] = [
  {
    id: 'fastapi', label: 'FastAPI Backend', sub: 'Python · uvicorn',
    x: 340, y: 360, w: 150, h: 64,
    color: '#9B59B6', badge: 'API',
    detail: ['/api/wells   /api/logs/{id}', '/api/qc      /api/corrections', '/api/recipes /api/recipes/runs', '/api/advisor/chat  /advisor/quick'],
  },
  {
    id: 'ui', label: 'React UI', sub: 'TypeScript · Vite',
    x: 580, y: 360, w: 150, h: 64,
    color: '#16A085', badge: 'UI',
    detail: ['Wells Registry (fleet table)', 'Log Viewer (7-track SVG plot)', 'QC & Corrections dashboard', 'Recipes  ·  Petrophysics AI Chat'],
  },
  {
    id: 'claude', label: 'claude-sonnet-4-5', sub: 'Foundation Model API',
    x: 340, y: 480, w: 150, h: 64,
    color: '#8E44AD', badge: 'LLM',
    detail: ['Databricks FMAPI endpoint', 'System prompt: petrophysics expert', 'Context: well status + QC scores', 'Conversation history preserved'],
  },
  {
    id: 'user', label: 'OFS Engineer', sub: 'Petrophysicist',
    x: 820, y: 360, w: 140, h: 64,
    color: '#2C3E50', badge: 'USER',
    detail: ['Views log tracks + QC scores', 'Runs correction recipes', 'Queries AI for interpretation', 'Exports petrophysical reports'],
  },
]

/* ─── Edge definitions ──────────────────────────────────────────────────── */
interface EdgeDef { from: string; to: string; label: string; color?: string; dashed?: boolean }

const PIPELINE_EDGES: EdgeDef[] = [
  { from: 'las',     to: 'bronze',   label: 'Auto Loader',  color: '#27AE60' },
  { from: 'bronze',  to: 'silver',   label: 'DLT clean',    color: '#CD6116' },
  { from: 'silver',  to: 'gold',     label: 'ML derive',    color: '#8E9AAF' },
  { from: 'gold',    to: 'lakebase', label: 'Reverse ETL',  color: '#F39C12' },
]

const APP_EDGES: EdgeDef[] = [
  { from: 'lakebase', to: 'fastapi', label: 'asyncpg',     color: '#2980B9' },
  { from: 'fastapi',  to: 'ui',      label: 'JSON REST',   color: '#9B59B6' },
  { from: 'ui',       to: 'user',    label: 'browser',     color: '#16A085' },
  { from: 'fastapi',  to: 'claude',  label: 'FMAPI',       color: '#8E44AD' },
  { from: 'claude',   to: 'fastapi', label: 'AI response', color: '#8E44AD', dashed: true },
]

/* ─── Helpers ───────────────────────────────────────────────────────────── */
function cx(n: NodeDef) { return n.x + n.w / 2 }
function cy(n: NodeDef) { return n.y + n.h / 2 }

function nodeById(id: string): NodeDef | undefined {
  return [...PIPELINE, ...APP_NODES].find(n => n.id === id)
}

function arrowPath(e: EdgeDef): string {
  const a = nodeById(e.from)!
  const b = nodeById(e.to)!
  const ax = cx(a), ay = cy(a), bx = cx(b), by = cy(b)

  // Horizontal edge (pipeline)
  if (Math.abs(ay - by) < 10) {
    const sx = a.x + a.w, ex = b.x
    return `M${sx},${ay} L${ex},${by}`
  }

  // lakebase → fastapi (down then left)
  if (e.from === 'lakebase' && e.to === 'fastapi') {
    const sx = cx(a), sy = a.y + a.h
    const ex = b.x + b.w, ey = cy(b)
    const midY = sy + 40
    return `M${sx},${sy} L${sx},${midY} L${ex},${midY} L${ex},${ey}`
  }

  // fastapi → claude (down)
  if (e.from === 'fastapi' && e.to === 'claude') {
    const sx = cx(a), sy = a.y + a.h, ex = cx(b), ey = b.y
    return `M${sx},${sy} L${sx},${(sy+ey)/2} L${ex},${(sy+ey)/2} L${ex},${ey}`
  }

  // claude → fastapi (up, offset to avoid overlap)
  if (e.from === 'claude' && e.to === 'fastapi') {
    const sx = cx(a) + 20, sy = a.y, ex = cx(b) + 20, ey = b.y + b.h
    return `M${sx},${sy} L${sx},${(sy+ey)/2} L${ex},${(sy+ey)/2} L${ex},${ey}`
  }

  // Default: straight
  return `M${ax},${ay} L${bx},${by}`
}

/* ─── FlowEdge component ────────────────────────────────────────────────── */
function FlowEdge({ e, idx }: { e: EdgeDef; idx: number }) {
  const d = arrowPath(e)
  const col = e.color ?? '#555'
  return (
    <g>
      <path d={d} fill="none" stroke={col} strokeWidth={1.5}
        strokeDasharray={e.dashed ? '5 4' : '6 3'}
        strokeOpacity={0.25} />
      <path d={d} fill="none" stroke={col} strokeWidth={2}
        strokeDasharray="6 3"
        style={{ animation: `flow-dash 1.6s linear ${idx * 0.3}s infinite` }} />
      <defs>
        <marker id={`arr-${e.from}-${e.to}`} markerWidth={8} markerHeight={8}
          refX={6} refY={3} orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill={col} />
        </marker>
      </defs>
      <path d={d} fill="none" stroke="none" markerEnd={`url(#arr-${e.from}-${e.to})`} />
    </g>
  )
}

/* ─── FlowNode component ────────────────────────────────────────────────── */
function FlowNode({ n, selected, onSelect }: {
  n: NodeDef; selected: boolean; onSelect: (id: string) => void
}) {
  return (
    <g onClick={() => onSelect(n.id)} style={{ cursor: 'pointer' }}>
      <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={8}
        fill="var(--bg-card)"
        stroke={selected ? n.color : 'var(--border)'}
        strokeWidth={selected ? 2 : 1}
        style={{ filter: selected ? `drop-shadow(0 0 6px ${n.color}88)` : 'none', transition: 'all 0.2s' }}
      />
      {/* Badge */}
      {n.badge && (
        <rect x={n.x + n.w - 52} y={n.y + 6} width={46} height={14} rx={3}
          fill={n.color + '33'} stroke={n.color} strokeWidth={0.8} />
      )}
      {n.badge && (
        <text x={n.x + n.w - 29} y={n.y + 16.5} textAnchor="middle"
          fill={n.color} fontSize={8} fontFamily="monospace" fontWeight={700}>
          {n.badge}
        </text>
      )}
      {/* Label */}
      <text x={n.x + 10} y={n.y + 24} fill="var(--text-primary)" fontSize={11}
        fontFamily="Helvetica,sans-serif" fontWeight={700}>{n.label}</text>
      <text x={n.x + 10} y={n.y + 40} fill="var(--text-muted)" fontSize={9.5}
        fontFamily="Helvetica,sans-serif">{n.sub}</text>
    </g>
  )
}

/* ─── Main component ────────────────────────────────────────────────────── */
export default function DataFlowTab() {
  const [sel, setSel] = useState<string | null>(null)
  const selNode = sel ? nodeById(sel) : null

  const select = (id: string) => setSel(s => s === id ? null : id)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── header strip ───────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {[
          { label: 'Data Pipeline', val: 'Bronze → Silver → Gold', color: 'var(--amber)' },
          { label: 'Serving Layer', val: 'Lakebase (PostgreSQL 16)', color: 'var(--blue)' },
          { label: 'AI Backend',   val: 'claude-sonnet-4-5 (FMAPI)', color: '#9B59B6' },
          { label: 'Frontend',     val: 'React · 5 tabs · SVG tracks', color: 'var(--green)' },
          { label: 'Governance',   val: 'Unity Catalog',              color: '#E67E22' },
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

      {/* ── main diagram + detail panel ────────────────────────────── */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        {/* SVG diagram */}
        <div className="card" style={{ flex: 1, overflow: 'hidden', padding: 0 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="label">DATA &amp; AI FLOW DIAGRAM</span>
            <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>
              Click any node for details
            </span>
          </div>

          <svg viewBox="0 0 1120 590" style={{ width: '100%', display: 'block' }}
            xmlns="http://www.w3.org/2000/svg">

            <style>{`
              @keyframes flow-dash {
                from { stroke-dashoffset: 18; }
                to   { stroke-dashoffset: 0;  }
              }
            `}</style>

            {/* ── Unity Catalog governance band ── */}
            <rect x={210} y={104} width={860} height={82} rx={10}
              fill="none" stroke="#E67E22" strokeWidth={1} strokeDasharray="6 3" strokeOpacity={0.5} />
            <rect x={220} y={96} width={148} height={16} rx={4} fill="var(--bg-card)" />
            <text x={226} y={107} fill="#E67E22" fontSize={10} fontFamily="Helvetica,sans-serif" fontWeight={700}>
              Unity Catalog Governance
            </text>

            {/* ── Section labels ── */}
            <text x={30} y={104} fill="var(--text-muted)" fontSize={10} fontFamily="Helvetica,sans-serif" fontWeight={700}>
              DATA PIPELINE
            </text>
            <text x={30} y={344} fill="var(--text-muted)" fontSize={10} fontFamily="Helvetica,sans-serif" fontWeight={700}>
              APP &amp; AI FLOW
            </text>

            {/* ── Divider ── */}
            <line x1={20} y1={320} x2={1100} y2={320} stroke="var(--border)" strokeWidth={1} strokeDasharray="4 4" />

            {/* ── Pipeline edges ── */}
            {PIPELINE_EDGES.map((e, i) => <FlowEdge key={e.from+e.to} e={e} idx={i} />)}

            {/* ── App edges ── */}
            {APP_EDGES.map((e, i) => <FlowEdge key={e.from+e.to} e={e} idx={i+4} />)}

            {/* ── Edge labels ── */}
            {PIPELINE_EDGES.map(e => {
              const a = nodeById(e.from)!, b = nodeById(e.to)!
              const mx = (a.x + a.w + b.x) / 2, my = cy(a) - 11
              return (
                <text key={e.label} x={mx} y={my} textAnchor="middle"
                  fill={e.color} fontSize={9} fontFamily="Helvetica,sans-serif" fontWeight={600}
                  style={{ pointerEvents: 'none' }}>
                  {e.label}
                </text>
              )
            })}

            {/* ── Pipeline nodes ── */}
            {PIPELINE.map(n => (
              <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />
            ))}

            {/* ── App nodes ── */}
            {APP_NODES.map(n => (
              <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />
            ))}

            {/* ── lakebase→fastapi label ── */}
            <text x={720} y={298} fill="#2980B9" fontSize={9} fontFamily="Helvetica,sans-serif" fontWeight={600}>
              asyncpg
            </text>

            {/* ── Claude loop labels ── */}
            <text x={310} y={432} fill="#8E44AD" fontSize={9} fontFamily="Helvetica,sans-serif" fontWeight={600}>
              FMAPI call
            </text>
            <text x={360} y={452} fill="#8E44AD" fontSize={9} fontFamily="Helvetica,sans-serif" fontWeight={600}>
              response
            </text>

            {/* ── Legend ── */}
            <g transform="translate(30, 548)">
              {[
                { color: '#27AE60', label: 'Source' },
                { color: '#CD6116', label: 'Bronze' },
                { color: '#8E9AAF', label: 'Silver' },
                { color: '#F39C12', label: 'Gold' },
                { color: '#2980B9', label: 'Lakebase' },
                { color: '#9B59B6', label: 'App' },
                { color: '#8E44AD', label: 'AI / LLM' },
              ].map((l, i) => (
                <g key={l.label} transform={`translate(${i * 130}, 0)`}>
                  <rect x={0} y={0} width={12} height={12} rx={2} fill={l.color} />
                  <text x={16} y={10} fill="var(--text-muted)" fontSize={9} fontFamily="Helvetica,sans-serif">
                    {l.label}
                  </text>
                </g>
              ))}
            </g>

          </svg>
        </div>

        {/* Detail panel */}
        <div style={{ width: 240, flexShrink: 0 }}>
          {selNode ? (
            <div className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: selNode.color }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>
                    {selNode.label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{selNode.sub}</div>
                </div>
              </div>
              {selNode.badge && (
                <div style={{
                  display: 'inline-block', marginBottom: 10,
                  background: selNode.color + '22', color: selNode.color,
                  border: `1px solid ${selNode.color}`, borderRadius: 4,
                  padding: '2px 8px', fontSize: 9, fontWeight: 700, fontFamily: 'monospace',
                }}>
                  {selNode.badge}
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
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
                marginTop: 12, width: '100%', background: 'transparent',
                border: '1px solid var(--border)', borderRadius: 5,
                color: 'var(--text-muted)', fontSize: 11, padding: '5px 0', cursor: 'pointer',
              }}>
                Dismiss
              </button>
            </div>
          ) : (
            <div className="card" style={{ padding: 16 }}>
              <div className="label" style={{ marginBottom: 12 }}>HOW IT WORKS</div>
              {[
                { step: '1', color: '#27AE60', text: 'LAS/DLIS files land in S3' },
                { step: '2', color: '#CD6116', text: 'Auto Loader ingests to las_raw (Bronze)' },
                { step: '3', color: '#8E9AAF', text: 'DLT pipeline cleans & corrects to las_curated (Silver)' },
                { step: '4', color: '#F39C12', text: 'ML derives VCL, φ_eff, Sw into las_gold' },
                { step: '5', color: '#2980B9', text: 'Reverse ETL syncs gold to Lakebase for low-latency queries' },
                { step: '6', color: '#9B59B6', text: 'FastAPI serves data to React UI via asyncpg' },
                { step: '7', color: '#8E44AD', text: 'AI Advisor calls Claude via FMAPI for petrophysical interpretation' },
              ].map(s => (
                <div key={s.step} style={{ display: 'flex', gap: 10, marginBottom: 10, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%', background: s.color + '33',
                    border: `1px solid ${s.color}`, color: s.color,
                    fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', flexShrink: 0,
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
