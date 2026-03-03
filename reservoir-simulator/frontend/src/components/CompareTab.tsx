import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Cell,
} from 'recharts'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Run {
  id: string; scenario_name: string; status: string
}

interface ProfilePoint {
  day: number; oil_rate: number; water_cut: number; pressure: number
}

interface WellLifting {
  lifting_cost_per_boe: number
  [key: string]: number
}

interface CompareRun {
  run_id: string
  scenario_name: string
  cum_oil_stb: number
  cum_gas_mscf: number
  cum_boe: number
  peak_oil_rate: number
  npv_usd: number
  irr: number
  payback_year: number
  total_cost_usd: number
  avg_lifting_cost_boe: number
  full_cycle_cost_boe: number
  num_operations: number
  profile: ProfilePoint[]
  lifting_by_well: Record<string, WellLifting>
}

interface CompareResponse {
  runs: CompareRun[]
  count: number
}

interface Props {
  activeRunId: string | null
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const RUN_COLORS = ['#00c875', '#4dabf7', '#ffa940', '#ff4d4f', '#b37feb', '#36cfc9']
const MAX_SELECTIONS = 6

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const fmt = (v: number | null | undefined): string => {
  const n = v ?? 0
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

const fmtNum = (v: number | null | undefined): string => {
  const n = v ?? 0
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return n.toFixed(0)
}

const tooltipStyle = {
  contentStyle: { background: '#13151a', border: '1px solid #2a2e3a', borderRadius: 6, fontSize: 11 },
  labelStyle: { color: '#b0b6c8' },
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function CompareTab({ activeRunId }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [compareData, setCompareData] = useState<CompareRun[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Fetch available runs
  useEffect(() => {
    fetch('/api/runs')
      .then(r => r.json())
      .then(d => {
        const all: Run[] = Array.isArray(d) ? d : []
        setRuns(all.filter(r => r.status === 'SUCCEEDED'))
      })
      .catch(() => {})
  }, [])

  // Pre-select the active run when it appears
  useEffect(() => {
    if (activeRunId) {
      setSelectedIds(prev => {
        const next = new Set(prev)
        next.add(activeRunId)
        return next
      })
    }
  }, [activeRunId])

  const toggleRun = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < MAX_SELECTIONS) {
        next.add(id)
      }
      return next
    })
  }

