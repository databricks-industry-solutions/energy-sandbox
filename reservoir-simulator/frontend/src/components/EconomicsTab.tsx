import { useState, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer
} from 'recharts'

interface CashflowItem {
  year: number; revenue: number; opex: number; capex: number
  net_cashflow: number; discounted_cf: number; cum_npv: number
}

interface EconResult {
  npv_usd: number; irr: number; payback_year: number
  total_revenue: number; total_opex: number; total_capex: number
  cashflows: CashflowItem[]
}

interface Run {
  id: string; scenario_name: string; status: string
}

interface Props {
  activeRunId: string | null
  onRunSelect: (id: string) => void
}

export default function EconomicsTab({ activeRunId, onRunSelect }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedRun, setSelectedRun] = useState(activeRunId || '')
  const [result, setResult] = useState<EconResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Inputs
  const [oilPrice, setOilPrice] = useState(75)
  const [gasPrice, setGasPrice] = useState(2.80)
  const [discountRate, setDiscountRate] = useState(0.10)
  const [opexPerBoe, setOpexPerBoe] = useState(8.50)
  const [capexPerWell, setCapexPerWell] = useState(8000000)

  useEffect(() => {
    fetch('/api/runs').then(r => r.json()).then(d => setRuns(Array.isArray(d) ? d : [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (activeRunId) setSelectedRun(activeRunId)
  }, [activeRunId])

  // Load existing economics when run changes
  useEffect(() => {
    if (!selectedRun) return
    fetch(`/api/economics/${selectedRun}`)
      .then(r => r.json())
      .then(data => {
        if (data.cashflows) {
          setResult({
            npv_usd: data.npv_usd,
            irr: data.irr,
            payback_year: data.payback_year,
            total_revenue: data.total_revenue || 0,
            total_opex: data.total_opex || 0,
            total_capex: data.total_capex || 0,
            cashflows: data.cashflows,
          })
        }
      })
      .catch(() => {})
  }, [selectedRun])

  const calculate = async () => {
    if (!selectedRun) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/economics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id: selectedRun,
          oil_price: oilPrice,
          gas_price: gasPrice,
          discount_rate: discountRate,
          opex_per_boe: opexPerBoe,
          capex_per_well: capexPerWell,
        }),
      })
      const data = await res.json()
      if (data.error) {
        setError(data.error)
      } else {
        setResult(data)
      }
    } catch {
      setError('Failed to compute economics')
    }
    setLoading(false)
  }

  const fmt = (v: number) => {
    if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
    if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
    if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`
    return `$${v.toFixed(0)}`
  }

  const tooltipStyle = {
    contentStyle: { background: '#13151a', border: '1px solid #2a2e3a', borderRadius: 6, fontSize: 11 },
    labelStyle: { color: '#b0b6c8' },
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600 }}>
      {/* Left panel: inputs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Run selector */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>SELECT RUN</div>
          <select value={selectedRun} onChange={e => { setSelectedRun(e.target.value); onRunSelect(e.target.value) }}
            style={{
              width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 11, outline: 'none',
            }}>
            <option value="">Choose run...</option>
            {runs.map(r => (
              <option key={r.id} value={r.id}>{r.scenario_name || 'Run'} — {r.id}</option>
            ))}
          </select>
        </div>

        {/* Price assumptions */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 10 }}>PRICE ASSUMPTIONS</div>
          {[
            { label: 'Oil Price ($/bbl)', value: oilPrice, set: setOilPrice, step: 5 },
            { label: 'Gas Price ($/MSCF)', value: gasPrice, set: setGasPrice, step: 0.25 },
          ].map(inp => (
            <div key={inp.label} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{inp.label}</div>
              <input type="number" value={inp.value} step={inp.step}
                onChange={e => inp.set(Number(e.target.value))}
                style={{
                  width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 12, outline: 'none',
                }} />
            </div>
          ))}
        </div>

        {/* Cost assumptions */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 10 }}>COST PARAMETERS</div>
          {[
            { label: 'Discount Rate', value: discountRate, set: setDiscountRate, step: 0.01 },
            { label: 'OPEX ($/BOE)', value: opexPerBoe, set: setOpexPerBoe, step: 0.5 },
            { label: 'CAPEX per Well ($)', value: capexPerWell, set: setCapexPerWell, step: 500000 },
          ].map(inp => (
            <div key={inp.label} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{inp.label}</div>
              <input type="number" value={inp.value} step={inp.step}
                onChange={e => inp.set(Number(e.target.value))}
                style={{
                  width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 12, outline: 'none',
                }} />
            </div>
          ))}
        </div>

        <button onClick={calculate} disabled={loading || !selectedRun} style={{
          background: loading || !selectedRun ? 'var(--bg-panel)' : 'var(--green-dim)',
          color: loading || !selectedRun ? 'var(--text-muted)' : 'var(--green)',
          border: `1px solid ${loading || !selectedRun ? 'var(--border)' : 'var(--green)'}`,
          borderRadius: 6, padding: '10px 16px', fontSize: 13, fontWeight: 700,
        }}>
          {loading ? 'Computing...' : 'Calculate Economics'}
        </button>

        {error && (
          <div style={{ background: 'var(--red-dim)', border: '1px solid var(--red)', borderRadius: 6, padding: '8px 12px', fontSize: 11, color: 'var(--red)' }}>
            {error}
          </div>
        )}
      </div>

      {/* Right panel: results */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {!result && !loading && (
          <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            {selectedRun ? 'Click "Calculate Economics" to compute NPV, IRR, and cashflows.' : 'Select a completed simulation run to begin.'}
          </div>
        )}

        {result && (
          <>
            {/* KPI row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
              {[
                { label: 'NPV', value: fmt(result.npv_usd), color: result.npv_usd > 0 ? 'var(--green)' : 'var(--red)', big: true },
                { label: 'IRR', value: `${(result.irr * 100).toFixed(1)}%`, color: 'var(--blue)', big: false },
                { label: 'Payback', value: `Year ${result.payback_year}`, color: 'var(--amber)', big: false },
                { label: 'Revenue', value: fmt(result.total_revenue), color: 'var(--teal)', big: false },
                { label: 'Total OPEX', value: fmt(result.total_opex), color: 'var(--purple)', big: false },
              ].map(kpi => (
                <div key={kpi.label} className="card" style={{ padding: '14px 16px', textAlign: 'center' }}>
                  <div style={{
                    fontSize: kpi.big ? 24 : 18, fontWeight: 700, color: kpi.color,
                    fontFamily: 'monospace', letterSpacing: '-0.02em',
                  }}>
                    {kpi.value}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontWeight: 600 }}>
                    {kpi.label}
                  </div>
                </div>
              ))}
            </div>

            {/* Annual cashflow bar chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>ANNUAL CASHFLOWS</div>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={result.cashflows.filter(c => c.year > 0)}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `Y${v}`} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `$${(v / 1e6).toFixed(0)}M`} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [fmt(v), '']} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Bar dataKey="revenue" fill="#00c875" name="Revenue" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="opex" fill="#ff4d4f" name="OPEX" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="net_cashflow" fill="#4dabf7" name="Net Cashflow" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Cumulative NPV line chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>CUMULATIVE NPV</div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={result.cashflows}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis dataKey="year" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `Y${v}`} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `$${(v / 1e6).toFixed(0)}M`} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [fmt(v), 'Cumulative NPV']} />
                  <Line type="monotone" dataKey="cum_npv" stroke="#ffa940" strokeWidth={2.5} dot={{ r: 3, fill: '#ffa940' }} name="Cumulative NPV" />
                  {/* Zero line */}
                  <Line type="monotone" dataKey={() => 0} stroke="#6b7280" strokeWidth={1} strokeDasharray="5 5" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
