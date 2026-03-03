import { useState, useEffect, useMemo, useCallback } from 'react'

const WELLS = ['BAKER-001','BAKER-002','CONOCO-7H','MARATHON-15X','SHELL-3D','PIONEER-22S']
const PLOT_H = 680
const DEPTH_W = 54

interface LogData {
  well_id: string; depth_range: [number, number]; sample_count: number
  md: number[]; curves: Record<string, (number | null)[]>
  formations: { formation_name: string; top_md: number; base_md: number; zone_type: string }[]
  has_raw: boolean; has_corrected: boolean; has_derived: boolean
}

// ── SVG log track renderer ──────────────────────────────────────────────────
function buildPath(
  md: number[], vals: (number | null)[], depthMin: number, depthMax: number,
  xMin: number, xMax: number, trackW: number, logScale = false
): string {
  if (!vals || vals.length === 0) return ''
  const yScale = (d: number) => ((d - depthMin) / (depthMax - depthMin)) * PLOT_H
  const xScale = (v: number) => {
    if (logScale) {
      const lmin = Math.log10(Math.max(xMin, 0.001))
      const lmax = Math.log10(Math.max(xMax, 0.001))
      return ((Math.log10(Math.max(v, 0.001)) - lmin) / (lmax - lmin)) * trackW
    }
    return ((v - xMin) / (xMax - xMin)) * trackW
  }
  let path = ''; let pen = false
  for (let i = 0; i < md.length; i++) {
    const d = md[i]; const v = vals[i]
    if (d < depthMin || d > depthMax) { pen = false; continue }
    if (v == null || isNaN(v) || !isFinite(v)) { pen = false; continue }
    const x = Math.max(0, Math.min(trackW, xScale(v)))
    const y = yScale(d)
    path += pen ? `L${x.toFixed(1)},${y.toFixed(1)}` : `M${x.toFixed(1)},${y.toFixed(1)}`
    pen = true
  }
  return path
}

function buildFillPath(
  md: number[], vals: (number | null)[], depthMin: number, depthMax: number,
  xMin: number, xMax: number, trackW: number, fillFrom: 'left' | 'right' = 'left'
): string {
  if (!vals || vals.length === 0) return ''
  const yScale = (d: number) => ((d - depthMin) / (depthMax - depthMin)) * PLOT_H
  const xScale = (v: number) => ((v - xMin) / (xMax - xMin)) * trackW
  const fX = fillFrom === 'left' ? 0 : trackW
  const segments: { y: number; x: number }[] = []
  for (let i = 0; i < md.length; i++) {
    const d = md[i]; const v = vals[i]
    if (d < depthMin || d > depthMax || v == null || isNaN(v)) continue
    segments.push({ y: yScale(d), x: Math.max(0, Math.min(trackW, xScale(v))) })
  }
  if (segments.length < 2) return ''
  let path = `M${fX},${segments[0].y}`
  for (const s of segments) path += `L${s.x},${s.y}`
  path += `L${fX},${segments[segments.length - 1].y}Z`
  return path
}

function buildQcDots(
  md: number[], qc: (number | null)[], depthMin: number, depthMax: number, trackW: number
): { x: number; y: number; color: string }[] {
  if (!qc) return []
  const yScale = (d: number) => ((d - depthMin) / (depthMax - depthMin)) * PLOT_H
  const dots: { x: number; y: number; color: string }[] = []
  for (let i = 0; i < md.length; i++) {
    const d = md[i]; const f = qc[i]
    if (d < depthMin || d > depthMax || !f) continue
    dots.push({
      x: trackW - 6,
      y: yScale(d),
      color: f === 1 ? '#ff4d4f' : f === 2 ? '#ffa940' : f === 3 ? '#722ed1' : '#40a9ff',
    })
  }
  return dots
}

interface TrackProps {
  label: string; subLabel?: string
  xMin: number; xMax: number; logScale?: boolean
  width: number; md: number[]; depthMin: number; depthMax: number
  curves: { vals: (number | null)[] | null; color: string; strokeW?: number; dash?: string; fill?: 'left' | 'right'; fillColor?: string; fillOpacity?: number }[]
  qcFlags?: (number | null)[] | null
  formations?: { formation_name: string; top_md: number; zone_type: string }[]
  xTicks?: number[]
}

