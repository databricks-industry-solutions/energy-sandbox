import { useState } from 'react'
import OverviewTab      from './components/OverviewTab'
import ThreeDViewerTab  from './components/ThreeDViewerTab'
import EconomicsTab     from './components/EconomicsTab'
import GovernanceTab    from './components/GovernanceTab'
import GenieTab         from './components/GenieTab'
import LogViewerTab     from './components/LogViewerTab'
import DataFlowTab      from './components/DataFlowTab'
import GenieSidebar     from './components/GenieSidebar'
import SupervisorTab    from './components/SupervisorTab'

const TABS = [
  { id: 'overview',   label: '🛰️ Overview' },
  { id: '3d',         label: '🌐 3D Viewer' },
  { id: 'viewer',     label: '📊 Log Viewer' },
  { id: 'economics',  label: '💰 Economics' },
  { id: 'governance', label: '🛡️ Governance' },
  { id: 'genie',      label: '✨ Genie' },
  { id: 'supervisor', label: '🧠 Subsurface Supervisor' },
  { id: 'dataflow',   label: '🔀 Data Flow' },
]

export default function App() {
  const [active, setActive]         = useState('overview')
  const [activeWell, setActiveWell] = useState('BAKER-001')

  const openWell = (wellId: string, tab: string = '3d') => {
    setActiveWell(wellId)
    setActive(tab)
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <header style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        display: 'flex', alignItems: 'center', gap: 16, height: 54,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🛢️</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              Subsurface Intelligence
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              OSDU · Unity Catalog · Genie · Foundation Models · Vector Search
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
              fontWeight: active === t.id ? 600 : 400, cursor: 'pointer',
            }}>
              {t.label}
            </button>
          ))}
        </nav>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'var(--green-dim)', color: 'var(--green)',
            border: '1px solid var(--green)', borderRadius: 20,
            padding: '3px 10px', fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: 4, background: 'var(--green)',
              animation: 'hdr-pulse 1.4s infinite',
            }} />
            LIVE · ADME
          </span>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: 'var(--bg-panel)', border: '1px solid var(--border)',
            borderRadius: 6, padding: '3px 10px',
          }}>
            <span style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>active well</span>
            <span style={{ color: 'var(--blue)', fontWeight: 700, fontFamily: 'monospace', fontSize: 11 }}>
              {activeWell}
            </span>
          </div>
          <span style={{
            background: 'var(--bg-panel)', color: 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: 20,
            padding: '2px 10px', fontSize: 10, fontFamily: 'monospace',
          }}>
            adme_client_demo
          </span>
          <style>{`@keyframes hdr-pulse { 0%,100% { opacity:.4 } 50% { opacity:1 } }`}</style>
        </div>
      </header>

      <main style={{ padding: '20px 24px', maxWidth: 1800, margin: '0 auto' }}>
        {active === 'overview'   && <OverviewTab     onOpenWell={openWell} />}
        {active === '3d'         && <ThreeDViewerTab wellId={activeWell} onWellChange={setActiveWell} />}
        {active === 'viewer'     && <LogViewerTab    wellId={activeWell} onWellChange={setActiveWell} />}
        {active === 'economics'  && <EconomicsTab    wellId={activeWell} />}
        {active === 'governance' && <GovernanceTab />}
        {active === 'genie'      && <GenieTab />}
        {active === 'supervisor' && <SupervisorTab />}
        {active === 'dataflow'   && <DataFlowTab />}
      </main>
      <GenieSidebar />
    </div>
  )
}
