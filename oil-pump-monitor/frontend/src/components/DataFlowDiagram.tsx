import { useState } from 'react';

/* ─── Types ─────────────────────────────────────────────────────────────── */
interface NodeDef {
  id: string; label: string; sub: string
  x: number; y: number; w: number; h: number
  color: string; badge?: string
  detail: string[]
}
interface EdgeDef { from: string; to: string; label?: string; color?: string; dashed?: boolean }

/* ─── Pipeline nodes (top section, horizontal) ──────────────────────────── */
const PIPELINE: NodeDef[] = [
  {
    id: 'sensors', label: '6× Pump Sensors', sub: 'IoT Field Devices',
    x: 20, y: 120, w: 155, h: 64, color: '#3b82f6', badge: 'SOURCE',
    detail: ['Vibration: amplitude (mm/s), freq (Hz)', 'Temperature (°F) · Pressure (PSI)', 'Pump speed (RPM)', 'Reading interval: 2 seconds'],
  },
  {
    id: 'fastapi', label: 'FastAPI Backend', sub: 'Python · uvicorn',
    x: 235, y: 120, w: 155, h: 64, color: '#06b6d4', badge: 'INGEST',
    detail: ['/api/readings/live', '/api/history/{pump_id}', '/api/spectrum/{pump_id}', '/api/alerts  /api/field'],
  },
  {
    id: 'lakebase', label: 'Lakebase', sub: 'Managed PostgreSQL 16',
    x: 450, y: 120, w: 155, h: 64, color: '#14b8a6', badge: 'POSTGRES',
    detail: ['Instance: oil-pump-monitor-db', 'Tables: readings, pumps,', '  alerts, spectrum_cache', 'OAuth token auth · SSL required'],
  },
  {
    id: 'spark', label: 'Databricks Spark', sub: 'Serverless Compute',
    x: 665, y: 120, w: 165, h: 64, color: '#7c3aed', badge: 'COMPUTE',
    detail: ['FFT computation (numpy/scipy)', 'Feature engineering pipeline', 'Batch aggregation jobs', 'Anomaly scoring pipeline'],
  },
  {
    id: 'delta', label: 'Delta Lake', sub: 'Unity Catalog',
    x: 890, y: 120, w: 195, h: 64, color: '#f97316', badge: 'DELTA',
    detail: ['Historical readings archive', 'ACID transactions', 'Parquet columnar format', 'oil_monitor.bronze.readings'],
  },
]

/* ─── Analysis & serving nodes (bottom section) ─────────────────────────── */
const APP_NODES: NodeDef[] = [
  {
    id: 'fft', label: 'FFT Analysis', sub: 'Spectrum Engine',
    x: 20, y: 360, w: 165, h: 64, color: '#a78bfa', badge: 'FFT',
    detail: ['numpy.fft.rfft() on readings', '4 harmonics tracked', 'Fundamental + 3× overtones', 'Bearing fault signature match'],
  },
  {
    id: 'anomaly', label: 'Anomaly Detection', sub: 'Threshold + ML',
    x: 235, y: 360, w: 175, h: 64, color: '#a78bfa', badge: 'ML',
    detail: ['Amplitude threshold: 5.0 mm/s', 'Frequency deviation: ±3 Hz', 'Temperature: 175°F critical', 'Z-score outlier detection'],
  },
  {
    id: 'predict', label: 'Predictive ML', sub: 'Failure Forecasting',
    x: 460, y: 360, w: 165, h: 64, color: '#a78bfa', badge: 'ML',
    detail: ['MTBF estimation model', 'Remaining-life regression', 'Trend extrapolation', 'Maintenance priority ranking'],
  },
  {
    id: 'genie', label: 'Databricks Genie AI', sub: 'Foundation Model API',
    x: 675, y: 350, w: 195, h: 80, color: '#6366f1', badge: 'LLM',
    detail: ['claude-sonnet-4-5 endpoint', 'System: vibration / pump expert', 'Tools: get_live_reading,', '  get_history, get_spectrum'],
  },
  {
    id: 'outputs', label: 'Alerts · Dashboard · Map', sub: 'React UI · 6 tabs',
    x: 920, y: 360, w: 175, h: 64, color: '#22c55e', badge: 'UI',
    detail: ['Alert Engine (critical notify)', 'Live Dashboard (waveforms)', 'Field Map (GPS pump locations)', 'Maintenance Queue (work orders)'],
  },
]

