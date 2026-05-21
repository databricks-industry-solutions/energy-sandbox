import { useState } from 'react'

interface NodeDef {
  id: string
  label: string
  sub: string
  x: number; y: number; w: number; h: number
  color: string
  badge?: string
  detail: string[]
}

interface EdgeDef { from: string; to: string; label: string; color?: string; dashed?: boolean }

// ─── Row 1: Sources ────────────────────────────────────────────────────────
const SOURCES: NodeDef[] = [
  {
    id: 'adme', label: 'ADME / OSDU', sub: 'opendes partition',
    x: 60, y: 60, w: 140, h: 60,
    color: '#27AE60', badge: 'SOURCE',
    detail: [
      'Live cloud OSDU (sandbox)',
      'Managed Identity auth',
      'Wellbore, reservoir, rock_and_fluid',
      'Entitlements + legal tags',
    ],
  },
  {
    id: 'fred', label: 'FRED WTI', sub: 'Marketplace · Δ-Sharing',
    x: 60, y: 140, w: 140, h: 60,
    color: '#27AE60', badge: 'SOURCE',
    detail: [
      'Daily WTI crude (DCOILWTICO)',
      'Installed from Databricks Marketplace',
      'Delta Sharing → catalog `fred_wti`',
      'Synthetic fallback if not installed',
    ],
  },
  {
    id: 'wbco2', label: 'World Bank CO₂', sub: 'Marketplace · Δ-Sharing',
    x: 60, y: 220, w: 140, h: 60,
    color: '#27AE60', badge: 'SOURCE',
    detail: [
      'Country-level CO₂ emissions (kt)',
      'Installed from Databricks Marketplace',
      'Delta Sharing → catalog `wb_co2`',
      'Drives ESG widget on Governance tab',
    ],
  },
]

// ─── Row 2: Medallion (Delta + UC) ─────────────────────────────────────────
const MEDALLION: NodeDef[] = [
  {
    id: 'bronze', label: 'Bronze', sub: 'raw ingest',
    x: 290, y: 60, w: 130, h: 60,
    color: '#CD6116', badge: 'BRONZE',
    detail: [
      'bronze_wellbore · _reservoir · _rock_and_fluid',
      'Auto Loader (cloudFiles)',
      'Schema inference + evolution',
      'Raw OSDU record preservation',
    ],
  },
  {
    id: 'silver', label: 'Silver', sub: 'cleaned',
    x: 460, y: 60, w: 130, h: 60,
    color: '#8E9AAF', badge: 'SILVER',
    detail: [
      'silver_wellbore · _reservoir · _rock_and_fluid',
      'Type cast + dedup',
      'Extension properties normalized',
      'Silver payload as structured JSON',
    ],
  },
  {
    id: 'gold', label: 'Gold tables', sub: 'wellbore · reservoir · rock_and_fluid',
    x: 630, y: 60, w: 170, h: 60,
    color: '#F39C12', badge: 'GOLD',
    detail: [
      'wellbore_search_source · gold_reservoir · gold_rock_and_fluid',
      'JSON silver_payload extracted into flat columns',
      'wellbore_search_source has pre-joined text for embedding',
      'Row filter (external_partner_filter) + column masks on lat/lon',
      'Powers Genie NL→SQL and Vector Search index',
    ],
  },
  {
    id: 'gov_tables', label: 'gov_* tables', sub: 'legal + entitlements',
    x: 460, y: 150, w: 130, h: 60,
    color: '#8E9AAF', badge: 'SILVER',
    detail: [
      'gov_legal_tags · _entitlements · _record_acl_mirror',
      'Sync from OSDU entitlement service',
      'Drives the Governance tab',
    ],
  },
  {
    id: 'mkt_catalogs', label: 'Marketplace catalogs', sub: 'fred_wti · wb_co2',
    x: 290, y: 220, w: 150, h: 60,
    color: '#F39C12', badge: 'SHARED',
    detail: [
      'Delta-shared catalogs auto-created on install',
      'Read by SQL warehouse / serving routes',
      'Same UC governance plane (grants apply)',
    ],
  },
]

