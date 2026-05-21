import { useEffect, useRef, useState } from 'react'

interface Msg {
  role: 'user' | 'genie'
  text?: string
  sql?: string | null
  columns?: string[]
  rows?: any[][]
  error?: string
  elapsedMs?: number
}

interface SpaceInfo {
  space_id: string
  url: string
  name: string
  cache_entries?: number
}

const SAMPLE_QUESTIONS: { q: string; cat: string }[] = [
  { q: 'Show me each operator well with its NPV and IRR, sorted by NPV',                       cat: 'operator' },
  { q: 'Which operator wells are currently in the money at the latest WTI price?',             cat: 'operator + WTI' },
  { q: 'What is the 30-day average WTI and how does it compare to the latest spot?',           cat: 'enterprise WTI' },
  { q: 'For each operator well, show NPV and its ADME analog well',                            cat: 'operator + ADME' },
  { q: 'Which wells have NPT hours above 30 in the last 30 days?',                             cat: 'drilling ops' },
  { q: 'Show the rig contractor and drilling phase for each operator well',                    cat: 'drilling ops' },
  { q: 'Plot WTI price over the last 90 days',                                                 cat: 'enterprise WTI' },
  { q: 'Average porosity and permeability by formation in the operator fleet',                 cat: 'petrophysics' },
  { q: 'Top ADME analog wells by primary reservoir',                                           cat: 'ADME analogs' },
  { q: 'Which ADME legal tags are currently valid?',                                           cat: 'governance' },
]

