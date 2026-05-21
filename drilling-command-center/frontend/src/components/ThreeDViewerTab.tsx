import { useEffect, useMemo, useRef, useState } from 'react'

// ─────────── Types ─────────────────────────────────────────────────────────
interface Trajectory { 0: number; 1: number; 2: number } // [x_ft, y_ft(neg down), z_ft]

interface Well {
  well_id: string
  well_name: string
  lat: number | null
  lon: number | null
  total_depth_ft: number
  tvd_ft: number
  well_type?: string
  status?: string
  quality_score?: number
  trajectory: [number, number, number][]
  formations: { formation_name: string; top_md: number; base_md: number; zone_type: string }[]
}

interface Reservoir {
  record_id: string
  name?: string
  formation?: string
  ooip_mm_sm3: number
  depth_ft: number
  pressure_bar?: number | null
  temp_c?: number | null
  cx_ft: number
  cz_ft: number
  extent_ft: number
  thickness_ft: number
}

interface Sample {
  record_id: string
  sample_id?: string
  formation?: string
  depth_ft: number
  porosity?: number | null
  perm_md?: number | null
  sw?: number | null
  so?: number | null
  cx_ft: number
  cz_ft: number
}

interface Scene {
  wells: Well[]
  reservoirs: Reservoir[]
  samples: Sample[]
}

// ─────────── Constants ─────────────────────────────────────────────────────
const W = 1000
const H = 640
const CX = W / 2
const CY = H / 2 + 40

const FT_TO_UNIT = 0.04  // 1 ft → 0.04 world units
const LATLON_SCALE = 80

const ZONE_COLORS: Record<string, string> = {
  shale:     '#3a4556',
  sand:      '#c8a05a',
  carbonate: '#88c8e0',
  reservoir: '#cd5c30',
  fluvial:   '#9b6b3a',
  default:   '#5c6470',
}

type PropKey = 'ooip' | 'pressure' | 'temperature' | 'porosity'

const PROP_COLORSCALES: Record<PropKey, { label: string; unit: string }> = {
  ooip:        { label: 'OOIP',          unit: 'MMSm³' },
  pressure:    { label: 'Pressure',      unit: 'bar' },
  temperature: { label: 'Temperature',   unit: '°C' },
  porosity:    { label: 'Porosity',      unit: '—' },
}

// Petrel-style diverging color scale (blue → cyan → green → yellow → red)
function colorScale(t: number): string {
  t = Math.max(0, Math.min(1, t))
  const stops = [
    { p: 0.00, r: 30,  g: 70,  b: 170 },
    { p: 0.25, r: 50,  g: 190, b: 220 },
    { p: 0.50, r: 100, g: 220, b: 130 },
    { p: 0.75, r: 245, g: 215, b: 80 },
    { p: 1.00, r: 240, g: 80,  b: 50 },
  ]
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i], b = stops[i + 1]
    if (t <= b.p) {
      const u = (t - a.p) / (b.p - a.p)
      return `rgb(${Math.round(a.r + (b.r - a.r) * u)}, ${Math.round(a.g + (b.g - a.g) * u)}, ${Math.round(a.b + (b.b - a.b) * u)})`
    }
  }
  return 'rgb(240,80,50)'
}

// ─────────── 3D math ───────────────────────────────────────────────────────
function project(x: number, y: number, z: number, yaw: number, pitch: number, zoom: number): [number, number, number] {
  const cx = Math.cos(yaw), sx = Math.sin(yaw)
  const rx1 = x * cx - z * sx
  const rz1 = x * sx + z * cx
  const cp = Math.cos(pitch), sp = Math.sin(pitch)
  const ry1 = y * cp - rz1 * sp
  const rz2 = y * sp + rz1 * cp
  const persp = 1200 / Math.max(1200 + rz2, 300)
  return [CX + rx1 * zoom * persp, CY + ry1 * zoom * persp, rz2]
}

// ─────────── Component ─────────────────────────────────────────────────────
interface Similar { well_key: string; well_name?: string; platform?: string; primary_reservoir?: string; drilling_result?: string; score: number }

