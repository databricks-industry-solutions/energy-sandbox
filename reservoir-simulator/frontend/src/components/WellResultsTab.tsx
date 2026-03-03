import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

interface WellData {
  well_name: string; day: number; timestep: number
  oil_rate_stbd: number; gas_rate_mscfd: number; water_rate_stbd: number
  bhp_bar: number; avg_pressure_bar: number; avg_so: number; avg_sw: number
  cum_oil_stb: number; cum_gas_mscf: number; cum_water_stb: number
}

interface Run {
  id: string; scenario_name: string; status: string
}

interface Props {
  activeRunId: string | null
  onRunSelect: (id: string) => void
}

const WELL_COLORS: Record<string, string> = {
  'PROD-1': '#ff4d4f',
  'PROD-2': '#ffa940',
  'PROD-3': '#00c875',
  'PROD-4': '#4dabf7',
  'FIELD': '#b37feb',
}

export default function WellResultsTab({ activeRunId, onRunSelect }: Props) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedRun, setSelectedRun] = useState(activeRunId || '')
  const [wellNames, setWellNames] = useState<string[]>([])
  const [wellsData, setWellsData] = useState<Record<string, WellData[]>>({})
  const [selectedWell, setSelectedWell] = useState('FIELD')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/runs').then(r => r.json()).then(d => setRuns(Array.isArray(d) ? d : [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (activeRunId) setSelectedRun(activeRunId)
  }, [activeRunId])

  useEffect(() => {
    if (!selectedRun) return
    setLoading(true)
    fetch(`/api/results/${selectedRun}/wells`)
      .then(r => r.json())
      .then(data => {
        const names = data.well_names || []
        setWellNames(['FIELD', ...names])
        setWellsData(data.wells || {})
        if (!names.includes(selectedWell) && selectedWell !== 'FIELD') {
          setSelectedWell('FIELD')
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [selectedRun])

  // Compute field data by aggregating all wells
  const fieldData: WellData[] = (() => {
    const allWells = Object.values(wellsData)
    if (allWells.length === 0) return []
    const nSteps = allWells[0]?.length || 0
    const result: WellData[] = []
    for (let i = 0; i < nSteps; i++) {
      let oil = 0, gas = 0, water = 0, bhp = 0, p = 0, count = 0
      let cum_oil = 0, cum_gas = 0, cum_water = 0
      for (const wData of allWells) {
        if (wData[i]) {
          oil += wData[i].oil_rate_stbd
          gas += wData[i].gas_rate_mscfd
          water += wData[i].water_rate_stbd
          bhp += wData[i].bhp_bar
          p += wData[i].avg_pressure_bar
          cum_oil += wData[i].cum_oil_stb
          cum_gas += wData[i].cum_gas_mscf
          cum_water += wData[i].cum_water_stb
          count++
        }
      }
      result.push({
        well_name: 'FIELD',
        day: allWells[0][i]?.day || i * 91.25,
        timestep: i + 1,
        oil_rate_stbd: Math.round(oil * 10) / 10,
        gas_rate_mscfd: Math.round(gas * 10) / 10,
        water_rate_stbd: Math.round(water * 10) / 10,
        bhp_bar: Math.round(bhp / Math.max(count, 1) * 10) / 10,
        avg_pressure_bar: Math.round(p / Math.max(count, 1) * 10) / 10,
        avg_so: 0, avg_sw: 0,
        cum_oil_stb: Math.round(cum_oil),
        cum_gas_mscf: Math.round(cum_gas),
        cum_water_stb: Math.round(cum_water),
      })
    }
    return result
  })()

  const chartData = selectedWell === 'FIELD' ? fieldData : (wellsData[selectedWell] || [])

  const tooltipStyle = {
    contentStyle: { background: '#13151a', border: '1px solid #2a2e3a', borderRadius: 6, fontSize: 11 },
    labelStyle: { color: '#b0b6c8' },
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600 }}>
      {/* Left panel */}
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

        {/* Well selector */}
        <div className="card" style={{ padding: 13, flex: 1 }}>
          <div className="label" style={{ marginBottom: 8 }}>WELLS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {wellNames.map(wn => (
              <button key={wn} onClick={() => setSelectedWell(wn)} style={{
                background: selectedWell === wn ? 'var(--bg-panel)' : 'transparent',
                border: selectedWell === wn ? '1px solid var(--blue)' : '1px solid var(--border)',
                borderRadius: 5, padding: '7px 10px', textAlign: 'left',
                display: 'flex', alignItems: 'center', gap: 7,
                color: selectedWell === wn ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: 12, fontWeight: selectedWell === wn ? 600 : 400,
              }}>
                <div className="well-dot" style={{ background: WELL_COLORS[wn] || 'var(--text-muted)' }} />
                {wn}
              </button>
            ))}
          </div>

          {/* Latest stats */}
          {chartData.length > 0 && (
            <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
              <div className="label" style={{ marginBottom: 6 }}>LATEST</div>
              {(() => {
                const last = chartData[chartData.length - 1]
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {[
                      { label: 'Oil Rate', value: `${last.oil_rate_stbd.toFixed(0)} STB/d`, color: 'var(--green)' },
                      { label: 'Gas Rate', value: `${last.gas_rate_mscfd.toFixed(0)} MSCF/d`, color: 'var(--red)' },
                      { label: 'Water Rate', value: `${last.water_rate_stbd.toFixed(0)} STB/d`, color: 'var(--blue)' },
                      { label: 'BHP', value: `${last.bhp_bar.toFixed(0)} bar`, color: 'var(--amber)' },
                      { label: 'Cum Oil', value: `${(last.cum_oil_stb / 1000).toFixed(0)}k STB`, color: 'var(--green)' },
                    ].map(s => (
                      <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.label}</span>
                        <span style={{ fontSize: 10, fontFamily: 'monospace', color: s.color, fontWeight: 600 }}>{s.value}</span>
                      </div>
                    ))}
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      </div>

      {/* Right panel: charts */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
        {loading && <div style={{ textAlign: 'center', padding: 40 }}><div className="spinner" /></div>}
        {!loading && chartData.length === 0 && (
          <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
            {selectedRun ? 'No well data available yet. Wait for the simulation to complete.' : 'Select a run to view well results.'}
          </div>
        )}
        {chartData.length > 0 && (
          <>
            {/* Oil Rate Chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>OIL PRODUCTION RATE — {selectedWell}</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `${Math.round(v)}d`} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)} STB/d`, 'Oil Rate']} />
                  <Line type="monotone" dataKey="oil_rate_stbd" stroke="#00c875" strokeWidth={2} dot={false} name="Oil Rate (STB/d)" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Gas Rate Chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>GAS PRODUCTION RATE — {selectedWell}</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `${Math.round(v)}d`} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toFixed(1)} MSCF/d`, 'Gas Rate']} />
                  <Line type="monotone" dataKey="gas_rate_mscfd" stroke="#ff4d4f" strokeWidth={2} dot={false} name="Gas Rate (MSCF/d)" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Water Rate + BHP Chart */}
            <div className="card" style={{ padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 10 }}>WATER RATE &amp; BHP — {selectedWell}</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#1e2130" strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={v => `${Math.round(v)}d`} />
                  <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip {...tooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Line yAxisId="left" type="monotone" dataKey="water_rate_stbd" stroke="#4dabf7" strokeWidth={2} dot={false} name="Water (STB/d)" />
                  <Line yAxisId="right" type="monotone" dataKey="bhp_bar" stroke="#ffa940" strokeWidth={2} dot={false} name="BHP (bar)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