export default function GenieTab() {
  const [info, setInfo] = useState<SpaceInfo | null>(null)
  const [q, setQ] = useState('')
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [conv, setConv] = useState<string | null>(null)
  const [loading, setLoad] = useState(false)
  const [stage, setStage] = useState<{ msg: string; elapsed_ms: number } | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    fetch('/api/genie/space').then(r => r.json()).then(setInfo).catch(() => {})
  }, [])

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' })
  }, [msgs, loading, stage])

  async function ask(text: string) {
    if (!text.trim() || loading) return
    const t0 = Date.now()
    setMsgs(m => [...m, { role: 'user', text }])
    setQ('')
    setLoad(true); setStage({ msg: 'Connecting', elapsed_ms: 0 })
    const ac = new AbortController(); abortRef.current = ac
    try {
      const resp = await fetch('/api/genie/ask_stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body:   JSON.stringify({ question: text, conversation_id: conv }),
        signal: ac.signal,
      })
      if (!resp.body) throw new Error('no body')
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let nl: number
        while ((nl = buf.indexOf('\n\n')) >= 0) {
          const chunk = buf.slice(0, nl); buf = buf.slice(nl + 2)
          let ev = 'message', dataStr = ''
          for (const line of chunk.split('\n')) {
            if (line.startsWith('event:')) ev = line.slice(6).trim()
            else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
          }
          if (!dataStr) continue
          let data: any
          try { data = JSON.parse(dataStr) } catch { continue }
          if (ev === 'status') {
            setStage({ msg: data.msg || 'Working', elapsed_ms: data.elapsed_ms || 0 })
          } else if (ev === 'answer') {
            if (data.error) {
              setMsgs(m => [...m, { role: 'genie', error: data.error }])
            } else {
              setConv(data.conversation_id || conv)
              setMsgs(m => [...m, {
                role: 'genie',
                text: data.text, sql: data.sql,
                columns: data.columns, rows: data.rows,
                elapsedMs: Date.now() - t0,
              }])
            }
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') setMsgs(m => [...m, { role: 'genie', error: String(e.message || e) }])
    } finally {
      setLoad(false); setStage(null); abortRef.current = null
    }
  }

  function cancel() {
    abortRef.current?.abort()
    setLoad(false); setStage(null)
  }

  function newConv() {
    setConv(null); setMsgs([])
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, alignItems: 'start' }}>

      {/* Left: sample questions + space info */}
      <div style={{ display: 'grid', gap: 16, position: 'sticky', top: 12 }}>
        <Panel title="Genie space" subtitle={info?.name || 'Drilling Command Center — ADME Live'}>
          <div style={{ display: 'grid', gap: 6, fontSize: 11 }}>
            <Row label="Operator" value="operator_wells · operator_economics_live (NA · 6 wells · simulated petrophysics + ops)" />
            <Row label="Market"   value="wti_prices (180-day WTI from FRED)" />
            <Row label="Analogs"  value="wellbore_search_source · gold_reservoir · gold_rock_and_fluid (ADME global blocks 15/9 + 34/10)" />
            <Row label="Govern."  value="gov_legal_tags (ADME ACL inheritance)" />
            {info?.url && (
              <a href={info.url} target="_blank" rel="noreferrer" style={{
                marginTop: 6, fontSize: 10, color: 'var(--blue)', textDecoration: 'none', fontFamily: 'monospace',
              }}>↗ open in Databricks</a>
            )}
          </div>
        </Panel>

        <Panel title="Try a question">
          <div style={{ display: 'grid', gap: 5 }}>
            {SAMPLE_QUESTIONS.map((s, i) => (
              <button key={i} onClick={() => ask(s.q)} disabled={loading} style={{
                textAlign: 'left', padding: '7px 10px', borderRadius: 6,
                background: 'var(--bg-panel)', color: 'var(--text-secondary)',
                border: '1px solid var(--border)', cursor: loading ? 'default' : 'pointer',
                fontSize: 11, lineHeight: 1.4,
              }}>
                <div>{s.q}</div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'monospace' }}>{s.cat}</div>
              </button>
            ))}
          </div>
        </Panel>
      </div>

      {/* Right: conversation */}
      <Panel
        title="Conversation"
        subtitle={conv ? `conversation_id ${conv.slice(0, 18)}…` : 'New conversation · ask anything about the ADME data'}
        right={
          <button onClick={newConv} disabled={loading || msgs.length === 0} style={{
            background: 'var(--bg-panel)', color: 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: 4, padding: '3px 10px',
            fontSize: 10, cursor: msgs.length === 0 || loading ? 'default' : 'pointer',
          }}>+ New conversation</button>
        }
      >
        <div ref={bodyRef} style={{
          minHeight: 380, maxHeight: 600, overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 12, paddingRight: 4,
        }}>
          {msgs.length === 0 && !loading && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '20px 0' }}>
              Genie translates natural-language questions into SQL over the four governed ADME gold tables.
              Pick a sample on the left or type your own. Genie remembers the conversation, so follow-ups work.
            </div>
          )}
          {msgs.map((m, i) => <MsgBubble key={i} m={m} />)}
          {loading && stage && (
            <div style={{
              background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '10px 14px', fontSize: 12,
              display: 'flex', alignItems: 'center', gap: 10, maxWidth: 420,
            }}>
              <span style={{
                display: 'inline-block', width: 9, height: 9, borderRadius: 5,
                background: 'var(--teal)', animation: 'genie-pulse 1.1s infinite',
              }} />
              <span style={{ color: 'var(--teal)', fontWeight: 600 }}>{stage.msg}</span>
              <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 10 }}>
                {(stage.elapsed_ms / 1000).toFixed(1)}s
              </span>
              <style>{`@keyframes genie-pulse { 0%,100% { opacity:.35 } 50% { opacity:1 } }`}</style>
            </div>
          )}
        </div>

        <form onSubmit={e => { e.preventDefault(); ask(q) }} style={{
          marginTop: 12, display: 'flex', gap: 8, alignItems: 'flex-end',
        }}>
          <textarea
            value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(q) } }}
            placeholder={loading ? 'Genie is working…' : 'Ask Genie a question…'}
            disabled={loading} rows={2}
            style={{
              flex: 1, background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '10px 12px', fontSize: 13, color: 'var(--text-primary)',
              opacity: loading ? 0.6 : 1, resize: 'vertical', fontFamily: 'inherit',
            }}
          />
          {loading ? (
            <button type="button" onClick={cancel} style={{
              padding: '11px 16px', fontSize: 12, fontWeight: 700, color: 'white',
              background: 'var(--red)', border: 'none', borderRadius: 6, cursor: 'pointer',
            }}>◼ Cancel</button>
          ) : (
            <button type="submit" disabled={!q.trim()} style={{
              padding: '11px 18px', fontSize: 12, fontWeight: 700,
              background: !q.trim() ? 'var(--bg-panel)' : 'linear-gradient(135deg, #00E5FF, #4dabf7)',
              color: !q.trim() ? 'var(--text-muted)' : '#0d0e11',
              border: 'none', borderRadius: 6, cursor: !q.trim() ? 'default' : 'pointer',
            }}>✨ Ask Genie</button>
          )}
        </form>
      </Panel>
    </div>
  )
}