const allNodes = [...PIPELINE, ...APP_NODES]
const nodeById = (id: string) => allNodes.find(n => n.id === id)!
const cx = (n: NodeDef) => n.x + n.w / 2
const cy = (n: NodeDef) => n.y + n.h / 2

/* ─── Edge paths ─────────────────────────────────────────────────────────── */
const PIPELINE_EDGES: EdgeDef[] = [
  { from: 'sensors', to: 'fastapi',  label: 'IoT stream', color: '#3b82f6' },
  { from: 'fastapi',  to: 'lakebase', label: 'asyncpg',   color: '#06b6d4' },
  { from: 'lakebase', to: 'spark',    label: 'JDBC',       color: '#14b8a6' },
  { from: 'spark',    to: 'delta',    label: 'Parquet',    color: '#7c3aed' },
]

const APP_EDGES: EdgeDef[] = [
  { from: 'spark',   to: 'fft',     color: '#7c3aed' },
  { from: 'spark',   to: 'anomaly', color: '#7c3aed' },
  { from: 'spark',   to: 'predict', color: '#7c3aed' },
  { from: 'fft',     to: 'genie',   color: '#a78bfa' },
  { from: 'anomaly', to: 'genie',   color: '#a78bfa' },
  { from: 'predict', to: 'genie',   color: '#a78bfa' },
  { from: 'genie',   to: 'outputs', label: 'alerts / actions', color: '#6366f1' },
]

function arrowPath(e: EdgeDef): string {
  const a = nodeById(e.from), b = nodeById(e.to)

  // Horizontal pipeline
  if (Math.abs(cy(a) - cy(b)) < 20) {
    return `M${a.x + a.w},${cy(a)} L${b.x},${cy(b)}`
  }

  // spark → analysis nodes (down through divider at y=310, then left)
  if (e.from === 'spark' && (e.to === 'fft' || e.to === 'anomaly' || e.to === 'predict')) {
    const offsets: Record<string, number> = { fft: -25, anomaly: 0, predict: 25 }
    const sx = cx(a) + offsets[e.to]
    const ex = cx(b), ey = b.y
    return `M${sx},${a.y + a.h} L${sx},310 L${ex},310 L${ex},${ey}`
  }

  // analysis → genie (right edge to genie left, staggered entry heights)
  if (e.to === 'genie') {
    const entryY: Record<string, number> = { fft: 363, anomaly: 390, predict: 417 }
    const sx = a.x + a.w, sy = cy(a)
    const ex = b.x, ey = entryY[e.from]
    const mx = (sx + ex) / 2
    return `M${sx},${sy} C${mx},${sy} ${mx},${ey} ${ex},${ey}`
  }

  // genie → outputs
  if (e.from === 'genie') {
    return `M${a.x + a.w},${cy(a)} L${b.x},${cy(b)}`
  }

  return `M${cx(a)},${cy(a)} L${cx(b)},${cy(b)}`
}

/* ─── FlowEdge ───────────────────────────────────────────────────────────── */
function FlowEdge({ e, idx }: { e: EdgeDef; idx: number }) {
  const d = arrowPath(e)
  const col = e.color ?? '#475569'
  const markerId = `arr-${e.from}-${e.to}`
  return (
    <g>
      <defs>
        <marker id={markerId} markerWidth={8} markerHeight={8} refX={6} refY={3} orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill={col} />
        </marker>
      </defs>
      {/* Static faint track */}
      <path d={d} fill="none" stroke={col} strokeWidth={1.5}
        strokeDasharray={e.dashed ? '5 4' : '6 3'} strokeOpacity={0.2} />
      {/* Animated flowing dash */}
      <path d={d} fill="none" stroke={col} strokeWidth={2} strokeDasharray="6 3"
        style={{ animation: `flow-dash 1.6s linear ${idx * 0.3}s infinite` }} />
      {/* Arrowhead (invisible stroke so marker renders at path end) */}
      <path d={d} fill="none" stroke="none" markerEnd={`url(#${markerId})`} />
    </g>
  )
}

