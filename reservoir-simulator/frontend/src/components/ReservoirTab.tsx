import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import Grid3D, {
  CellData, PropertyKey, NI, NJ, NK,
  CELL_W, CELL_H, CELL_D, PROPERTY_RANGES,
  getColor, jetColor, norneInitialCells, cellIndex, EdgeLines,
} from './Grid3D'
import * as THREE from 'three'

// ─── ResInsight viewport background ──────────────────────────────────────────
const RI_BG       = '#8DAFC6'   // ResInsight blue-gray viewport
const RI_PANEL    = '#1E2832'   // dark panel background
const RI_PANEL2   = '#263040'   // slightly lighter panel
const RI_BORDER   = '#374858'   // panel border
const RI_TEXT     = '#D8E8F0'   // primary text
const RI_MUTED    = '#7A9AB0'   // secondary text
const RI_ACTIVE   = '#4AB8FF'   // highlight / active
const RI_TREEBG   = '#161E28'   // project tree background
const RI_LEGBG    = 'rgba(245,250,255,0.95)' // legend background (light)

// ─── Norne well definitions ───────────────────────────────────────────────────
const WELL_COLORS = ['#00E676', '#40C4FF', '#FFAB40', '#CE93D8', '#FF5252', '#26C6DA']
const DEFAULT_WELLS = [
  { name: 'B-2H', type: 'PROD', i: 5,  j: 7 },
  { name: 'D-1H', type: 'PROD', i: 9,  j: 4 },
  { name: 'E-3H', type: 'PROD', i: 5,  j: 3 },
  { name: 'D-2H', type: 'PROD', i: 15, j: 3 },
  { name: 'C-4H', type: 'INJ',  i: 15, j: 7 },
]
const GAP = 1

interface WellDef { name: string; type: string; i: number; j: number; color?: string }
interface Run {
  id: string; scenario_name: string; deck_id: string; status: string
  progress: number; current_timestep: number; total_timesteps: number
  scenario_id?: number
}
interface Props { activeRunId: string | null; onRunSelect: (id: string) => void }

// ─── Well trajectories (ResInsight style: bright cylinders + labels) ─────────
function WellBores({ wells }: { wells: WellDef[] }) {
  const totalH = NK * (CELL_D + GAP) + 20
  const topY   = (CELL_D + GAP) * 2
  return (
    <>
      {wells.map((w) => {
        const color = w.color || '#00E676'
        const x = (w.i - NI/2 + 0.5) * (CELL_W + GAP)
        const z = (w.j - NJ/2 + 0.5) * (CELL_H + GAP)
        const midY = -(NK - 1) * (CELL_D + GAP) / 2
        return (
          <group key={w.name}>
            {/* Bore cylinder */}
            <mesh position={[x, midY, z]}>
              <cylinderGeometry args={[3.5, 3.5, totalH, 10]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4}
                transparent opacity={0.85} roughness={0.3} metalness={0.5} />
            </mesh>
            {/* Wellhead sphere */}
            <mesh position={[x, topY, z]}>
              <sphereGeometry args={[10, 16, 16]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6}
                roughness={0.2} metalness={0.6} />
            </mesh>
            {/* Injector marker */}
            {w.type === 'INJ' && (
              <mesh position={[x, topY + 18, z]} rotation={[Math.PI/4, 0, Math.PI/4]}>
                <boxGeometry args={[14, 14, 14]} />
                <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7}
                  roughness={0.2} metalness={0.5} />
              </mesh>
            )}
          </group>
        )
      })}
    </>
  )
}

// ─── XYZ axis gizmo (HTML overlay) ───────────────────────────────────────────
function AxisGizmo() {
  return (
    <div style={{
      position: 'absolute', bottom: 14, right: 14, zIndex: 10,
      background: 'rgba(14,22,34,0.75)', border: '1px solid #2A3C50',
      borderRadius: 6, padding: '7px 10px', backdropFilter: 'blur(4px)',
      userSelect: 'none',
    }}>
      <div style={{ fontSize: 9, color: RI_MUTED, marginBottom: 5, letterSpacing: '0.08em' }}>ORIENTATION</div>
      {[['X', '#E84040'], ['Y', '#40C84A'], ['Z', '#4080E8']].map(([axis, col]) => (
        <div key={axis} style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
          <div style={{ width: 18, height: 3, background: col, borderRadius: 2 }} />
          <div style={{ width: 6, height: 6, background: col, borderRadius: '50%' }} />
          <span style={{ fontSize: 9, color: col, fontWeight: 700, fontFamily: 'monospace' }}>{axis}</span>
        </div>
      ))}
    </div>
  )
}

