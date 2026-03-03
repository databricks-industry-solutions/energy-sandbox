import { useState, useEffect, useMemo, useRef, useCallback } from 'react'

/* ─── Types ───────────────────────────────────────────────────── */

interface Operation {
  well_name: string
  activity_type: string
  activity_name: string
  category: string
  start_day: number
  duration_days: number
  end_day: number
  trigger_reason: string
  color: string
}

interface OperationsResponse {
  run_id: string
  operations: Operation[]
  count: number
}

interface Run {
  id: string
  scenario_name: string
  status: string
}

interface Props {
  activeRunId: string | null
  onRunSelect: (id: string) => void
}

/* ─── Constants ───────────────────────────────────────────────── */

const CATEGORIES = [
  'All',
  'D&C',
  'Artificial Lift',
  'Production Chemistry',
  'Well Intervention',
  'Maintenance',
  'Injection',
] as const

type Category = (typeof CATEGORIES)[number]

const CATEGORY_COLORS: Record<string, string> = {
  'D&C': 'var(--blue)',
  'Artificial Lift': 'var(--purple)',
  'Production Chemistry': 'var(--teal)',
  'Well Intervention': 'var(--amber)',
  'Maintenance': 'var(--red)',
  'Injection': 'var(--green)',
}

const GANTT_ROW_HEIGHT = 32
const GANTT_LABEL_WIDTH = 100
const GANTT_PADDING_TOP = 36
const GANTT_PADDING_BOTTOM = 28
const GANTT_MIN_HEIGHT = 400
const BAR_HEIGHT = 18
const BAR_RADIUS = 4

/* ─── Component ───────────────────────────────────────────────── */

