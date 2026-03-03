import { useState, useEffect } from 'react'

// ── Types ────────────────────────────────────────────────────────────────────

interface ShareTable {
  table: string
  rows: number
  last_sync: string
  status: 'ACTIVE' | 'PENDING' | 'ERROR'
}

interface ShareGroup {
  share_name: string
  tables: ShareTable[]
  uc_catalog: string
  uc_schema: string
}

interface DeltaSharingSummary {
  total_inbound_tables: number
  total_outbound_tables: number
  active_inbound: number
  pending_outbound: number
}

interface UCGovernance {
  catalog: string
  schemas: string[]
  access_control: string
  audit_log: string
}

interface DeltaSharingStatus {
  inbound: ShareGroup[]
  outbound: ShareGroup[]
  summary: DeltaSharingSummary
  uc_governance: UCGovernance
}

// ── Fallback data ────────────────────────────────────────────────────────────

const FALLBACK: DeltaSharingStatus = {
  inbound: [
    {
      share_name: 'sap_bdc_to_databricks',
      uc_catalog: 'oil_pump_monitor_catalog',
      uc_schema: 'sap_inbound',
      tables: [
        { table: 'material_pricing',   rows: 124830, last_sync: '2026-02-24T08:12:00Z', status: 'ACTIVE' },
        { table: 'equipment_inventory', rows: 47620,  last_sync: '2026-02-24T08:12:00Z', status: 'ACTIVE' },
        { table: 'service_contracts',   rows: 8940,   last_sync: '2026-02-24T07:45:00Z', status: 'ACTIVE' },
        { table: 'vendor_lead_times',   rows: 3215,   last_sync: '2026-02-24T06:30:00Z', status: 'PENDING' },
      ],
    },
  ],
  outbound: [
    {
      share_name: 'databricks_to_sap_bdc',
      uc_catalog: 'oil_pump_monitor_catalog',
      uc_schema: 'sap_outbound',
      tables: [
        { table: 'production_forecast',    rows: 56200, last_sync: '2026-02-24T08:00:00Z', status: 'ACTIVE' },
        { table: 'material_requirements',  rows: 31480, last_sync: '2026-02-24T08:00:00Z', status: 'ACTIVE' },
        { table: 'cost_estimates',         rows: 12750, last_sync: '2026-02-24T07:30:00Z', status: 'ACTIVE' },
        { table: 'procurement_triggers',   rows: 1890,  last_sync: '2026-02-24T06:00:00Z', status: 'PENDING' },
      ],
    },
  ],
  summary: {
    total_inbound_tables: 4,
    total_outbound_tables: 4,
    active_inbound: 3,
    pending_outbound: 1,
  },
  uc_governance: {
    catalog: 'oil_pump_monitor_catalog',
    schemas: ['sap_inbound', 'sap_outbound', 'sim', 'econ'],
    access_control: 'Unity Catalog ACLs + row-level security',
    audit_log: 'System tables · audit_logs · lineage',
  },
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtRows(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function fmtSync(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getUTCHours()).padStart(2, '0')
    const mm = String(d.getUTCMinutes()).padStart(2, '0')
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')} ${hh}:${mm}`
  } catch {
    return iso
  }
}

function statusColor(s: string): string {
  if (s === 'ACTIVE') return 'var(--green)'
  if (s === 'PENDING') return 'var(--amber)'
  return 'var(--red)'
}

function statusBg(s: string): string {
  if (s === 'ACTIVE') return 'var(--green-dim)'
  if (s === 'PENDING') return 'var(--amber-dim)'
  return 'var(--red-dim)'
}

// ── Component ────────────────────────────────────────────────────────────────