// ─── Row 3: Serving / AI ───────────────────────────────────────────────────
const SERVING: NodeDef[] = [
  {
    id: 'vs', label: 'Vector Search', sub: 'subsurface-vs',
    x: 290, y: 320, w: 150, h: 60,
    color: '#4dabf7', badge: 'VS',
    detail: [
      'Δ-sync index on wellbore_search_source',
      'databricks-gte-large-en embeddings',
      'Semantic well similarity',
      'Powers similar-wells in 3D viewer + Supervisor analogs',
    ],
  },
  {
    id: 'uc_fn', label: 'UC Functions', sub: 'Python in catalog',
    x: 460, y: 320, w: 150, h: 60,
    color: '#b37feb', badge: 'UC FN',
    detail: [
      'calculate_npv10()',
      'calculate_break_even()',
      'forecast_decline_curve()',
      'EXECUTE granted to app SP',
    ],
  },
  {
    id: 'genie', label: 'Genie Space', sub: 'Drilling Command Center — ADME Live',
    x: 630, y: 320, w: 150, h: 60,
    color: '#00E5FF', badge: 'GENIE',
    detail: [
      'space_id 01f13f7f8e20…',
      'NL → SQL over 4 flat OSDU tables (wellbore_search, gold_reservoir,',
      '  gold_rock_and_fluid, gov_legal_tags) · ADME blocks 15/9 + 34/10',
      'Conversation API (start + msg + poll)',
      'Floating sidebar + called by the Decision Supervisor',
    ],
  },
  {
    id: 'fmapi', label: 'Claude Sonnet 4.5', sub: 'Foundation Model API',
    x: 800, y: 320, w: 160, h: 60,
    color: '#9254de', badge: 'LLM',
    detail: [
      'databricks-claude-sonnet-4-5 endpoint',
      'Tool-calling (OpenAI-compatible)',
      'Supervisor synthesises across all 5 specialists',
      'Trace surfaced inline per call',
    ],
  },
]

// ─── Row 4: App ────────────────────────────────────────────────────────────
const APPL: NodeDef[] = [
  {
    id: 'duckdb', label: 'DuckDB · in-app', sub: 'OLAP cache',
    x: 290, y: 440, w: 140, h: 60,
    color: '#2980B9', badge: 'CACHE',
    detail: [
      'Seeded on startup from OSDU',
      'Postgres-dialect shim over asyncpg API',
      'Sub-ms reads — no warehouse round-trip',
      'No persistence across restart',
    ],
  },
  {
    id: 'lakebase', label: 'Lakebase · PG', sub: 'drilling_cc',
    x: 290, y: 520, w: 140, h: 60,
    color: '#16A085', badge: 'PG',
    detail: [
      'Bound via Databricks Apps `database` resource',
      'Tables: dcc.journal · dcc.alerts',
      'OBO auth — SP gets PG role automatically',
      'Persistent — survives app restarts',
    ],
  },
  {
    id: 'fastapi', label: 'FastAPI', sub: 'Python · uvicorn',
    x: 460, y: 480, w: 150, h: 60,
    color: '#16A085', badge: 'API',
    detail: [
      '/api/subsurface · /economics · /governance',
      '/api/genie · /supervisor (SSE) · /wells · /logs',
      'OBO via X-Forwarded-Access-Token',
      'Deployed as a Databricks App on Azure',
    ],
  },
  {
    id: 'supervisor', label: 'Subsurface Supervisor', sub: 'multi-agent · 5 specialists',
    x: 630, y: 480, w: 170, h: 60,
    color: '#00E5FF', badge: 'MAS',
    detail: [
      'Fans out 5 specialists in parallel via asyncio.gather',
      'analogs (Vector Search) · petrophysics (FM API · Claude 4.5)',
      'economics (UC Functions · NPV / break-even)',
      'regulatory (ADME legal tags) · drilling ops (Lakebase)',
      'Streams results to UI as Server-Sent Events',
      'Synthesises final recommendation with Claude 4.5',
    ],
  },
  {
    id: 'react', label: 'React UI', sub: 'Vite + TypeScript',
    x: 820, y: 480, w: 160, h: 60,
    color: '#73d13d', badge: 'UI',
    detail: [
      'Dark theme, 8 tabs + floating Genie',
      'Recharts + SVG 3D Petrel-style viewer',
      'Real US states map (react-simple-maps) for fleet',
      'Operator journal writes to Lakebase',
      'Built static, served by FastAPI',
    ],
  },
]

// ─── User ──────────────────────────────────────────────────────────────────
const USER: NodeDef = {
  id: 'user', label: 'You', sub: 'SA / petrotech user',
  x: 1010, y: 60, w: 130, h: 60,
  color: '#2C3E50', badge: 'USER',
  detail: [
    'OBO identity forwarded to app',
    'Persona toggle drives UC row/column masks',
    'Launches Subsurface Supervisor + Genie queries',
    'Adds journal entries that persist in Lakebase',
  ],
}

