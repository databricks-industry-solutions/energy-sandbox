import { useEffect, useMemo, useState } from 'react'

interface Persona {
  persona: string
  label: string
  allowed_fields: string
  row_filter: string | null
  description: string
}

interface PersonaView {
  persona: string
  label: string
  allowed_fields: string[]
  row_filter: string | null
  description: string
  visible_count: number
  total_count: number
  redacted_count: number
  wells: any[]
}

interface Chain {
  chain: { step: string; title: string; detail: string; examples: string[] }[]
}

interface Co2Row { country_name: string; country_code: string; year: number; co2_kt: number }
interface Co2Resp { installed: boolean; source?: string; year?: number; rows: Co2Row[]; error?: string }

interface AuditEvent {
  event_time: string
  actor: string
  action: string
  service: string
  status: number
  target?: string
}
interface AuditResp { source: string; events: AuditEvent[]; synthetic: boolean; note?: string }

const SENSITIVE_COLS: { col: string; classification: string; rule: string; affects: string }[] = [
  { col: 'lat',         classification: 'Location · PII-adjacent', rule: 'Masked for analyst, external personas',   affects: 'silver_wellbore.lat'        },
  { col: 'lon',         classification: 'Location · PII-adjacent', rule: 'Masked for analyst, external personas',   affects: 'silver_wellbore.lon'        },
  { col: 'api_number',  classification: 'Regulatory ID',           rule: 'Masked for external persona',             affects: 'wells.api_number'           },
  { col: 'notes',       classification: 'Free-text · may contain PII', rule: 'Masked for external persona',         affects: 'wells.notes'                },
  { col: 'kb_elevation_ft', classification: 'Engineering detail',  rule: 'Visible to operator only',                affects: 'wells.kb_elevation_ft'      },
  { col: 'spud_date',   classification: 'Operational',             rule: 'Visible to operator only',                affects: 'wells.spud_date'            },
]

const COMPLIANCE_BADGES = [
  { label: 'ADME ACL inheritance',  status: 'Enforced',  detail: 'Legal tags propagated to UC row tags' },
  { label: 'Encryption at rest',    status: 'AES-256',   detail: 'Delta + Lakebase managed keys'         },
  { label: 'Encryption in transit', status: 'TLS 1.2+',  detail: 'OBO tokens, no static secrets'         },
  { label: 'Data residency',        status: 'Azure US',  detail: 'centralus · ADME opendes partition'    },
  { label: 'Retention policy',      status: '7 yr',      detail: 'Wells · audit logs 1 yr in system.access' },
  { label: 'GDPR / SOX ready',      status: 'Auditable', detail: 'Lineage + audit trail via Unity Catalog' },
]