export default function ThreeDViewerTab({ wellId, onWellChange }: { wellId: string; onWellChange: (w: string) => void }) {
  const [scene, setScene] = useState<Scene | null>(null)
  const [loading, setLoading] = useState(true)
  const [yaw, setYaw]     = useState(0.6)
  const [pitch, setPitch] = useState(0.35)
  const [zoom, setZoom]   = useState(0.9)
  const [prop, setProp]   = useState<PropKey>('ooip')
  const [hover, setHover] = useState<string | null>(null)
  const [similar, setSimilar] = useState<Similar[]>([])
  const dragRef = useRef<{ x: number; y: number } | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch('/api/subsurface/scene').then(r => r.json()).then(s => { setScene(s); setLoading(false) })
  }, [])

  useEffect(() => {
    if (!wellId) return
    fetch(`/api/subsurface/similar/${wellId}`).then(r => r.json()).then(d => setSimilar(d.results || []))
  }, [wellId])

  const geo = useMemo(() => {
    if (!scene) return { lat0: 40, lon0: -100 }
    const c = scene.wells.filter(w => w.lat != null && w.lon != null)
    if (!c.length) return { lat0: 40, lon0: -100 }
    return {
      lat0: c.reduce((s, w) => s + (w.lat as number), 0) / c.length,
      lon0: c.reduce((s, w) => s + (w.lon as number), 0) / c.length,
    }
  }, [scene])

  function wellSurface(w: Well): [number, number] {
    if (w.lat == null || w.lon == null) return [0, 0]
    return [(w.lon - geo.lon0) * LATLON_SCALE, -(w.lat - geo.lat0) * LATLON_SCALE]
  }

  const items = useMemo(() => {
    if (!scene) return [] as { z: number; render: () => JSX.Element }[]
    const out: { z: number; render: () => JSX.Element }[] = []

    // Model bounding box (wireframe)
    const BOX = 1800
    const TOP = 0
    const BOT = -500  // TVD 0 to 12,500 ft ~= 500 units
    const cube: [number, number, number][] = [
      [-BOX, TOP, -BOX], [BOX, TOP, -BOX], [BOX, TOP, BOX], [-BOX, TOP, BOX],
      [-BOX, BOT, -BOX], [BOX, BOT, -BOX], [BOX, BOT, BOX], [-BOX, BOT, BOX],
    ]
    const cubeP = cube.map(([x, y, z]) => project(x, y, z, yaw, pitch, zoom))
    const edges = [
      [0,1],[1,2],[2,3],[3,0],  // top
      [4,5],[5,6],[6,7],[7,4],  // bottom
      [0,4],[1,5],[2,6],[3,7],  // verticals
    ]
    edges.forEach(([a, b], i) => {
      const za = (cubeP[a][2] + cubeP[b][2]) / 2
      out.push({
        z: za - 5000,
        render: () => (
          <line key={`cube-${i}`} x1={cubeP[a][0]} y1={cubeP[a][1]} x2={cubeP[b][0]} y2={cubeP[b][1]}
                stroke="#3a4556" strokeWidth="0.5" strokeDasharray="3 2" opacity="0.5" />
        ),
      })
    })

    // Surface grid
    for (let g = -BOX; g <= BOX; g += 300) {
      const a = project(g, 0, -BOX, yaw, pitch, zoom)
      const b = project(g, 0, BOX, yaw, pitch, zoom)
      out.push({ z: (a[2] + b[2]) / 2 - 4000, render: () =>
        <line key={`sgx${g}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke="#1a2030" strokeWidth="0.4" opacity="0.6" /> })
      const c = project(-BOX, 0, g, yaw, pitch, zoom)
      const d = project(BOX, 0, g, yaw, pitch, zoom)
      out.push({ z: (c[2] + d[2]) / 2 - 4000, render: () =>
        <line key={`sgz${g}`} x1={c[0]} y1={c[1]} x2={d[0]} y2={d[1]} stroke="#1a2030" strokeWidth="0.4" opacity="0.6" /> })
    }

    // Reservoirs as faceted grid cells (Petrel-style)
    const resMin = prop === 'pressure' ? 100 : prop === 'temperature' ? 40 : 10
    const resMax = prop === 'pressure' ? 400 : prop === 'temperature' ? 120 : 400
    scene.reservoirs.forEach(r => {
      const value = prop === 'pressure' ? (r.pressure_bar || 150)
                  : prop === 'temperature' ? (r.temp_c || 70)
                  : r.ooip_mm_sm3
      const t = Math.max(0, Math.min(1, (value - resMin) / (resMax - resMin)))
      const col = colorScale(t)
      const halfX = r.extent_ft * FT_TO_UNIT / 2
      const halfZ = r.extent_ft * FT_TO_UNIT / 2
      const halfY = r.thickness_ft * FT_TO_UNIT / 2
      const cy0 = -r.depth_ft * FT_TO_UNIT
      const cx0 = r.cx_ft * FT_TO_UNIT
      const cz0 = r.cz_ft * FT_TO_UNIT

      // Subdivide into NxNx2 "grid cells" for Petrel look
      const N = 4
      for (let i = 0; i < N; i++) {
        for (let j = 0; j < N; j++) {
          for (let k = 0; k < 2; k++) {
            const x0 = cx0 - halfX + (i / N) * halfX * 2
            const x1 = cx0 - halfX + ((i + 1) / N) * halfX * 2
            const z0 = cz0 - halfZ + (j / N) * halfZ * 2
            const z1 = cz0 - halfZ + ((j + 1) / N) * halfZ * 2
            const y0 = cy0 - halfY + (k / 2) * halfY * 2
            const y1 = cy0 - halfY + ((k + 1) / 2) * halfY * 2
            // Top + bottom + 4 sides per cell — render only the 3 visible from current pov
            const pts = [
              [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1],  // top
            ] as [number, number, number][]
            const proj = pts.map(p => project(p[0], p[1], p[2], yaw, pitch, zoom))
            const zMean = proj.reduce((s, p) => s + p[2], 0) / 4
            const poly = proj.map(p => `${p[0]},${p[1]}`).join(' ')
            // Cell color perturbed slightly for facet look
            const jitter = ((i + j + k) % 2 === 0 ? 0.97 : 1.03)
            const cellCol = perturb(col, jitter)
            out.push({
              z: zMean,
              render: () => (
                <polygon key={`res-${r.record_id}-${i}-${j}-${k}-top`} points={poly}
                         fill={cellCol} opacity="0.65" stroke="#0a1a2e" strokeWidth="0.3" />
              ),
            })
          }
        }
      }
      // Sides (single polygons) with slight darker shade
      const sideCol = perturb(col, 0.7)
      const sideFaces: [number, number, number][][] = [
        // front (cz+halfZ)
        [[cx0-halfX, cy0+halfY, cz0+halfZ], [cx0+halfX, cy0+halfY, cz0+halfZ], [cx0+halfX, cy0-halfY, cz0+halfZ], [cx0-halfX, cy0-halfY, cz0+halfZ]],
        // back
        [[cx0-halfX, cy0+halfY, cz0-halfZ], [cx0+halfX, cy0+halfY, cz0-halfZ], [cx0+halfX, cy0-halfY, cz0-halfZ], [cx0-halfX, cy0-halfY, cz0-halfZ]],
        // left
        [[cx0-halfX, cy0+halfY, cz0-halfZ], [cx0-halfX, cy0+halfY, cz0+halfZ], [cx0-halfX, cy0-halfY, cz0+halfZ], [cx0-halfX, cy0-halfY, cz0-halfZ]],
        // right
        [[cx0+halfX, cy0+halfY, cz0-halfZ], [cx0+halfX, cy0+halfY, cz0+halfZ], [cx0+halfX, cy0-halfY, cz0+halfZ], [cx0+halfX, cy0-halfY, cz0-halfZ]],
      ]
      sideFaces.forEach((face, idx) => {
        const proj = face.map(p => project(p[0], p[1], p[2], yaw, pitch, zoom))
        const zMean = proj.reduce((s, p) => s + p[2], 0) / 4
        const poly = proj.map(p => `${p[0]},${p[1]}`).join(' ')
        out.push({ z: zMean - 10, render: () => (
          <polygon key={`res-${r.record_id}-side-${idx}`} points={poly}
                   fill={sideCol} opacity="0.5" stroke="#0a1a2e" strokeWidth="0.5" />
        )})
      })

      // Reservoir label
      const labP = project(cx0, cy0 + halfY + 30, cz0, yaw, pitch, zoom)
      out.push({
        z: labP[2] + 10000,
        render: () => (
          <g key={`res-label-${r.record_id}`} style={{ pointerEvents: 'none' }}>
            <text x={labP[0]} y={labP[1]} textAnchor="middle" fill="#e8eaf0" fontSize="11"
                  fontWeight="600" fontFamily="monospace" style={{
                    filter: 'drop-shadow(0 0 3px rgba(0,0,0,0.9))',
                  }}>
              {r.name || r.formation}
            </text>
          </g>
        ),
      })
    })

    // Samples (rock_and_fluid)
    scene.samples.forEach(s => {
      const t = s.porosity == null ? 0.5 : Math.max(0, Math.min(1, s.porosity / 0.35))
      const col = prop === 'porosity' ? colorScale(t) : '#ffd666'
      const p = project(s.cx_ft * FT_TO_UNIT, -s.depth_ft * FT_TO_UNIT, s.cz_ft * FT_TO_UNIT, yaw, pitch, zoom)
      out.push({
        z: p[2] + 100,
        render: () => (
          <g key={`sample-${s.record_id}`}>
            <circle cx={p[0]} cy={p[1]} r="7" fill={col} opacity="0.25" />
            <circle cx={p[0]} cy={p[1]} r="3.5" fill={col} stroke="#000" strokeWidth="0.5" />
            <text x={p[0] + 7} y={p[1] - 5} fontSize="9" fill="#b0b6c8" fontFamily="monospace" style={{ pointerEvents: 'none' }}>
              {s.sample_id}
            </text>
          </g>
        ),
      })
    })

    // Wells with deviated trajectories
    scene.wells.forEach(w => {
      const [sx, sz] = wellSurface(w)
      const active = w.well_id === wellId
      const h = hover === w.well_id
      const pts3d = w.trajectory.map(([x, y, z]) => [
        (sx + x) * FT_TO_UNIT, y * FT_TO_UNIT, (sz + z) * FT_TO_UNIT,
      ] as [number, number, number])
      const projPts = pts3d.map(([x, y, z]) => project(x, y, z, yaw, pitch, zoom))

      // Color segments by depth (gradient)
      for (let i = 0; i < projPts.length - 1; i++) {
        const a = projPts[i]
        const b = projPts[i + 1]
        const t = i / (projPts.length - 1)
        const baseCol = active ? '#00E5FF' : colorScale(t)
        out.push({
          z: (a[2] + b[2]) / 2 + 200,
          render: () => (
            <line key={`well-${w.well_id}-seg${i}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}
                  stroke={baseCol} strokeWidth={active ? 3.5 : h ? 2.8 : 2}
                  opacity={active ? 1 : 0.85} strokeLinecap="round" />
          ),
        })
      }
      // Surface marker
      const top = projPts[0]
      const bot = projPts[projPts.length - 1]
      out.push({ z: top[2] + 300, render: () => (
        <g key={`well-${w.well_id}-top`}>
          <circle cx={top[0]} cy={top[1]} r="5" fill={active ? '#00E5FF' : '#ffd666'} stroke="#000" strokeWidth="0.8" />
          <circle cx={top[0]} cy={top[1]} r="10" fill="none" stroke={active ? '#00E5FF' : '#ffd666'} strokeWidth="0.6" opacity="0.5" />
        </g>
      )})
      // Bit marker
      out.push({ z: bot[2] + 400, render: () => (
        <g key={`well-${w.well_id}-bit`}>
          <circle cx={bot[0]} cy={bot[1]} r={active ? 6 : 4} fill={active ? '#ff7a45' : '#ffa940'}>
            {active && <animate attributeName="r" values="4;8;4" dur="1.5s" repeatCount="indefinite" />}
          </circle>
        </g>
      )})
      // Label
      out.push({ z: top[2] + 5000, render: () => (
        <g key={`well-${w.well_id}-label`}
           onClick={() => onWellChange(w.well_id)}
           onMouseEnter={() => setHover(w.well_id)}
           onMouseLeave={() => setHover(null)}
           style={{ cursor: 'pointer' }}>
          {/* Invisible hit area */}
          <line x1={top[0]} y1={top[1]} x2={bot[0]} y2={bot[1]} stroke="transparent" strokeWidth="14" />
          <text x={top[0] + 9} y={top[1] - 6} fontSize="10" fontFamily="monospace"
                fill={active ? '#00E5FF' : '#e8eaf0'} fontWeight={active ? 700 : 400}
                style={{ filter: 'drop-shadow(0 0 3px #000)', pointerEvents: 'none' }}>
            {w.well_id}
          </text>
        </g>
      )})
    })

    // Similar-well connection rays (Vector Search overlay)
    if (scene && similar.length > 0) {
      const active = scene.wells.find(w => w.well_id === wellId)
      if (active) {
        const [ax, az] = wellSurface(active)
        const a3 = project(ax * FT_TO_UNIT, 0, az * FT_TO_UNIT, yaw, pitch, zoom)
        similar.forEach((s, i) => {
          // Match OSDU well_key suffix to an existing scene well by the hash prefix
          const match = scene.wells.find(w => w.well_id.startsWith('OSDU-') && s.well_key.endsWith(w.well_id.slice(5)))
          if (!match) return
          const [bx, bz] = wellSurface(match)
          const b3 = project(bx * FT_TO_UNIT, 0, bz * FT_TO_UNIT, yaw, pitch, zoom)
          const zMean = (a3[2] + b3[2]) / 2 + 6000
          out.push({
            z: zMean,
            render: () => (
              <g key={`similar-${s.well_key}-${i}`}>
                <line x1={a3[0]} y1={a3[1]} x2={b3[0]} y2={b3[1]}
                      stroke="#00E5FF" strokeWidth="1" strokeDasharray="4 3" opacity="0.55" />
                <circle cx={b3[0]} cy={b3[1]} r="14" fill="none" stroke="#00E5FF" strokeWidth="1" opacity="0.4" />
                <text x={(a3[0] + b3[0]) / 2} y={(a3[1] + b3[1]) / 2 - 4} fill="#00E5FF"
                      fontSize="9" fontFamily="monospace" textAnchor="middle" style={{ pointerEvents: 'none' }}>
                  {s.score.toFixed(2)}
                </text>
              </g>
            ),
          })
        })
      }
    }

    // Painter's algorithm
    out.sort((a, b) => a.z - b.z)
    return out
  }, [scene, yaw, pitch, zoom, prop, wellId, hover, similar])

  function onMouseDown(e: React.MouseEvent) { dragRef.current = { x: e.clientX, y: e.clientY } }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragRef.current) return
    const dx = e.clientX - dragRef.current.x
    const dy = e.clientY - dragRef.current.y
    setYaw(y => y + dx * 0.005)
    setPitch(p => Math.max(-0.2, Math.min(1.4, p + dy * 0.005)))
    dragRef.current = { x: e.clientX, y: e.clientY }
  }
  function onMouseUp() { dragRef.current = null }
  function onWheel(e: React.WheelEvent) {
    setZoom(z => Math.max(0.3, Math.min(3, z * (e.deltaY < 0 ? 1.1 : 0.9))))
  }

  const activeWell = scene?.wells.find(w => w.well_id === wellId)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '3.2fr 1fr', gap: 16 }}>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        <div style={{
          padding: '10px 14px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
              Subsurface Model · 3D
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Drag to orbit · scroll to zoom · click a well to focus
              {scene && ` · ${scene.wells.length} wells · ${scene.reservoirs.length} reservoirs · ${scene.samples.length} samples`}
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            {(Object.keys(PROP_COLORSCALES) as PropKey[]).map(k => (
              <button key={k} onClick={() => setProp(k)} style={{
                padding: '3px 10px', fontSize: 11,
                background: prop === k ? 'var(--teal-dim)' : 'var(--bg-panel)',
                color: prop === k ? 'var(--teal)' : 'var(--text-muted)',
                border: `1px solid ${prop === k ? 'var(--teal)' : 'var(--border)'}`,
                borderRadius: 4, cursor: 'pointer',
              }}>{PROP_COLORSCALES[k].label}</button>
            ))}
            <button onClick={() => { setYaw(0.6); setPitch(0.35); setZoom(0.9) }} style={{
              padding: '3px 10px', fontSize: 11,
              background: 'var(--bg-panel)', color: 'var(--text-muted)',
              border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer',
            }}>reset</button>
          </div>
        </div>

        <svg width="100%" viewBox={`0 0 ${W} ${H}`}
             style={{ background: 'radial-gradient(ellipse at 50% 55%, #0d1a2f 0%, #05070c 75%)',
                      display: 'block', cursor: dragRef.current ? 'grabbing' : 'grab' }}
             onMouseDown={onMouseDown} onMouseMove={onMouseMove}
             onMouseUp={onMouseUp} onMouseLeave={onMouseUp} onWheel={onWheel}>
          {loading && (
            <text x={CX} y={CY} textAnchor="middle" fill="#6b7280" fontSize="14">Loading subsurface…</text>
          )}

          {items.map(i => i.render())}

          {/* Color scale legend */}
          <g transform="translate(16, 40)">
            <text x="0" y="-4" fill="#b0b6c8" fontSize="10" fontFamily="monospace" fontWeight="600">
              {PROP_COLORSCALES[prop].label} ({PROP_COLORSCALES[prop].unit})
            </text>
            <defs>
              <linearGradient id="petrelScale" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0" stopColor={colorScale(0)} />
                <stop offset="0.25" stopColor={colorScale(0.25)} />
                <stop offset="0.5" stopColor={colorScale(0.5)} />
                <stop offset="0.75" stopColor={colorScale(0.75)} />
                <stop offset="1" stopColor={colorScale(1)} />
              </linearGradient>
            </defs>
            <rect x="0" y="0" width="16" height="180" fill="url(#petrelScale)" stroke="#2a2e3a" />
            {[0, 0.25, 0.5, 0.75, 1].map(t => (
              <g key={t}>
                <line x1="16" y1={180 - t * 180} x2="22" y2={180 - t * 180} stroke="#2a2e3a" />
                <text x="26" y={180 - t * 180 + 3} fill="#6b7280" fontSize="9" fontFamily="monospace">
                  {propValueForT(t, prop)}
                </text>
              </g>
            ))}
          </g>

          {/* Axis cube */}
          <g transform={`translate(${W - 70}, ${H - 70})`}>
            <AxisCube yaw={yaw} pitch={pitch} />
          </g>
        </svg>
      </div>

      {/* Right column */}
      <div style={{ display: 'grid', gap: 12, alignContent: 'start' }}>
        <Panel title="Active well">
          {activeWell ? (
            <div style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 700, color: 'var(--blue)', fontFamily: 'monospace' }}>{activeWell.well_id}</div>
              <div style={{ color: 'var(--text-primary)' }}>{activeWell.well_name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                {activeWell.well_type} · TD {activeWell.total_depth_ft?.toLocaleString()} ft · TVD {Math.round(activeWell.tvd_ft).toLocaleString()} ft
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                {activeWell.lat != null && activeWell.lon != null && `Surface ${activeWell.lat.toFixed(3)}, ${activeWell.lon.toFixed(3)}`}
              </div>
            </div>
          ) : <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Pick a well</div>}
        </Panel>

        <Panel title="Reservoirs" subtitle={`${scene?.reservoirs?.length || 0} · live from OSDU`}>
          <div style={{ display: 'grid', gap: 6 }}>
            {scene?.reservoirs.map(r => {
              const value = prop === 'pressure' ? r.pressure_bar : prop === 'temperature' ? r.temp_c : r.ooip_mm_sm3
              return (
                <div key={r.record_id} style={{
                  background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  borderRadius: 4, padding: '6px 8px', fontSize: 11,
                }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.name || '—'}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                    {r.formation} · {Math.round(r.depth_ft).toLocaleString()} ft
                  </div>
                  <div style={{ color: 'var(--teal)', fontSize: 10, marginTop: 2 }}>
                    {PROP_COLORSCALES[prop].label}: {typeof value === 'number' ? value.toFixed(1) : '—'} {PROP_COLORSCALES[prop].unit}
                  </div>
                </div>
              )
            })}
          </div>
        </Panel>

        <Panel title="Similar wells · Vector Search" subtitle={`top ${similar.length} by semantic match`}>
          {similar.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No matches yet.</div>
          ) : (
            <div style={{ display: 'grid', gap: 6 }}>
              {similar.map(s => (
                <div key={s.well_key} style={{
                  background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  borderRadius: 4, padding: '6px 8px', fontSize: 11,
                }}>
                  <div style={{ fontFamily: 'monospace', color: 'var(--teal)', fontSize: 11 }}>
                    {s.well_name || s.well_key.slice(-10)}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 2 }}>
                    {s.platform} · {s.primary_reservoir} · {s.drilling_result}
                  </div>
                  <div style={{ color: 'var(--blue)', fontSize: 10, marginTop: 2 }}>
                    score {s.score.toFixed(3)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Wells" subtitle={`${scene?.wells?.length || 0} total`}>
          <div style={{ maxHeight: 200, overflow: 'auto' }}>
            {scene?.wells.map(w => (
              <button key={w.well_id} onClick={() => onWellChange(w.well_id)} style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '4px 8px', fontSize: 11, marginBottom: 2,
                background: w.well_id === wellId ? 'var(--blue-dim)' : 'transparent',
                color: w.well_id === wellId ? 'var(--blue)' : 'var(--text-secondary)',
                border: `1px solid ${w.well_id === wellId ? 'var(--blue)' : 'transparent'}`,
                borderRadius: 4, cursor: 'pointer', fontFamily: 'monospace',
              }}>{w.well_id} <span style={{ color: 'var(--text-muted)', float: 'right' }}>{w.well_type}</span></button>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function AxisCube({ yaw, pitch }: { yaw: number; pitch: number }) {
  const proj = (x: number, y: number, z: number) => {
    const cx = Math.cos(yaw), sx = Math.sin(yaw)
    const rx = x * cx - z * sx
    const rz = x * sx + z * cx
    const cp = Math.cos(pitch), sp = Math.sin(pitch)
    const ry = y * cp - rz * sp
    return [rx * 25, ry * 25]
  }
  const n = proj(0, 0, -1); const s = proj(0, 0, 1)
  const e = proj(1, 0, 0); const w = proj(-1, 0, 0)
  const up = proj(0, -1, 0); const dn = proj(0, 1, 0)
  return (
    <g>
      <circle cx="0" cy="0" r="28" fill="#0d0e11" stroke="#2a2e3a" opacity="0.95" />
      <line x1="0" y1="0" x2={n[0]} y2={n[1]} stroke="#ff4d4f" strokeWidth="1.5" />
      <line x1="0" y1="0" x2={s[0]} y2={s[1]} stroke="#6b7280" strokeWidth="1" />
      <line x1="0" y1="0" x2={e[0]} y2={e[1]} stroke="#00E5FF" strokeWidth="1.5" />
      <line x1="0" y1="0" x2={w[0]} y2={w[1]} stroke="#6b7280" strokeWidth="1" />
      <line x1="0" y1="0" x2={up[0]} y2={up[1]} stroke="#73d13d" strokeWidth="1.5" />
      <line x1="0" y1="0" x2={dn[0]} y2={dn[1]} stroke="#6b7280" strokeWidth="1" />
      <text x={n[0]} y={n[1] - 3} textAnchor="middle" fill="#ff4d4f" fontSize="9" fontWeight="700">N</text>
      <text x={e[0] + 4} y={e[1] + 3} fill="#00E5FF" fontSize="9" fontWeight="700">E</text>
      <text x={up[0]} y={up[1] - 3} textAnchor="middle" fill="#73d13d" fontSize="9" fontWeight="700">Z</text>
    </g>
  )
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{title}</div>
        {subtitle && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
      </div>
      {children}
    </div>
  )
}

function perturb(rgb: string, scale: number): string {
  const m = rgb.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/)
  if (!m) return rgb
  const r = Math.round(Math.min(255, Math.max(0, parseInt(m[1]) * scale)))
  const g = Math.round(Math.min(255, Math.max(0, parseInt(m[2]) * scale)))
  const b = Math.round(Math.min(255, Math.max(0, parseInt(m[3]) * scale)))
  return `rgb(${r},${g},${b})`
}

function propValueForT(t: number, prop: PropKey): string {
  if (prop === 'ooip')        return `${Math.round(10 + t * 390)}`
  if (prop === 'pressure')    return `${Math.round(100 + t * 300)}`
  if (prop === 'temperature') return `${Math.round(40 + t * 80)}`
  return t.toFixed(2)
}
