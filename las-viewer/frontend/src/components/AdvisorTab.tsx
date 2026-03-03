import { useState, useEffect, useRef } from 'react'

const WELLS = ['BAKER-001','BAKER-002','CONOCO-7H','MARATHON-15X','SHELL-3D','PIONEER-22S']

const QUICK_Q = [
  'What is the overall data quality and which curves need attention?',
  'Interpret the Westwater reservoir: porosity, saturation, and pay potential.',
  'What environmental corrections are recommended for this well?',
  'Identify any washout or invasion effects in the log data.',
  'Should I use linear GR or spectral CGR for clay volume in this formation?',
  'What synthetic log would you generate first and why?',
  'Summarise the formation evaluation results for a petrophysical report.',
]

interface Msg { role: 'user' | 'assistant'; content: string; status?: string; ts: number }
interface QuickStatus {
  well_name: string; status: string; quality_score: number; current_depth_ft: number
  gr_latest: number; rhob_latest: number; nphi_latest: number; rt_latest: number
  phi_eff: number; sw: number
  curve_quality: { curve_name: string; quality_score: number }[]
  alerts: { level: string; msg: string }[]
}

interface Props { wellId: string; onWellChange: (id: string) => void }

export default function AdvisorTab({ wellId, onWellChange }: Props) {
  const [msgs, setMsgs]   = useState<Msg[]>([{
    role: 'assistant',
    content: "Hello! I'm your Petrophysics AI — specialising in LAS log analysis, curve QC, formation evaluation, and Databricks well-log workflows. I have full access to this well's log data, QC scores, formation tops, and processing history. What would you like to analyse?",
    ts: Date.now(),
  }])
  const [input, setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const [qs, setQs]           = useState<QuickStatus | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    fetch(`/api/advisor/quick/${wellId}`).then(r => r.json()).then(setQs).catch(() => {})
  }, [wellId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  const send = async (text: string) => {
    if (!text.trim() || loading) return
    const userMsg: Msg = { role: 'user', content: text.trim(), ts: Date.now() }
    const history = msgs.map(m => ({ role: m.role, content: m.content }))
    setMsgs(p => [...p, userMsg]); setInput(''); setLoading(true)
    try {
      const res = await fetch('/api/advisor/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text.trim(), well_id: wellId, history }),
      })
      const d = await res.json()
      setMsgs(p => [...p, { role: 'assistant', content: d.answer || 'No response.', status: d.status, ts: Date.now() }])
      fetch(`/api/advisor/quick/${wellId}`).then(r => r.json()).then(setQs).catch(() => {})
    } catch {
      setMsgs(p => [...p, { role: 'assistant', content: 'Connection error — please retry.', status: 'error', ts: Date.now() }])
    }
    setLoading(false)
  }

  const qColor = (v: number) => v >= 80 ? 'var(--green)' : v >= 60 ? 'var(--amber)' : 'var(--red)'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '290px 1fr', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600 }}>
      {/* Left panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Well selector */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>ACTIVE WELL</div>
          <select value={wellId} onChange={e => onWellChange(e.target.value)}
            style={{ width: '100%', background: 'var(--bg-panel)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: 6, padding: '6px 10px', fontSize: 12, outline: 'none' }}>
            {WELLS.map(w => <option key={w} value={w}>{w}</option>)}
          </select>
        </div>

        {/* Live status */}
        {qs && (
          <div className="card" style={{ padding: 13 }}>
            <div className="label" style={{ marginBottom: 10 }}>LIVE WELL STATUS</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
              {[
                { label: 'Quality',   value: `${qs.quality_score}/100`, color: qColor(qs.quality_score) },
                { label: 'GR (last)', value: `${qs.gr_latest.toFixed(1)} API`, color: 'var(--gr-color)' },
                { label: 'RHOB',      value: `${qs.rhob_latest.toFixed(3)} g/cc`, color: 'var(--rhob-color)' },
                { label: 'RT',        value: `${qs.rt_latest.toFixed(1)} Ω·m`,   color: 'var(--rt-color)' },
                { label: 'φ_eff',     value: qs.phi_eff > 0 ? `${(qs.phi_eff * 100).toFixed(1)}%` : '—', color: 'var(--phi-color)' },
                { label: 'Sw',        value: qs.sw > 0 ? `${(qs.sw * 100).toFixed(1)}%` : '—', color: 'var(--sw-color)' },
              ].map(kpi => (
                <div key={kpi.label} style={{ background: 'var(--bg-panel)', borderRadius: 5, padding: '7px 9px', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: kpi.color, fontFamily: 'monospace' }}>{kpi.value}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{kpi.label}</div>
                </div>
              ))}
            </div>

            {/* Curve quality bars */}
            {qs.curve_quality.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {qs.curve_quality.slice(0, 5).map(c => (
                  <div key={c.curve_name} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-muted)', width: 60 }}>{c.curve_name.toUpperCase()}</span>
                    <div style={{ flex: 1, height: 5, background: 'var(--bg-panel)', borderRadius: 2 }}>
                      <div style={{ width: `${c.quality_score}%`, height: '100%', background: qColor(c.quality_score), borderRadius: 2 }} />
                    </div>
                    <span style={{ fontSize: 10, color: qColor(c.quality_score), width: 24, textAlign: 'right' }}>{c.quality_score}</span>
                  </div>
                ))}
              </div>
            )}

            {qs.alerts.length > 0 && (
              <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
                {qs.alerts.slice(0, 3).map((a, i) => (
                  <div key={i} style={{ padding: '5px 8px', background: a.level === 'critical' ? 'var(--red-dim)' : 'var(--amber-dim)', border: `1px solid ${a.level === 'critical' ? 'var(--red)' : 'var(--amber)'}`, borderRadius: 5, fontSize: 10, color: a.level === 'critical' ? 'var(--red)' : 'var(--amber)' }}>
                    {a.level === 'critical' ? '🔴' : '🟡'} {a.msg}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Quick questions */}
        <div className="card" style={{ padding: 13, flex: 1, overflow: 'hidden' }}>
          <div className="label" style={{ marginBottom: 8 }}>QUICK QUESTIONS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, overflowY: 'auto', maxHeight: 280 }}>
            {QUICK_Q.map((q, i) => (
              <button key={i} onClick={() => send(q)} disabled={loading} style={{
                background: 'var(--bg-panel)', color: 'var(--text-secondary)',
                border: '1px solid var(--border)', borderRadius: 5,
                padding: '7px 10px', fontSize: 11, textAlign: 'left',
                lineHeight: 1.4, opacity: loading ? 0.5 : 1,
              }}>{q}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Chat panel */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '11px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 30, height: 30, background: 'var(--blue-dim)', border: '1px solid var(--blue)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>🤖</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>Petrophysics AI</div>
            <div style={{ fontSize: 10, color: 'var(--blue)' }}>Databricks Claude · {wellId}</div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <span className="badge badge-gold">⭐ las_gold context</span>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {msgs.map((m, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                maxWidth: '84%',
                background: m.role === 'user' ? 'var(--blue-dim)' : 'var(--bg-panel)',
                border: `1px solid ${m.role === 'user' ? 'var(--blue)' : 'var(--border)'}`,
                borderRadius: m.role === 'user' ? '12px 12px 2px 12px' : '2px 12px 12px 12px',
                padding: '10px 13px',
                color: m.role === 'user' ? 'var(--blue)' : 'var(--text-primary)',
              }}>
                {m.role === 'assistant' && (
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 5, fontWeight: 700 }}>
                    PETROPHYSICS AI {m.status === 'fallback' ? '· DEMO MODE' : '· DATABRICKS CLAUDE'}
                  </div>
                )}
                <div style={{ fontSize: 12, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{m.content}</div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 5, textAlign: 'right' }}>
                  {new Date(m.ts).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'flex-start' }}>
              <div style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: '2px 12px 12px 12px', padding: '10px 14px' }}>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 4 }}>ANALYSING WELL DATA…</div>
                <div style={{ display: 'flex', gap: 5 }}>
                  {[0, 1, 2].map(i => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--blue)', animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
          <textarea ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) } }}
            placeholder="Ask about log interpretation, QC issues, formation evaluation, correction strategies…"
            rows={2} disabled={loading} style={{
              flex: 1, background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 7, padding: '8px 11px', color: 'var(--text-primary)',
              fontSize: 12, resize: 'none', outline: 'none', fontFamily: 'inherit',
            }}
          />
          <button onClick={() => send(input)} disabled={loading || !input.trim()} style={{
            background: loading || !input.trim() ? 'var(--bg-panel)' : 'var(--blue-dim)',
            color: loading || !input.trim() ? 'var(--text-muted)' : 'var(--blue)',
            border: `1px solid ${loading || !input.trim() ? 'var(--border)' : 'var(--blue)'}`,
            borderRadius: 7, padding: '0 16px', fontWeight: 600, fontSize: 13,
          }}>Send</button>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%,100% { opacity:0.3; transform:scale(0.9); }
          50% { opacity:1; transform:scale(1.1); }
        }
      `}</style>
    </div>
  )
}
