import { useEffect, useMemo, useState } from 'react'
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps'
import statesTopo from 'us-atlas/states-10m.json'

interface OverviewProps {
  onOpenWell: (id: string, tab?: string) => void
}

interface Well {
  well_id: string
  well_name: string
  basin?: string
  status?: string
  quality_score: number
  lat: number | null
  lon: number | null
  total_depth_ft: number
  anomaly_count: number
  critical_count: number
}

interface EconSummary {
  wti_spot: number
  total_npv_live_musd: number
  total_capex_musd: number
  total_co2_tonnes_yr: number
  wells: { npv10_live_musd: number }[]
}

interface Alert { well_id: string; well_name: string; severity: 'critical'|'warn'|'info'; kind: string; msg: string; ts?: string|null }
interface LastDecision { verdict?: string; well_id?: string; well_name?: string; basin?: string; ts?: number; total_ms?: number; text?: string; empty?: boolean }

export default function OverviewTab({ onOpenWell }: OverviewProps) {
  const [wells, setWells] = useState<Well[]>([])
  const [econ,  setEcon]  = useState<EconSummary | null>(null)
  const [prices, setPrices] = useState<{ date: string; price: number }[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [lastDecision, setLastDecision] = useState<LastDecision | null>(null)

  useEffect(() => {
    ;(async () => {
      const [w, e, p, a, ld] = await Promise.all([
        fetch('/api/wells').then(r => r.json()),
        fetch('/api/economics/summary').then(r => r.json()),
        fetch('/api/economics/prices').then(r => r.json()),
        fetch('/api/wells/alerts').then(r => r.json()).catch(() => ({ alerts: [] })),
        fetch('/api/supervisor/last_decision').then(r => r.json()).catch(() => ({ empty: true })),
      ])
      setWells(w)
      setEcon(e)
      setPrices(p)
      setAlerts(a.alerts || [])
      setLastDecision(ld)
    })()
  }, [])

  // Operator's fleet = the LAS wells in North America. ADME is the global
  // field/analog catalog the Supervisor pulls from.
  const operatorWells = useMemo(() => wells.filter(w => !w.well_id.startsWith('OSDU-')), [wells])
  const gold = operatorWells.filter(w => w.status === 'gold').length
  const corrected = operatorWells.filter(w => w.status === 'corrected').length
  const critical = operatorWells.reduce((s, w) => s + (w.critical_count || 0), 0)
  const avgQ = operatorWells.length ? operatorWells.reduce((s, w) => s + (w.quality_score || 0), 0) / operatorWells.length : 0
  const admeAnalogs = wells.filter(w => w.well_id.startsWith('OSDU-')).length

  const priceWindow = prices.slice(-120)

  const withCoord = operatorWells.filter(w => w.lat != null && w.lon != null) as Required<Well>[]

  // Auto-fit US states map to operator fleet bounds (geoAlbersUsa projection).
  const mapCenter = useMemo<[number, number]>(() => {
    if (withCoord.length === 0) return [-98, 38]
    const cLat = withCoord.reduce((s, w) => s + w.lat!, 0) / withCoord.length
    const cLon = withCoord.reduce((s, w) => s + w.lon!, 0) / withCoord.length
    return [cLon, cLat]
  }, [withCoord])
  const mapZoom = useMemo(() => {
    if (withCoord.length < 2) return 3.5
    const lats = withCoord.map(w => w.lat!)
    const lons = withCoord.map(w => w.lon!)
    const spanLon = Math.max(...lons) - Math.min(...lons)
    const spanLat = Math.max(...lats) - Math.min(...lats)
    const span = Math.max(spanLon, spanLat, 4)
    return Math.min(8, Math.max(2, 40 / span))
  }, [withCoord])

  const criticalCount = alerts.filter(a => a.severity === 'critical').length
  const verdictColor: Record<string, string> = {
    DRILL: '#27AE60', HOLD: '#F39C12', 'DE-SCOPE': '#CD6116', ABANDON: '#E74C3C', REVIEW: '#4dabf7',
  }

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
        <Kpi label="Operator fleet" value={`${operatorWells.length}`} sub={`+ ${admeAnalogs} ADME analogs`} color="var(--blue)" />
        <Kpi label="Gold wells" value={`${gold}`} sub={`${corrected} corrected`} color="var(--gold)" />
        <Kpi label="WTI spot" value={econ ? `$${econ.wti_spot.toFixed(2)}` : '…'} sub="FRED live" color="var(--green)" />
        <Kpi label="Portfolio NPV₁₀" value={econ ? `$${econ.total_npv_live_musd.toFixed(0)}M` : '…'} sub={econ ? `CAPEX $${econ.total_capex_musd.toFixed(0)}M` : ''} color="var(--teal)" />
        <Kpi label="Critical alerts" value={`${critical}`} sub={critical > 0 ? '⚠ action needed' : 'all clear'} color={critical > 0 ? 'var(--red)' : 'var(--green)'} />
        <Kpi label="Avg Quality" value={`${avgQ.toFixed(0)}`} sub="out of 100 · QC score" color="var(--purple)" />
      </div>

      {/* Last AI decision + Live alerts ticker */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Panel
          title="Last AI decision"
          subtitle={lastDecision && !lastDecision.empty
            ? `Subsurface Supervisor · ${lastDecision.well_id} (${lastDecision.basin || '—'})`
            : 'Subsurface Supervisor · no runs yet'}
        >
          {(!lastDecision || lastDecision.empty) ? (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
              Run the Subsurface Supervisor to populate this card. The most recent verdict appears here.
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              <div style={{
                padding: '10px 18px', borderRadius: 8,
                background: verdictColor[lastDecision.verdict || 'REVIEW'] || verdictColor.REVIEW,
                color: 'white', fontSize: 22, fontWeight: 800, letterSpacing: '0.04em',
                boxShadow: `0 4px 18px ${verdictColor[lastDecision.verdict || 'REVIEW']}55`,
                flexShrink: 0,
              }}>{lastDecision.verdict || 'REVIEW'}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 600 }}>
                  {lastDecision.well_name || lastDecision.well_id}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  synthesised in {lastDecision.total_ms}ms · click below to re-run
                </div>
                <div style={{
                  fontSize: 11, color: 'var(--text-secondary)', marginTop: 6,
                  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  overflow: 'hidden', lineHeight: 1.5,
                }}>{(lastDecision.text || '').split('\n')[0]}</div>
              </div>
            </div>
          )}
        </Panel>

        <Panel
          title="Live drilling alerts"
          subtitle={`${alerts.length} active · ${criticalCount} critical · from las.drilling_operations`}
        >
          {alerts.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
              All wells nominal · no NPT, BHA, supply chain, or incident flags.
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 5, maxHeight: 130, overflowY: 'auto' }}>
              {alerts.slice(0, 6).map((a, i) => {
                const col = a.severity === 'critical' ? 'var(--red)' :
                            a.severity === 'warn'     ? 'var(--amber)' : 'var(--text-muted)'
                return (
                  <div key={i} onClick={() => onOpenWell(a.well_id, 'viewer')} style={{
                    display: 'grid', gridTemplateColumns: '12px 70px 1fr', gap: 8, alignItems: 'center',
                    padding: '5px 8px', borderRadius: 4,
                    background: 'var(--bg-panel)', border: '1px solid var(--border)',
                    cursor: 'pointer', fontSize: 11,
                  }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: 4, background: col,
                      animation: a.severity === 'critical' ? 'genie-pulse 1.1s infinite' : 'none',
                    }} />
                    <span style={{ color: col, fontFamily: 'monospace', fontSize: 10, fontWeight: 600 }}>{a.kind}</span>
                    <span style={{ color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <b style={{ color: 'var(--blue)', fontFamily: 'monospace' }}>{a.well_id}</b> · {a.msg}
                    </span>
                  </div>
                )
              })}
              <style>{`@keyframes genie-pulse { 0%,100% { opacity:.35 } 50% { opacity:1 } }`}</style>
            </div>
          )}
        </Panel>
      </div>

      {/* Map + WTI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        <Panel title="Operator fleet locations" subtitle={`${withCoord.length} wells in NA · green=gold, amber=corrected, red=critical alerts · click a well to open Log Viewer`}>
          <div style={{
            background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-dim)',
            position: 'relative', overflow: 'hidden',
          }}>
            <ComposableMap projection="geoAlbersUsa" projectionConfig={{ scale: 1000 }} width={900} height={420} style={{ width: '100%', height: 'auto', display: 'block' }}>
              <ZoomableGroup center={mapCenter} zoom={mapZoom} minZoom={1} maxZoom={12}>
                <Geographies geography={statesTopo}>
                  {({ geographies }) =>
                    geographies.map(geo => (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        style={{
                          default: { fill: '#1a1f2b', stroke: '#3a4254', strokeWidth: 0.5, outline: 'none' },
                          hover:   { fill: '#222a3a', stroke: '#4a5468', strokeWidth: 0.5, outline: 'none' },
                          pressed: { fill: '#222a3a', stroke: '#4a5468', strokeWidth: 0.5, outline: 'none' },
                        }}
                      />
                    ))
                  }
                </Geographies>
                {withCoord.map(w => {
                  const color = w.critical_count > 0 ? '#E74C3C' : w.status === 'gold' ? '#27AE60' : '#F39C12'
                  return (
                    <Marker key={w.well_id} coordinates={[w.lon!, w.lat!]} onClick={() => onOpenWell(w.well_id, 'viewer')} style={{ default: { cursor: 'pointer' } }}>
                      <circle r={9} fill={color} opacity={0.18} />
                      <circle r={5} fill={color} opacity={0.45} />
                      <circle r={2.8} fill={color}>
                        <animate attributeName="opacity" values="0.6;1;0.6" dur="2s" repeatCount="indefinite" />
                      </circle>
                      <text x={9} y={3} fontSize={7} fill="var(--text-primary)" fontFamily="monospace" style={{ pointerEvents: 'none' }}>
                        {w.well_id}
                      </text>
                    </Marker>
                  )
                })}
              </ZoomableGroup>
            </ComposableMap>
            <div style={{
              position: 'absolute', top: 10, right: 10, fontSize: 10, fontFamily: 'monospace',
              background: 'rgba(13,17,23,0.85)', border: '1px solid var(--border-dim)', borderRadius: 4,
              padding: '6px 9px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 3,
            }}>
              <div><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: '#27AE60', marginRight: 6 }} />gold</div>
              <div><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: '#F39C12', marginRight: 6 }} />corrected</div>
              <div><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: '#E74C3C', marginRight: 6 }} />critical</div>
              <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid var(--border-dim)' }}>scroll to zoom · drag to pan</div>
            </div>
          </div>
        </Panel>

        <Panel title="WTI · last 120 days" subtitle="FRED DCOILWTICO (fallback if egress blocked)">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={priceWindow}>
              <defs>
                <linearGradient id="wtiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="var(--gold)" stopOpacity="0.6" />
                  <stop offset="1" stopColor="var(--gold)" stopOpacity="0" />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)' }} width={40} />
              <Tooltip contentStyle={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', fontSize: 11 }} />
              <Area type="monotone" dataKey="price" stroke="var(--gold)" strokeWidth={2} fill="url(#wtiGrad)" />
            </AreaChart>
          </ResponsiveContainer>
          {econ && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
              Spot <b style={{ color: 'var(--gold)' }}>${econ.wti_spot.toFixed(2)}</b> · portfolio re-rated to <b style={{ color: 'var(--green)' }}>${econ.total_npv_live_musd.toFixed(0)}M</b>
            </div>
          )}
        </Panel>
      </div>

      {/* Ingest pipeline */}
      <Panel title="OSDU Ingest Pipeline" subtitle="Medallion flow: live OSDU → Bronze → Silver → Gold → Serving">
        <svg width="100%" viewBox="0 0 1280 210" style={{ display: 'block' }}>
          <defs>
            <linearGradient id="flow" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#00E5FF" stopOpacity="0" />
              <stop offset="0.5" stopColor="#00E5FF" stopOpacity="1" />
              <stop offset="1" stopColor="#00E5FF" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[
            { x: 20,   label: 'ADME / OSDU',   sub: 'opendes partition',         color: '#27AE60', badge: 'SOURCE' },
            { x: 280,  label: 'Bronze',        sub: 'bronze_wellbore · raw',     color: '#CD6116', badge: 'BRONZE' },
            { x: 540,  label: 'Silver',        sub: 'silver_wellbore · cleaned', color: '#8E9AAF', badge: 'SILVER' },
            { x: 800,  label: 'Gold',          sub: 'wellbore_search_source',    color: '#F39C12', badge: 'GOLD' },
            { x: 1060, label: 'Vector Search', sub: 'subsurface-vs · gte-large', color: '#00E5FF', badge: 'SERVING' },
          ].map((n, i, arr) => (
            <g key={n.label}>
              {i < arr.length - 1 && (
                <>
                  <line x1={n.x + 200} y1="70" x2={arr[i+1].x} y2="70" stroke="#2a2e3a" strokeWidth="1" strokeDasharray="4 3" />
                  <circle cx={n.x + 200} cy="70" r="2.5" fill="#00E5FF">
                    <animate attributeName="cx" values={`${n.x + 200};${arr[i+1].x}`} dur="2.5s" repeatCount="indefinite" begin={`${i * 0.5}s`} />
                    <animate attributeName="opacity" values="0;1;0" dur="2.5s" repeatCount="indefinite" begin={`${i * 0.5}s`} />
                  </circle>
                </>
              )}
              <rect x={n.x} y="20" width="200" height="100" rx="6" fill="var(--bg-panel)" stroke={n.color} strokeWidth="1.5" />
              <text x={n.x + 100} y="48" textAnchor="middle" fill={n.color} fontSize="11" fontWeight="700" fontFamily="monospace" letterSpacing="1">{n.badge}</text>
              <text x={n.x + 100} y="76" textAnchor="middle" fill="var(--text-primary)" fontSize="14" fontWeight="600">{n.label}</text>
              <text x={n.x + 100} y="100" textAnchor="middle" fill="var(--text-muted)" fontSize="10" fontFamily="monospace">{n.sub}</text>
            </g>
          ))}
          <text x="640" y="170" textAnchor="middle" fill="var(--text-muted)" fontSize="12" fontStyle="italic">
            Auto Loader → Delta Live Tables → Vector Search Δ-Sync · governed by Unity Catalog row filters + column masks
          </text>
        </svg>
      </Panel>

      {/* Well list with drill-in */}
      <Panel title="Fleet status" subtitle="Click a row to open the Log Viewer · operator wells in NA + ADME analog wells from the global OSDU catalog">
        <div style={{ overflow: 'auto', maxHeight: 420 }}>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
              <tr>
                {['Well', 'Name', 'Basin', 'Status', 'Quality', 'TD (ft)', 'Anomalies', 'Critical', 'Source'].map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left', borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {wells.map(w => {
                const isOsdu = w.well_id.startsWith('OSDU-')
                return (
                  <tr key={w.well_id} onClick={() => onOpenWell(w.well_id, 'viewer')}
                      style={{ cursor: 'pointer', borderBottom: '1px solid var(--border-dim)' }}>
                    <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: 'var(--blue)' }}>{w.well_id}</td>
                    <td style={{ padding: '7px 10px' }}>{w.well_name}</td>
                    <td style={{ padding: '7px 10px' }}>{w.basin || '—'}</td>
                    <td style={{ padding: '7px 10px' }}>
                      <Pill value={w.status} />
                    </td>
                    <td style={{ padding: '7px 10px', color: w.quality_score >= 80 ? 'var(--green)' : w.quality_score >= 60 ? 'var(--amber)' : 'var(--red)' }}>
                      {w.quality_score}
                    </td>
                    <td style={{ padding: '7px 10px', fontFamily: 'monospace' }}>{w.total_depth_ft?.toLocaleString()}</td>
                    <td style={{ padding: '7px 10px' }}>{w.anomaly_count}</td>
                    <td style={{ padding: '7px 10px', color: w.critical_count > 0 ? 'var(--red)' : 'var(--text-muted)', fontWeight: w.critical_count > 0 ? 600 : 400 }}>
                      {w.critical_count}
                    </td>
                    <td style={{ padding: '7px 10px' }}>
                      <span style={{
                        fontSize: 10, padding: '2px 7px', borderRadius: 10,
                        background: isOsdu ? 'var(--blue-dim)' : 'var(--bg-panel)',
                        color: isOsdu ? 'var(--blue)' : 'var(--text-muted)',
                      }}>{isOsdu ? 'ADME live' : 'Operator'}</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

function Kpi({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 14px',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>
    </div>
  )
}

function Pill({ value }: { value?: string }) {
  const color = value === 'gold' ? 'var(--green)' : value === 'corrected' ? 'var(--amber)' : value === 'raw' ? 'var(--red)' : 'var(--text-muted)'
  const bg = value === 'gold' ? 'var(--green-dim)' : value === 'corrected' ? 'var(--amber-dim)' : value === 'raw' ? 'var(--red-dim)' : 'var(--bg-panel)'
  return <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10, background: bg, color }}>{value || '—'}</span>
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>{title}</div>
        {subtitle && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
      </div>
      {children}
    </div>
  )
}