/* ─── FlowNode ───────────────────────────────────────────────────────────── */
function FlowNode({ n, selected, onSelect }: { n: NodeDef; selected: boolean; onSelect: (id: string) => void }) {
  return (
    <g onClick={() => onSelect(n.id)} style={{ cursor: 'pointer' }}>
      <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={8}
        fill="#0a0e1a"
        stroke={selected ? n.color : '#1e293b'}
        strokeWidth={selected ? 2 : 1}
        style={{ filter: selected ? `drop-shadow(0 0 6px ${n.color}88)` : 'none', transition: 'all 0.2s' }}
      />
      {n.badge && (
        <>
          <rect x={n.x + n.w - 54} y={n.y + 6} width={48} height={14} rx={3}
            fill={n.color + '33'} stroke={n.color} strokeWidth={0.8} />
          <text x={n.x + n.w - 30} y={n.y + 16.5} textAnchor="middle"
            fill={n.color} fontSize={8} fontFamily="monospace" fontWeight={700}>
            {n.badge}
          </text>
        </>
      )}
      <text x={n.x + 10} y={n.y + 26} fill="#e2e8f0" fontSize={11}
        fontFamily="Helvetica, Arial, sans-serif" fontWeight={700}>{n.label}</text>
      <text x={n.x + 10} y={n.y + 42} fill="#64748b" fontSize={9.5}
        fontFamily="Helvetica, Arial, sans-serif">{n.sub}</text>
    </g>
  )
}