// ─── Edges ─────────────────────────────────────────────────────────────────
const EDGES: EdgeDef[] = [
  { from: 'adme',         to: 'bronze',       label: 'connector',          color: '#27AE60' },
  { from: 'fred',         to: 'mkt_catalogs', label: 'marketplace install', color: '#27AE60' },
  { from: 'wbco2',        to: 'mkt_catalogs', label: 'marketplace install', color: '#27AE60' },
  { from: 'bronze',       to: 'silver',       label: 'DLT clean',          color: '#CD6116' },
  { from: 'silver',       to: 'gold',         label: 'text union',         color: '#8E9AAF' },
  { from: 'silver',       to: 'gov_tables',   label: 'gov split',          color: '#8E9AAF', dashed: true },
  { from: 'gold',         to: 'vs',           label: 'Δ-sync · gte-large', color: '#F39C12' },
  { from: 'mkt_catalogs', to: 'uc_fn',        label: 'price + ESG read',   color: '#F39C12', dashed: true },
  { from: 'genie',        to: 'fastapi',      label: 'Conversation API',   color: '#00E5FF', dashed: true },
  { from: 'duckdb',       to: 'fastapi',      label: 'fast reads',         color: '#2980B9' },
  { from: 'lakebase',     to: 'fastapi',      label: 'ops/journal',        color: '#16A085' },
  { from: 'supervisor',   to: 'vs',           label: 'analogs',            color: '#00E5FF', dashed: true },
  { from: 'supervisor',   to: 'uc_fn',        label: 'NPV / BE',           color: '#00E5FF', dashed: true },
  { from: 'supervisor',   to: 'genie',        label: 'ops NL→SQL',         color: '#00E5FF', dashed: true },
  { from: 'supervisor',   to: 'fmapi',        label: 'synthesise',         color: '#00E5FF', dashed: true },
  { from: 'supervisor',   to: 'gov_tables',   label: 'legal-tag gate',     color: '#00E5FF', dashed: true },
  { from: 'supervisor',   to: 'react',        label: 'SSE stream',         color: '#00E5FF' },
  { from: 'fastapi',      to: 'react',        label: 'JSON REST',          color: '#16A085' },
  { from: 'react',        to: 'user',         label: 'browser',            color: '#73d13d' },
]

const ALL_NODES: NodeDef[] = [...SOURCES, ...MEDALLION, ...SERVING, ...APPL, USER]
const nodeById = (id: string) => ALL_NODES.find(n => n.id === id)

function arrowPath(e: EdgeDef): string {
  const a = nodeById(e.from); const b = nodeById(e.to)
  if (!a || !b) return ''
  const ay = a.y + a.h / 2
  const by = b.y + b.h / 2
  if (Math.abs(ay - by) < 10) {
    return `M${a.x + a.w},${ay} L${b.x},${by}`
  }
  const ax = a.x + a.w / 2
  const bx = b.x + b.w / 2
  if (Math.abs(ax - bx) < 10) {
    return `M${ax},${a.y + a.h} L${bx},${b.y}`
  }
  const midX = (a.x + a.w + b.x) / 2
  return `M${a.x + a.w},${ay} L${midX},${ay} L${midX},${by} L${b.x},${by}`
}

