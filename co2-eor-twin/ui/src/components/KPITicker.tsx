import type { KPI } from '../App';

interface Props {
  kpis: KPI[];
  loading: boolean;
}

/** Default KPI placeholder set shown before backend responds. */
const PLACEHOLDER_KPIS: KPI[] = [
  { label: 'Oil Production', value: '--', unit: 'bbl/d', color: 'accent' },
  { label: 'Gas Production', value: '--', unit: 'Mcf/d', color: 'accent' },
  { label: 'CO\u2082 Injected', value: '--', unit: 'Mcf/d', color: 'co2' },
  { label: 'Incremental Oil', value: '--', unit: 'bbl/d', color: 'success' },
  { label: 'CO\u2082 Stored', value: '--', unit: 'tCO\u2082', color: 'co2' },
  { label: 'Carbon Intensity', value: '--', unit: 'kgCO\u2082/bbl', color: 'blue' },
  { label: 'Compliance', value: '--', unit: '%', color: 'success' },
  { label: 'Revenue', value: '--', unit: '$/d', color: 'warning' },
  { label: 'Netback', value: '--', unit: '$/bbl', color: 'warning' },
  { label: 'CO\u2082 Cost', value: '--', unit: '$/boe', color: 'blue' },
];

/**
 * Group divider indices — insert a thin vertical rule between categories.
 * Groups: Production (0-3) | Environmental (4-6) | Economics (7-9)
 */
const DIVIDER_AFTER = new Set([3, 6]);

function formatValue(val: string | number): string {
  if (typeof val === 'number') {
    if (Math.abs(val) >= 1_000_000) return (val / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(val) >= 1_000) return (val / 1_000).toFixed(1) + 'k';
    return val.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }
  return val;
}

export default function KPITicker({ kpis, loading }: Props) {
  const items = kpis.length > 0 ? kpis : PLACEHOLDER_KPIS;

  return (
    <div className="kpi-ticker">
      {loading && kpis.length === 0 && (
        <div style={{ marginRight: 8 }}>
          <div className="loading-spinner" />
        </div>
      )}
      {items.map((kpi, idx) => (
        <div key={kpi.label + idx} style={{ display: 'contents' }}>
          <div className="kpi-card">
            <span className="kpi-label">{kpi.label}</span>
            <span className={`kpi-value ${kpi.color ?? ''}`}>
              {formatValue(kpi.value)}
            </span>
            <span className="kpi-unit">{kpi.unit}</span>
          </div>
          {DIVIDER_AFTER.has(idx) && <div className="kpi-divider" />}
        </div>
      ))}
    </div>
  );
}
