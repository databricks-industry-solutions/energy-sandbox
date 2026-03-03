import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts'

interface Run { id: string; scenario_name: string; status: string }
interface LiftingData {
  total_opex_usd: number; total_cost_usd: number; cum_boe: number
  lifting_cost_per_boe: number; full_cycle_cost_per_boe: number
}
interface CostData {
  total_cost_usd: number
  well_costs: Record<string, { total: number; categories: Record<string, number> }>
  category_costs: Record<string, number>
  sap_materials_used: number
  sap_services_used: number
}
interface Props { activeRunId: string | null; onRunSelect: (id: string) => void }

const CAT_COLORS: Record<string, string> = {
  'D&C': '#E67E22', 'Artificial Lift': '#3498DB', 'Production Chemistry': '#9B59B6',
  'Well Intervention': '#E74C3C', 'Maintenance': '#7F8C8D', 'Injection': '#2980B9',
}

const fmt = (v: number) => {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

export default function CostAnalysisTab({ activeRunId, onRunSelect }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedRun, setSelectedRun] = useState(activeRunId || '')
  const [costs, setCosts] = useState<CostData | null>(null)
  const [lifting, setLifting] = useState<Record<string, LiftingData>>({})
  const [sapCounts, setSapCounts] = useState({ materials: 0, services: 0, equipment: 0 })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/runs').then(r => r.json()).then(d => setRuns(Array.isArray(d) ? d : [])).catch(() => {})
    Promise.all([
      fetch('/api/sap/materials').then(r => r.json()).catch(() => ({ count: 0 })),
      fetch('/api/sap/services').then(r => r.json()).catch(() => ({ count: 0 })),
      fetch('/api/sap/equipment').then(r => r.json()).catch(() => ({ count: 0 })),
    ]).then(([m, s, e]) => setSapCounts({ materials: m.count || 0, services: s.count || 0, equipment: e.count || 0 }))
  }, [])

  useEffect(() => { if (activeRunId) setSelectedRun(activeRunId) }, [activeRunId])

  useEffect(() => {
    if (!selectedRun) return
    setLoading(true)
    Promise.all([
      fetch(`/api/costs/${selectedRun}`).then(r => r.json()).catch(() => null),
      fetch(`/api/costs/${selectedRun}/lifting`).then(r => r.json()).catch(() => null),
    ]).then(([c, l]) => {
      if (c && c.total_cost_usd !== undefined) setCosts(c)
      else setCosts(null)
      if (l && l.lifting_costs) setLifting(l.lifting_costs)
      else setLifting({})
    }).finally(() => setLoading(false))
  }, [selectedRun])

  const catData = costs ? Object.entries(costs.category_costs).map(([cat, cost]) => ({
    category: cat, cost, color: CAT_COLORS[cat] || '#888',
  })).sort((a, b) => b.cost - a.cost) : []

  const wellData = costs ? Object.entries(costs.well_costs).map(([well, data]) => ({
    well, total: data.total,
  })).sort((a, b) => b.total - a.total) : []

  const dncCost = costs?.category_costs['D&C'] || 0
  const opexCost = costs ? costs.total_cost_usd - dncCost : 0
  const liftingVals = Object.values(lifting)
  const avgLifting = liftingVals.length
    ? liftingVals.reduce((a, v) => a + v.lifting_cost_per_boe, 0) / liftingVals.length : 0

  const tooltipStyle = {
    contentStyle: { background: '#13151a', border: '1px solid #2a2e3a', borderRadius: 6, fontSize: 11 },
    labelStyle: { color: '#b0b6c8' },
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600 }}>
      {/* Left panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>SELECT RUN</div>
          <select value={selectedRun} onChange={e => { setSelectedRun(e.target.value); onRunSelect(e.target.value) }}
            style={{ width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 11, outline: 'none' }}>
            <option value="">Choose run...</option>
            {runs.map(r => <option key={r.id} value={r.id}>{r.scenario_name || 'Run'} — {r.id}</option>)}
          </select>
        </div>

        {/* SAP Data Status */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 10 }}>SAP BDC — SUPPLY CHAIN DATA</div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 10 }}>Via Delta Sharing · Unity Catalog</div>
          {[
            { label: 'Materials', count: sapCounts.materials, color: 'var(--amber)' },
            { label: 'Service Contracts', count: sapCounts.services, color: 'var(--blue)' },
            { label: 'Equipment Inventory', count: sapCounts.equipment, color: 'var(--teal)' },
          ].map(item => (
            <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{item.label}</span>
              <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'monospace', color: item.color }}>{item.count}</span>
            </div>
          ))}
          <div style={{ marginTop: 8, padding: '5px 8px', background: 'var(--green-dim)', border: '1px solid var(--green)', borderRadius: 4, fontSize: 9, color: 'var(--green)', textAlign: 'center', fontWeight: 700 }}>
            LIVE · {sapCounts.materials + sapCounts.services + sapCounts.equipment} items synced
          </div>
        </div>

        {/* Cost summary */}
        {costs && (
          <div className="card" style={{ padding: 13, flex: 1 }}>
            <div className="label" style={{ marginBottom: 10 }}>COST SUMMARY</div>
            {catData.map(cd => (
              <div key={cd.category} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: cd.color }} />
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{cd.category}</span>
                  </div>
                  <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-primary)', fontWeight: 600 }}>{fmt(cd.cost)}</span>
                </div>
                <div style={{ height: 3, background: 'var(--bg-panel)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${(cd.cost / (costs?.total_cost_usd || 1)) * 100}%`, background: cd.color, borderRadius: 2 }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Right panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {loading && <div style={{ textAlign: 'center', padding: 40 }}><div className="spinner" /></div>}
        {!loading && !costs && (
          <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            {selectedRun ? 'No cost data available. Run a simulation to generate operations & cost estimates.' : 'Select a completed simulation run.'}
          </div>
        )}

        {costs && (
          <>
            {/* KPIs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
              {[
                { label: 'Total Cost', value: fmt(costs.total_cost_usd), color: 'var(--amber)', big: true },
                { label: 'D&C Cost', value: fmt(dncCost), color: '#E67E22' },
                { label: 'OPEX Cost', value: fmt(opexCost), color: 'var(--blue)' },
                { label: 'Avg Lifting $/BOE', value: `$${avgLifting.toFixed(2)}`, color: 'var(--teal)' },
                { label: 'SAP Items Used', value: `${(costs.sap_materials_used || 0) + (costs.sap_services_used || 0)}`, color: 'var(--purple)' },
              ].map(kpi => (
                <div key={kpi.label} className="card" style={{ padding: '14px 16px', textAlign: 'center' }}>
                  <div style={{ fontSize: kpi.big ? 22 : 17, fontWeight: 700, color: kpi.color, fontFamily: 'monospace' }}>{kpi.value}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontWeight: 600 }}>{kpi.label}</div>
                </div>
              ))}
            </div>

            {/* Cost by Category */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>COST BY CATEGORY (SAP PRICING)</div>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={catData} layout="vertical" margin={{ left: 120 }}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => fmt(v)} />
                  <YAxis type="category" dataKey="category" tick={{ fontSize: 10, fill: '#b0b6c8' }} width={115} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [fmt(v), 'Cost']} />
                  <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={22}>
                    {catData.map((cd, i) => <Cell key={i} fill={cd.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Per-well cost */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>COST PER WELL</div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={wellData}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis dataKey="well" tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => fmt(v)} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [fmt(v), 'Total Cost']} />
                  <Bar dataKey="total" fill="var(--blue)" radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Lifting cost table */}
            {Object.keys(lifting).length > 0 && (
              <div className="card" style={{ padding: '14px 16px' }}>
                <div className="label" style={{ marginBottom: 10 }}>LIFTING COST BREAKDOWN (PER WELL)</div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-panel)' }}>
                        {['Well', 'Total OPEX', 'Total Cost', 'Cum BOE', 'Lifting $/BOE', 'Full-Cycle $/BOE'].map(h => (
                          <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, letterSpacing: '0.05em', borderBottom: '1px solid var(--border)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(lifting).sort(([a], [b]) => a.localeCompare(b)).map(([well, data]) => (
                        <tr key={well} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                          <td style={{ padding: '7px 12px', fontWeight: 600, fontFamily: 'monospace', color: 'var(--text-primary)' }}>{well}</td>
                          <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: 'var(--amber)' }}>{fmt(data.total_opex_usd)}</td>
                          <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{fmt(data.total_cost_usd)}</td>
                          <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{data.cum_boe.toLocaleString()}</td>
                          <td style={{ padding: '7px 12px', fontFamily: 'monospace', fontWeight: 700, color: data.lifting_cost_per_boe < 5 ? 'var(--green)' : data.lifting_cost_per_boe < 10 ? 'var(--amber)' : 'var(--red)' }}>
                            ${data.lifting_cost_per_boe.toFixed(2)}
                          </td>
                          <td style={{ padding: '7px 12px', fontFamily: 'monospace', color: 'var(--teal)' }}>${data.full_cycle_cost_per_boe.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
