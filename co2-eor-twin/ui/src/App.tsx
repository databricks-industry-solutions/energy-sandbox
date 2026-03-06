import { useState, useEffect, useCallback } from 'react';
import KPITicker from './components/KPITicker';
import AlertTicker from './components/AlertTicker';
import GeospatialTab from './components/GeospatialTab';
import DataAIFlowTab from './components/DataAIFlowTab';
import InjectionPatternsTab from './components/InjectionPatternsTab';
import CO2BalanceTab from './components/CO2BalanceTab';
import EconomicsTab from './components/EconomicsTab';
import ShiftLogTab from './components/ShiftLogTab';
import DigitalTwinTab from './components/DigitalTwinTab';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface KPI {
  label: string;
  value: string | number;
  unit: string;
  color?: string;
}

export interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical' | 'emergency';
  message: string;
  timestamp: string;
  source?: string;
  acknowledged?: boolean;
}

export interface TwinState {
  kpis?: {
    production?: {
      totalOil: number;
      totalGas: number;
      totalWater: number;
      co2Injected: number;
      co2Recycled: number;
      co2Purchased: number;
      co2Utilization: number;
      incrementalOil: number;
      gor: number;
      waterCut: number;
      uptime: number;
    };
    economics?: {
      revenue: number;
      opex: number;
      co2Cost: number;
      netback: number;
      incrementalNetback: number;
      co2CostPerBoe: number;
      breakeven: number;
    };
    environmental?: {
      co2Stored: number;
      co2Emitted: number;
      flaring: number;
      carbonIntensity: number;
      methaneLeaks: number;
      complianceScore: number;
    };
  };
  alerts?: Alert[];
  [key: string]: unknown;
}

/* ------------------------------------------------------------------ */
/*  Tabs                                                               */
/* ------------------------------------------------------------------ */

const TABS = [
  { id: 'field', label: 'Field Overview' },
  { id: 'dataflow', label: 'Data & AI Flow' },
  { id: 'injection', label: 'Injection Patterns' },
  { id: 'co2balance', label: 'CO\u2082 Balance' },
  { id: 'economics', label: 'Economics' },
  { id: 'shift', label: 'Shift Log' },
  { id: 'twin', label: 'Digital Twin' },
] as const;

type TabId = (typeof TABS)[number]['id'];

/* ------------------------------------------------------------------ */
/*  App                                                                */
/* ------------------------------------------------------------------ */

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('field');
  const [twinState, setTwinState] = useState<TwinState | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [shiftLabel, setShiftLabel] = useState<string>('');
  const [loading, setLoading] = useState(true);

  /* Fetch twin state on mount (and periodically) */
  const fetchTwinState = useCallback(async () => {
    try {
      const res = await fetch('/api/twin/state');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TwinState = await res.json();
      setTwinState(data);
      if (data.alerts) setAlerts(data.alerts);
    } catch {
      /* In dev without backend, silently degrade */
      console.warn('Failed to fetch twin state — backend may not be running');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch('/api/twin/alerts');
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setAlerts(data);
      else if (data.alerts) setAlerts(data.alerts);
    } catch {
      /* silent */
    }
  }, []);

  const fetchShift = useCallback(async () => {
    try {
      const res = await fetch('/api/shift/current');
      if (!res.ok) return;
      const data = await res.json();
      setShiftLabel(data.label || data.shift || '');
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    fetchTwinState();
    fetchAlerts();
    fetchShift();

    const interval = setInterval(() => {
      fetchTwinState();
      fetchAlerts();
    }, 15_000);

    return () => clearInterval(interval);
  }, [fetchTwinState, fetchAlerts, fetchShift]);

  /* Build KPI list from state */
  const kpis: KPI[] = [];
  if (twinState?.kpis) {
    const { production: p, economics: e, environmental: env } = twinState.kpis;
    if (p) {
      kpis.push(
        { label: 'Oil Production', value: p.totalOil, unit: 'bbl/d', color: 'accent' },
        { label: 'Gas Production', value: p.totalGas, unit: 'Mcf/d', color: 'accent' },
        { label: 'CO\u2082 Injected', value: p.co2Injected, unit: 'Mcf/d', color: 'co2' },
        { label: 'Incremental Oil', value: p.incrementalOil, unit: 'bbl/d', color: 'success' },
      );
    }
    if (env) {
      kpis.push(
        { label: 'CO\u2082 Stored', value: env.co2Stored, unit: 'tCO\u2082/d', color: 'co2' },
        { label: 'Carbon Intensity', value: env.carbonIntensity, unit: 'kgCO\u2082/boe', color: 'blue' },
        { label: 'Compliance', value: env.complianceScore, unit: '%', color: 'success' },
      );
    }
    if (e) {
      kpis.push(
        { label: 'Revenue', value: Math.round(e.revenue), unit: '$/d', color: 'warning' },
        { label: 'Netback', value: e.netback, unit: '$/boe', color: 'warning' },
        { label: 'CO\u2082 Cost', value: e.co2CostPerBoe, unit: '$/boe', color: 'blue' },
      );
    }
  }

  /* Active alerts count */
  const activeAlertCount = alerts.filter((a) => !a.acknowledged).length;

  /* ---------------------------------------------------------------- */
  /*  Render tab content                                               */
  /* ---------------------------------------------------------------- */
  function renderTab() {
    switch (activeTab) {
      case 'field':
        return <GeospatialTab />;
      case 'dataflow':
        return <DataAIFlowTab />;
      case 'injection':
        return <InjectionPatternsTab />;
      case 'co2balance':
        return <CO2BalanceTab />;
      case 'economics':
        return <EconomicsTab />;
      case 'shift':
        return <ShiftLogTab />;
      case 'twin':
        return <DigitalTwinTab />;
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
          <div className="header-logo">CO</div>
          <span className="header-title">
            CO<sub>2</sub>-EOR Digital Twin
          </span>
        </div>

        <span className="env-badge">DEV</span>

        <div className="header-spacer" />

        {shiftLabel && (
          <div className="header-shift">
            <span className="shift-dot" />
            <span>{shiftLabel}</span>
          </div>
        )}

        <button
          className="header-alerts"
          title="Active alerts"
          onClick={() => setActiveTab('field')}
        >
          <span className="alert-icon">&#9888;</span>
          <span>{activeAlertCount}</span>
        </button>
      </header>

      {/* ---------- KPI Ticker ---------- */}
      <KPITicker kpis={kpis} loading={loading} />

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

      {/* ---------- Alert Ticker ---------- */}
      <AlertTicker alerts={alerts} />
    </div>
  );
}
