import { useState, useEffect } from 'react'

interface Well {
  well_id: string; well_name: string; field_name: string; basin: string
  county: string; state: string; status: string; quality_score: number
  total_depth_ft: number; well_type: string; anomaly_count: number
  critical_count: number; spud_date: string; notes: string
}

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  gold:        { label: 'GOLD',        cls: 'badge-gold' },
  corrected:   { label: 'CORRECTED',   cls: 'badge-green' },
  qc_complete: { label: 'QC DONE',     cls: 'badge-blue' },
  raw:         { label: 'RAW',         cls: 'badge-muted' },
}

function QBar({ score }: { score: number }) {
  const color = score >= 80 ? 'var(--green)' : score >= 60 ? 'var(--amber)' : 'var(--red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 80, height: 6, background: 'var(--bg-panel)', borderRadius: 3 }}>
        <div style={{ width: `${score}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 28 }}>{score}</span>
    </div>
  )
}

interface Props { activeWell: string; onOpenWell: (id: string, tab?: string) => void }

export default function WellsTab({ activeWell, onOpenWell }: Props) {
  const [wells, setWells] = useState<Well[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    fetch('/api/wells').then(r => r.json()).then(setWells).finally(() => setLoading(false))
  }, [])

  const shown = wells.filter(w =>
    !filter || w.well_id.toLowerCase().includes(filter.toLowerCase()) ||
    w.well_name.toLowerCase().includes(filter.toLowerCase()) ||
    w.basin?.toLowerCase().includes(filter.toLowerCase()) ||
    w.field_name?.toLowerCase().includes(filter.toLowerCase())
  )

  // Fleet stats
  const goldCount      = wells.filter(w => w.status === 'gold').length
  const correctedCount = wells.filter(w => w.status === 'corrected').length
  const avgQuality     = wells.length ? Math.round(wells.reduce((s, w) => s + w.quality_score, 0) / wells.length) : 0
  const totalAnomaly   = wells.reduce((s, w) => s + w.anomaly_count, 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Fleet KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
        {[
          { label: 'Total Wells',     value: wells.length,    color: 'var(--blue)',   icon: '🛢️' },
          { label: 'Gold Layer',      value: goldCount,       color: 'var(--gold)',   icon: '⭐' },
          { label: 'Corrected',       value: correctedCount,  color: 'var(--green)',  icon: '✓' },
          { label: 'Fleet Quality',   value: avgQuality + '/100', color: avgQuality >= 70 ? 'var(--green)' : 'var(--amber)', icon: '📊' },
          { label: 'Open Anomalies',  value: totalAnomaly,    color: totalAnomaly > 5 ? 'var(--red)' : 'var(--amber)', icon: '⚠️' },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding: '14px 16px' }}>
            <div style={{ fontSize: 22, marginBottom: 6 }}>{k.icon}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: k.color, fontFamily: 'monospace' }}>{k.value}</div>
            <div className="label" style={{ marginTop: 4 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* Search + table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="label">WELL REGISTRY — {shown.length} of {wells.length}</div>
          <input
            value={filter} onChange={e => setFilter(e.target.value)}
            placeholder="Search well ID, name, basin…"
            style={{
              marginLeft: 'auto', background: 'var(--bg-panel)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '5px 12px', color: 'var(--text-primary)', fontSize: 12, width: 240,
              outline: 'none',
            }}
          />
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center' }}><span className="spinner" /></div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-panel)' }}>
                  {['Well ID', 'Well Name', 'Basin / Field', 'Type', 'TD ft', 'Status', 'Quality', 'Anomalies', 'Notes', 'Actions'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.06em', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>
                      {h.toUpperCase()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map((w, i) => {
                  const sc = STATUS_CONFIG[w.status] || { label: w.status, cls: 'badge-muted' }
                  const isActive = w.well_id === activeWell
                  return (
                    <tr key={w.well_id} style={{
                      background: isActive ? 'var(--blue-dim)' : i % 2 === 0 ? 'transparent' : 'var(--bg-panel)',
                      borderBottom: '1px solid var(--border-dim)',
                      cursor: 'pointer',
                    }}
                      onClick={() => onOpenWell(w.well_id, 'viewer')}
                    >
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color: isActive ? 'var(--blue)' : 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                        {w.well_id}
                      </td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{w.well_name}</td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-muted)', whiteSpace: 'nowrap', fontSize: 11 }}>
                        {w.basin}<br /><span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{w.field_name}</span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{w.well_type}</span>
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 12 }}>
                        {w.total_depth_ft?.toLocaleString()}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span className={`badge ${sc.cls}`}>{sc.label}</span>
                      </td>
                      <td style={{ padding: '10px 12px' }}><QBar score={w.quality_score} /></td>
                      <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                        {w.critical_count > 0 ? (
                          <span style={{ color: 'var(--red)', fontWeight: 700, fontSize: 12 }}>
                            🔴 {w.anomaly_count}
                          </span>
                        ) : w.anomaly_count > 0 ? (
                          <span style={{ color: 'var(--amber)', fontSize: 12 }}>⚠️ {w.anomaly_count}</span>
                        ) : (
                          <span style={{ color: 'var(--green)', fontSize: 12 }}>✓</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 11, maxWidth: 220 }}>
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.notes}</div>
                      </td>
                      <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {(['viewer', 'qc', 'advisor'] as const).map(tab => (
                            <button key={tab} onClick={e => { e.stopPropagation(); onOpenWell(w.well_id, tab) }} style={{
                              background: 'var(--bg-panel)', color: 'var(--text-secondary)',
                              border: '1px solid var(--border)', borderRadius: 4,
                              padding: '3px 7px', fontSize: 10,
                            }}>
                              {tab === 'viewer' ? '📊' : tab === 'qc' ? '🔍' : '🤖'}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="card" style={{ padding: '12px 16px', display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="label">PIPELINE STAGES:</span>
        {Object.entries(STATUS_CONFIG).map(([k, v]) => (
          <span key={k} className={`badge ${v.cls}`}>{v.label}</span>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
          Data managed in <span style={{ color: 'var(--blue)' }}>las_raw → las_curated → las_gold</span> catalogs via Unity Catalog
        </span>
      </div>
    </div>
  )
}