/* ─── Main component ─────────────────────────────────────────────────────── */
export function DataFlowDiagram() {
  const [sel, setSel] = useState<string | null>(null)
  const selNode = sel ? nodeById(sel) : null
  const select = (id: string) => setSel(s => s === id ? null : id)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Stat cards ── */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {[
          { label: 'Data Pipeline',  val: 'Sensors → Lakebase → Delta Lake', color: '#3b82f6' },
          { label: 'Compute',        val: 'Databricks Spark (Serverless)',    color: '#7c3aed' },
          { label: 'AI / LLM',       val: 'Genie AI · claude-sonnet-4-5',    color: '#6366f1' },
          { label: 'Frontend',       val: 'React · 6 tabs · live monitor',   color: '#22c55e' },
          { label: 'Governance',     val: 'Unity Catalog',                   color: '#f97316' },
        ].map(k => (
          <div key={k.label} style={{
            background: '#0f172a', border: '1px solid #1e293b', borderRadius: 10,
            padding: '8px 14px', flex: 1, minWidth: 160,
          }}>
            <div style={{ fontSize: 9, color: '#64748b', letterSpacing: '0.06em', marginBottom: 4 }}>
              {k.label.toUpperCase()}
            </div>
            <div style={{ fontSize: 11, fontWeight: 600, color: k.color, fontFamily: 'monospace' }}>
              {k.val}
            </div>
          </div>
        ))}
      </div>

      {/* ── Diagram + detail panel ── */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        {/* SVG diagram card */}
        <div style={{
          flex: 1, background: '#0f172a', border: '1px solid #1e293b',
          borderRadius: 12, overflow: 'hidden',
        }}>
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid #1e293b',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Data &amp; AI Flow Diagram
            </span>
            <span style={{ marginLeft: 'auto', fontSize: 10, color: '#475569' }}>
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
            <rect x={420} y={104} width={680} height={82} rx={10}
              fill="none" stroke="#f97316" strokeWidth={1} strokeDasharray="6 3" strokeOpacity={0.45} />
            <rect x={430} y={96} width={162} height={16} rx={4} fill="#0f172a" />
            <text x={436} y={107} fill="#f97316" fontSize={10}
              fontFamily="Helvetica, Arial, sans-serif" fontWeight={700}>
              Unity Catalog Governance
            </text>

            {/* ── Section labels ── */}
            <text x={20} y={104} fill="#64748b" fontSize={10}
              fontFamily="Helvetica, Arial, sans-serif" fontWeight={700}>DATA PIPELINE</text>
            <text x={20} y={344} fill="#64748b" fontSize={10}
              fontFamily="Helvetica, Arial, sans-serif" fontWeight={700}>ANALYSIS &amp; AI SERVING</text>

            {/* ── Divider ── */}
            <line x1={20} y1={320} x2={1100} y2={320} stroke="#1e293b" strokeWidth={1} strokeDasharray="4 4" />

            {/* ── Pipeline edges ── */}
            {PIPELINE_EDGES.map((e, i) => <FlowEdge key={e.from + e.to} e={e} idx={i} />)}

            {/* ── App edges ── */}
            {APP_EDGES.map((e, i) => <FlowEdge key={e.from + e.to} e={e} idx={i + 4} />)}

            {/* ── Pipeline edge labels ── */}
            {PIPELINE_EDGES.map(e => {
              const a = nodeById(e.from), b = nodeById(e.to)
              const mx = (a.x + a.w + b.x) / 2
              const my = cy(a) - 11
              return (
                <text key={e.label} x={mx} y={my} textAnchor="middle"
                  fill={e.color} fontSize={9} fontFamily="Helvetica, Arial, sans-serif" fontWeight={600}
                  style={{ pointerEvents: 'none' }}>
                  {e.label}
                </text>
              )
            })}

            {/* ── Genie output label ── */}
            <text x={860} y={370} fill="#6366f1" fontSize={9}
              fontFamily="Helvetica, Arial, sans-serif" fontWeight={600}>
              alerts / actions
            </text>

            {/* ── Pipeline nodes ── */}
            {PIPELINE.map(n => <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />)}

            {/* ── App nodes ── */}
            {APP_NODES.map(n => <FlowNode key={n.id} n={n} selected={sel === n.id} onSelect={select} />)}

            {/* ── Legend ── */}
            <g transform="translate(20, 556)">
              {[
                { color: '#3b82f6', label: 'Source / IoT' },
                { color: '#06b6d4', label: 'Ingestion' },
                { color: '#14b8a6', label: 'Lakebase' },
                { color: '#7c3aed', label: 'Compute' },
                { color: '#f97316', label: 'Delta Lake' },
                { color: '#a78bfa', label: 'AI / ML' },
                { color: '#6366f1', label: 'Genie AI' },
                { color: '#22c55e', label: 'Serving / UI' },
              ].map((l, i) => (
                <g key={l.label} transform={`translate(${i * 128}, 0)`}>
                  <rect x={0} y={0} width={12} height={12} rx={2} fill={l.color} />
                  <text x={16} y={10} fill="#64748b" fontSize={9}
                    fontFamily="Helvetica, Arial, sans-serif">{l.label}</text>
                </g>
              ))}
            </g>

          </svg>
        </div>

        {/* ── Detail / how-it-works panel ── */}
        <div style={{ width: 240, flexShrink: 0 }}>
          {selNode ? (
            <div style={{
              background: '#0f172a', border: '1px solid #1e293b', borderRadius: 12, padding: 16,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: selNode.color }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: '#e2e8f0' }}>{selNode.label}</div>
                  <div style={{ fontSize: 10, color: '#64748b' }}>{selNode.sub}</div>
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
                    fontSize: 11, color: '#94a3b8',
                    padding: '5px 9px', background: '#060b18',
                    borderRadius: 5, fontFamily: 'monospace', lineHeight: 1.5,
                  }}>
                    {d}
                  </div>
                ))}
              </div>
              <button onClick={() => setSel(null)} style={{
                marginTop: 12, width: '100%', background: 'transparent',
                border: '1px solid #1e293b', borderRadius: 5,
                color: '#64748b', fontSize: 11, padding: '5px 0', cursor: 'pointer',
              }}>
                Dismiss
              </button>
            </div>
          ) : (
            <div style={{
              background: '#0f172a', border: '1px solid #1e293b', borderRadius: 12, padding: 16,
            }}>
              <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
                How It Works
              </div>
              {[
                { step: '1', color: '#3b82f6', text: 'Pump sensors emit readings every 2 seconds' },
                { step: '2', color: '#06b6d4', text: 'FastAPI ingests and stores readings in Lakebase' },
                { step: '3', color: '#14b8a6', text: 'Lakebase serves live data to the React dashboard' },
                { step: '4', color: '#7c3aed', text: 'Spark computes FFT, features, and anomaly scores' },
                { step: '5', color: '#f97316', text: 'Historical data archived in Delta Lake (Unity Catalog)' },
                { step: '6', color: '#a78bfa', text: 'ML models detect anomalies and forecast failures' },
                { step: '7', color: '#6366f1', text: 'Genie AI synthesises findings into plain-language diagnoses' },
              ].map(s => (
                <div key={s.step} style={{ display: 'flex', gap: 10, marginBottom: 10, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 20, height: 20, borderRadius: '50%',
                    background: s.color + '33', border: `1px solid ${s.color}`,
                    color: s.color, fontSize: 10, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}>
                    {s.step}
                  </div>
                  <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.5 }}>{s.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