function LogTrack({ label, subLabel, xMin, xMax, logScale, width, md, depthMin, depthMax, curves, qcFlags, formations, xTicks }: TrackProps) {
  const paths = useMemo(() => curves.map(c => {
    if (!c.vals) return { line: '', fill: '' }
    return {
      line: buildPath(md, c.vals, depthMin, depthMax, xMin, xMax, width, logScale),
      fill: c.fill ? buildFillPath(md, c.vals, depthMin, depthMax, xMin, xMax, width, c.fill) : '',
    }
  }), [md, curves, depthMin, depthMax, xMin, xMax, width, logScale])

  const qcDots = useMemo(() =>
    qcFlags ? buildQcDots(md, qcFlags, depthMin, depthMax, width) : []
  , [md, qcFlags, depthMin, depthMax, width])

  const formLines = useMemo(() => {
    if (!formations) return []
    const yScale = (d: number) => ((d - depthMin) / (depthMax - depthMin)) * PLOT_H
    return formations
      .filter(f => f.top_md >= depthMin - 50 && f.top_md <= depthMax + 50)
      .map(f => ({ y: yScale(f.top_md), name: f.formation_name, type: f.zone_type }))
  }, [formations, depthMin, depthMax])

  const ticks = useMemo(() => {
    if (xTicks) return xTicks
    if (logScale) {
      const result = []
      for (let p = Math.floor(Math.log10(xMin)); p <= Math.ceil(Math.log10(xMax)); p++) {
        for (const m of [1, 2, 5]) {
          const v = m * Math.pow(10, p)
          if (v >= xMin && v <= xMax) result.push(v)
        }
      }
      return result
    }
    const step = (xMax - xMin) / 4
    return [0, 1, 2, 3, 4].map(i => xMin + i * step)
  }, [xMin, xMax, logScale, xTicks])

  const xTickPos = (v: number) => {
    if (logScale) {
      const lmin = Math.log10(Math.max(xMin, 0.001))
      const lmax = Math.log10(Math.max(xMax, 0.001))
      return ((Math.log10(Math.max(v, 0.001)) - lmin) / (lmax - lmin)) * width
    }
    return ((v - xMin) / (xMax - xMin)) * width
  }

  const headerH = 42
  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', borderRight: '1px solid var(--border)', flexShrink: 0 }}>
      {/* Track header */}
      <div style={{
        width, height: headerH, background: 'var(--bg-card)', borderBottom: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
        padding: '0 4px',
      }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'center', lineHeight: 1.2 }}>{label}</div>
        {subLabel && <div style={{ fontSize: 9, color: 'var(--text-muted)', textAlign: 'center', marginTop: 2 }}>{subLabel}</div>}
        {/* Scale ticks */}
        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginTop: 3 }}>
          <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {logScale ? xMin.toExponential(0) : xMin.toFixed(0)}
          </span>
          <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {logScale ? xMax.toExponential(0) : xMax.toFixed(0)}
          </span>
        </div>
      </div>
      {/* SVG body */}
      <svg width={width} height={PLOT_H} style={{ background: '#0a0b0e', display: 'block', overflow: 'hidden' }}>
        {/* Grid lines from X ticks */}
        {ticks.map((t, i) => {
          const x = xTickPos(t)
          return x > 1 && x < width - 1 ? (
            <line key={i} x1={x} y1={0} x2={x} y2={PLOT_H} stroke="#1c2030" strokeWidth={1} />
          ) : null
        })}
        {/* Formation top lines */}
        {formLines.map((fl, i) => (
          <g key={i}>
            <line x1={0} y1={fl.y} x2={width} y2={fl.y} stroke="#5a4000" strokeWidth={1} strokeDasharray="3,3" />
          </g>
        ))}
        {/* Fills */}
        {curves.map((c, i) =>
          c.fill && c.vals && paths[i].fill ? (
            <path key={`fill-${i}`} d={paths[i].fill} fill={c.fillColor || c.color} fillOpacity={c.fillOpacity ?? 0.25} />
          ) : null
        )}
        {/* Lines */}
        {curves.map((c, i) =>
          c.vals && paths[i].line ? (
            <path key={`line-${i}`} d={paths[i].line} fill="none" stroke={c.color} strokeWidth={c.strokeW ?? 1.5} strokeDasharray={c.dash} />
          ) : null
        )}
        {/* QC dots */}
        {qcDots.map((d, i) => (
          <circle key={i} cx={d.x} cy={d.y} r={3} fill={d.color} opacity={0.8} />
        ))}
      </svg>
    </div>
  )
}