export default function OperationsTab({ activeRunId, onRunSelect }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedRun, setSelectedRun] = useState(activeRunId || '')
  const [operations, setOperations] = useState<Operation[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeCategory, setActiveCategory] = useState<Category>('All')
  const [tooltip, setTooltip] = useState<{
    op: Operation; x: number; y: number
  } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  /* ── Data fetching ───────────────────────────────── */

  useEffect(() => {
    fetch('/api/runs')
      .then(r => r.json())
      .then(d => setRuns(Array.isArray(d) ? d : []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (activeRunId) setSelectedRun(activeRunId)
  }, [activeRunId])

  useEffect(() => {
    if (!selectedRun) {
      setOperations([])
      return
    }
    setLoading(true)
    setError('')
    fetch(`/api/operations/${selectedRun}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: OperationsResponse) => {
        setOperations(data.operations || [])
      })
      .catch(() => setError('Failed to load operations data'))
      .finally(() => setLoading(false))
  }, [selectedRun])

  /* ── Derived data ────────────────────────────────── */

  const filtered = useMemo(
    () =>
      activeCategory === 'All'
        ? operations
        : operations.filter(o => o.category === activeCategory),
    [operations, activeCategory],
  )

  const wellNames = useMemo(() => {
    const names = [...new Set(filtered.map(o => o.well_name))]
    names.sort()
    return names
  }, [filtered])

  const maxDay = useMemo(
    () => (filtered.length > 0 ? Math.max(...filtered.map(o => o.end_day)) : 0),
    [filtered],
  )

  /* KPI counts */
  const totalCount = operations.length
  const dncCount = operations.filter(o => o.category === 'D&C').length
  const interventionCount = operations.filter(o => o.category === 'Well Intervention').length
  const maintenanceCount = operations.filter(o => o.category === 'Maintenance').length

  /* Category summary for sidebar */
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const op of operations) {
      counts[op.category] = (counts[op.category] || 0) + 1
    }
    return counts
  }, [operations])

  /* ── Gantt helpers ───────────────────────────────── */

  const ganttHeight = Math.max(
    GANTT_MIN_HEIGHT,
    GANTT_PADDING_TOP + wellNames.length * GANTT_ROW_HEIGHT + GANTT_PADDING_BOTTOM,
  )

  const chartWidth = useRef(800)
  const [svgWidth, setSvgWidth] = useState(800)

  useEffect(() => {
    if (!svgRef.current) return
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        chartWidth.current = w
        setSvgWidth(w)
      }
    })
    observer.observe(svgRef.current.parentElement!)
    return () => observer.disconnect()
  }, [])

  const plotWidth = svgWidth - GANTT_LABEL_WIDTH - 16 // 16px right padding
  const dayScale = maxDay > 0 ? plotWidth / maxDay : 1

  /* X-axis ticks */
  const xTicks = useMemo(() => {
    if (maxDay === 0) return []
    const idealCount = Math.floor(plotWidth / 80)
    const rawStep = maxDay / Math.max(idealCount, 1)
    const niceSteps = [1, 5, 10, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000]
    const step = niceSteps.find(s => s >= rawStep) || rawStep
    const ticks: number[] = []
    for (let t = 0; t <= maxDay; t += step) {
      ticks.push(Math.round(t))
    }
    if (ticks[ticks.length - 1] < maxDay) ticks.push(maxDay)
    return ticks
  }, [maxDay, plotWidth])

  const handleBarMouseEnter = useCallback(
    (op: Operation, e: React.MouseEvent<SVGRectElement>) => {
      const rect = svgRef.current?.getBoundingClientRect()
      if (!rect) return
      setTooltip({ op, x: e.clientX - rect.left, y: e.clientY - rect.top })
    },
    [],
  )

  const handleBarMouseLeave = useCallback(() => setTooltip(null), [])

  /* ── Render ──────────────────────────────────────── */

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '240px 1fr',
        gap: 16,
        height: 'calc(100vh - 130px)',
        minHeight: 600,
      }}
    >
      {/* ──────────── Left sidebar ──────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {/* Run selector */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>
            SELECT RUN
          </div>
          <select
            value={selectedRun}
            onChange={e => {
              setSelectedRun(e.target.value)
              onRunSelect(e.target.value)
            }}
            style={{
              width: '100%',
              background: 'var(--bg-panel)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 11,
              outline: 'none',
            }}
          >
            <option value="">Choose run...</option>
            {runs.map(r => (
              <option key={r.id} value={r.id}>
                {r.scenario_name || 'Run'} — {r.id}
              </option>
            ))}
          </select>
        </div>

        {/* Activity stats */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>
            ACTIVITY SUMMARY
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {CATEGORIES.filter(c => c !== 'All').map(cat => (
              <div key={cat} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      background: CATEGORY_COLORS[cat] || 'var(--text-muted)',
                    }}
                  />
                  <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{cat}</span>
                </div>
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                  }}
                >
                  {categoryCounts[cat] || 0}
                </span>
              </div>
            ))}
            <div
              style={{
                marginTop: 6,
                paddingTop: 6,
                borderTop: '1px solid var(--border)',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600 }}>Total</span>
              <span
                style={{
                  fontSize: 10,
                  fontFamily: 'monospace',
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                }}
              >
                {totalCount}
              </span>
            </div>
          </div>
        </div>

        {/* Category filter */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>
            FILTER BY CATEGORY
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {CATEGORIES.map(cat => {
              const isActive = activeCategory === cat
              const catColor = cat === 'All' ? 'var(--text-primary)' : CATEGORY_COLORS[cat]
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  style={{
                    background: isActive ? 'var(--bg-panel)' : 'transparent',
                    border: isActive
                      ? `1px solid ${catColor || 'var(--border)'}`
                      : '1px solid var(--border)',
                    borderRadius: 5,
                    padding: '6px 10px',
                    textAlign: 'left',
                    color: isActive ? catColor : 'var(--text-secondary)',
                    fontSize: 11,
                    fontWeight: isActive ? 600 : 400,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {cat}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* ──────────── Right panel ──────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {/* Loading / error states */}
        {loading && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div className="spinner" />
          </div>
        )}

        {error && (
          <div
            style={{
              background: 'var(--red-dim)',
              border: '1px solid var(--red)',
              borderRadius: 6,
              padding: '8px 12px',
              fontSize: 11,
              color: 'var(--red)',
            }}
          >
            {error}
          </div>
        )}

        {!loading && !error && !selectedRun && (
          <div
            className="card"
            style={{
              padding: 40,
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: 13,
            }}
          >
            Select a completed simulation run to view operations.
          </div>
        )}

        {!loading && !error && selectedRun && operations.length === 0 && (
          <div
            className="card"
            style={{
              padding: 40,
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: 13,
            }}
          >
            No operational activities found for this run.
          </div>
        )}

        {!loading && operations.length > 0 && (
          <>
            {/* ── KPI Row ── */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              {[
                { label: 'Total Activities', value: totalCount, color: 'var(--text-primary)' },
                { label: 'D&C', value: dncCount, color: 'var(--blue)' },
                { label: 'Well Intervention', value: interventionCount, color: 'var(--amber)' },
                { label: 'Maintenance', value: maintenanceCount, color: 'var(--red)' },
              ].map(kpi => (
                <div key={kpi.label} className="card" style={{ padding: '14px 16px', textAlign: 'center' }}>
                  <div
                    style={{
                      fontSize: 22,
                      fontWeight: 700,
                      color: kpi.color,
                      fontFamily: 'monospace',
                      letterSpacing: '-0.02em',
                    }}
                  >
                    {kpi.value}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontWeight: 600 }}>
                    {kpi.label}
                  </div>
                </div>
              ))}
            </div>

            {/* ── Gantt Chart ── */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>
                OPERATIONS TIMELINE
                {activeCategory !== 'All' && (
                  <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>
                    — {activeCategory}
                  </span>
                )}
              </div>

              <div style={{ width: '100%', overflowX: 'auto', position: 'relative' }}>
                <svg
                  ref={svgRef}
                  width="100%"
                  height={ganttHeight}
                  style={{ display: 'block', minWidth: 500 }}
                >
                  {/* Grid lines */}
                  {xTicks.map(t => {
                    const x = GANTT_LABEL_WIDTH + t * dayScale
                    return (
                      <line
                        key={`grid-${t}`}
                        x1={x}
                        y1={GANTT_PADDING_TOP - 4}
                        x2={x}
                        y2={GANTT_PADDING_TOP + wellNames.length * GANTT_ROW_HEIGHT}
                        stroke="#1e2130"
                        strokeWidth={1}
                      />
                    )
                  })}

                  {/* X-axis labels */}
                  {xTicks.map(t => (
                    <text
                      key={`tick-${t}`}
                      x={GANTT_LABEL_WIDTH + t * dayScale}
                      y={GANTT_PADDING_TOP - 10}
                      textAnchor="middle"
                      fill="#6b7280"
                      fontSize={9}
                      fontFamily="monospace"
                    >
                      {t}d
                    </text>
                  ))}

                  {/* Row backgrounds and well labels */}
                  {wellNames.map((well, i) => {
                    const y = GANTT_PADDING_TOP + i * GANTT_ROW_HEIGHT
                    return (
                      <g key={`row-${well}`}>
                        {i % 2 === 0 && (
                          <rect
                            x={0}
                            y={y}
                            width="100%"
                            height={GANTT_ROW_HEIGHT}
                            fill="rgba(255,255,255,0.015)"
                          />
                        )}
                        <line
                          x1={GANTT_LABEL_WIDTH}
                          y1={y + GANTT_ROW_HEIGHT}
                          x2="100%"
                          y2={y + GANTT_ROW_HEIGHT}
                          stroke="#1e2130"
                          strokeWidth={0.5}
                        />
                        <text
                          x={GANTT_LABEL_WIDTH - 8}
                          y={y + GANTT_ROW_HEIGHT / 2}
                          textAnchor="end"
                          dominantBaseline="central"
                          fill="#b0b6c8"
                          fontSize={10}
                          fontWeight={500}
                        >
                          {well}
                        </text>
                      </g>
                    )
                  })}

                  {/* Activity bars */}
                  {filtered.map((op, idx) => {
                    const rowIdx = wellNames.indexOf(op.well_name)
                    if (rowIdx === -1) return null
                    const y =
                      GANTT_PADDING_TOP +
                      rowIdx * GANTT_ROW_HEIGHT +
                      (GANTT_ROW_HEIGHT - BAR_HEIGHT) / 2
                    const x = GANTT_LABEL_WIDTH + op.start_day * dayScale
                    const w = Math.max(op.duration_days * dayScale, 3) // min 3px so tiny bars are visible
                    return (
                      <rect
                        key={`bar-${idx}`}
                        x={x}
                        y={y}
                        width={w}
                        height={BAR_HEIGHT}
                        rx={BAR_RADIUS}
                        ry={BAR_RADIUS}
                        fill={op.color || '#6b7280'}
                        fillOpacity={0.85}
                        stroke={op.color || '#6b7280'}
                        strokeWidth={0.5}
                        style={{ cursor: 'pointer', transition: 'fill-opacity 0.15s' }}
                        onMouseEnter={e => handleBarMouseEnter(op, e)}
                        onMouseMove={e => handleBarMouseEnter(op, e)}
                        onMouseLeave={handleBarMouseLeave}
                      />
                    )
                  })}
                </svg>

                {/* Tooltip */}
                {tooltip && (
                  <div
                    style={{
                      position: 'absolute',
                      left: tooltip.x + 12,
                      top: tooltip.y - 8,
                      background: '#13151a',
                      border: '1px solid #2a2e3a',
                      borderRadius: 6,
                      padding: '8px 12px',
                      fontSize: 11,
                      color: 'var(--text-primary)',
                      pointerEvents: 'none',
                      zIndex: 20,
                      whiteSpace: 'nowrap',
                      boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 4, color: tooltip.op.color }}>
                      {tooltip.op.activity_name}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      <span style={{ color: 'var(--text-muted)' }}>Well:</span> {tooltip.op.well_name}
                      <br />
                      <span style={{ color: 'var(--text-muted)' }}>Category:</span>{' '}
                      {tooltip.op.category}
                      <br />
                      <span style={{ color: 'var(--text-muted)' }}>Days:</span>{' '}
                      {tooltip.op.start_day} — {tooltip.op.end_day} ({tooltip.op.duration_days}d)
                      <br />
                      <span style={{ color: 'var(--text-muted)' }}>Trigger:</span>{' '}
                      {tooltip.op.trigger_reason}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── Activity Detail Table ── */}
            <div className="card" style={{ padding: '14px 16px', flex: 1, minHeight: 200 }}>
              <div className="label" style={{ marginBottom: 10 }}>
                ACTIVITY DETAILS
                <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>
                  ({filtered.length} {filtered.length === 1 ? 'activity' : 'activities'})
                </span>
              </div>
              <div style={{ overflowY: 'auto', maxHeight: 320 }}>
                <table
                  style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: 11,
                  }}
                >
                  <thead>
                    <tr>
                      {['Well', 'Activity', 'Category', 'Start Day', 'Duration', 'Trigger Reason'].map(
                        col => (
                          <th
                            key={col}
                            style={{
                              textAlign: 'left',
                              padding: '8px 10px',
                              color: 'var(--text-muted)',
                              fontWeight: 600,
                              fontSize: 10,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                              borderBottom: '1px solid var(--border)',
                              position: 'sticky',
                              top: 0,
                              background: 'var(--bg-card)',
                              zIndex: 1,
                            }}
                          >
                            {col}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((op, idx) => (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={e =>
                          ((e.currentTarget as HTMLTableRowElement).style.background =
                            'rgba(255,255,255,0.025)')
                        }
                        onMouseLeave={e =>
                          ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
                        }
                      >
                        <td style={{ padding: '7px 10px', color: 'var(--text-primary)', fontWeight: 500 }}>
                          {op.well_name}
                        </td>
                        <td style={{ padding: '7px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div
                              style={{
                                width: 8,
                                height: 8,
                                borderRadius: 2,
                                background: op.color || 'var(--text-muted)',
                                flexShrink: 0,
                              }}
                            />
                            <span style={{ color: 'var(--text-primary)' }}>{op.activity_name}</span>
                          </div>
                        </td>
                        <td style={{ padding: '7px 10px' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 7px',
                              borderRadius: 4,
                              fontSize: 10,
                              fontWeight: 600,
                              background:
                                CATEGORY_COLORS[op.category]
                                  ? `color-mix(in srgb, ${CATEGORY_COLORS[op.category]} 15%, transparent)`
                                  : 'var(--bg-panel)',
                              color: CATEGORY_COLORS[op.category] || 'var(--text-secondary)',
                              border: `1px solid ${
                                CATEGORY_COLORS[op.category]
                                  ? `color-mix(in srgb, ${CATEGORY_COLORS[op.category]} 30%, transparent)`
                                  : 'var(--border)'
                              }`,
                            }}
                          >
                            {op.category}
                          </span>
                        </td>
                        <td
                          style={{
                            padding: '7px 10px',
                            fontFamily: 'monospace',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {op.start_day}
                        </td>
                        <td
                          style={{
                            padding: '7px 10px',
                            fontFamily: 'monospace',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {op.duration_days}d
                        </td>
                        <td
                          style={{
                            padding: '7px 10px',
                            color: 'var(--text-muted)',
                            maxWidth: 240,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {op.trigger_reason}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
