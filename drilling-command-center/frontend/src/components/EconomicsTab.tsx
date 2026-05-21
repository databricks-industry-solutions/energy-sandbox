import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid, ReferenceLine } from 'recharts'

interface EconWell {
  well_id: string
  well_name: string
  basin?: string
  status?: string
  capex_musd: number
  opex_musd_yr: number
  peak_rate_bopd: number
  decline_pct_yr: number
  wti_break_even: number
  npv10_base_musd: number
  npv10_live_musd: number
  irr_pct: number
  payback_years: number
  co2_tonnes_yr: number
  margin_per_bbl: number
}

interface Summary {
  wti_spot: number
  wti_date: string | null
  total_capex_musd: number
  total_npv_live_musd: number
  total_co2_tonnes_yr: number
  wells: EconWell[]
}

export default function EconomicsTab({ wellId }: { wellId: string }) {
  const [data, setData]         = useState<Summary | null>(null)
  const [prices, setPrices]     = useState<{ date: string; price: number }[]>([])
  const [curve, setCurve]       = useState<any>(null)
  const [selected, setSelected] = useState(wellId)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    ;(async () => {
      setLoading(true)
      const [s, p] = await Promise.all([
        fetch('/api/economics/summary').then(r => r.json()),
        fetch('/api/economics/prices').then(r => r.json()),
      ])
      setData(s)
      setPrices(p)
      setLoading(false)
    })()
  }, [])

  useEffect(() => {
    ;(async () => {
      if (!selected) return
      const c = await fetch(`/api/economics/${selected}/curve`).then(r => r.json())
      setCurve(c)
    })()
  }, [selected])

  if (loading || !data) {
    return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Loading economics…</div>
  }

  const priceSeries = prices.slice(-360)  // ~last year daily
  const topNpv = [...data.wells].sort((a, b) => b.npv10_live_musd - a.npv10_live_musd).slice(0, 8)

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12,
      }}>
        <Kpi label="WTI Spot (FRED)"     value={`$${data.wti_spot.toFixed(2)}`} sub={data.wti_date || ''} color="var(--gold)" />
        <Kpi label="Portfolio NPV₁₀"     value={`$${data.total_npv_live_musd.toFixed(0)}M`} sub={`${data.wells.length} wells · live WTI`} color="var(--green)" />
        <Kpi label="Total CAPEX Committed" value={`$${data.total_capex_musd.toFixed(0)}M`} sub="across portfolio" color="var(--blue)" />
        <Kpi label="CO₂ (annual)"        value={`${(data.total_co2_tonnes_yr/1000).toFixed(0)}k t`} sub="tonnes CO₂ / year" color="var(--amber)" />
        <Kpi label="Avg Break-Even"      value={`$${(data.wells.reduce((s, w) => s + w.wti_break_even, 0) / Math.max(data.wells.length, 1)).toFixed(0)}`} sub="$ / bbl WTI" color="var(--purple)" />
      </div>

      <Panel title="WTI spot · daily · 3-year window (FRED / DCOILWTICO)" subtitle="Live price drives portfolio NPV re-rating">
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={priceSeries} margin={{ left: -6, right: 6, top: 6, bottom: 0 }}>
            <CartesianGrid stroke="var(--border-dim)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} minTickGap={50} />
            <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} domain={['auto', 'auto']} width={44} />
            <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', fontSize: 12 }} />
            <Line type="monotone" dataKey="price" stroke="var(--gold)" strokeWidth={1.6} dot={false} />
            <ReferenceLine y={data.wti_spot} stroke="var(--green)" strokeDasharray="4 4" label={{ value: `spot $${data.wti_spot.toFixed(0)}`, fill: 'var(--green)', fontSize: 10 }} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel title="NPV₁₀ — live vs base" subtitle="Live uses current WTI spot, base uses book assumption">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topNpv} margin={{ left: -6, right: 10, top: 10, bottom: 30 }}>
              <CartesianGrid stroke="var(--border-dim)" vertical={false} />
              <XAxis dataKey="well_id" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} angle={-35} textAnchor="end" interval={0} height={50} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', fontSize: 12 }} />
              <Bar dataKey="npv10_base_musd" fill="var(--blue)" name="base $M" />
              <Bar dataKey="npv10_live_musd" fill="var(--green)" name="live $M" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title={`Production forecast — ${selected}`} subtitle="10-yr decline · rate and cumulative cashflow">
          {curve && (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={curve.years.map((y: number, i: number) => ({
                year: y,
                rate: curve.rate_bopd[i],
                cum: curve.cumulative_musd[i],
              }))} margin={{ left: 0, right: 10, top: 10, bottom: 0 }}>
                <CartesianGrid stroke="var(--border-dim)" vertical={false} />
                <XAxis dataKey="year" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis yAxisId="l" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', fontSize: 12 }} />
                <Line yAxisId="l" type="monotone" dataKey="rate" name="BOPD" stroke="var(--teal)" strokeWidth={2} dot={false} />
                <Line yAxisId="r" type="monotone" dataKey="cum" name="Cum $M" stroke="var(--green)" strokeWidth={2} strokeDasharray="4 3" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Panel>
      </div>

      <Panel title="Portfolio economics" subtitle="Click a row to focus the production curve">
        <div style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-panel)', color: 'var(--text-muted)' }}>
                {['Well', 'Basin', 'Status', 'Peak BOPD', 'Break-even', 'Margin $/bbl', 'CAPEX $M', 'NPV₁₀ live', 'IRR %', 'Payback yr', 'CO₂ t/yr'].map(h =>
                  <th key={h} style={{ textAlign: h === 'Well' || h === 'Basin' || h === 'Status' ? 'left' : 'right', padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>{h}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {data.wells.map(w => (
                <tr key={w.well_id} onClick={() => setSelected(w.well_id)} style={{
                  cursor: 'pointer',
                  background: selected === w.well_id ? 'var(--bg-hover)' : 'transparent',
                }}>
                  <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: 'var(--blue)' }}>{w.well_id}</td>
                  <td style={{ padding: '7px 10px' }}>{w.basin || '—'}</td>
                  <td style={{ padding: '7px 10px' }}>
                    <span style={{ padding: '1px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
                      background: w.status === 'gold' ? 'var(--green-dim)' : 'var(--bg-panel)',
                      color: w.status === 'gold' ? 'var(--green)' : 'var(--text-muted)',
                    }}>{w.status}</span>
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right' }}>{w.peak_rate_bopd.toLocaleString()}</td>
                  <td style={{ padding: '7px 10px', textAlign: 'right' }}>${w.wti_break_even.toFixed(0)}</td>
                  <td style={{ padding: '7px 10px', textAlign: 'right', color: w.margin_per_bbl > 0 ? 'var(--green)' : 'var(--red)' }}>
                    {w.margin_per_bbl > 0 ? '+' : ''}${w.margin_per_bbl.toFixed(1)}
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right' }}>${w.capex_musd.toFixed(0)}</td>
                  <td style={{ padding: '7px 10px', textAlign: 'right', color: w.npv10_live_musd > 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    ${w.npv10_live_musd.toFixed(1)}
                  </td>
                  <td style={{ padding: '7px 10px', textAlign: 'right' }}>{w.irr_pct.toFixed(0)}%</td>
                  <td style={{ padding: '7px 10px', textAlign: 'right' }}>{w.payback_years.toFixed(1)}</td>
                  <td style={{ padding: '7px 10px', textAlign: 'right' }}>{w.co2_tonnes_yr.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

function Kpi({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 14px',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>
    </div>
  )
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
      padding: 16,
    }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{title}</div>
        {subtitle && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
      </div>
      {children}
    </div>
  )
}