export default function DeltaSharingTab() {
  const [data, setData] = useState<DeltaSharingStatus>(FALLBACK)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch('/api/delta-sharing/status')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d: DeltaSharingStatus) => {
        if (!cancelled) {
          setData(d)
          setError('')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData(FALLBACK)
          setError('Using demo data — API unavailable')
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const { summary, uc_governance: gov } = data
  const allInbound = data.inbound.flatMap(g => g.tables)
  const allOutbound = data.outbound.flatMap(g => g.tables)

  // ── SVG constants ────────────────────────────────────────────────────────

  const SVG_W = 960
  const SVG_H = 520

  // Inbound table names (SAP → Databricks)
  const inboundNames = ['material_pricing', 'equipment_inventory', 'service_contracts', 'vendor_lead_times']
  // Outbound table names (Databricks → SAP)
  const outboundNames = ['production_forecast', 'material_requirements', 'cost_estimates', 'procurement_triggers']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Error banner ── */}
      {error && (
        <div style={{
          padding: '6px 14px', borderRadius: 6,
          background: 'var(--amber-dim)', border: '1px solid var(--amber)',
          color: 'var(--amber)', fontSize: 11, fontWeight: 600,
        }}>
          {error}
        </div>
      )}

      {/* ── Summary KPI strip ── */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {[
          { label: 'Inbound Tables',  val: String(summary.total_inbound_tables),  color: 'var(--teal)' },
          { label: 'Outbound Tables', val: String(summary.total_outbound_tables), color: 'var(--gold)' },
          { label: 'Active Shares',   val: String(summary.active_inbound + (summary.total_outbound_tables - summary.pending_outbound)), color: 'var(--green)' },
          { label: 'Unity Catalog',   val: gov.catalog, color: 'var(--amber)' },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding: '8px 14px', flex: 1, minWidth: 170 }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 4 }}>
              {k.label.toUpperCase()}
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: k.color, fontFamily: 'monospace' }}>
              {k.val}
            </div>
          </div>
        ))}
      </div>

      {/* ── SVG Data Flow Diagram ── */}
      <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
        <div style={{
          padding: '10px 16px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span className="label">SAP BUSINESS DATA CLOUD &harr; DATABRICKS DELTA SHARING</span>
          <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>
            {loading ? 'Loading...' : 'Live'}
          </span>
          {!loading && (
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: error ? 'var(--amber)' : 'var(--green)',
              display: 'inline-block',
            }} />
          )}
        </div>

        <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ width: '100%', display: 'block' }}>
          <style>{`
            @keyframes ds-dash {
              from { stroke-dashoffset: 18; }
              to   { stroke-dashoffset: 0; }
            }
            @keyframes ds-dash-rev {
              from { stroke-dashoffset: 0; }
              to   { stroke-dashoffset: 18; }
            }
            @keyframes ds-pulse {
              0%, 100% { opacity: 0.7; }
              50%      { opacity: 1; }
            }
          `}</style>

          {/* ── Background regions ── */}
          {/* SAP side (left) */}
          <rect x={20} y={20} width={280} height={480} rx={12}
            fill="#1a2a35" stroke="#2d8c9e" strokeWidth={1} strokeOpacity={0.35} />
          <text x={40} y={50} fill="#36cfc9" fontSize={13} fontWeight={700}
            fontFamily="system-ui,sans-serif">SAP Business Data Cloud</text>
          <text x={40} y={66} fill="#2d8c9e" fontSize={9.5}
            fontFamily="system-ui,sans-serif">Enterprise Resource Planning</text>

          {/* Databricks side (right) */}
          <rect x={660} y={20} width={280} height={480} rx={12}
            fill="#2a2518" stroke="#c49a2e" strokeWidth={1} strokeOpacity={0.35} />
          <text x={680} y={50} fill="#ffd666" fontSize={13} fontWeight={700}
            fontFamily="system-ui,sans-serif">Databricks Unity Catalog</text>
          <text x={680} y={66} fill="#c49a2e" fontSize={9.5}
            fontFamily="system-ui,sans-serif">oil_pump_monitor_catalog</text>

          {/* ── Center: Delta Sharing Protocol ── */}
          <rect x={355} y={60} width={250} height={54} rx={10}
            fill="var(--bg-card)" stroke="var(--purple)" strokeWidth={1.5} />
          <text x={480} y={84} textAnchor="middle" fill="var(--purple)" fontSize={12}
            fontWeight={700} fontFamily="system-ui,sans-serif">Delta Sharing Protocol</text>
          <text x={480} y={100} textAnchor="middle" fill="var(--text-muted)" fontSize={9}
            fontFamily="system-ui,sans-serif">Open protocol for secure data exchange</text>

          {/* ── Bidirectional arrows (center) ── */}
          {/* Arrow: SAP → Databricks (top flow line) */}
          <defs>
            <marker id="ds-arr-right" markerWidth={8} markerHeight={8} refX={6} refY={3} orient="auto">
              <path d="M0,0 L0,6 L8,3 z" fill="var(--teal)" />
            </marker>
            <marker id="ds-arr-left" markerWidth={8} markerHeight={8} refX={2} refY={3} orient="auto">
              <path d="M8,0 L8,6 L0,3 z" fill="var(--gold)" />
            </marker>
          </defs>

          {/* Inbound label */}
          <text x={480} y={140} textAnchor="middle" fill="var(--teal)" fontSize={9.5}
            fontWeight={600} fontFamily="system-ui,sans-serif">
            INBOUND (SAP &rarr; Databricks)
          </text>

          {/* Inbound flow line: static track */}
          <line x1={300} y1={150} x2={660} y2={150}
            stroke="var(--teal)" strokeWidth={1.5} strokeDasharray="6 3" strokeOpacity={0.18} />
          {/* Inbound flow line: animated */}
          <line x1={300} y1={150} x2={654} y2={150}
            stroke="var(--teal)" strokeWidth={2} strokeDasharray="6 3"
            markerEnd="url(#ds-arr-right)"
            style={{ animation: 'ds-dash 1.6s linear infinite' }} />

          {/* Outbound label */}
          <text x={480} y={180} textAnchor="middle" fill="var(--gold)" fontSize={9.5}
            fontWeight={600} fontFamily="system-ui,sans-serif">
            OUTBOUND (Databricks &rarr; SAP)
          </text>

          {/* Outbound flow line: static track */}
          <line x1={660} y1={190} x2={300} y2={190}
            stroke="var(--gold)" strokeWidth={1.5} strokeDasharray="6 3" strokeOpacity={0.18} />
          {/* Outbound flow line: animated */}
          <line x1={660} y1={190} x2={306} y2={190}
            stroke="var(--gold)" strokeWidth={2} strokeDasharray="6 3"
            markerEnd="url(#ds-arr-left)"
            style={{ animation: 'ds-dash-rev 1.6s linear infinite' }} />

          {/* ── Inbound tables (under SAP box) ── */}
          <text x={40} y={104} fill="var(--teal)" fontSize={9} fontWeight={700}
            fontFamily="system-ui,sans-serif" letterSpacing="0.06em">INBOUND TABLES</text>

          {inboundNames.map((name, i) => {
            const ty = 118 + i * 36
            return (
              <g key={name}>
                <rect x={35} y={ty} width={250} height={28} rx={5}
                  fill="var(--bg-panel)" stroke="var(--border)" strokeWidth={0.8} />
                <circle cx={50} cy={ty + 14} r={4} fill="var(--teal)" />
                <text x={60} y={ty + 17} fill="var(--text-secondary)" fontSize={10.5}
                  fontFamily="monospace" fontWeight={500}>{name}</text>

                {/* Connector line from table to center flow */}
                <line x1={285} y1={ty + 14} x2={300} y2={150}
                  stroke="var(--teal)" strokeWidth={0.8} strokeOpacity={0.25} strokeDasharray="3 2" />
              </g>
            )
          })}

          {/* ── Outbound tables (under Databricks box) ── */}
          <text x={680} y={104} fill="var(--gold)" fontSize={9} fontWeight={700}
            fontFamily="system-ui,sans-serif" letterSpacing="0.06em">OUTBOUND TABLES</text>

          {outboundNames.map((name, i) => {
            const ty = 118 + i * 36
            return (
              <g key={name}>
                <rect x={675} y={ty} width={250} height={28} rx={5}
                  fill="var(--bg-panel)" stroke="var(--border)" strokeWidth={0.8} />
                <circle cx={690} cy={ty + 14} r={4} fill="var(--gold)" />
                <text x={700} y={ty + 17} fill="var(--text-secondary)" fontSize={10.5}
                  fontFamily="monospace" fontWeight={500}>{name}</text>

                {/* Connector line from table to center flow */}
                <line x1={675} y1={ty + 14} x2={660} y2={190}
                  stroke="var(--gold)" strokeWidth={0.8} strokeOpacity={0.25} strokeDasharray="3 2" />
              </g>
            )
          })}

          {/* ── Process boxes at bottom ── */}
          {/* SAP side process */}
          <rect x={35} y={300} width={250} height={70} rx={8}
            fill="var(--bg-card)" stroke="#2d8c9e" strokeWidth={1} />
          <text x={55} y={322} fill="var(--teal)" fontSize={11} fontWeight={700}
            fontFamily="system-ui,sans-serif">SAP Data Integration</text>
          <text x={55} y={340} fill="var(--text-muted)" fontSize={9}
            fontFamily="system-ui,sans-serif">S/4HANA &middot; BW/4HANA &middot; MDG</text>
          <text x={55} y={356} fill="var(--text-muted)" fontSize={9}
            fontFamily="system-ui,sans-serif">Real-time CDC &middot; Batch sync</text>

          {/* Databricks side process */}
          <rect x={675} y={300} width={250} height={70} rx={8}
            fill="var(--bg-card)" stroke="#c49a2e" strokeWidth={1} />
          <text x={695} y={322} fill="var(--gold)" fontSize={11} fontWeight={700}
            fontFamily="system-ui,sans-serif">Lakehouse Processing</text>
          <text x={695} y={340} fill="var(--text-muted)" fontSize={9}
            fontFamily="system-ui,sans-serif">Delta Lake &middot; Spark &middot; SQL Warehouse</text>
          <text x={695} y={356} fill="var(--text-muted)" fontSize={9}
            fontFamily="system-ui,sans-serif">ML models &middot; Feature engineering</text>

          {/* Center governance note */}
          <rect x={355} y={310} width={250} height={50} rx={8}
            fill="none" stroke="var(--amber)" strokeWidth={1} strokeDasharray="6 3" strokeOpacity={0.5} />
          <text x={480} y={332} textAnchor="middle" fill="var(--amber)" fontSize={10}
            fontWeight={700} fontFamily="system-ui,sans-serif">Unity Catalog Governance</text>
          <text x={480} y={348} textAnchor="middle" fill="var(--text-muted)" fontSize={9}
            fontFamily="system-ui,sans-serif">ACLs &middot; Lineage &middot; Audit Logging</text>

          {/* ── Security badges ── */}
          {[
            { x: 380, y: 395, label: 'TLS 1.3', color: 'var(--green)' },
            { x: 450, y: 395, label: 'REST API', color: 'var(--blue)' },
            { x: 525, y: 395, label: 'OAuth 2.0', color: 'var(--purple)' },
          ].map(b => (
            <g key={b.label}>
              <rect x={b.x} y={b.y} width={58} height={18} rx={9}
                fill="var(--bg-card)" stroke={b.color} strokeWidth={0.8} />
              <text x={b.x + 29} y={b.y + 12.5} textAnchor="middle"
                fill={b.color} fontSize={8} fontWeight={600} fontFamily="monospace">{b.label}</text>
            </g>
          ))}

          {/* ── Legend ── */}
          <g transform="translate(30, 465)">
            {[
              { color: '#36cfc9', label: 'SAP Inbound' },
              { color: '#ffd666', label: 'Databricks Outbound' },
              { color: '#b37feb', label: 'Delta Sharing Protocol' },
              { color: '#ffa940', label: 'Unity Catalog Governance' },
              { color: '#00c875', label: 'Active Sync' },
            ].map((l, i) => (
              <g key={l.label} transform={`translate(${i * 180}, 0)`}>
                <rect x={0} y={0} width={11} height={11} rx={2} fill={l.color} />
                <text x={15} y={9} fill="var(--text-muted)" fontSize={9}
                  fontFamily="system-ui,sans-serif">{l.label}</text>
              </g>
            ))}
          </g>
        </svg>
      </div>

      {/* ── Share tables: Inbound + Outbound side by side ── */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>

        {/* Inbound Shares */}
        <div className="card" style={{ flex: 1, overflow: 'hidden' }}>
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: 2,
              background: 'var(--teal)', display: 'inline-block',
            }} />
            <span className="label">INBOUND SHARES (SAP &rarr; DATABRICKS)</span>
            <span style={{ marginLeft: 'auto' }} className="badge badge-blue">
              {data.inbound.map(g => g.share_name).join(', ')}
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Table', 'Rows', 'Last Sync', 'Status'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '8px 14px',
                      borderBottom: '1px solid var(--border)',
                      color: 'var(--text-muted)', fontSize: 10,
                      fontWeight: 700, letterSpacing: '0.05em',
                    }}>
                      {h.toUpperCase()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allInbound.map(t => (
                  <tr key={t.table} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                    <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {t.table}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                      {fmtRows(t.rows)}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'monospace', color: 'var(--text-muted)', fontSize: 11 }}>
                      {fmtSync(t.last_sync)}
                    </td>
                    <td style={{ padding: '8px 14px' }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center',
                        padding: '2px 8px', borderRadius: 20,
                        fontSize: 10, fontWeight: 600,
                        background: statusBg(t.status),
                        color: statusColor(t.status),
                        border: `1px solid ${statusColor(t.status) === 'var(--green)' ? 'var(--green)' : statusColor(t.status) === 'var(--amber)' ? 'var(--amber)' : 'var(--red)'}`,
                      }}>
                        {t.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Outbound Shares */}
        <div className="card" style={{ flex: 1, overflow: 'hidden' }}>
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: 2,
              background: 'var(--gold)', display: 'inline-block',
            }} />
            <span className="label">OUTBOUND SHARES (DATABRICKS &rarr; SAP)</span>
            <span style={{ marginLeft: 'auto' }} className="badge badge-gold">
              {data.outbound.map(g => g.share_name).join(', ')}
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Table', 'Rows', 'Last Sync', 'Status'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '8px 14px',
                      borderBottom: '1px solid var(--border)',
                      color: 'var(--text-muted)', fontSize: 10,
                      fontWeight: 700, letterSpacing: '0.05em',
                    }}>
                      {h.toUpperCase()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allOutbound.map(t => (
                  <tr key={t.table} style={{ borderBottom: '1px solid var(--border-dim)' }}>
                    <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {t.table}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                      {fmtRows(t.rows)}
                    </td>
                    <td style={{ padding: '8px 14px', fontFamily: 'monospace', color: 'var(--text-muted)', fontSize: 11 }}>
                      {fmtSync(t.last_sync)}
                    </td>
                    <td style={{ padding: '8px 14px' }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center',
                        padding: '2px 8px', borderRadius: 20,
                        fontSize: 10, fontWeight: 600,
                        background: statusBg(t.status),
                        color: statusColor(t.status),
                        border: `1px solid ${statusColor(t.status) === 'var(--green)' ? 'var(--green)' : statusColor(t.status) === 'var(--amber)' ? 'var(--amber)' : 'var(--red)'}`,
                      }}>
                        {t.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Unity Catalog Governance card ── */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{
          padding: '10px 16px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: 2,
            background: 'var(--amber)', display: 'inline-block',
          }} />
          <span className="label">UNITY CATALOG GOVERNANCE</span>
        </div>
        <div style={{
          padding: 16, display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
        }}>
          {/* Catalog */}
          <div style={{
            padding: '12px 16px', background: 'var(--bg-panel)',
            borderRadius: 6, border: '1px solid var(--border-dim)',
          }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 6 }}>
              CATALOG
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--amber)', fontFamily: 'monospace' }}>
              {gov.catalog}
            </div>
          </div>

          {/* Schemas */}
          <div style={{
            padding: '12px 16px', background: 'var(--bg-panel)',
            borderRadius: 6, border: '1px solid var(--border-dim)',
          }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 6 }}>
              SCHEMAS
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {gov.schemas.map(s => (
                <span key={s} style={{
                  display: 'inline-block', padding: '2px 8px',
                  borderRadius: 4, fontSize: 11, fontFamily: 'monospace',
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  color: 'var(--text-secondary)', fontWeight: 500,
                }}>
                  {s}
                </span>
              ))}
            </div>
          </div>

          {/* Access Control */}
          <div style={{
            padding: '12px 16px', background: 'var(--bg-panel)',
            borderRadius: 6, border: '1px solid var(--border-dim)',
          }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 6 }}>
              ACCESS CONTROL
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {gov.access_control}
            </div>
          </div>

          {/* Audit Log */}
          <div style={{
            padding: '12px 16px', background: 'var(--bg-panel)',
            borderRadius: 6, border: '1px solid var(--border-dim)',
          }}>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: 6 }}>
              AUDIT &amp; LINEAGE
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {gov.audit_log}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
