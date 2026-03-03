import { useState, useEffect } from 'react'

interface Well {
  name: string; type: string; i: number; j: number; bhp: number; inj_bhp?: number
}
interface Scenario {
  id: number; name: string; deck_id: string; description: string
  config: {
    wells?: Well[]; start_date?: string; end_date?: string; timestep_days?: number
    grid?: { ni: number; nj: number; nk: number }
    initial_pressure_bar?: number; porosity?: number; permeability_md?: number
    oil_viscosity_cp?: number; oil_fvf?: number; gor_scf_bbl?: number
  }
  created_at: string
}
interface Props {
  onRunStarted: (runId: string, scenarioId: number) => void
  activeScenarioId: number | null
  onScenarioSelect: (id: number) => void
}

export default function ScenariosTab({ onRunStarted, activeScenarioId, onScenarioSelect }: Props) {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [selected, setSelected] = useState<Scenario | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)

  // Form state for new scenario
  const [editName, setEditName] = useState('')
  const [editDeck, setEditDeck] = useState('eagleford_base')
  const [editDesc, setEditDesc] = useState('')
  const [editWells, setEditWells] = useState<Well[]>([
    { name: 'PROD-1', type: 'PROD', i: 2, j: 2, bhp: 150 },
    { name: 'PROD-2', type: 'PROD', i: 8, j: 2, bhp: 150 },
    { name: 'PROD-3', type: 'PROD', i: 12, j: 8, bhp: 150 },
    { name: 'PROD-4', type: 'PROD', i: 18, j: 8, bhp: 150 },
  ])
  const [editStartDate, setEditStartDate] = useState('2024-01-01')
  const [editEndDate, setEditEndDate] = useState('2034-01-01')
  const [editTimestep, setEditTimestep] = useState(91)
  const [isNew, setIsNew] = useState(false)

  useEffect(() => { loadScenarios() }, [])

  useEffect(() => {
    if (activeScenarioId && scenarios.length > 0) {
      const s = scenarios.find(s => s.id === activeScenarioId)
      if (s) selectScenario(s)
    }
  }, [activeScenarioId, scenarios])

  const loadScenarios = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/scenarios')
      const data = await res.json()
      setScenarios(Array.isArray(data) ? data : [])
      if (data.length > 0 && !selected) selectScenario(data[0])
    } catch { /* empty */ }
    setLoading(false)
  }

  const selectScenario = (s: Scenario) => {
    setSelected(s)
    setIsNew(false)
    onScenarioSelect(s.id)
    const c = s.config || {}
    setEditName(s.name)
    setEditDeck(s.deck_id)
    setEditDesc(s.description || '')
    setEditWells(c.wells || editWells)
    setEditStartDate(c.start_date || '2024-01-01')
    setEditEndDate(c.end_date || '2034-01-01')
    setEditTimestep(c.timestep_days || 91)
  }

  const startNew = () => {
    setIsNew(true)
    setSelected(null)
    setEditName('')
    setEditDeck('eagleford_base')
    setEditDesc('')
    setEditWells([
      { name: 'PROD-1', type: 'PROD', i: 2, j: 2, bhp: 150 },
      { name: 'PROD-2', type: 'PROD', i: 8, j: 2, bhp: 150 },
      { name: 'PROD-3', type: 'PROD', i: 12, j: 8, bhp: 150 },
      { name: 'PROD-4', type: 'PROD', i: 18, j: 8, bhp: 150 },
    ])
    setEditStartDate('2024-01-01')
    setEditEndDate('2034-01-01')
    setEditTimestep(91)
  }

  const saveScenario = async () => {
    const body = {
      name: editName,
      deck_id: editDeck,
      description: editDesc,
      config: {
        wells: editWells,
        start_date: editStartDate,
        end_date: editEndDate,
        timestep_days: editTimestep,
        grid: { ni: 20, nj: 10, nk: 5 },
        initial_pressure_bar: 500,
        porosity: 0.08,
        permeability_md: 0.05,
        oil_viscosity_cp: 0.35,
        oil_fvf: 1.45,
        gor_scf_bbl: 800,
      },
    }
    try {
      await fetch('/api/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setIsNew(false)
      await loadScenarios()
    } catch { /* empty */ }
  }

  const runSimulation = async () => {
    const sid = selected?.id
    if (!sid) return
    setRunning(true)
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: sid }),
      })
      const data = await res.json()
      if (data.run_id) {
        onRunStarted(data.run_id, sid)
      }
    } catch { /* empty */ }
    setRunning(false)
  }

  const deleteScenario = async (id: number) => {
    await fetch(`/api/scenarios/${id}`, { method: 'DELETE' })
    await loadScenarios()
    if (selected?.id === id) { setSelected(null); setIsNew(false) }
  }

  const updateWellField = (idx: number, field: keyof Well, value: string | number) => {
    setEditWells(prev => prev.map((w, i) => i === idx ? { ...w, [field]: value } : w))
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600 }}>
      {/* Left panel: scenario list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="card" style={{ padding: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div className="label">SCENARIOS</div>
            <button onClick={startNew} style={{
              background: 'var(--green-dim)', color: 'var(--green)',
              border: '1px solid var(--green)', borderRadius: 5,
              padding: '3px 10px', fontSize: 11, fontWeight: 600,
            }}>+ New</button>
          </div>
          {loading && <div className="spinner" style={{ margin: '20px auto', display: 'block' }} />}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {scenarios.map(s => (
              <div key={s.id} onClick={() => selectScenario(s)}
                style={{
                  background: selected?.id === s.id ? 'var(--bg-panel)' : 'transparent',
                  border: selected?.id === s.id ? '1px solid var(--blue)' : '1px solid var(--border)',
                  borderRadius: 6, padding: '10px 12px', cursor: 'pointer',
                  transition: 'all 0.15s',
                }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>{s.name}</div>
                  <button onClick={e => { e.stopPropagation(); deleteScenario(s.id) }}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 11, padding: '2px 4px' }}>
                    x
                  </button>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                  <span className="badge badge-muted" style={{ fontSize: 9, padding: '1px 6px', marginRight: 5 }}>{s.deck_id}</span>
                  {s.config?.wells?.length || 4} wells
                </div>
                {s.description && (
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                    {s.description.slice(0, 100)}{s.description.length > 100 ? '...' : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel: detail editor */}
      <div className="card" style={{ padding: 20, overflowY: 'auto' }}>
        {!selected && !isNew ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>
            Select a scenario or create a new one
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div className="label">{isNew ? 'NEW SCENARIO' : 'EDIT SCENARIO'}</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {isNew && (
                  <button onClick={saveScenario} disabled={!editName.trim()} style={{
                    background: 'var(--green-dim)', color: 'var(--green)',
                    border: '1px solid var(--green)', borderRadius: 5,
                    padding: '5px 14px', fontSize: 12, fontWeight: 600,
                  }}>Save</button>
                )}
                {selected && (
                  <button onClick={runSimulation} disabled={running} style={{
                    background: running ? 'var(--bg-panel)' : 'var(--blue-dim)',
                    color: running ? 'var(--text-muted)' : 'var(--blue)',
                    border: `1px solid ${running ? 'var(--border)' : 'var(--blue)'}`,
                    borderRadius: 5, padding: '5px 14px', fontSize: 12, fontWeight: 600,
                  }}>
                    {running ? 'Starting...' : 'Run Simulation'}
                  </button>
                )}
              </div>
            </div>

            {/* Name and deck */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
              <div>
                <div className="label" style={{ marginBottom: 5 }}>NAME</div>
                <input value={editName} onChange={e => setEditName(e.target.value)}
                  disabled={!isNew}
                  style={{
                    width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', borderRadius: 6, padding: '7px 10px', fontSize: 12, outline: 'none',
                  }} />
              </div>
              <div>
                <div className="label" style={{ marginBottom: 5 }}>SIMULATION DECK</div>
                <select value={editDeck} onChange={e => setEditDeck(e.target.value)}
                  disabled={!isNew}
                  style={{
                    width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', borderRadius: 6, padding: '7px 10px', fontSize: 12, outline: 'none',
                  }}>
                  <option value="eagleford_base">eagleford_base</option>
                  <option value="eagleford_hnp">eagleford_hnp</option>
                </select>
              </div>
            </div>

            {/* Description */}
            <div style={{ marginBottom: 16 }}>
              <div className="label" style={{ marginBottom: 5 }}>DESCRIPTION</div>
              <textarea value={editDesc} onChange={e => setEditDesc(e.target.value)}
                disabled={!isNew} rows={3}
                style={{
                  width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', borderRadius: 6, padding: '7px 10px', fontSize: 12,
                  outline: 'none', resize: 'vertical', fontFamily: 'inherit',
                }} />
            </div>

            {/* Simulation controls */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14, marginBottom: 20 }}>
              <div>
                <div className="label" style={{ marginBottom: 5 }}>START DATE</div>
                <input type="date" value={editStartDate} onChange={e => setEditStartDate(e.target.value)}
                  disabled={!isNew}
                  style={{
                    width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', borderRadius: 6, padding: '7px 10px', fontSize: 12, outline: 'none',
                  }} />
              </div>
              <div>
                <div className="label" style={{ marginBottom: 5 }}>END DATE</div>
                <input type="date" value={editEndDate} onChange={e => setEditEndDate(e.target.value)}
                  disabled={!isNew}
                  style={{
                    width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', borderRadius: 6, padding: '7px 10px', fontSize: 12, outline: 'none',
                  }} />
              </div>
              <div>
                <div className="label" style={{ marginBottom: 5 }}>TIMESTEP (DAYS)</div>
                <input type="number" value={editTimestep} onChange={e => setEditTimestep(Number(e.target.value))}
                  disabled={!isNew}
                  style={{
                    width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', borderRadius: 6, padding: '7px 10px', fontSize: 12, outline: 'none',
                  }} />
              </div>
            </div>

            {/* Well configuration table */}
            <div className="label" style={{ marginBottom: 8 }}>WELL CONFIGURATION</div>
            <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-panel)' }}>
                    {['Well Name', 'Type', 'I', 'J', 'BHP Target (bar)'].map(h => (
                      <th key={h} style={{ padding: '7px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, letterSpacing: '0.05em', borderBottom: '1px solid var(--border)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {editWells.map((w, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                      <td style={{ padding: '5px 10px' }}>
                        <input value={w.name} onChange={e => updateWellField(idx, 'name', e.target.value)}
                          disabled={!isNew}
                          style={{ background: 'transparent', border: 'none', color: 'var(--text-primary)', fontSize: 11, outline: 'none', width: '100%', fontFamily: 'monospace' }} />
                      </td>
                      <td style={{ padding: '5px 10px' }}>
                        <select value={w.type} onChange={e => updateWellField(idx, 'type', e.target.value)}
                          disabled={!isNew}
                          style={{ background: 'transparent', border: 'none', color: w.type === 'PROD' ? 'var(--green)' : w.type === 'INJ' ? 'var(--blue)' : 'var(--amber)', fontSize: 11, outline: 'none' }}>
                          <option value="PROD">PROD</option>
                          <option value="INJ">INJ</option>
                          <option value="HNP">HNP</option>
                        </select>
                      </td>
                      <td style={{ padding: '5px 10px' }}>
                        <input type="number" value={w.i} onChange={e => updateWellField(idx, 'i', Number(e.target.value))}
                          disabled={!isNew}
                          style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: 11, outline: 'none', width: 50, fontFamily: 'monospace' }} />
                      </td>
                      <td style={{ padding: '5px 10px' }}>
                        <input type="number" value={w.j} onChange={e => updateWellField(idx, 'j', Number(e.target.value))}
                          disabled={!isNew}
                          style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: 11, outline: 'none', width: 50, fontFamily: 'monospace' }} />
                      </td>
                      <td style={{ padding: '5px 10px' }}>
                        <input type="number" value={w.bhp} onChange={e => updateWellField(idx, 'bhp', Number(e.target.value))}
                          disabled={!isNew}
                          style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: 11, outline: 'none', width: 70, fontFamily: 'monospace' }} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Grid info (read-only) */}
            <div className="label" style={{ marginBottom: 8 }}>GRID PROPERTIES</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              {[
                { label: 'Grid Size', value: '20 x 10 x 5', color: 'var(--blue)' },
                { label: 'Init Pressure', value: '500 bar', color: 'var(--amber)' },
                { label: 'Porosity', value: '0.08 (8%)', color: 'var(--teal)' },
                { label: 'Permeability', value: '0.05 md', color: 'var(--purple)' },
                { label: 'Oil Viscosity', value: '0.35 cp', color: 'var(--green)' },
                { label: 'Oil FVF', value: '1.45 rb/stb', color: 'var(--gold)' },
                { label: 'GOR', value: '800 scf/bbl', color: 'var(--red)' },
                { label: 'Total Cells', value: '1,000', color: 'var(--text-primary)' },
              ].map(kpi => (
                <div key={kpi.label} style={{ background: 'var(--bg-panel)', borderRadius: 5, padding: '8px 10px', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: kpi.color, fontFamily: 'monospace' }}>{kpi.value}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{kpi.label}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