// ─── Component ─────────────────────────────────────────────────────────────
export default function DataFlowTab() {
  const [selected, setSelected] = useState<string | null>(null)
  const sel = selected ? nodeById(selected) : null

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 8, padding: 14,
      }}>
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Subsurface Intelligence · Data & AI Flow</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Click any node to see what it does · orange dashed box = Unity Catalog governance boundary
          </div>
        </div>

        <svg viewBox="0 0 1200 660" style={{ width: '100%', background: 'var(--bg-primary)', borderRadius: 6 }}>
          {/* Layer labels — placed at the top, above the orange UC banner */}
          <text x="12"  y="18" fill="var(--text-muted)" fontSize="10" fontFamily="monospace">SOURCES</text>
          <text x="220" y="18" fill="var(--text-muted)" fontSize="10" fontFamily="monospace">MEDALLION · Delta</text>
          <text x="220" y="306" fill="var(--text-muted)" fontSize="10" fontFamily="monospace">SERVING · AI</text>
          <text x="220" y="426" fill="var(--text-muted)" fontSize="10" fontFamily="monospace">APPLICATION · orchestration</text>

          {/* Unity Catalog governance boundary — banner sits BELOW the row labels */}
          <text x="550" y="42" textAnchor="middle" fill="#F39C12" fontSize="11" fontWeight="600" fontFamily="monospace">
            Unity Catalog · governance · tags · row filters · masks · UC Functions · Vector Search
          </text>
          <rect x="270" y="50" width="560" height="370" fill="none" stroke="#F39C12" strokeWidth="1"
                strokeDasharray="6 4" rx="10" opacity="0.85" />

          <defs>
            <marker id="dfArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 Z" fill="#6b7280" />
            </marker>
          </defs>

          {EDGES.map((e, i) => {
            const d = arrowPath(e)
            const col = e.color || '#6b7280'
            return (
              <g key={`edge-${i}`}>
                <path d={d} fill="none" stroke={col} strokeWidth="1.2"
                      strokeDasharray={e.dashed ? '5 4' : 'none'}
                      markerEnd="url(#dfArrow)" opacity="0.85" />
                <text fontSize="9" fill={col} fontFamily="monospace">
                  <textPath href={`#label-path-${i}`} startOffset="42%" textAnchor="middle">{e.label}</textPath>
                </text>
                <path id={`label-path-${i}`} d={d} fill="none" stroke="none" />
              </g>
            )
          })}

          {ALL_NODES.map(n => (
            <g key={n.id} style={{ cursor: 'pointer' }} onClick={() => setSelected(n.id)}>
              <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6"
                    fill="var(--bg-card)" stroke={selected === n.id ? '#00E5FF' : n.color}
                    strokeWidth={selected === n.id ? 2 : 1.2} />
              {n.badge && (
                <>
                  <rect x={n.x + 8} y={n.y + 6} width="58" height="14" rx="3" fill={n.color} opacity="0.25" />
                  <text x={n.x + 37} y={n.y + 16} textAnchor="middle" fill={n.color} fontSize="9"
                        fontFamily="monospace" fontWeight="700">{n.badge}</text>
                </>
              )}
              <text x={n.x + n.w / 2} y={n.y + 38} textAnchor="middle" fill="var(--text-primary)"
                    fontSize="12" fontWeight="600">{n.label}</text>
              <text x={n.x + n.w / 2} y={n.y + 51} textAnchor="middle" fill="var(--text-muted)"
                    fontSize="9" fontFamily="monospace">{n.sub}</text>
            </g>
          ))}
        </svg>
      </div>

      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 8, padding: 16,
      }}>
        {sel ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{
                padding: '2px 8px', borderRadius: 3, background: sel.color, opacity: 0.85,
                fontSize: 10, fontFamily: 'monospace', fontWeight: 700, color: '#0d0e11',
              }}>{sel.badge}</span>
              <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)' }}>{sel.label}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>· {sel.sub}</div>
              <button onClick={() => setSelected(null)} style={{
                marginLeft: 'auto', background: 'transparent', color: 'var(--text-muted)',
                border: '1px solid var(--border)', borderRadius: 4, padding: '2px 10px',
                fontSize: 11, cursor: 'pointer',
              }}>Back to overview</button>
            </div>
            <ul style={{ fontSize: 12, color: 'var(--text-secondary)', paddingLeft: 20, lineHeight: 1.7 }}>
              {sel.detail.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          </>
        ) : (
          <>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', marginBottom: 10 }}>
              How it works
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              {[
                { h: '1 · Ingest',       c: 'ADME/OSDU lands in Bronze via connector. FRED + WB CO₂ arrive as Delta-Shared catalogs from Marketplace.', col: '#27AE60' },
                { h: '2 · Transform',    c: 'DLT cleans Bronze → Silver. JSON silver_payload is exploded into 3 flat Gold tables (wellbore, reservoir, rock_and_fluid).', col: '#CD6116' },
                { h: '3 · Serve',        c: 'Vector Search indexes wellbore_search_source; UC Functions expose NPV / break-even / decline; Genie owns NL→SQL over the gold OSDU tables.', col: '#4dabf7' },
                { h: '4 · Multi-agent',  c: 'Subsurface Supervisor fans out 5 specialists in parallel (Vector Search · FM API · UC Functions · ADME legal tags · Lakebase drilling ops), streams results via SSE, then Claude 4.5 synthesises a recommendation.', col: '#00E5FF' },
                { h: 'Persistence',      c: 'DuckDB caches reads in-process for sub-ms responses. Lakebase Postgres holds the journal + alerts that need to outlive the app.', col: '#16A085' },
                { h: 'Governance',       c: 'Unity Catalog row filters + column masks gate lat/lon and drilling_result by persona group membership — same plane covers Marketplace data.', col: '#F39C12' },
                { h: 'OBO auth',         c: 'Databricks Apps forwards X-Forwarded-Access-Token. SQL, Vector Search, Genie, and Lakebase all run as the user, not the app SP.', col: '#2980B9' },
              ].map(c => (
                <div key={c.h} style={{
                  background: 'var(--bg-panel)', border: '1px solid var(--border)',
                  borderLeft: `3px solid ${c.col}`, borderRadius: 4,
                  padding: '10px 12px',
                }}>
                  <div style={{ fontWeight: 600, fontSize: 12, color: c.col, marginBottom: 4 }}>{c.h}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{c.c}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
