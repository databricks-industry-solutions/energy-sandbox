import { useState, useCallback } from 'react'
import ScenariosTab from './components/ScenariosTab'
import ReservoirTab from './components/ReservoirTab'
import WellResultsTab from './components/WellResultsTab'
import EconomicsTab from './components/EconomicsTab'
import AgentTab from './components/AgentTab'
import DataFlowTab from './components/DataFlowTab'

const TABS = [
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'reservoir', label: '3D Reservoir' },
  { id: 'wells',     label: 'Well Results' },
  { id: 'economics', label: 'Economics' },
  { id: 'agent',     label: 'Agent' },
  { id: 'dataflow',  label: 'Data & AI Flow' },
]

export default function App() {
  const [active, setActive] = useState('scenarios')
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [activeScenarioId, setActiveScenarioId] = useState<number | null>(null)

  const handleRunStarted = useCallback((runId: string, scenarioId: number) => {
    setActiveRunId(runId)
    setActiveScenarioId(scenarioId)
    setActive('reservoir')
  }, [])

  const statusColor = activeRunId ? 'var(--green)' : 'var(--text-muted)'
  const statusText = activeRunId ? activeRunId : 'None'

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
          <span style={{ fontSize: 22 }}>&#9906;</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              Reservoir Simulator
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Powered by Databricks · OPM Flow · Norne Benchmark
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
            Run: 
            <span style={{ color: statusColor, fontWeight: 600, fontFamily: 'monospace' }}>
              {statusText}
            </span>
          </div>
          <span className="badge badge-blue">OPM Flow</span>
          <span className="badge badge-green">Norne Field</span>
        </div>
      </header>

      <main style={{ padding: '20px 24px', maxWidth: 1800, margin: '0 auto' }}>
        {active === 'scenarios' && (
          <ScenariosTab
            onRunStarted={handleRunStarted}
            activeScenarioId={activeScenarioId}
            onScenarioSelect={setActiveScenarioId}
          />
        )}
        {active === 'reservoir' && (
          <ReservoirTab
            activeRunId={activeRunId}
            onRunSelect={setActiveRunId}
          />
        )}
        {active === 'wells' && (
          <WellResultsTab activeRunId={activeRunId} onRunSelect={setActiveRunId} />
        )}
        {active === 'economics' && (
          <EconomicsTab activeRunId={activeRunId} onRunSelect={setActiveRunId} />
        )}
        {active === 'agent' && (
          <AgentTab activeRunId={activeRunId} activeScenarioId={activeScenarioId} />
        )}
        {active === 'dataflow' && <DataFlowTab />}
      </main>
    </div>
  )
}
