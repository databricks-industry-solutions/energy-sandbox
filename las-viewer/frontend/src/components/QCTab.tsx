import { useState, useEffect } from 'react'

const WELLS = ['BAKER-001','BAKER-002','CONOCO-7H','MARATHON-15X','SHELL-3D','PIONEER-22S']

interface CQ { curve_name: string; coverage_pct: number; spike_count: number; gap_count: number; quality_score: number }
interface Anomaly { id: number; curve_name: string; depth_start: number; depth_end: number; anomaly_type: string; severity: string; description: string }
interface QCData {
  well_id: string; well_status: string; overall_quality: number
  curve_quality: CQ[]; anomalies: Anomaly[]
  critical_curves: string[]; total_anomalies: number; critical_anomalies: number
}

function QBar({ score, width = 120 }: { score: number; width?: number }) {
  const c = score >= 80 ? 'var(--green)' : score >= 60 ? 'var(--amber)' : 'var(--red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width, height: 7, background: 'var(--bg-panel)', borderRadius: 3, flexShrink: 0 }}>
        <div style={{ width: `${score}%`, height: '100%', background: c, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color: c, minWidth: 30 }}>{score}</span>
    </div>
  )
}

const RECIPES = [
  { id: 'STD-PETRO-V1',   label: 'Standard Petrophysical' },
  { id: 'FAST-DRILL-V1',  label: 'Fast Turnaround' },
  { id: 'HIFI-RSVR-V1',   label: 'High Fidelity Reservoir' },
]

interface Props { wellId: string; onWellChange: (id: string) => void }