  const compare = async () => {
    const ids = Array.from(selectedIds)
    if (ids.length < 2) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_ids: ids }),
      })
      const data: CompareResponse = await res.json()
      if ((data as any).error) {
        setError((data as any).error)
      } else {
        setCompareData(data.runs)
      }
    } catch {
      setError('Failed to fetch comparison data')
    }
    setLoading(false)
  }

  // Map run_id -> color (stable ordering based on selection order in compareData)
  const colorMap = useMemo(() => {
    const m: Record<string, string> = {}
    if (compareData) {
      compareData.forEach((r, i) => { m[r.run_id] = RUN_COLORS[i % RUN_COLORS.length] })
    }
    return m
  }, [compareData])

  // Build unified production profile data: each point has { day, run1_oil, run2_oil, ... }
  const profileData = useMemo(() => {
    if (!compareData) return []
    const dayMap = new Map<number, Record<string, number>>()
    compareData.forEach(r => {
      r.profile.forEach(p => {
        if (!dayMap.has(p.day)) dayMap.set(p.day, { day: p.day })
        dayMap.get(p.day)![r.run_id] = p.oil_rate
      })
    })
    return Array.from(dayMap.values()).sort((a, b) => a.day - b.day)
  }, [compareData])

  // NPV bar chart data
  const npvBarData = useMemo(() => {
    if (!compareData) return []
    return compareData.map(r => ({
      name: r.scenario_name || r.run_id.slice(0, 8),
      run_id: r.run_id,
      npv: r.npv_usd,
    }))
  }, [compareData])

  // Lifting cost per-well grouped bar data
  const liftingData = useMemo(() => {
    if (!compareData) return { data: [] as Record<string, any>[], wells: [] as string[] }
    // Collect all well names across runs
    const wellSet = new Set<string>()
    compareData.forEach(r => {
      Object.keys(r.lifting_by_well || {}).forEach(w => wellSet.add(w))
    })
    const wells = Array.from(wellSet).sort()
    // Each data point is a well, with keys for each run
    const data = wells.map(w => {
      const point: Record<string, any> = { well: w }
      compareData.forEach(r => {
        const key = r.run_id
        point[key] = r.lifting_by_well?.[w]?.lifting_cost_per_boe ?? 0
      })
      return point
    })
    return { data, wells }
  }, [compareData])

  // Summary table metrics
  const summaryMetrics = useMemo<{ label: string; unit: string; key: string; format: (v: number) => string }[]>(() => [
    { label: 'Cum Oil', unit: 'STB', key: 'cum_oil_stb', format: v => fmtNum(v) },
    { label: 'Cum Gas', unit: 'MSCF', key: 'cum_gas_mscf', format: v => fmtNum(v) },
    { label: 'Peak Rate', unit: 'STB/d', key: 'peak_oil_rate', format: v => (v ?? 0).toFixed(0) },
    { label: 'NPV', unit: 'USD', key: 'npv_usd', format: v => fmt(v) },
    { label: 'IRR', unit: '%', key: 'irr', format: v => `${((v ?? 0) * 100).toFixed(1)}%` },
    { label: 'Payback', unit: 'Year', key: 'payback_year', format: v => `Y${(v ?? 0).toFixed(1)}` },
    { label: 'Total Cost', unit: 'USD', key: 'total_cost_usd', format: v => fmt(v) },
    { label: 'Avg Lifting $/BOE', unit: '$/BOE', key: 'avg_lifting_cost_boe', format: v => `$${(v ?? 0).toFixed(2)}` },
    { label: 'Full-Cycle $/BOE', unit: '$/BOE', key: 'full_cycle_cost_boe', format: v => `$${(v ?? 0).toFixed(2)}` },
  ], [])

  // Determine best value per metric for highlighting
  const bestByMetric = useMemo(() => {
    if (!compareData || compareData.length === 0) return {} as Record<string, string>
    const best: Record<string, string> = {}
    summaryMetrics.forEach(m => {
      // Higher is better for: cum_oil_stb, cum_gas_mscf, peak_oil_rate, npv_usd, irr
      // Lower is better for: payback_year, total_cost_usd, avg_lifting_cost_boe, full_cycle_cost_boe
      const higherBetter = ['cum_oil_stb', 'cum_gas_mscf', 'peak_oil_rate', 'npv_usd', 'irr'].includes(m.key)
      let bestVal = higherBetter ? -Infinity : Infinity
      let bestId = ''
      compareData.forEach(r => {
        const val = (r as any)[m.key] as number
        if (higherBetter ? val > bestVal : val < bestVal) {
          bestVal = val
          bestId = r.run_id
        }
      })
      best[m.key] = bestId
    })
    return best
  }, [compareData, summaryMetrics])

  const completedRuns = runs

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600, overflowY: 'auto' }}>

      {/* ─── Run Selector ─── */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div>
            <div className="label">SELECT RUNS TO COMPARE</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
              Choose 2-{MAX_SELECTIONS} completed runs, then click Compare.
            </div>
          </div>
          <button
            onClick={compare}
            disabled={loading || selectedIds.size < 2}
            style={{
              background: loading || selectedIds.size < 2 ? 'var(--bg-panel)' : 'var(--green-dim)',
              color: loading || selectedIds.size < 2 ? 'var(--text-muted)' : 'var(--green)',
              border: `1px solid ${loading || selectedIds.size < 2 ? 'var(--border)' : 'var(--green)'}`,
              borderRadius: 6, padding: '8px 20px', fontSize: 13, fontWeight: 700,
            }}
          >
            {loading ? 'Comparing...' : `Compare (${selectedIds.size})`}
          </button>
        </div>

        {completedRuns.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '10px 0' }}>
            No completed runs found. Run a simulation first.
          </div>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {completedRuns.map(r => {
            const checked = selectedIds.has(r.id)
            const disabled = !checked && selectedIds.size >= MAX_SELECTIONS
            return (
              <label
                key={r.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  background: checked ? 'var(--bg-panel)' : 'transparent',
                  border: checked ? '1px solid var(--blue)' : '1px solid var(--border)',
                  borderRadius: 6, padding: '7px 12px',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  opacity: disabled ? 0.45 : 1,
                  transition: 'all 0.15s',
                  minWidth: 180,
                }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  onChange={() => toggleRun(r.id)}
                  style={{ accentColor: '#4dabf7', width: 14, height: 14, cursor: disabled ? 'not-allowed' : 'pointer' }}
                />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: checked ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {r.scenario_name || 'Run'}
                  </div>
                  <div style={{ fontSize: 9, fontFamily: 'monospace', color: 'var(--text-muted)' }}>
                    {r.id.slice(0, 12)}
                  </div>
                </div>
              </label>
            )
          })}
        </div>
      </div>

      {/* ─── Error ─── */}
      {error && (
        <div style={{ background: 'var(--red-dim)', border: '1px solid var(--red)', borderRadius: 6, padding: '8px 14px', fontSize: 11, color: 'var(--red)' }}>
          {error}
        </div>
      )}

      {/* ─── Empty state ─── */}
      {!compareData && !loading && (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
          Select at least two completed runs and click "Compare" to view side-by-side analysis.
        </div>
      )}

      {/* ─── Loading ─── */}
      {loading && (
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div className="spinner" />
        </div>
      )}

      {/* ─── Results ─── */}
      {compareData && compareData.length > 0 && (
        <>
          {/* ── KPI Comparison Cards ── */}
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(compareData.length, 3)}, 1fr)`, gap: 12 }}>
            {compareData.map((r, idx) => (
              <div key={r.run_id} className="card" style={{ padding: 16, borderTop: `3px solid ${colorMap[r.run_id]}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <div style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: colorMap[r.run_id], flexShrink: 0,
                  }} />
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>
                    {r.scenario_name || `Run ${idx + 1}`}
                  </div>
                  <div style={{ fontSize: 9, fontFamily: 'monospace', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                    {r.run_id.slice(0, 10)}
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {[
                    { label: 'Cum Oil', value: `${fmtNum(r.cum_oil_stb)} STB`, color: 'var(--green)' },
                    { label: 'NPV', value: fmt(r.npv_usd), color: (r.npv_usd ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' },
                    { label: 'IRR', value: `${((r.irr ?? 0) * 100).toFixed(1)}%`, color: 'var(--blue)' },
                    { label: 'Avg Lifting $/BOE', value: `$${(r.avg_lifting_cost_boe ?? 0).toFixed(2)}`, color: 'var(--amber)' },
                    { label: 'Total Cost', value: fmt(r.total_cost_usd), color: 'var(--purple)' },
                    { label: 'Peak Rate', value: `${(r.peak_oil_rate ?? 0).toFixed(0)} STB/d`, color: 'var(--teal)' },
                  ].map(kpi => (
                    <div key={kpi.label} style={{ background: 'var(--bg-panel)', borderRadius: 5, padding: '8px 10px', border: '1px solid var(--border-dim)' }}>
                      <div style={{ fontSize: 15, fontWeight: 700, color: kpi.color, fontFamily: 'monospace', letterSpacing: '-0.02em' }}>
                        {kpi.value}
                      </div>
                      <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontWeight: 600 }}>
                        {kpi.label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* ── Production Profile Overlay ── */}
          <div className="card" style={{ padding: '14px 16px' }}>
            <div className="label" style={{ marginBottom: 10 }}>PRODUCTION PROFILE OVERLAY</div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={profileData}>
                <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: '#6b7280' }}
                  tickFormatter={(v: number) => `${Math.round(v)}d`}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: '#6b7280' }}
                  label={{ value: 'Oil Rate (STB/d)', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#6b7280' } }}
                />
                <Tooltip
                  {...tooltipStyle}
                  formatter={(v: number, name: string) => {
                    const run = compareData.find(r => r.run_id === name)
                    const label = run?.scenario_name || name.slice(0, 10)
                    return [`${v.toFixed(1)} STB/d`, label]
                  }}
                  labelFormatter={(v: number) => `Day ${Math.round(v)}`}
                />
                <Legend
                  wrapperStyle={{ fontSize: 10 }}
                  formatter={(value: string) => {
                    const run = compareData.find(r => r.run_id === value)
                    return run?.scenario_name || value.slice(0, 10)
                  }}
                />
                {compareData.map(r => (
                  <Line
                    key={r.run_id}
                    type="monotone"
                    dataKey={r.run_id}
                    stroke={colorMap[r.run_id]}
                    strokeWidth={2}
                    dot={false}
                    name={r.run_id}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ── Charts Row: NPV + Lifting Cost ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {/* NPV Comparison Bar Chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>NPV COMPARISON</div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={npvBarData}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    interval={0}
                    angle={-25}
                    textAnchor="end"
                    height={50}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    tickFormatter={(v: number) => fmt(v)}
                  />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={(v: number) => [fmt(v), 'NPV']}
                  />
                  <Bar dataKey="npv" radius={[3, 3, 0, 0]} name="NPV">
                    {npvBarData.map((entry, i) => (
                      <Cell key={entry.run_id} fill={colorMap[entry.run_id] || RUN_COLORS[i % RUN_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Lifting Cost Per-Well Bar Chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>LIFTING COST PER WELL ($/BOE)</div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={liftingData.data}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="well"
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    interval={0}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={(v: number, name: string) => {
                      const run = compareData.find(r => r.run_id === name)
                      const label = run?.scenario_name || name.slice(0, 10)
                      return [`$${v.toFixed(2)}/BOE`, label]
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 10 }}
                    formatter={(value: string) => {
                      const run = compareData.find(r => r.run_id === value)
                      return run?.scenario_name || value.slice(0, 10)
                    }}
                  />
                  {compareData.map(r => (
                    <Bar
                      key={r.run_id}
                      dataKey={r.run_id}
                      fill={colorMap[r.run_id]}
                      radius={[2, 2, 0, 0]}
                      name={r.run_id}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── Summary Comparison Table ── */}
          <div className="card" style={{ padding: '14px 16px' }}>
            <div className="label" style={{ marginBottom: 10 }}>SUMMARY COMPARISON</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-panel)' }}>
                    <th style={{
                      padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)',
                      fontWeight: 600, fontSize: 10, letterSpacing: '0.05em',
                      borderBottom: '1px solid var(--border)', position: 'sticky', left: 0,
                      background: 'var(--bg-panel)', zIndex: 1, minWidth: 140,
                    }}>
                      Metric
                    </th>
                    {compareData.map((r, idx) => (
                      <th key={r.run_id} style={{
                        padding: '8px 12px', textAlign: 'right',
                        fontWeight: 600, fontSize: 10, letterSpacing: '0.05em',
                        borderBottom: '1px solid var(--border)', minWidth: 120,
                        color: colorMap[r.run_id],
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: colorMap[r.run_id] }} />
                          {r.scenario_name || `Run ${idx + 1}`}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summaryMetrics.map((m, mIdx) => (
                    <tr key={m.key} style={{
                      borderBottom: '1px solid var(--border-dim)',
                      background: mIdx % 2 === 0 ? 'transparent' : 'var(--bg-card)',
                    }}>
                      <td style={{
                        padding: '7px 12px', color: 'var(--text-secondary)',
                        fontWeight: 500, position: 'sticky', left: 0,
                        background: mIdx % 2 === 0 ? 'var(--bg-card)' : 'var(--bg-card)',
                        zIndex: 1,
                      }}>
                        {m.label}
                        <span style={{ fontSize: 9, color: 'var(--text-muted)', marginLeft: 5 }}>({m.unit})</span>
                      </td>
                      {compareData.map(r => {
                        const val = (r as any)[m.key] as number
                        const isBest = bestByMetric[m.key] === r.run_id
                        return (
                          <td key={r.run_id} style={{
                            padding: '7px 12px', textAlign: 'right',
                            fontFamily: 'monospace', fontWeight: isBest ? 700 : 400,
                            color: isBest ? 'var(--green)' : 'var(--text-primary)',
                            background: isBest ? 'var(--green-dim)' : 'transparent',
                            borderRadius: isBest ? 3 : 0,
                          }}>
                            {m.format(val)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
