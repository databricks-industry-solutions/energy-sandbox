import { useState } from 'react'
import WellsTab      from './components/WellsTab'
import LogViewerTab  from './components/LogViewerTab'
import QCTab         from './components/QCTab'
import RecipesTab    from './components/RecipesTab'
import AdvisorTab    from './components/AdvisorTab'
import DataFlowTab   from './components/DataFlowTab'

const TABS = [
  { id: 'wells',    label: '🛢️ Wells' },
  { id: 'viewer',   label: '📊 Log Viewer' },
  { id: 'qc',       label: '🔍 QC & Corrections' },
  { id: 'recipes',  label: '⚙️ Recipes' },
  { id: 'advisor',  label: '🤖 Petrophysics AI' },
  { id: 'dataflow', label: '🔀 Data & AI Flow' },
]

export default function App() {
  const [active, setActive]     = useState('wells')
  const [activeWell, setActiveWell] = useState('BAKER-001')

  const openWell = (wellId: string, tab: string = 'viewer') => {
    setActiveWell(wellId)
    setActive(tab)
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Header */}
      <header style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        display: 'flex', alignItems: 'center', gap: 16, height: 54,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🪨</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              LAS Viewer
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Powered by Databricks · Lakebase · Unity Catalog
            </div>
          </div>
        </div>

        <nav style={{ display: 'flex', gap: 2, marginLeft: 12 }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setActive(t.id)} style={{
              background: active === t.id ? 'var(--bg-panel)' : 'transparent',
              color: active === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              border: active === t.id ? '1px solid var(--border)' : '1px solid transparent',
              borderRadius: 6, padding: '4px 13px', fontSize: 12,
              fontWeight: active === t.id ? 600 : 400,
            }}>
              {t.label}
            </button>
          ))}
        </nav>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Active:&nbsp;
            <span style={{ color: 'var(--blue)', fontWeight: 600, fontFamily: 'monospace' }}>
              {activeWell}
            </span>
          </div>
          <span style={{
            background: 'var(--green-dim)', color: 'var(--green)',
            border: '1px solid var(--green)', borderRadius: 20,
            padding: '2px 10px', fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
          }}>
            ◈ las_gold · Delta Lake
          </span>
        </div>
      </header>

      <main style={{ padding: '20px 24px', maxWidth: 1800, margin: '0 auto' }}>
        {active === 'wells'    && <WellsTab    activeWell={activeWell} onOpenWell={openWell} />}
        {active === 'viewer'   && <LogViewerTab wellId={activeWell} onWellChange={setActiveWell} />}
        {active === 'qc'       && <QCTab       wellId={activeWell} onWellChange={setActiveWell} />}
        {active === 'recipes'  && <RecipesTab   wellId={activeWell} />}
        {active === 'advisor'  && <AdvisorTab   wellId={activeWell} onWellChange={setActiveWell} />}
        {active === 'dataflow' && <DataFlowTab />}
      </main>
    </div>
  )
}
