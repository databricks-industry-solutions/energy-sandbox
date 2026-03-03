import { useState, useEffect } from 'react'

interface Step { step: number; module: string; params: Record<string, unknown> }
interface Recipe {
  recipe_id: string; name: string; description: string; version: string
  category: string; steps: Step[]; is_active: boolean; created_ts: string
  recent_runs?: Run[]
}
interface Run {
  run_id: string; well_id: string; well_name: string; recipe_id: string; recipe_name: string
  status: string; started_ts: string; completed_ts: string; metrics: Record<string, unknown>
}

const CAT_COLORS: Record<string, string> = {
  standard:     'badge-blue',
  fast:         'badge-green',
  high_fidelity:'badge-gold',
}

const MODULE_ICONS: Record<string, string> = {
  depth_alignment:     '📐',
  despiking:           '⚡',
  env_corrections:     '🌊',
  gap_fill:            '▢',
  curve_harmonization: '🎛️',
  petrophysics:        '🪨',
  synthetic_dt:        '🤖',
  geomechanics:        '⚙️',
}

function RunRow({ run }: { run: Run }) {
  const sc = run.status === 'complete' ? 'var(--green)' : run.status === 'failed' ? 'var(--red)' : run.status === 'running' ? 'var(--blue)' : 'var(--text-muted)'
  const m = run.metrics as Record<string, number>
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '130px 120px 80px 120px 1fr', gap: 10, alignItems: 'center', padding: '8px 14px', borderBottom: '1px solid var(--border-dim)' }}>
      <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--blue)' }}>{run.run_id}</span>
      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{run.well_id}</span>
      <span style={{ fontSize: 10, fontWeight: 700, color: sc }}>{run.status.toUpperCase()}</span>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
        {run.started_ts ? new Date(run.started_ts).toLocaleString() : '—'}
      </span>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', gap: 12 }}>
        {m.samples != null && <span>{m.samples.toLocaleString()} smp</span>}
        {m.spikes_corrected != null && <span>⚡ {m.spikes_corrected} spikes</span>}
        {m.gaps_filled != null && <span>▢ {m.gaps_filled} gaps</span>}
        {m.phi_mean != null && <span>φ={Number(m.phi_mean).toFixed(3)}</span>}
        {m.sw_mean != null && <span>Sw={Number(m.sw_mean).toFixed(3)}</span>}
      </div>
    </div>
  )
}

interface Props { wellId: string }
export default function RecipesTab({ wellId }: Props) {
  const [recipes, setRecipes]   = useState<Recipe[]>([])
  const [allRuns, setAllRuns]   = useState<Run[]>([])
  const [selected, setSelected] = useState<Recipe | null>(null)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/recipes').then(r => r.json()),
      fetch('/api/recipes/runs/all').then(r => r.json()),
    ]).then(([recs, runs]) => {
      setRecipes(recs)
      setAllRuns(runs)
      if (recs.length > 0) setSelected(recs[0])
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}><span className="spinner" /></div>

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, alignItems: 'start' }}>
      {/* Recipe list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="label" style={{ padding: '4px 0' }}>PROCESSING RECIPES</div>
        {recipes.map(r => (
          <div key={r.recipe_id} onClick={() => setSelected(r)} className="card" style={{
            padding: '12px 14px', cursor: 'pointer',
            border: `1px solid ${selected?.recipe_id === r.recipe_id ? 'var(--blue)' : 'var(--border)'}`,
            background: selected?.recipe_id === r.recipe_id ? 'var(--blue-dim)' : 'var(--bg-card)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
              <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>{r.name}</span>
              <span className={`badge ${CAT_COLORS[r.category] ?? 'badge-muted'}`} style={{ marginLeft: 'auto', fontSize: 9 }}>
                {r.category.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>v{r.version} · {r.steps.length} steps</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{r.description.slice(0, 80)}…</div>
          </div>
        ))}
      </div>

      {/* Recipe detail */}
      {selected && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Header */}
          <div className="card" style={{ padding: '14px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 3 }}>{selected.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>ID: <span style={{ fontFamily: 'monospace', color: 'var(--blue)' }}>{selected.recipe_id}</span> · Version {selected.version}</div>
              </div>
              <span className={`badge ${CAT_COLORS[selected.category] ?? 'badge-muted'}`} style={{ marginLeft: 'auto' }}>
                {selected.category.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{selected.description}</div>
          </div>

          {/* Steps */}
          <div className="card">
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
              <span className="label">PROCESSING PIPELINE — {selected.steps.length} STEPS</span>
            </div>
            <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {selected.steps.map((s, i) => (
                <div key={s.step} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                  <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--blue-dim)', border: '1px solid var(--blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 11, fontWeight: 700, color: 'var(--blue)' }}>
                    {s.step}
                  </div>
                  {i < selected.steps.length - 1 && (
                    <div style={{ position: 'absolute', left: 13, top: 28, width: 2, height: 10, background: 'var(--border)' }} />
                  )}
                  <div style={{ flex: 1, background: 'var(--bg-panel)', borderRadius: 6, border: '1px solid var(--border)', padding: '10px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                      <span style={{ fontSize: 16 }}>{MODULE_ICONS[s.module] ?? '⚙️'}</span>
                      <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                        {s.module.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {Object.entries(s.params).map(([k, v]) => (
                        <div key={k} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 4, padding: '2px 8px', fontSize: 10 }}>
                          <span style={{ color: 'var(--text-muted)' }}>{k}:</span>{' '}
                          <span style={{ color: 'var(--green)', fontFamily: 'monospace' }}>{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Run history */}
          <div className="card">
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
              <span className="label">RUN HISTORY (ALL WELLS)</span>
            </div>
            {allRuns.filter(r => r.recipe_id === selected.recipe_id).length === 0 ? (
              <div style={{ padding: '20px', color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
                No runs for this recipe yet.
              </div>
            ) : (
              <>
                <div style={{ padding: '6px 14px', background: 'var(--bg-panel)', borderBottom: '1px solid var(--border)', display: 'grid', gridTemplateColumns: '130px 120px 80px 120px 1fr', gap: 10 }}>
                  {['Run ID', 'Well', 'Status', 'Started', 'Metrics'].map(h => (
                    <span key={h} style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>{h.toUpperCase()}</span>
                  ))}
                </div>
                {allRuns.filter(r => r.recipe_id === selected.recipe_id).map(r => <RunRow key={r.run_id} run={r} />)}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
