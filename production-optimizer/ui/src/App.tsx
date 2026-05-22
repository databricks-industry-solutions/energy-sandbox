import { useState } from 'react';
import GeospatialTab from './components/GeospatialTab';
import DataAIFlowTab from './components/DataAIFlowTab';
import DigitalTwinTab from './components/DigitalTwinTab';
import ProductionOptimizerTab from './components/ProductionOptimizerTab';
import AskGeniePage from './components/AskGeniePage';
import SupervisorTab from './components/SupervisorTab';

/* ------------------------------------------------------------------ */
/*  Tabs                                                               */
/* ------------------------------------------------------------------ */

const TABS = [
  { id: 'field', label: 'Field Overview' },
  { id: 'twin', label: 'Digital Twin' },
  { id: 'optimizer', label: 'Production Optimizer' },
  { id: 'genie', label: '✨ Ask Genie' },
  { id: 'supervisor', label: '🧠 Supervisor' },
  { id: 'dataflow', label: 'Data & AI Flow' },
] as const;

type TabId = (typeof TABS)[number]['id'];

/* ------------------------------------------------------------------ */
/*  App                                                                */
/* ------------------------------------------------------------------ */

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('field');

  /* ---------------------------------------------------------------- */
  /*  Render tab content                                               */
  /* ---------------------------------------------------------------- */
  function renderTab() {
    switch (activeTab) {
      case 'field':
        return <GeospatialTab />;
      case 'twin':
        return <DigitalTwinTab />;
      case 'optimizer':
        return <ProductionOptimizerTab />;
      case 'genie':
        return <AskGeniePage />;
      case 'supervisor':
        return <SupervisorTab />;
      case 'dataflow':
        return <DataAIFlowTab />;
      default:
        return null;
    }
  }

  /* ---------------------------------------------------------------- */
  /*  JSX                                                              */
  /* ---------------------------------------------------------------- */
  return (
    <div className="app-layout">
      {/* ---------- Header ---------- */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">PO</div>
          <span className="header-title">Production Optimizer</span>
        </div>
        <span className="env-badge">LIVE</span>
        <div className="header-spacer" />
      </header>

      {/* ---------- Tab Bar ---------- */}
      <nav className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* ---------- Active Tab ---------- */}
      <div className="main-content">{renderTab()}</div>
    </div>
  );
}