export default function QCTab({ wellId, onWellChange }: Props) {
  const [qc, setQc]             = useState<QCData | null>(null)
  const [loading, setLoading]   = useState(true)
  const [runLoading, setRunLoading] = useState(false)
  const [corLoading, setCorLoading] = useState(false)
  const [recipe, setRecipe]     = useState('STD-PETRO-V1')
  const [lastMsg, setLastMsg]   = useState('')

  const loadQC = (wid: string) => {
    setLoading(true)
    fetch(`/api/qc/${wid}`).then(r => r.json()).then(setQc).finally(() => setLoading(false))
  }

  useEffect(() => { loadQC(wellId) }, [wellId])

  const runQC = async () => {
    setRunLoading(true); setLastMsg('')
    const res = await fetch('/api/qc/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ well_id: wellId, recipe_id: recipe }) })
    const data = await res.json()
    setLastMsg(data.message || 'QC complete')
    setRunLoading(false)
    loadQC(wellId)
  }

  const applyCorr = async () => {
    setCorLoading(true); setLastMsg('')
    const res = await fetch('/api/corrections/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ well_id: wellId, recipe_id: recipe }) })
    const data = await res.json()
    setLastMsg(data.message || 'Corrections applied')
    setCorLoading(false)
    loadQC(wellId)
  }

  const anomalyColor = (sev: string) => sev === 'critical' ? 'var(--red)' : 'var(--amber)'
  const anomalyBg    = (sev: string) => sev === 'critical' ? 'var(--red-dim)' : 'var(--amber-dim)'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, alignItems: 'start' }}>
      {/* Left panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Well selector */}
        <div className="card" style={{ padding: 14 }}>
          <div className="label" style={{ marginBottom: 8 }}>ACTIVE WELL</div>
          <select value={wellId} onChange={e => { onWellChange(e.target.value); loadQC(e.target.value) }}
            style={{ width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 12, outline: 'none' }}>
            {WELLS.map(w => <option key={w} value={w}>{w}</option>)}
          </select>
        </div>

        {/* Overall quality */}
        {qc && (
          <div className="card" style={{ padding: 14 }}>
            <div className="label" style={{ marginBottom: 10 }}>OVERALL QUALITY</div>
            <div style={{ fontSize: 36, fontWeight: 700, color: qc.overall_quality >= 70 ? 'var(--green)' : qc.overall_quality >= 50 ? 'var(--amber)' : 'var(--red)', fontFamily: 'monospace' }}>
              {qc.overall_quality.toFixed(0)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>/100 · {qc.well_status}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: qc.critical_anomalies > 0 ? 'var(--red)' : 'var(--text-muted)' }}>{qc.critical_anomalies}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>CRITICAL</div>
              </div>
              <div style={{ textAlign: 'center', marginLeft: 12 }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--amber)' }}>{qc.total_anomalies}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>ANOMALIES</div>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="card" style={{ padding: 14 }}>
          <div className="label" style={{ marginBottom: 8 }}>CORRECTION RECIPE</div>
          <select value={recipe} onChange={e => setRecipe(e.target.value)}
            style={{ width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 12, outline: 'none', marginBottom: 10 }}>
            {RECIPES.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
          </select>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            <button onClick={runQC} disabled={runLoading} style={{
              background: 'var(--blue-dim)', color: 'var(--blue)', border: '1px solid var(--blue)',
              borderRadius: 6, padding: '8px 0', fontSize: 12, fontWeight: 600,
            }}>
              {runLoading ? '⏳ Running QC…' : '🔍 Run QC'}
            </button>
            <button onClick={applyCorr} disabled={corLoading} style={{
              background: 'var(--green-dim)', color: 'var(--green)', border: '1px solid var(--green)',
              borderRadius: 6, padding: '8px 0', fontSize: 12, fontWeight: 600,
            }}>
              {corLoading ? '⏳ Applying…' : '⚙️ Apply Corrections'}
            </button>
          </div>
          {lastMsg && (
            <div style={{ marginTop: 10, padding: '8px 10px', background: 'var(--green-dim)', border: '1px solid var(--green)', borderRadius: 5, fontSize: 11, color: 'var(--green)' }}>
              ✓ {lastMsg}
            </div>
          )}
        </div>
      </div>

      {/* Right panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center' }}><span className="spinner" /></div>
        ) : qc ? (
          <>
            {/* Curve quality grid */}
            <div className="card">
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                <div className="label">CURVE QC SCORECARD</div>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-panel)' }}>
                      {['Curve', 'Coverage', 'Spikes', 'Gaps', 'Quality Score'].map(h => (
                        <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.06em', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h.toUpperCase()}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {qc.curve_quality.map((c, i) => (
                      <tr key={c.curve_name} style={{ background: i % 2 ? 'var(--bg-panel)' : 'transparent', borderBottom: '1px solid var(--border-dim)' }}>
                        <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color: 'var(--blue)' }}>
                          {c.curve_name.toUpperCase()}
                        </td>
                        <td style={{ padding: '10px 14px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 80, height: 5, background: 'var(--bg-panel)', borderRadius: 2 }}>
                              <div style={{ width: `${c.coverage_pct}%`, height: '100%', background: c.coverage_pct > 95 ? 'var(--green)' : 'var(--amber)', borderRadius: 2 }} />
                            </div>
                            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{c.coverage_pct.toFixed(1)}%</span>
                          </div>
                        </td>
                        <td style={{ padding: '10px 14px', fontSize: 12, color: c.spike_count > 3 ? 'var(--red)' : c.spike_count > 0 ? 'var(--amber)' : 'var(--green)' }}>
                          {c.spike_count > 0 ? `⚡ ${c.spike_count}` : '—'}
                        </td>
                        <td style={{ padding: '10px 14px', fontSize: 12, color: c.gap_count > 0 ? 'var(--amber)' : 'var(--green)' }}>
                          {c.gap_count > 0 ? `▢ ${c.gap_count}` : '—'}
                        </td>
                        <td style={{ padding: '10px 14px' }}><QBar score={c.quality_score} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Anomalies */}
            {qc.anomalies.length > 0 && (
              <div className="card">
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="label">ANOMALY LOG</div>
                  <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>{qc.anomalies.length} detected</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {qc.anomalies.map((a, i) => (
                    <div key={a.id} style={{
                      padding: '10px 14px', display: 'grid', gridTemplateColumns: '100px 90px 90px 1fr',
                      gap: 12, alignItems: 'center',
                      background: i % 2 ? 'var(--bg-panel)' : 'transparent',
                      borderBottom: '1px solid var(--border-dim)',
                    }}>
                      <div>
                        <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 3, background: anomalyBg(a.severity), color: anomalyColor(a.severity), border: `1px solid ${anomalyColor(a.severity)}` }}>
                          {a.severity.toUpperCase()}
                        </span>
                      </div>
                      <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--blue)' }}>
                        {a.curve_name.toUpperCase()}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                        {a.depth_start.toFixed(0)}–{a.depth_end?.toFixed(0)} ft
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{a.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* DQ rules reference */}
            <div className="card" style={{ padding: 14 }}>
              <div className="label" style={{ marginBottom: 8 }}>ACTIVE DQ RULES</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                {[
                  '✓ GR: 0–250 API range check | coverage ≥ 95%',
                  '✓ RT: 0.01–5000 Ω·m range | spike detect (z-score > 3.5)',
                  '✓ RHOB: 1.50–3.00 g/cc critical range',
                  '✓ NPHI: -0.15–0.60 v/v range check',
                  '✓ DT: 40–200 μs/ft range | monotonic depth',
                  '✓ CALI: 4–18 in borehole size',
                  '✓ MD: strictly increasing depth validation',
                ].map(r => <div key={r}>{r}</div>)}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