export default function GovernanceTab() {
  const [personas, setPersonas] = useState<Persona[] | null>(null)
  const [active, setActive]     = useState('operator')
  const [view, setView]         = useState<PersonaView | null>(null)
  const [legal, setLegal]       = useState<any>(null)
  const [chain, setChain]       = useState<Chain | null>(null)
  const [co2, setCo2]           = useState<Co2Resp | null>(null)
  const [audit, setAudit]       = useState<AuditResp | null>(null)
  const [wellsCount, setWellsCount] = useState<{ total: number; osdu: number } | null>(null)

  // Each fetch resolves independently — no blocking gate.
  useEffect(() => { fetch('/api/governance/uc_chain').then(r => r.json()).then(setChain).catch(() => {}) }, [])
  useEffect(() => { fetch('/api/governance/personas').then(r => r.json()).then(setPersonas).catch(() => {}) }, [])
  useEffect(() => { fetch('/api/governance/legal_tags').then(r => r.json()).then(setLegal).catch(() => {}) }, [])
  useEffect(() => { fetch('/api/governance/co2').then(r => r.json()).then(setCo2).catch(() => {}) }, [])
  useEffect(() => { fetch('/api/governance/audit').then(r => r.json()).then(setAudit).catch(() => {}) }, [])
  useEffect(() => {
    fetch('/api/wells').then(r => r.json()).then((ws: any[]) => {
      setWellsCount({ total: ws.length, osdu: ws.filter(w => w.well_id?.startsWith('OSDU-')).length })
    }).catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`/api/governance/view/${active}`).then(r => r.json()).then(setView).catch(() => {})
  }, [active])

  const rowFilterCount = useMemo(() => (personas || []).filter(p => p.row_filter).length, [personas])
  const allowedFieldsCount = useMemo(() => {
    const all = new Set<string>()
    ;(personas || []).forEach(p => (p.allowed_fields || '').split(',').forEach(f => f.trim() && all.add(f.trim())))
    return all.size
  }, [personas])

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
        <Kpi label="ADME legal tags"   value={legal?.legal_tags?.length ?? '…'} sub={legal?.error ? 'UC fetch failed' : 'gov_legal_tags'} color="var(--teal)" />
        <Kpi label="Entitlement groups" value={legal?.total_groups ?? '…'}      sub="gov_entitlements" color="var(--purple)" />
        <Kpi label="Personas"          value={personas?.length ?? '…'}          sub={`${rowFilterCount} with row filters`} color="var(--blue)" />
        <Kpi label="Allowed fields"    value={allowedFieldsCount || '…'}        sub={`across ${personas?.length ?? 0} personas`} color="var(--amber)" />
        <Kpi label="Wells governed"    value={wellsCount?.total ?? '…'}         sub={wellsCount ? `${wellsCount.osdu} via ADME` : 'loading…'} color="var(--green)" />
      </div>

      {/* Compliance badges */}
      <Panel title="Compliance posture" subtitle="Continuous controls inherited from ADME source through Unity Catalog">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {COMPLIANCE_BADGES.map(b => (
            <div key={b.label} style={{
              background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '10px 12px', display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: 8,
            }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-primary)' }}>{b.label}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{b.detail}</div>
              </div>
              <span style={{
                fontSize: 10, fontWeight: 700, fontFamily: 'monospace',
                padding: '3px 8px', borderRadius: 10,
                background: 'var(--green-dim)', color: 'var(--green)', whiteSpace: 'nowrap',
              }}>✓ {b.status}</span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Governance chain · ADME → Unity Catalog → App" subtitle="Legal tags propagate from source to the UI. Persona toggle below demonstrates runtime enforcement.">
        {chain ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {chain.chain.map((s, i) => (
              <div key={s.step} style={{
                background: 'var(--bg-panel)', border: '1px solid var(--border)',
                borderRadius: 8, padding: 14, position: 'relative',
              }}>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.08em' }}>STEP {i + 1}</div>
                <div style={{ fontWeight: 700, color: 'var(--teal)', fontSize: 14 }}>{s.step}</div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4, fontWeight: 600 }}>{s.title}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>{s.detail}</div>
                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {s.examples.map(ex => (
                    <span key={ex} style={{
                      fontSize: 10, padding: '2px 7px', borderRadius: 4,
                      background: 'var(--bg-card)', color: 'var(--text-muted)',
                      fontFamily: 'monospace',
                    }}>{ex}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : <Skeleton lines={3} />}
      </Panel>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>
        <Panel title="Persona" subtitle="Switch persona to see enforcement">
          {personas ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {personas.map(p => (
                <button key={p.persona} onClick={() => setActive(p.persona)} style={{
                  textAlign: 'left', padding: '10px 12px',
                  background: active === p.persona ? 'var(--blue-dim)' : 'var(--bg-panel)',
                  border: `1px solid ${active === p.persona ? 'var(--blue)' : 'var(--border)'}`,
                  borderRadius: 6, cursor: 'pointer',
                }}>
                  <div style={{ fontWeight: 600, color: active === p.persona ? 'var(--blue)' : 'var(--text-primary)', fontSize: 13 }}>
                    {p.label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.4 }}>{p.description}</div>
                </button>
              ))}
            </div>
          ) : <Skeleton lines={3} />}
        </Panel>

        <Panel
          title={`Active view · ${view?.label || active}`}
          subtitle={view ? `${view?.visible_count}/${view?.total_count} rows visible · ${view?.redacted_count} hidden by row filter · ${view?.allowed_fields?.length === 1 && view.allowed_fields[0] === 'all' ? 'all fields' : `${view?.allowed_fields?.length || 0} allowed fields`}` : 'loading…'}
        >
          {view ? (
            <>
              {view.row_filter && (
                <div style={{
                  padding: 8, marginBottom: 10, borderRadius: 6,
                  background: 'var(--amber-dim)', border: '1px solid var(--amber)',
                  fontSize: 11, color: 'var(--amber)', fontFamily: 'monospace',
                }}>
                  Row filter: {view.row_filter}
                </div>
              )}
              <div style={{ overflow: 'auto', maxHeight: 380 }}>
                <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                  <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                    <tr>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>well_id</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>well_name</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>basin</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>status</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>notes</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>lat/lon</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10 }}>API #</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.wells.map((w: any) => (
                      <tr key={w.well_id} style={{ borderTop: '1px solid var(--border-dim)' }}>
                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', color: 'var(--blue)' }}>{w.well_id}</td>
                        <Td v={w.well_name} />
                        <Td v={w.basin} />
                        <Td v={w.status} />
                        <Td v={w.notes} trunc={40} />
                        <Td v={w.lat && w.lon ? `${String(w.lat).slice(0, 6)}, ${String(w.lon).slice(0, 7)}` : w.lat} />
                        <Td v={w.api_number} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : <Skeleton lines={5} />}
        </Panel>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel title="ADME legal tags" subtitle={`Live from ${legal?.source || `${'<catalog>'}.<schema>`}.gov_legal_tags`}>
          {!legal ? <Skeleton lines={4} /> : legal.error ? (
            <div style={{ fontSize: 11, color: 'var(--amber)' }}>⚠️ {legal.error}</div>
          ) : legal.legal_tags?.length ? (
            <div style={{ maxHeight: 220, overflow: 'auto' }}>
              {legal.legal_tags.map((t: any, i: number) => (
                <div key={i} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-dim)' }}>
                  <div style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--teal)' }}>
                    {t.legal_tag_name} {t.is_valid ? '✓' : '✗'}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{t.description}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No legal tag data yet</div>
          )}
        </Panel>
        <Panel title={`ADME entitlements${legal?.total_groups ? ` (${legal.total_groups})` : ''}`} subtitle="group membership drives ADME record ACL">
          {!legal ? <Skeleton lines={4} /> : legal.entitlement_groups?.length ? (
            <div style={{ maxHeight: 220, overflow: 'auto' }}>
              {legal.entitlement_groups.map((g: any, i: number) => (
                <div key={i} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-dim)' }}>
                  <div style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--purple)' }}>{g.group_name || g.group_id}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{g.description}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No entitlement group data yet</div>
          )}
        </Panel>
      </div>

      {/* Sensitive columns inventory */}
      <Panel title="Sensitive columns inventory" subtitle="Column-level masking rules enforced by Unity Catalog per persona">
        <div style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Column', 'Classification', 'Masking rule', 'Bound to'].map(h => (
                  <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10, borderBottom: '1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SENSITIVE_COLS.map(c => (
                <tr key={c.col} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                  <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: 'var(--amber)' }}>{c.col}</td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-primary)' }}>{c.classification}</td>
                  <td style={{ padding: '7px 10px', color: 'var(--text-secondary)' }}>{c.rule}</td>
                  <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{c.affects}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* Audit events feed */}
      <Panel
        title="Audit events"
        subtitle={audit?.synthetic ? 'Synthetic demo events · grant SELECT ON system.access.audit to wire live' : `Live · ${audit?.source ?? 'system.access.audit'}`}
      >
        {!audit ? <Skeleton lines={5} /> : audit.events.length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No recent events</div>
        ) : (
          <div style={{ maxHeight: 280, overflow: 'auto' }}>
            <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                <tr>
                  {['Time', 'Actor', 'Action', 'Service', 'Status', 'Target'].map(h => (
                    <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontSize: 10, borderBottom: '1px solid var(--border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {audit.events.map((e, i) => {
                  const ok = e.status >= 200 && e.status < 300
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                      <td style={{ padding: '6px 10px', fontFamily: 'monospace', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{formatTime(e.event_time)}</td>
                      <td style={{ padding: '6px 10px', color: 'var(--text-primary)' }}>{e.actor}</td>
                      <td style={{ padding: '6px 10px', fontFamily: 'monospace', color: 'var(--blue)' }}>{e.action}</td>
                      <td style={{ padding: '6px 10px', color: 'var(--text-secondary)' }}>{e.service}</td>
                      <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontWeight: 600, color: ok ? 'var(--green)' : 'var(--red)' }}>{e.status}</td>
                      <td style={{ padding: '6px 10px', color: 'var(--text-muted)' }}>{e.target || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ESG / CO2 panel */}
      <Panel
        title="ESG · CO₂ emissions"
        subtitle={
          co2?.installed
            ? `Top emitters · ${co2.year} · live from ${co2.source}`
            : co2?.error
              ? `Marketplace not wired: ${co2.error.slice(0, 80)}`
              : 'World Bank Open Data via Databricks Marketplace'
        }
      >
        {!co2 ? <Skeleton lines={6} /> : co2.installed && co2.rows.length > 0 ? (
          <div>
            {(() => {
              const max = Math.max(...co2.rows.map(r => r.co2_kt || 0))
              return co2.rows.map(r => {
                const pct = max ? ((r.co2_kt || 0) / max) * 100 : 0
                return (
                  <div key={r.country_code} style={{ display: 'grid', gridTemplateColumns: '180px 1fr 110px', gap: 10, alignItems: 'center', padding: '4px 0', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-primary)' }}>
                      <span style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>{r.country_code}</span>{' '}
                      {r.country_name}
                    </span>
                    <div style={{ background: 'var(--bg-panel)', height: 8, borderRadius: 2, position: 'relative' }}>
                      <div style={{ background: 'linear-gradient(90deg, var(--green), var(--amber), var(--red))', width: `${pct}%`, height: '100%', borderRadius: 2 }} />
                    </div>
                    <span style={{ textAlign: 'right', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                      {((r.co2_kt || 0) / 1000).toLocaleString(undefined, { maximumFractionDigits: 0 })} Mt
                    </span>
                  </div>
                )
              })
            })()}
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 10, lineHeight: 1.5 }}>
              CO₂ emissions in kilotons, World Bank indicator EN.ATM.CO2E.KT. Same Unity Catalog governance plane as
              the ADME data — grants, tags, and column masks apply uniformly.
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            CO₂ data isn't wired yet. Install the World Bank CO₂ Marketplace listing and grant the app SP SELECT.
          </div>
        )}
      </Panel>
    </div>
  )
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  } catch { return iso.slice(11, 16) }
}

function Kpi({ label, value, sub, color }: { label: string; value: any; sub: string; color: string }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>
    </div>
  )
}

function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} style={{
          height: 12, borderRadius: 4, background: 'var(--bg-panel)',
          opacity: 0.4 + (i % 2) * 0.2,
        }} />
      ))}
    </div>
  )
}

function Td({ v, trunc }: { v: any; trunc?: number }) {
  const redacted = v === '🔒 redacted'
  const val = v == null ? '—' : trunc && typeof v === 'string' && v.length > trunc ? v.slice(0, trunc) + '…' : String(v)
  return (
    <td style={{ padding: '5px 8px', color: redacted ? 'var(--red)' : 'var(--text-primary)', fontStyle: redacted ? 'italic' : 'normal' }}>
      {val}
    </td>
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
