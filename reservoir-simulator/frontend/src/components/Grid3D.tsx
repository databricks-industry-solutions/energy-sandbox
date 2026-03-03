import { useEffect, useRef, useMemo, useCallback } from 'react'
import { useFrame } from '@react-three/fiber'
import type { ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'

export const NI = 20, NJ = 10, NK = 5
export const TOTAL_CELLS = NI * NJ * NK
export const CELL_W = 80, CELL_H = 40, CELL_D = 14
const GAP = 1
const VERTS_PER_CELL = 36   // 6 faces × 2 tris × 3 verts

const HW = CELL_W / 2, HD = CELL_D / 2, HH = CELL_H / 2

// ── Box face vertices (CCW from outside, 36 verts per cell) ───────────────────
const BOX_OFFSETS: number[] = [
  // +X  right  (1,0,0)
  HW,-HD,-HH,  HW,HD,-HH,  HW,HD,HH,    HW,-HD,-HH,  HW,HD,HH,   HW,-HD,HH,
  // -X  left  (-1,0,0)
  -HW,-HD,HH,  -HW,HD,HH,  -HW,HD,-HH,  -HW,-HD,HH,  -HW,HD,-HH, -HW,-HD,-HH,
  // +Y  top    (0,1,0)
  -HW,HD,HH,   HW,HD,HH,   HW,HD,-HH,   -HW,HD,HH,   HW,HD,-HH,  -HW,HD,-HH,
  // -Y  bot    (0,-1,0)
  -HW,-HD,-HH, HW,-HD,-HH, HW,-HD,HH,   -HW,-HD,-HH, HW,-HD,HH,  -HW,-HD,HH,
  // +Z  front  (0,0,1)
  -HW,-HD,HH,  HW,-HD,HH,  HW,HD,HH,    -HW,-HD,HH,  HW,HD,HH,   -HW,HD,HH,
  // -Z  back   (0,0,-1)
  -HW,-HD,-HH, -HW,HD,-HH, HW,HD,-HH,   -HW,-HD,-HH, HW,HD,-HH,  HW,-HD,-HH,
]
const BOX_NORMALS: number[] = [
   1,0,0,  1,0,0,  1,0,0,  1,0,0,  1,0,0,  1,0,0,
  -1,0,0, -1,0,0, -1,0,0, -1,0,0, -1,0,0, -1,0,0,
   0,1,0,  0,1,0,  0,1,0,  0,1,0,  0,1,0,  0,1,0,
   0,-1,0, 0,-1,0, 0,-1,0, 0,-1,0, 0,-1,0, 0,-1,0,
   0,0,1,  0,0,1,  0,0,1,  0,0,1,  0,0,1,  0,0,1,
   0,0,-1, 0,0,-1, 0,0,-1, 0,0,-1, 0,0,-1, 0,0,-1,
]

// ── 12 box edges as vertex pairs (24 verts × 3 = 72 offsets per cell) ─────────
const EDGE_OFFSETS: number[] = [
  // Bottom face
  -HW,-HD,-HH,  HW,-HD,-HH,   HW,-HD,-HH,  HW,-HD,HH,
   HW,-HD, HH, -HW,-HD, HH,  -HW,-HD, HH, -HW,-HD,-HH,
  // Top face
  -HW, HD,-HH,  HW, HD,-HH,   HW, HD,-HH,  HW, HD, HH,
   HW, HD, HH, -HW, HD, HH,  -HW, HD, HH, -HW, HD,-HH,
  // Verticals
  -HW,-HD,-HH, -HW, HD,-HH,   HW,-HD,-HH,  HW, HD,-HH,
   HW,-HD, HH,  HW, HD, HH,  -HW,-HD, HH, -HW, HD, HH,
]  // 72 numbers = 24 vertices × 3

export interface CellData {
  i: number; j: number; k: number
  pressure: number; so: number; sw: number; sg: number
}
export type PropertyKey = 'pressure' | 'so' | 'sw' | 'sg'

export const PROPERTY_RANGES = {
  pressure: { min: 120, max: 400, unit: 'bar', label: 'Reservoir Pressure' },
  so:       { min: 0.10, max: 0.68, unit: '',  label: 'Oil Saturation (So)' },
  sw:       { min: 0.20, max: 0.80, unit: '',  label: 'Water Saturation (Sw)' },
  sg:       { min: 0.00, max: 0.30, unit: '',  label: 'Gas Saturation (Sg)' },
} as const

// ResInsight jet colormap: blue → cyan → green → yellow → red
export function jetColor(t: number): THREE.Color {
  t = Math.max(0, Math.min(1, t))
  let r: number, g: number, b: number
  if      (t < 0.125) { r = 0;              g = 0;           b = 0.5 + t * 4 }
  else if (t < 0.375) { r = 0;              g = (t-0.125)*4; b = 1 }
  else if (t < 0.625) { const u=(t-0.375)/0.25; r=u;   g=1; b=1-u }
  else if (t < 0.875) { const u=(t-0.625)/0.25; r=1;   g=1-u; b=0 }
  else                { r = 1-(t-0.875)*2;  g = 0;           b = 0 }
  return new THREE.Color(Math.max(0,r), Math.max(0,g), Math.max(0,b))
}

export function getColor(property: PropertyKey, value: number): THREE.Color {
  const rng = PROPERTY_RANGES[property]
  return jetColor((value - rng.min) / (rng.max - rng.min))
}

export function cellIndex(i: number, j: number, k: number): number {
  return k * NI * NJ + j * NI + i
}

// Initial Norne conditions — depth gradient spans full colormap
export function norneInitialCells(): CellData[] {
  const cells: CellData[] = []
  for (let k = 0; k < NK; k++) {
    for (let j = 0; j < NJ; j++) {
      for (let i = 0; i < NI; i++) {
        const depthP = 260 + k * 28
        const het    = 0.92 + 0.16 * Math.sin(i*0.7+0.4) * Math.cos(j*0.55+0.9)
        const pressure = Math.max(120, Math.min(400, Math.round(depthP * het * 10) / 10))
        const soBase = 0.68 - k * 0.11
        const soHet  = 0.85 + 0.30 * Math.sin(i*0.6) * Math.cos(j*0.5+1.0)
        const so  = Math.round(Math.max(0.10, Math.min(0.68, soBase * soHet)) * 1000) / 1000
        const sw  = Math.round(Math.min(0.80, Math.max(0.20, 0.27 + k * 0.09)) * 1000) / 1000
        cells.push({ i, j, k, pressure, so, sw, sg: 0.05 })
      }
    }
  }
  return cells
}

// ── Static position + normal buffers (computed once at module load) ────────────
function makeStaticBuffers() {
  const N = TOTAL_CELLS * VERTS_PER_CELL
  const pos = new Float32Array(N * 3)
  const nor = new Float32Array(N * 3)
  let vptr = 0
  for (let k = 0; k < NK; k++) {
    for (let j = 0; j < NJ; j++) {
      for (let i = 0; i < NI; i++) {
        const cx = (i - NI/2 + 0.5) * (CELL_W + GAP)
        const cy = -k * (CELL_D + GAP)
        const cz = (j - NJ/2 + 0.5) * (CELL_H + GAP)
        for (let v = 0; v < VERTS_PER_CELL; v++) {
          const pi = vptr * 3, oi = v * 3
          pos[pi]   = cx + BOX_OFFSETS[oi];   pos[pi+1] = cy + BOX_OFFSETS[oi+1]; pos[pi+2] = cz + BOX_OFFSETS[oi+2]
          nor[pi]   = BOX_NORMALS[oi];         nor[pi+1] = BOX_NORMALS[oi+1];      nor[pi+2] = BOX_NORMALS[oi+2]
          vptr++
        }
      }
    }
  }
  return { pos, nor }
}
const { pos: STATIC_POS, nor: STATIC_NOR } = makeStaticBuffers()

function writeCellColor(buf: Float32Array, ci: number, r: number, g: number, b: number) {
  const base = ci * VERTS_PER_CELL * 3
  for (let v = 0; v < VERTS_PER_CELL; v++) {
    buf[base + v*3] = r; buf[base + v*3+1] = g; buf[base + v*3+2] = b
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// EdgeLines — renders dark cell-boundary edges (ResInsight style)
// ─────────────────────────────────────────────────────────────────────────────
export function EdgeLines({ visibleK }: { visibleK?: Set<number> }) {
  const geo = useMemo(() => {
    let count = 0
    for (let k = 0; k < NK; k++) if (!visibleK || visibleK.has(k)) count += NI * NJ
    const pos = new Float32Array(count * 24 * 3)   // 24 edge-verts per cell
    let vptr = 0
    for (let k = 0; k < NK; k++) {
      if (visibleK && !visibleK.has(k)) continue
      for (let j = 0; j < NJ; j++) {
        for (let i = 0; i < NI; i++) {
          const cx = (i - NI/2 + 0.5) * (CELL_W + GAP)
          const cy = -k * (CELL_D + GAP)
          const cz = (j - NJ/2 + 0.5) * (CELL_H + GAP)
          for (let v = 0; v < 24; v++) {
            const oi = v * 3, pi = vptr * 3
            pos[pi]   = cx + EDGE_OFFSETS[oi]
            pos[pi+1] = cy + EDGE_OFFSETS[oi+1]
            pos[pi+2] = cz + EDGE_OFFSETS[oi+2]
            vptr++
          }
        }
      }
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    return g
  }, [visibleK])

  useEffect(() => () => geo.dispose(), [geo])

  return (
    <lineSegments geometry={geo}>
      <lineBasicMaterial color="#0D1C2E" transparent opacity={0.55} />
    </lineSegments>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Grid3D — main colored cell mesh with smooth useFrame animation
// ─────────────────────────────────────────────────────────────────────────────
interface Props {
  cells: CellData[]
  property: PropertyKey
  visibleK?: Set<number>
  onCellClick?: (cell: CellData) => void
}

export default function Grid3D({ cells, property, visibleK, onCellClick }: Props) {
  const meshRef   = useRef<THREE.Mesh>(null)
  const curColRef = useRef<Float32Array>(new Float32Array(TOTAL_CELLS * VERTS_PER_CELL * 3))
  const tgtColRef = useRef<Float32Array>(new Float32Array(TOTAL_CELLS * VERTS_PER_CELL * 3))
  const lerpRef   = useRef(1.0)

  const cellMap = useMemo(() => {
    const map = new Map<number, CellData>()
    for (const c of cells) map.set(cellIndex(c.i, c.j, c.k), c)
    return map
  }, [cells])

  // Create geometry once — positions + normals static, colors dynamic
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    const posAttr = new THREE.BufferAttribute(STATIC_POS, 3); posAttr.setUsage(THREE.StaticDrawUsage)
    const norAttr = new THREE.BufferAttribute(STATIC_NOR, 3); norAttr.setUsage(THREE.StaticDrawUsage)
    const colAttr = new THREE.BufferAttribute(curColRef.current, 3); colAttr.setUsage(THREE.DynamicDrawUsage)
    geo.setAttribute('position', posAttr)
    geo.setAttribute('normal',   norAttr)
    geo.setAttribute('color',    colAttr)
    return geo
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => geometry.dispose(), [geometry])

  // Recompute target colors on data/property/visibility change
  useEffect(() => {
    const tgt = tgtColRef.current
    for (let k = 0; k < NK; k++) {
      const hidden = visibleK != null && !visibleK.has(k)
      const depth  = 1.0 - k * 0.04
      for (let j = 0; j < NJ; j++) {
        for (let i = 0; i < NI; i++) {
          const ci = cellIndex(i, j, k)
          if (hidden) { writeCellColor(tgt, ci, 0.54, 0.67, 0.77); continue }  // match bg
          const cell = cellMap.get(ci)
          if (cell) {
            const c = getColor(property, cell[property] as number)
            writeCellColor(tgt, ci, c.r * depth, c.g * depth, c.b * depth)
          } else {
            writeCellColor(tgt, ci, 0.45, 0.55, 0.63)
          }
        }
      }
    }
    lerpRef.current = 0
  }, [cellMap, property, visibleK])

  // Smooth exponential lerp toward target each frame
  useFrame((_, delta) => {
    if (lerpRef.current >= 1) return
    const cur = curColRef.current, tgt = tgtColRef.current
    const alpha = 1 - Math.pow(0.005, delta * 4)
    let done = true
    for (let i = 0; i < cur.length; i++) {
      const d = tgt[i] - cur[i]
      if (Math.abs(d) > 0.001) { cur[i] += d * alpha; done = false }
      else cur[i] = tgt[i]
    }
    ;(geometry.getAttribute('color') as THREE.BufferAttribute).needsUpdate = true
    if (done) lerpRef.current = 1
  })

  // Click → identify cell by face index
  const handleClick = useCallback((e: ThreeEvent<MouseEvent>) => {
    if (!onCellClick || e.faceIndex == null) return
    e.stopPropagation()
    const ci = Math.floor(e.faceIndex / 12)   // 12 triangles per cell
    const k  = Math.floor(ci / (NI * NJ))
    const j  = Math.floor((ci % (NI * NJ)) / NI)
    const ii = ci % NI
    const cell = cellMap.get(cellIndex(ii, j, k))
    if (cell) onCellClick(cell)
  }, [cellMap, onCellClick])

  return (
    <mesh ref={meshRef} geometry={geometry} onClick={handleClick}>
      <meshStandardMaterial
        vertexColors
        toneMapped={false}
        roughness={0.82}
        metalness={0.0}
      />
    </mesh>
  )
}