// ─── ResInsight vertical color legend ────────────────────────────────────────
function ResInsightLegend({ property, cells }: { property: PropertyKey; cells: CellData[] }) {
  const range   = PROPERTY_RANGES[property]
  const N_TICKS = 9
  const vals    = cells.map(c => c[property] as number)
  const dMin    = vals.length ? Math.min(...vals) : range.min
  const dMax    = vals.length ? Math.max(...vals) : range.max
  const span    = dMax - dMin || 1

  const ticks = Array.from({ length: N_TICKS }, (_, i) => {
    const frac  = 1 - i / (N_TICKS - 1)   // top = max
    const value = dMin + frac * span
    const t     = (value - range.min) / (range.max - range.min)
    const c     = jetColor(t)
    return { value, hex: '#' + new THREE.Color(c.r, c.g, c.b).getHexString() }
  })

  const gradStops = Array.from({ length: 64 }, (_, i) => {
    const t = 1 - i / 63
    const c = jetColor(t * (dMax - range.min) / (range.max - range.min) + (dMin - range.min) / (range.max - range.min))
    return `#${new THREE.Color(c.r, c.g, c.b).getHexString()} ${((1 - t) * 100).toFixed(1)}%`
  }).join(', ')

  const fmt = (v: number) => property === 'pressure' ? v.toFixed(1) : v.toFixed(3)

  return (
    <div style={{
      background: RI_LEGBG,
      border: '1px solid #B8CCE0',
      borderRadius: 5,
      padding: '10px 8px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
    }}>
      {/* Header */}
      <div style={{ fontSize: 10, fontWeight: 700, color: '#1A2C3C', fontFamily: 'sans-serif', marginBottom: 2 }}>
        Cell Result
      </div>
      <div style={{ fontSize: 9, color: '#3A5A70', fontFamily: 'sans-serif', marginBottom: 10, lineHeight: 1.3 }}>
        {range.label}
        {range.unit && <span style={{ color: '#5A7A90' }}> ({range.unit})</span>}
      </div>

      {/* Color bar + ticks */}
      <div style={{ display: 'flex', gap: 5, height: 210 }}>
        {/* Gradient bar */}
        <div style={{
          width: 20, flexShrink: 0, borderRadius: 2,
          background: `linear-gradient(to bottom, ${gradStops})`,
          border: '1px solid #B0C8DC',
        }} />

        {/* Tick marks + labels */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          justifyContent: 'space-between', paddingTop: 0,
        }}>
          {ticks.map((tick, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <div style={{ width: 6, height: 1, background: '#8AAABB', flexShrink: 0 }} />
              <span style={{
                fontSize: 8.5, color: '#1A3040', fontFamily: 'monospace',
                whiteSpace: 'nowrap', fontWeight: idx === 0 || idx === N_TICKS-1 ? 700 : 400,
              }}>
                {fmt(tick.value)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Mapping type footer */}
      <div style={{
        marginTop: 8, fontSize: 8, color: '#6A8A9A', fontFamily: 'sans-serif',
        borderTop: '1px solid #CCE0EC', paddingTop: 6,
      }}>
        ≡ Continuous Linear  ·  {N_TICKS} levels
      </div>
    </div>
  )
}

// ─── Left project tree ────────────────────────────────────────────────────────
function ProjectTree({
  visibleK, setVisibleK, wells, property, onProperty,
}: {
  visibleK: Set<number>; setVisibleK: (s: Set<number>) => void
  wells: WellDef[]; property: PropertyKey; onProperty: (p: PropertyKey) => void
}) {
  const [openGrid, setOpenGrid] = useState(true)
  const [openWells, setOpenWells] = useState(true)
  const [openResults, setOpenResults] = useState(true)

  const layerColors = ['#4AB8FF', '#7DE08A', '#FFCC44', '#FF8C44', '#FF5252']

  const toggleK = (k: number) => {
    const next = new Set(visibleK)
    if (next.has(k)) { if (next.size > 1) next.delete(k) } else next.add(k)
    setVisibleK(next)
  }

  const treeRow = (depth: number, content: React.ReactNode, onClick?: () => void) => (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 4,
        paddingLeft: 8 + depth * 14, paddingRight: 8,
        paddingTop: 3, paddingBottom: 3,
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 3, fontSize: 11, color: RI_TEXT,
        fontFamily: 'system-ui, sans-serif',
      }}
      onMouseEnter={e => onClick && ((e.currentTarget as HTMLElement).style.background = 'rgba(74,184,255,0.12)')}
      onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
    >
      {content}
    </div>
  )

  const expandBtn = (open: boolean) => (
    <span style={{ fontSize: 9, color: RI_MUTED, width: 10, display: 'inline-block' }}>
      {open ? '▼' : '▶'}
    </span>
  )

  return (
    <div style={{ height: '100%', overflowY: 'auto', fontSize: 11 }}>
      {/* Header */}
      <div style={{
        padding: '8px 10px', fontSize: 10, fontWeight: 700, letterSpacing: '0.07em',
        color: RI_MUTED, borderBottom: `1px solid ${RI_BORDER}`, fontFamily: 'monospace',
      }}>
        PROJECT TREE
      </div>

      <div style={{ padding: '4px 0' }}>
        {/* Root */}
        {treeRow(0,
          <><span style={{ fontSize: 13, marginRight: 4 }}>🗂</span>
            <span style={{ fontWeight: 600, color: '#C8E0F0' }}>Norne Field</span></>,
        )}

        {/* Grid section */}
        {treeRow(1,
          <>{expandBtn(openGrid)}<span style={{ marginLeft: 3 }}>📊</span>
            <span style={{ marginLeft: 4 }}>Grid Model</span>
            <span style={{ marginLeft: 6, fontSize: 9, color: RI_MUTED }}>20×10×5</span></>,
          () => setOpenGrid(o => !o),
        )}
        {openGrid && Array.from({ length: NK }, (_, k) => (
          <div key={k}
            onClick={() => toggleK(k)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              paddingLeft: 8 + 3 * 14, paddingRight: 8,
              paddingTop: 2, paddingBottom: 2,
              cursor: 'pointer', borderRadius: 3,
              background: visibleK.has(k) ? 'rgba(74,184,255,0.08)' : 'transparent',
            }}
            onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(74,184,255,0.14)')}
            onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = visibleK.has(k) ? 'rgba(74,184,255,0.08)' : 'transparent')}
          >
            <div style={{
              width: 11, height: 11, borderRadius: 2, flexShrink: 0,
              border: `1px solid ${visibleK.has(k) ? layerColors[k] : RI_BORDER}`,
              background: visibleK.has(k) ? layerColors[k] + '44' : 'transparent',
            }}>
              {visibleK.has(k) && (
                <div style={{ width: 7, height: 7, margin: '1px auto', background: layerColors[k], borderRadius: 1 }} />
              )}
            </div>
            <span style={{ fontSize: 10, color: visibleK.has(k) ? RI_TEXT : RI_MUTED }}>
              Layer {k + 1} (K={k + 1})
            </span>
            <div style={{ width: 8, height: 8, background: layerColors[k], borderRadius: '50%', marginLeft: 'auto' }} />
          </div>
        ))}

        {/* Divider */}
        <div style={{ height: 1, background: RI_BORDER, margin: '5px 8px' }} />

        {/* Wells */}
        {treeRow(1,
          <>{expandBtn(openWells)}<span style={{ marginLeft: 3 }}>🔧</span>
            <span style={{ marginLeft: 4 }}>Simulation Wells</span></>,
          () => setOpenWells(o => !o),
        )}
        {openWells && wells.map((w, idx) => (
          treeRow(2,
            <>
              <div style={{
                width: 9, height: 9, borderRadius: w.type === 'INJ' ? 2 : '50%',
                background: w.color || WELL_COLORS[idx], flexShrink: 0,
              }} />
              <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: 10.5 }}>{w.name}</span>
              <span style={{
                marginLeft: 'auto', fontSize: 8, padding: '1px 4px', borderRadius: 2,
                background: w.type === 'INJ' ? '#FF525222' : '#00E67622',
                color: w.type === 'INJ' ? '#FF7A7A' : '#00E676',
                border: `1px solid ${w.type === 'INJ' ? '#FF5252' : '#00E676'}44`,
                fontWeight: 700,
              }}>{w.type}</span>
            </>,
          )
        ))}

        {/* Divider */}
        <div style={{ height: 1, background: RI_BORDER, margin: '5px 8px' }} />

        {/* Results */}
        {treeRow(1,
          <>{expandBtn(openResults)}<span style={{ marginLeft: 3 }}>📈</span>
            <span style={{ marginLeft: 4 }}>Cell Results</span></>,
          () => setOpenResults(o => !o),
        )}
        {openResults && (['pressure', 'so', 'sw', 'sg'] as PropertyKey[]).map(p => {
          const labels: Record<PropertyKey, string> = { pressure: 'Pressure', so: 'Oil Sat. (So)', sw: 'Water Sat. (Sw)', sg: 'Gas Sat. (Sg)' }
          const active = property === p
          return (
            <div key={p}
              onClick={() => onProperty(p)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                paddingLeft: 8 + 3 * 14, paddingRight: 8,
                paddingTop: 3, paddingBottom: 3, cursor: 'pointer',
                background: active ? 'rgba(74,184,255,0.18)' : 'transparent',
                borderRadius: 3, borderLeft: active ? `2px solid ${RI_ACTIVE}` : '2px solid transparent',
              }}
            >
              <span style={{ fontSize: 9, color: active ? RI_ACTIVE : RI_MUTED }}>
                {active ? '●' : '○'}
              </span>
              <span style={{ fontSize: 10, color: active ? RI_ACTIVE : RI_TEXT, fontWeight: active ? 600 : 400 }}>
                {labels[p]}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Right info panel — cell result detail (appears on click) ─────────────────
function CellInfoPanel({ cell, cells, property }: { cell: CellData | null; cells: CellData[]; property: PropertyKey }) {
  if (!cell) {
    return (
      <div style={{
        background: RI_LEGBG, border: '1px solid #B8CCE0', borderRadius: 5,
        padding: '10px 10px', textAlign: 'center',
        color: '#8AAABB', fontSize: 9, fontFamily: 'sans-serif',
      }}>
        Click a cell to inspect
      </div>
    )
  }
  const items = [
    { label: 'Cell',     value: `I=${cell.i+1}  J=${cell.j+1}  K=${cell.k+1}`, color: '#1A3040' },
    { label: 'Pressure', value: `${cell.pressure.toFixed(1)} bar`,               color: '#D04040' },
    { label: 'Oil Sat.', value: cell.so.toFixed(4),                              color: '#40A040' },
    { label: 'Water Sat.', value: cell.sw.toFixed(4),                            color: '#2060C0' },
    { label: 'Gas Sat.', value: cell.sg.toFixed(4),                              color: '#C08020' },
  ]
  return (
    <div style={{
      background: RI_LEGBG, border: '1px solid #B8CCE0', borderRadius: 5,
      padding: '10px 8px', boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: '#1A2C3C', marginBottom: 8, fontFamily: 'sans-serif' }}>
        Result Info
      </div>
      {items.map(item => (
        <div key={item.label} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
          marginBottom: 6, gap: 6,
        }}>
          <span style={{ fontSize: 9, color: '#5A7A90', fontFamily: 'sans-serif', flexShrink: 0 }}>{item.label}</span>
          <span style={{ fontSize: 9.5, color: item.color, fontFamily: 'monospace', fontWeight: 600, textAlign: 'right' }}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Sparkline ────────────────────────────────────────────────────────────────
function Sparkline({ data, color, height = 44 }: { data: number[]; color: string; height?: number }) {
  if (data.length < 2) return <div style={{ height, background: RI_PANEL2, borderRadius: 4 }} />
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1
  const W = 100, H = 100
  const pts = data.map((v, i) => `${(i/(data.length-1))*W},${H - ((v-min)/range)*H*0.85 - H*0.075}`)
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
      style={{ display: 'block', borderRadius: 4, background: RI_PANEL2 }}>
      <defs>
        <linearGradient id={`sp-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.45" />
          <stop offset="100%" stopColor={color} stopOpacity="0.03" />
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${pts.join(' ')} ${W},${H}`} fill={`url(#sp-${color.replace('#','')})`} />
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="2.5" />
    </svg>
  )
}

// ─── Main ReservoirTab ────────────────────────────────────────────────────────
export default function ReservoirTab({ activeRunId, onRunSelect }: Props) {
  const [runs,            setRuns]            = useState<Run[]>([])
  const [selectedRun,     setSelectedRun]     = useState<string>(activeRunId || '')
  const [property,        setProperty]        = useState<PropertyKey>('so')
  const [timestep,        setTimestep]        = useState(0)
  const [maxTimestep,     setMaxTimestep]     = useState(40)
  const [playing,         setPlaying]         = useState(false)
  const [cells,           setCells]           = useState<CellData[]>(() => norneInitialCells())
  const [runStatus,       setRunStatus]       = useState<string>('')
  const [progress,        setProgress]        = useState(0)
  const [fieldData,       setFieldData]       = useState<Record<string, number>>({})
  const [wells,           setWells]           = useState<WellDef[]>(DEFAULT_WELLS.map((w, i) => ({ ...w, color: WELL_COLORS[i] })))
  const [visibleK,        setVisibleK]        = useState<Set<number>>(new Set([0, 1, 2, 3, 4]))
  const [oilHistory,      setOilHistory]      = useState<number[]>([])
  const [pressureHistory, setPressureHistory] = useState<number[]>([])
  const [selectedCell,    setSelectedCell]    = useState<CellData | null>(null)
  const wsRef      = useRef<WebSocket | null>(null)
  const playRef    = useRef(false)
  const snapshotsRef = useRef<Record<number, CellData[]>>({ 0: norneInitialCells() })

  // ── Load runs ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try { const d = await fetch('/api/runs').then(r => r.json()); setRuns(Array.isArray(d) ? d : []) }
      catch { /* ignore */ }
    }
    load(); const iv = setInterval(load, 6000); return () => clearInterval(iv)
  }, [])

  useEffect(() => { if (activeRunId) setSelectedRun(activeRunId) }, [activeRunId])

  // ── When run selected: load metadata + connect WS ─────────────────────────
  useEffect(() => {
    if (!selectedRun) return
    setOilHistory([]); setPressureHistory([])
    snapshotsRef.current = { 0: norneInitialCells() }
    setCells(norneInitialCells()); setTimestep(0)

    const loadMeta = async () => {
      try {
        const runData = await fetch(`/api/runs/${selectedRun}`).then(r => r.json())
        setRunStatus(runData.status || ''); setMaxTimestep(runData.total_timesteps || 40); setProgress(runData.progress || 0)
        if (runData.scenario_id) {
          const scData = await fetch(`/api/scenarios/${runData.scenario_id}`).then(r => r.json())
          if (scData.config?.wells)
            setWells(scData.config.wells.map((w: WellDef, i: number) => ({ ...w, color: WELL_COLORS[i % WELL_COLORS.length] })))
        }
      } catch { /* ignore */ }
    }
    loadMeta()

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/simulate/${selectedRun}`)
    wsRef.current = ws
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'grid_update') {
          const ts: number = msg.timestep || 0
          setMaxTimestep(prev => Math.max(prev, ts)); setTimestep(ts); setProgress(msg.progress || 0)
          if (msg.field) {
            setFieldData(msg.field)
            setOilHistory(prev => [...prev.slice(-79), msg.field.field_oil_rate_stbd])
            setPressureHistory(prev => [...prev.slice(-79), msg.field.field_avg_pressure_bar])
          }
          setCells(prev => {
            const map = new Map(prev.map(c => [cellIndex(c.i, c.j, c.k), c]))
            for (const c of (msg.cells || [])) map.set(cellIndex(c.i, c.j, c.k), c)
            const next = Array.from(map.values())
            snapshotsRef.current[ts] = [...next]; return next
          })
        } else if (msg.type === 'complete') {
          setRunStatus('SUCCEEDED'); setProgress(100)
          setTimestep(0); setTimeout(() => setPlaying(true), 800)
        } else if (msg.type === 'status') {
          setRunStatus(msg.data?.status || '')
        }
      } catch { /* ignore */ }
    }
    ws.onerror = () => {}
    return () => { ws.close(); wsRef.current = null }
  }, [selectedRun])

  // ── Playback ───────────────────────────────────────────────────────────────
  useEffect(() => {
    playRef.current = playing
    if (!playing) return
    const iv = setInterval(() => {
      if (!playRef.current) return
      setTimestep(prev => {
        if (prev >= maxTimestep) { setPlaying(false); playRef.current = false; return prev }
        return prev + 1
      })
    }, 300)
    return () => clearInterval(iv)
  }, [playing, maxTimestep])

  // ── Snapshot scrubbing ─────────────────────────────────────────────────────
  useEffect(() => {
    if (runStatus === 'RUNNING') return
    const snap = snapshotsRef.current[timestep]
    if (snap) { setCells(snap); return }
    if (!selectedRun || timestep === 0) return
    fetch(`/api/runs/${selectedRun}/grid/${timestep}`)
      .then(r => r.json()).then(d => { if (d.cells) { setCells(d.cells); snapshotsRef.current[timestep] = d.cells } })
      .catch(() => {})
  }, [timestep, selectedRun, runStatus])

  const handleRunChange = useCallback((id: string) => { setSelectedRun(id); onRunSelect(id) }, [onRunSelect])

  const day = Math.round(timestep * 91.25)

  const stats = useMemo(() => {
    if (!cells.length) return null
    const ps = cells.map(c => c.pressure), sos = cells.map(c => c.so), sws = cells.map(c => c.sw)
    return {
      avgP:  (ps.reduce((a,b)=>a+b,0)/ps.length).toFixed(1),
      avgSo: (sos.reduce((a,b)=>a+b,0)/sos.length).toFixed(3),
      avgSw: (sws.reduce((a,b)=>a+b,0)/sws.length).toFixed(3),
      minP:  Math.min(...ps).toFixed(0), maxP: Math.max(...ps).toFixed(0),
    }
  }, [cells])

  const statusColor: Record<string, string> = {
    RUNNING: '#4AB8FF', SUCCEEDED: '#00E676', FAILED: '#FF5252', PENDING: '#FFCC44',
  }

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 0,
      height: 'calc(100vh - 120px)', minHeight: 700,
      background: RI_PANEL, border: `1px solid ${RI_BORDER}`, borderRadius: 8, overflow: 'hidden',
    }}>

      {/* ── ResInsight-style toolbar ── */}
      <div style={{
        background: RI_PANEL2, borderBottom: `1px solid ${RI_BORDER}`,
        padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
      }}>
        {/* Cell Result selector */}
        <span style={{ fontSize: 9, color: RI_MUTED, letterSpacing: '0.07em', fontFamily: 'monospace' }}>CELL RESULT</span>
        <div style={{ display: 'flex', gap: 2, background: '#0D1520', borderRadius: 4, padding: 2 }}>
          {(['pressure', 'so', 'sw', 'sg'] as PropertyKey[]).map(p => {
            const labels: Record<PropertyKey, string> = { pressure: 'Pressure', so: 'Oil Sat', sw: 'Water Sat', sg: 'Gas Sat' }
            const active = property === p
            return (
              <button key={p} onClick={() => setProperty(p)} style={{
                padding: '3px 10px', fontSize: 10, borderRadius: 3,
                border: `1px solid ${active ? RI_ACTIVE : 'transparent'}`,
                background: active ? 'rgba(74,184,255,0.18)' : 'transparent',
                color: active ? RI_ACTIVE : RI_MUTED,
                cursor: 'pointer', fontFamily: 'system-ui',
              }}>
                {labels[p]}
              </button>
            )
          })}
        </div>

        <div style={{ width: 1, height: 20, background: RI_BORDER }} />

        {/* Playback */}
        <button onClick={() => setTimestep(0)} style={{ ...tbBtn, fontSize: 13 }}>⏮</button>
        <button onClick={() => setTimestep(t => Math.max(0, t-1))} style={{ ...tbBtn, fontSize: 13 }}>⏴</button>
        <button onClick={() => setPlaying(!playing)} style={{
          ...tbBtn, fontSize: 12,
          background: playing ? 'rgba(255,82,82,0.18)' : 'rgba(0,230,118,0.18)',
          borderColor: playing ? '#FF5252' : '#00E676',
          color: playing ? '#FF5252' : '#00E676',
          padding: '3px 14px',
        }}>
          {playing ? '⏸ Pause' : '▶ Play'}
        </button>
        <button onClick={() => setTimestep(t => Math.min(maxTimestep, t+1))} style={{ ...tbBtn, fontSize: 13 }}>⏵</button>
        <button onClick={() => setTimestep(maxTimestep)} style={{ ...tbBtn, fontSize: 13 }}>⏭</button>

        <div style={{ width: 1, height: 20, background: RI_BORDER }} />

        {/* Timestep slider */}
        <input type="range" min={0} max={maxTimestep} value={timestep}
          onChange={e => { setPlaying(false); setTimestep(Number(e.target.value)) }}
          style={{ flex: 1, minWidth: 100, maxWidth: 240, accentColor: RI_ACTIVE }}
        />
        <span style={{ fontSize: 10, fontFamily: 'monospace', color: RI_TEXT, whiteSpace: 'nowrap' }}>
          Step {timestep}/{maxTimestep}
          <span style={{ color: RI_MUTED }}> · Day {day}</span>
        </span>

        <div style={{ width: 1, height: 20, background: RI_BORDER }} />

        {/* Run selector */}
        <select value={selectedRun} onChange={e => handleRunChange(e.target.value)} style={{
          background: '#0D1520', border: `1px solid ${RI_BORDER}`,
          color: RI_TEXT, borderRadius: 4, padding: '3px 8px', fontSize: 10,
        }}>
          <option value="">— No run selected —</option>
          {runs.map(r => (
            <option key={r.id} value={r.id}>{r.scenario_name} · {r.id}</option>
          ))}
        </select>

        {runStatus && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 3, fontFamily: 'monospace',
            background: (statusColor[runStatus] || RI_MUTED) + '22',
            color: statusColor[runStatus] || RI_MUTED,
            border: `1px solid ${statusColor[runStatus] || RI_BORDER}55`,
          }}>
            {runStatus}
            {runStatus === 'RUNNING' && ` ${progress}%`}
          </span>
        )}
      </div>

      {/* ── Progress bar ── */}
      {runStatus === 'RUNNING' && (
        <div style={{ height: 3, background: '#0D1520' }}>
          <div style={{ height: '100%', width: `${progress}%`, background: RI_ACTIVE, transition: 'width 0.3s ease' }} />
        </div>
      )}

      {/* ── Main: tree | 3D | info ── */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '185px 1fr 220px', minHeight: 0 }}>

        {/* Left: Project tree */}
        <div style={{ background: RI_TREEBG, borderRight: `1px solid ${RI_BORDER}`, overflowY: 'auto' }}>
          <ProjectTree
            visibleK={visibleK} setVisibleK={setVisibleK}
            wells={wells} property={property} onProperty={setProperty}
          />
        </div>

        {/* Centre: 3D viewport */}
        <div style={{ position: 'relative', overflow: 'hidden' }}>
          {/* ResInsight info overlay (top-left) */}
          <div style={{
            position: 'absolute', top: 10, left: 10, zIndex: 10,
            background: 'rgba(13,22,34,0.82)', border: '1px solid #2A3C50',
            borderRadius: 5, padding: '6px 10px', backdropFilter: 'blur(4px)',
            fontFamily: 'monospace',
          }}>
            <div style={{ fontSize: 8.5, color: RI_MUTED, letterSpacing: '0.07em' }}>
              NORNE FIELD · RES FLOW ENGINE
            </div>
            <div style={{ fontSize: 10, color: RI_TEXT, marginTop: 2 }}>
              Grid: {NI}×{NJ}×{NK} &nbsp;·&nbsp; {NI*NJ*NK} cells
            </div>
            {stats && (
              <div style={{ fontSize: 9.5, color: RI_ACTIVE, marginTop: 2 }}>
                {property === 'pressure'
                  ? `P̄ = ${stats.avgP} bar  [${stats.minP}–${stats.maxP}]`
                  : property === 'so' ? `S̄o = ${stats.avgSo}`
                  : property === 'sw' ? `S̄w = ${stats.avgSw}`
                  : 'Gas Saturation'}
              </div>
            )}
          </div>

          {/* Timestep label (top-right) */}
          <div style={{
            position: 'absolute', top: 10, right: 10, zIndex: 10,
            background: 'rgba(13,22,34,0.82)', border: '1px solid #2A3C50',
            borderRadius: 5, padding: '5px 10px', backdropFilter: 'blur(4px)',
            fontFamily: 'monospace', textAlign: 'right',
          }}>
            <div style={{ fontSize: 8.5, color: RI_MUTED }}>TIME STEP</div>
            <div style={{ fontSize: 13, color: RI_TEXT, fontWeight: 700 }}>
              {timestep} <span style={{ fontSize: 9, color: RI_MUTED }}>/ {maxTimestep}</span>
            </div>
            <div style={{ fontSize: 8.5, color: RI_MUTED }}>Day {day}</div>
          </div>

          {/* XYZ Gizmo */}
          <AxisGizmo />

          {/* Three.js Canvas — ResInsight blue-gray background */}
          <Canvas
            camera={{ position: [1000, 580, 720], fov: 42, near: 1, far: 14000 }}
            style={{ height: '100%' }}
          >
            <color attach="background" args={[RI_BG]} />
            <ambientLight intensity={0.80} />
            <directionalLight position={[1400, 1200, 700]} intensity={0.65} />
            <directionalLight position={[-500, 800, -400]} intensity={0.25} color="#D0E8FF" />
            <directionalLight position={[0, -600, 0]} intensity={0.12} color="#A0C0FF" />
            <Grid3D cells={cells} property={property} visibleK={visibleK} onCellClick={setSelectedCell} />
            <EdgeLines visibleK={visibleK} />
            <WellBores wells={wells} />
            <OrbitControls
              enableDamping dampingFactor={0.08}
              minDistance={150} maxDistance={7000}
              target={[0, -(NK * (CELL_D+1)) / 2, 0]}
            />
          </Canvas>
        </div>

        {/* Right: legend + cell info */}
        <div style={{
          background: '#1A2535', borderLeft: `1px solid ${RI_BORDER}`,
          display: 'flex', flexDirection: 'column', gap: 10,
          padding: 10, overflowY: 'auto',
        }}>
          <ResInsightLegend property={property} cells={cells} />
          <CellInfoPanel cell={selectedCell} cells={cells} property={property} />

          {/* Field rates (when simulation active) */}
          {fieldData.field_oil_rate_stbd !== undefined && (
            <div style={{
              background: RI_LEGBG, border: '1px solid #B8CCE0',
              borderRadius: 5, padding: '10px 8px',
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#1A2C3C', marginBottom: 8, fontFamily: 'sans-serif' }}>
                Field Rates
              </div>
              {[
                { label: 'Oil Rate',   v: fieldData.field_oil_rate_stbd?.toFixed(0),   unit: 'Sm³/d',  color: '#2A7A2A' },
                { label: 'Gas Rate',   v: fieldData.field_gas_rate_mscfd?.toFixed(0),  unit: 'MSm³/d', color: '#A07020' },
                { label: 'Water Rate', v: fieldData.field_water_rate_stbd?.toFixed(0), unit: 'Sm³/d',  color: '#2050A0' },
                { label: 'Water Cut',  v: fieldData.water_cut_pct?.toFixed(1),          unit: '%',      color: '#4080C0' },
                { label: 'Avg Press.', v: fieldData.field_avg_pressure_bar?.toFixed(1), unit: 'bar',    color: '#802020' },
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                  <span style={{ fontSize: 9, color: '#5A7A90', fontFamily: 'sans-serif' }}>{item.label}</span>
                  <span style={{ fontSize: 9.5, color: item.color, fontFamily: 'monospace', fontWeight: 700 }}>
                    {item.v} <span style={{ fontWeight: 400, color: '#8AAABB' }}>{item.unit}</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom: sparklines ── */}
      {(oilHistory.length > 1 || pressureHistory.length > 1) && (
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
          padding: '8px 10px', background: RI_PANEL2, borderTop: `1px solid ${RI_BORDER}`,
        }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 9, color: RI_MUTED, letterSpacing: '0.06em', fontFamily: 'monospace' }}>
                FIELD OIL RATE
              </span>
              <span style={{ fontSize: 10, color: '#00E676', fontFamily: 'monospace', fontWeight: 700 }}>
                {oilHistory[oilHistory.length-1]?.toFixed(0)} Sm³/d
              </span>
            </div>
            <Sparkline data={oilHistory} color="#00E676" height={48} />
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 9, color: RI_MUTED, letterSpacing: '0.06em', fontFamily: 'monospace' }}>
                AVG RESERVOIR PRESSURE
              </span>
              <span style={{ fontSize: 10, color: '#4AB8FF', fontFamily: 'monospace', fontWeight: 700 }}>
                {pressureHistory[pressureHistory.length-1]?.toFixed(1)} bar
              </span>
            </div>
            <Sparkline data={pressureHistory} color="#4AB8FF" height={48} />
          </div>
        </div>
      )}
    </div>
  )
}

// toolbar button base style
const tbBtn: React.CSSProperties = {
  background: 'transparent', border: `1px solid ${RI_BORDER}`,
  color: RI_TEXT, borderRadius: 4, padding: '3px 8px',
  fontSize: 10, cursor: 'pointer', fontFamily: 'system-ui',
}
