import { useState, useEffect, useRef } from 'react'

const QUICK_Q = [
  'What is the current field oil recovery factor?',
  'Which well has the highest water breakthrough risk?',
  'Compare NPV between base and HnP scenarios',
  "What's driving pressure depletion in the south sector?",
  'Recommend injection rate changes to improve sweep',
  'Show the payback period sensitivity to oil price',
]

interface Msg { role: 'user' | 'assistant'; content: string; status?: string; ts: number }

interface Props {
  activeRunId: string | null
  activeScenarioId: number | null
}

export default function AgentTab({ activeRunId, activeScenarioId }: Props) {
  const [msgs, setMsgs] = useState<Msg[]>([{
    role: 'assistant',
    content: "Hello! I'm your Reservoir & Economics Agent — specialising in Eagle Ford simulation analysis, well performance, pressure depletion patterns, and economic evaluation. I have context on the current scenario, simulation run, production rates, and economics. What would you like to analyse?",
    ts: Date.now(),
  }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  const send = async (text: string) => {
    if (!text.trim() || loading) return
    const userMsg: Msg = { role: 'user', content: text.trim(), ts: Date.now() }
    const history = msgs.map(m => ({ role: m.role, content: m.content }))
    setMsgs(p => [...p, userMsg]); setInput(''); setLoading(true)
    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text.trim(),
          run_id: activeRunId,
          scenario_id: activeScenarioId,
          history,
        }),
      })
      const d = await res.json()
      setMsgs(p => [...p, { role: 'assistant', content: d.answer || 'No response.', status: d.status, ts: Date.now() }])
    } catch {
      setMsgs(p => [...p, { role: 'assistant', content: 'Connection error — please retry.', status: 'error', ts: Date.now() }])
    }
    setLoading(false)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '290px 1fr', gap: 16, height: 'calc(100vh - 130px)', minHeight: 600 }}>
      {/* Left panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Context info */}
        <div className="card" style={{ padding: 13 }}>
          <div className="label" style={{ marginBottom: 8 }}>CONTEXT</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <div style={{ background: 'var(--bg-panel)', borderRadius: 5, padding: '6px 8px', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Run</div>
              <div style={{ fontSize: 11, fontFamily: 'monospace', color: activeRunId ? 'var(--blue)' : 'var(--text-muted)', fontWeight: 600 }}>
                {activeRunId || 'None'}
              </div>
            </div>
            <div style={{ background: 'var(--bg-panel)', borderRadius: 5, padding: '6px 8px', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Scenario</div>
              <div style={{ fontSize: 11, fontFamily: 'monospace', color: activeScenarioId ? 'var(--green)' : 'var(--text-muted)', fontWeight: 600 }}>
                {activeScenarioId ? `#${activeScenarioId}` : 'None'}
              </div>
            </div>
          </div>
        </div>

        {/* Quick questions */}
        <div className="card" style={{ padding: 13, flex: 1, overflow: 'hidden' }}>
          <div className="label" style={{ marginBottom: 8 }}>QUICK QUESTIONS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, overflowY: 'auto', maxHeight: 400 }}>
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
          <div style={{ width: 30, height: 30, background: 'var(--amber-dim)', border: '1px solid var(--amber)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>
            &#9981;
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)' }}>Reservoir &amp; Economics Agent</div>
            <div style={{ fontSize: 10, color: 'var(--amber)' }}>Databricks Claude &middot; Eagle Ford</div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <span className="badge badge-gold">Res Flow context</span>
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
                    RESERVOIR AGENT {m.status === 'fallback' ? '-- DEMO MODE' : '-- DATABRICKS CLAUDE'}
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
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 4 }}>ANALYSING RESERVOIR DATA...</div>
                <div style={{ display: 'flex', gap: 5 }}>
                  {[0, 1, 2].map(i => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--amber)', animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }} />
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
            placeholder="Ask about reservoir performance, well optimization, economics, recovery factors..."
            rows={2} disabled={loading} style={{
              flex: 1, background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 7, padding: '8px 11px', color: 'var(--text-primary)',
              fontSize: 12, resize: 'none', outline: 'none', fontFamily: 'inherit',
            }}
          />
          <button onClick={() => send(input)} disabled={loading || !input.trim()} style={{
            background: loading || !input.trim() ? 'var(--bg-panel)' : 'var(--amber-dim)',
            color: loading || !input.trim() ? 'var(--text-muted)' : 'var(--amber)',
            border: `1px solid ${loading || !input.trim() ? 'var(--border)' : 'var(--amber)'}`,
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