function MsgBubble({ m }: { m: Msg }) {
  if (m.role === 'user') {
    return (
      <div style={{
        alignSelf: 'flex-end', maxWidth: '70%',
        background: 'var(--blue-dim)', border: '1px solid var(--blue)',
        borderRadius: 10, padding: '8px 12px', fontSize: 13, color: 'var(--text-primary)',
      }}>
        {m.text}
      </div>
    )
  }
  return (
    <div style={{ alignSelf: 'flex-start', maxWidth: '95%' }}>
      {m.error && (
        <div style={{ background: 'var(--red-dim)', border: '1px solid var(--red)', color: 'var(--red)', padding: 10, fontSize: 12, borderRadius: 6 }}>
          ⚠️ {m.error}
        </div>
      )}
      {m.text && (
        <div style={{
          background: 'var(--bg-panel)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '10px 14px', fontSize: 13, color: 'var(--text-primary)',
          lineHeight: 1.55, whiteSpace: 'pre-wrap',
        }}>{m.text}</div>
      )}
      {m.sql && (
        <details open style={{
          marginTop: 8,
          background: 'var(--bg-primary)', border: '1px solid var(--border-dim)', borderRadius: 6,
        }}>
          <summary style={{ cursor: 'pointer', padding: '6px 10px', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>
            Generated SQL
          </summary>
          <pre style={{
            margin: 0, padding: '8px 12px', fontFamily: 'monospace', fontSize: 11,
            color: 'var(--teal)', whiteSpace: 'pre-wrap', overflowX: 'auto',
          }}>{m.sql}</pre>
        </details>
      )}
      {m.rows && m.rows.length > 0 && (
        <div style={{
          marginTop: 8, maxHeight: 320, overflow: 'auto',
          border: '1px solid var(--border-dim)', borderRadius: 6,
        }}>
          <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-panel)', position: 'sticky', top: 0 }}>
                {(m.columns || []).map(c => (
                  <th key={c} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600 }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {m.rows.slice(0, 100).map((row, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border-dim)' }}>
                  {row.map((v: any, j: number) => (
                    <td key={j} style={{ padding: '5px 10px', color: 'var(--text-primary)' }}>
                      {v == null ? '—' : typeof v === 'number' ? Number(v).toLocaleString() : String(v).slice(0, 80)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {m.rows.length > 100 && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: 6, textAlign: 'center' }}>
              + {m.rows.length - 100} more rows
            </div>
          )}
        </div>
      )}
      {m.elapsedMs && (
        <div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
          answered in {(m.elapsedMs / 1000).toFixed(1)}s
        </div>
      )}
    </div>
  )
}

function Panel({ title, subtitle, right, children }: { title: string; subtitle?: string; right?: any; children: any }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 8, padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 12, gap: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{title}</div>
          {subtitle && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
        </div>
        {right}
      </div>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '70px 1fr', gap: 6, fontSize: 11 }}>
      <div style={{ color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ color: 'var(--text-primary)', wordBreak: 'break-word' }}>{value}</div>
    </div>
  )
}