// Depth track (left axis)
function DepthTrack({ depthMin, depthMax }: { depthMin: number; depthMax: number }) {
  const headerH = 42
  const ticks = useMemo(() => {
    const interval = depthMax - depthMin <= 1000 ? 100 : depthMax - depthMin <= 2000 ? 200 : 500
    const first = Math.ceil(depthMin / interval) * interval
    const result = []
    for (let t = first; t <= depthMax; t += interval) result.push(t)
    return result
  }, [depthMin, depthMax])

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', borderRight: '1px solid var(--border)', flexShrink: 0 }}>
      <div style={{
        width: DEPTH_W, height: headerH, background: 'var(--bg-card)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700 }}>MD (ft)</span>
      </div>
      <svg width={DEPTH_W} height={PLOT_H} style={{ background: '#0d0f14', display: 'block' }}>
        {ticks.map(t => {
          const y = ((t - depthMin) / (depthMax - depthMin)) * PLOT_H
          return (
            <g key={t}>
              <line x1={DEPTH_W - 6} y1={y} x2={DEPTH_W} y2={y} stroke="#555" />
              <text x={DEPTH_W - 8} y={y + 3} textAnchor="end" fontSize={9} fill="#778" fontFamily="monospace">
                {t.toLocaleString()}
              </text>
            </g>
          )
        })}
        {/* Continuous tick marks every 50 ft */}
        {Array.from({ length: Math.floor((depthMax - depthMin) / 50) + 1 }, (_, i) => depthMin + i * 50).map(t => {
          const y = ((t - depthMin) / (depthMax - depthMin)) * PLOT_H
          return <line key={`m${t}`} x1={DEPTH_W - 3} y1={y} x2={DEPTH_W} y2={y} stroke="#333" />
        })}
      </svg>
    </div>
  )
}

// Formation name overlay (rightmost)
function FormationTrack({ formations, depthMin, depthMax }: {
  formations: { formation_name: string; top_md: number; zone_type: string }[]
  depthMin: number; depthMax: number
}) {
  const headerH = 42
  const zoneColors: Record<string, string> = {
    shale: '#5a4000', sand: '#1a3a1a', carbonate: '#1a2a4a', reservoir: '#003322', fluvial: '#2a2a00'
  }
  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', borderRight: '1px solid var(--border)', flexShrink: 0 }}>
      <div style={{
        width: 90, height: headerH, background: 'var(--bg-card)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700 }}>FORMATION</span>
      </div>
      <svg width={90} height={PLOT_H} style={{ background: '#0a0b0e', display: 'block', overflow: 'hidden' }}>
        {formations
          .filter(f => f.top_md <= depthMax && (f.top_md + 200) >= depthMin)
          .map((f, i, arr) => {
            const yTop  = Math.max(0, ((f.top_md - depthMin) / (depthMax - depthMin)) * PLOT_H)
            const nextTop = arr[i + 1]?.top_md ?? depthMax
            const yBot  = Math.min(PLOT_H, ((nextTop - depthMin) / (depthMax - depthMin)) * PLOT_H)
            const midY  = (yTop + yBot) / 2
            const bg    = zoneColors[f.zone_type] || '#111'
            return (
              <g key={f.formation_name}>
                <rect x={0} y={yTop} width={90} height={yBot - yTop} fill={bg} opacity={0.6} />
                <line x1={0} y1={yTop} x2={90} y2={yTop} stroke="#5a4000" strokeWidth={1} />
                {yBot - yTop > 18 && (
                  <text x={4} y={midY + 4} fontSize={9} fill="#aaa" fontFamily="sans-serif"
                    style={{ textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                    {f.formation_name.length > 11 ? f.formation_name.slice(0, 11) + '…' : f.formation_name}
                  </text>
                )}
              </g>
            )
          })}
      </svg>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
interface Props { wellId: string; onWellChange: (id: string) => void }

export default function LogViewerTab({ wellId, onWellChange }: Props) {
  const [data, setData]           = useState<LogData | null>(null)
  const [loading, setLoading]     = useState(false)
  const [depthMin, setDepthMin]   = useState(5000)
  const [depthMax, setDepthMax]   = useState(7000)
  const [mode, setMode]           = useState<'raw' | 'corrected' | 'both'>('both')
  const [showDerived, setShowDerived] = useState(true)

  const loadData = useCallback((wid: string) => {
    setLoading(true)
    fetch(`/api/logs/${wid}`)
      .then(r => r.json())
      .then((d: LogData) => {
        setData(d)
        const dmin = Math.floor(d.depth_range[0] / 100) * 100
        setDepthMin(dmin)
        setDepthMax(Math.min(dmin + 2000, d.depth_range[1]))
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData(wellId) }, [wellId, loadData])

  const window = depthMax - depthMin

  const md  = data?.md  ?? []
  const crv = data?.curves ?? {}

  // Which set of curves to show
  const gr   = mode === 'corrected' ? crv.gr_c   : crv.gr_raw
  const rt   = mode === 'corrected' ? crv.rt_c   : crv.rt_raw
  const rhob = mode === 'corrected' ? crv.rhob_c : crv.rhob_raw
  const nphi = mode === 'corrected' ? crv.nphi_c : crv.nphi_raw
  const dt   = mode === 'corrected' ? crv.dt_c   : crv.dt_raw

  const hasCorr    = data?.has_corrected ?? false
  const hasDerived = data?.has_derived   ?? false
  const formations = data?.formations    ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Well selector */}
        <div className="card" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="label">WELL</span>
          <select value={wellId} onChange={e => { onWellChange(e.target.value); loadData(e.target.value) }} style={{
            background: 'var(--bg-panel)', border: '1px solid var(--border)', color: 'var(--text-primary)',
            borderRadius: 5, padding: '4px 8px', fontSize: 12, outline: 'none',
          }}>
            {WELLS.map(w => <option key={w} value={w}>{w}</option>)}
          </select>
        </div>

        {/* Depth window */}
        <div className="card" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="label">DEPTH</span>
          <input type="number" value={depthMin} step={100}
            onChange={e => setDepthMin(Number(e.target.value))} style={inputStyle} />
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>–</span>
          <input type="number" value={depthMax} step={100}
            onChange={e => setDepthMax(Number(e.target.value))} style={inputStyle} />
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>ft</span>
        </div>

        {/* Zoom presets */}
        <div className="card" style={{ padding: '8px 10px', display: 'flex', gap: 4 }}>
          {[500, 1000, 2000, 5000].map(w => (
            <button key={w} onClick={() => setDepthMax(depthMin + w)} style={{
              background: window === w ? 'var(--blue-dim)' : 'var(--bg-panel)',
              color: window === w ? 'var(--blue)' : 'var(--text-muted)',
              border: `1px solid ${window === w ? 'var(--blue)' : 'var(--border)'}`,
              borderRadius: 4, padding: '3px 9px', fontSize: 11,
            }}>{w} ft</button>
          ))}
        </div>

        {/* Curve mode */}
        <div className="card" style={{ padding: '8px 10px', display: 'flex', gap: 4 }}>
          {(['raw', 'corrected', 'both'] as const).map(m => (
            <button key={m} onClick={() => setMode(m)} disabled={m !== 'raw' && !hasCorr} style={{
              background: mode === m ? 'var(--green-dim)' : 'var(--bg-panel)',
              color: mode === m ? 'var(--green)' : 'var(--text-muted)',
              border: `1px solid ${mode === m ? 'var(--green)' : 'var(--border)'}`,
              borderRadius: 4, padding: '3px 9px', fontSize: 11, textTransform: 'capitalize',
            }}>{m}</button>
          ))}
        </div>

        {hasDerived && (
          <button onClick={() => setShowDerived(d => !d)} style={{
            background: showDerived ? 'var(--gold-dim)' : 'var(--bg-card)',
            color: showDerived ? 'var(--gold)' : 'var(--text-muted)',
            border: `1px solid ${showDerived ? 'var(--gold)' : 'var(--border)'}`,
            borderRadius: 6, padding: '6px 12px', fontSize: 11, fontWeight: 600,
          }}>⭐ Derived curves</button>
        )}

        {loading && <span className="spinner" />}

        {data && (
          <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
            {data.sample_count.toLocaleString()} samples ·
            {data.has_corrected ? ' ✓ Corrected' : ' ⚠ Raw only'} ·
            {data.has_derived   ? ' ⭐ Derived' : ''}
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11 }}>
        {[
          { color: 'var(--gr-color)',   label: 'GR (API)' },
          { color: 'var(--rt-color)',   label: 'RT (Ω·m)' },
          { color: 'var(--rhob-color)', label: 'RHOB (g/cc)' },
          { color: 'var(--nphi-color)', label: 'NPHI (v/v)' },
          { color: 'var(--dt-color)',   label: 'DT (μs/ft)' },
          { color: 'var(--vcl-color)',  label: 'VCL' },
          { color: 'var(--phi-color)',  label: 'φ_eff' },
          { color: 'var(--sw-color)',   label: 'Sw' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 20, height: 2, background: l.color }} />
            <span style={{ color: 'var(--text-muted)' }}>{l.label}</span>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, fontSize: 10, alignItems: 'center' }}>
          {[['🔴','Spike (QC=1)'],['🟠','Range (QC=2)'],['🟣','Gap (QC=3)']].map(([d, l]) => (
            <span key={l as string} style={{ color: 'var(--text-muted)' }}>{d} {l as string}</span>
          ))}
        </div>
      </div>

      {/* Log plot */}
      {!data || loading ? (
        <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span className="spinner" />
        </div>
      ) : (
        <div className="card" style={{ overflowX: 'auto', padding: 0 }}>
          <div style={{ display: 'inline-flex', minWidth: '100%' }}>
            <DepthTrack depthMin={depthMin} depthMax={depthMax} />

            {/* Track 1: GR */}
            <LogTrack label="GR" subLabel="0 ── 150 API" xMin={0} xMax={150} width={130}
              md={md} depthMin={depthMin} depthMax={depthMax}
              formations={formations} qcFlags={crv.gr_qc}
              curves={[
                { vals: gr, color: 'var(--gr-color)', fill: 'left', fillColor: '#2d3d1a', fillOpacity: 0.55 },
                ...(mode === 'both' && crv.gr_c ? [{ vals: crv.gr_c, color: '#b7eb8f', strokeW: 1, dash: '4,2' }] : [])
              ]}
            />

            {/* Track 2: SP / Caliper */}
            <LogTrack label="SP / CALI" subLabel="SP(mV) | Cali(in)" xMin={-120} xMax={40} width={90}
              md={md} depthMin={depthMin} depthMax={depthMax}
              curves={[
                { vals: crv.sp_raw,   color: '#faad14' },
                { vals: crv.cali_raw, color: '#69b1ff', strokeW: 1, dash: '3,3' },
              ]}
            />

            {/* Track 3: Resistivity (log scale) */}
            <LogTrack label="RT / RXO" subLabel="0.1 ── 1000 Ω·m" xMin={0.1} xMax={1000} logScale width={130}
              md={md} depthMin={depthMin} depthMax={depthMax}
              formations={formations} qcFlags={crv.rt_qc}
              curves={[
                { vals: rt,       color: 'var(--rt-color)', strokeW: 2 },
                { vals: crv.rxo_raw, color: '#ffd591', strokeW: 1, dash: '4,2' },
                ...(mode === 'both' && crv.rt_c ? [{ vals: crv.rt_c, color: '#ff9c6e', strokeW: 1, dash: '2,3' }] : [])
              ]}
            />

            {/* Track 4: RHOB / NPHI (density-neutron crossplot) */}
            <LogTrack label="RHOB / NPHI" subLabel="ρ:1.65-2.65 | N:0.45-(-0.15)" xMin={1.65} xMax={2.65} width={145}
              md={md} depthMin={depthMin} depthMax={depthMax}
              formations={formations} qcFlags={crv.rhob_qc}
              curves={[
                { vals: rhob, color: 'var(--rhob-color)', strokeW: 2 },
                // NPHI overlaid on same axis (remapped to 0.45→1.65 and -0.15→2.65)
                { vals: (nphi && nphi.map(v => v !== null ? 2.65 - (v + 0.15) / 0.60 * (2.65 - 1.65) : null)),
                  color: 'var(--nphi-color)', strokeW: 2 },
                ...(mode === 'both' && crv.rhob_c ? [{ vals: crv.rhob_c, color: '#d3adf7', strokeW: 1, dash: '3,2' }] : [])
              ]}
            />

            {/* Track 5: DT (Sonic) */}
            <LogTrack label="DT" subLabel="140 ── 40 μs/ft" xMin={40} xMax={140} width={100}
              md={md} depthMin={depthMin} depthMax={depthMax}
              qcFlags={crv.dt_qc}
              curves={[
                { vals: dt, color: 'var(--dt-color)', strokeW: 2 },
                ...(mode === 'both' && crv.dt_c ? [{ vals: crv.dt_c, color: '#87e8de', strokeW: 1, dash: '4,2' }] : [])
              ]}
            />

            {/* Track 6: PEF */}
            <LogTrack label="PEF" subLabel="0 ── 6 b/e" xMin={0} xMax={6} width={80}
              md={md} depthMin={depthMin} depthMax={depthMax}
              curves={[{ vals: crv.pef_raw, color: '#ff85c2' }]}
            />

            {/* Track 7: Derived (only when gold layer) */}
            {hasDerived && showDerived && (
              <LogTrack label="VCL / φ / Sw" subLabel="0 ── 1 (fraction)" xMin={0} xMax={1} width={130}
                md={md} depthMin={depthMin} depthMax={depthMax}
                formations={formations}
                curves={[
                  { vals: crv.vcl,     color: 'var(--vcl-color)', fill: 'left', fillColor: '#333', fillOpacity: 0.7 },
                  { vals: crv.phi_eff, color: 'var(--phi-color)', fill: 'left', fillColor: '#003399', fillOpacity: 0.4 },
                  { vals: crv.sw,      color: 'var(--sw-color)',  strokeW: 2 },
                ]}
              />
            )}

            {/* Formation column */}
            <FormationTrack formations={formations} depthMin={depthMin} depthMax={depthMax} />
          </div>
        </div>
      )}

      {/* Formation legend */}
      {formations.length > 0 && (
        <div className="card" style={{ padding: '10px 14px' }}>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="label">FORMATIONS:</span>
            {formations.map(f => {
              const inView = f.top_md >= depthMin - 200 && f.top_md <= depthMax + 200
              return (
                <button key={f.formation_name} onClick={() => {
                  const w = depthMax - depthMin
                  setDepthMin(Math.max(5000, f.top_md - 100))
                  setDepthMax(Math.max(5000, f.top_md - 100) + w)
                }} style={{
                  background: inView ? 'var(--amber-dim)' : 'transparent',
                  color: inView ? 'var(--amber)' : 'var(--text-muted)',
                  border: `1px solid ${inView ? 'var(--amber)' : 'var(--border)'}`,
                  borderRadius: 4, padding: '3px 9px', fontSize: 11,
                }}>
                  {f.formation_name} <span style={{ fontSize: 9, opacity: 0.7 }}>{f.top_md.toFixed(0)} ft</span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  background: 'var(--bg-panel)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', borderRadius: 5,
  padding: '3px 7px', fontSize: 12, width: 72, outline: 'none',
}
