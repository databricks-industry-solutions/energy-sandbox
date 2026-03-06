import { useState, useEffect, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types (matching actual API responses)                              */
/* ------------------------------------------------------------------ */

interface CO2Balance {
  totalInjected: number;
  totalPurchased: number;
  totalRecycled: number;
  totalProduced: number;
  netStored: number;
  netStoredTons: number;
  purchasedCost: number;
  recycledSavings: number;
  co2Sources: { name: string; rate: number; cost: number }[];
  storageSummary: string;
}

interface FacilityConstraint {
  facilityId: string;
  facilityName: string;
  type: string;
  utilization: number;
  oilUtilization: number;
  gasUtilization: number;
  waterUtilization: number;
  co2Utilization: number;
  flagged: boolean;
  bottleneck: string | null;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtNum(n: number, d = 0): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: d });
}

function fmtCur(n: number): string {
  return '$' + fmtNum(n, 0);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function CO2BalanceTab() {
  const [balance, setBalance] = useState<CO2Balance | null>(null);
  const [constraints, setConstraints] = useState<FacilityConstraint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [balRes, conRes] = await Promise.all([
        fetch('/api/twin/co2-balance'),
        fetch('/api/twin/facility-constraints'),
      ]);
      if (!balRes.ok) throw new Error(`HTTP ${balRes.status}`);
      if (!conRes.ok) throw new Error(`HTTP ${conRes.status}`);
      setBalance(await balRes.json());
      setConstraints(await conRes.json());
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30_000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (loading) {
    return <div className="tab-loading"><div className="loading-spinner" /><span>Loading CO₂ balance...</span></div>;
  }
  if (error || !balance) {
    return <div className="tab-loading" style={{ color: 'var(--danger)' }}>Error: {error || 'No data'}</div>;
  }

  const totalIn = balance.totalPurchased + balance.totalRecycled;
  const pctPurchased = totalIn > 0 ? (balance.totalPurchased / totalIn) * 100 : 50;
  const pctRecycled = 100 - pctPurchased;

  const emitted = Math.max(0, balance.totalInjected - balance.netStored - balance.totalProduced);
  const totalOut = balance.netStored + balance.totalProduced + emitted;
  const pctStored = totalOut > 0 ? (balance.netStored / totalOut) * 100 : 34;
  const pctProduced = totalOut > 0 ? (balance.totalProduced / totalOut) * 100 : 33;
  const pctEmitted = 100 - pctStored - pctProduced;

  return (
    <div className="tab-scroll-layout">
      {/* Summary cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-card-label">Total CO₂ Injected</div>
          <div className="summary-card-value co2">{fmtNum(balance.totalInjected)}</div>
          <div className="summary-card-unit">Mcf/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Total Purchased</div>
          <div className="summary-card-value purple">{fmtNum(balance.totalPurchased)}</div>
          <div className="summary-card-unit">Mcf/d · {fmtCur(balance.purchasedCost)}/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Total Recycled</div>
          <div className="summary-card-value co2">{fmtNum(balance.totalRecycled)}</div>
          <div className="summary-card-unit">Mcf/d · saves {fmtCur(balance.recycledSavings)}/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Net Stored</div>
          <div className="summary-card-value success">{fmtNum(balance.netStoredTons, 1)}</div>
          <div className="summary-card-unit">tCO₂/d</div>
        </div>
      </div>

      {/* Sankey-style flow */}
      <div className="co2-flow-visual">
        <div className="section-header" style={{ margin: '0 0 12px', border: 'none', padding: 0 }}>CO₂ Mass Balance Flow</div>

        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Sources</div>
        <div className="co2-flow-row">
          <div className="co2-flow-bar" style={{ width: `${pctPurchased}%`, background: '#a855f7', borderRadius: '4px 0 0 4px' }}>
            Purchased {fmtNum(balance.totalPurchased)}
          </div>
          <div className="co2-flow-bar" style={{ width: `${pctRecycled}%`, background: '#06b6d4', borderRadius: '0 4px 4px 0' }}>
            Recycled {fmtNum(balance.totalRecycled)}
          </div>
        </div>

        <div style={{ textAlign: 'center', fontSize: 18, color: 'var(--text-muted)', lineHeight: 1 }}>▼</div>

        <div className="co2-flow-row">
          <div className="co2-flow-bar" style={{ width: '100%', background: 'var(--co2)', borderRadius: 4, height: 36, fontSize: 13 }}>
            Total Injected: {fmtNum(balance.totalInjected)} Mcf/d
          </div>
        </div>

        <div style={{ textAlign: 'center', fontSize: 18, color: 'var(--text-muted)', lineHeight: 1 }}>▼</div>

        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Disposition</div>
        <div className="co2-flow-row">
          <div className="co2-flow-bar" style={{ width: `${pctStored}%`, background: '#00d4aa', borderRadius: '4px 0 0 4px', minWidth: 60 }}>
            Stored {fmtNum(balance.netStored)}
          </div>
          <div className="co2-flow-bar" style={{ width: `${pctProduced}%`, background: '#f59e0b', minWidth: 60 }}>
            Produced {fmtNum(balance.totalProduced)}
          </div>
          {emitted > 0 && (
            <div className="co2-flow-bar" style={{ width: `${pctEmitted}%`, background: '#ef4444', borderRadius: '0 4px 4px 0', minWidth: 50 }}>
              Emitted {fmtNum(emitted)}
            </div>
          )}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 10 }}>
          {[
            { label: 'Purchased', color: '#a855f7' },
            { label: 'Recycled', color: '#06b6d4' },
            { label: 'Stored', color: '#00d4aa' },
            { label: 'Produced', color: '#f59e0b' },
            { label: 'Emitted', color: '#ef4444' },
          ].map((l) => (
            <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: l.color }} />
              <span style={{ color: 'var(--text-secondary)' }}>{l.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom: Sources table + Storage summary */}
      <div className="two-col">
        <div>
          <div className="section-header">CO₂ Sources</div>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th style={{ textAlign: 'right' }}>Rate (Mcf/d)</th>
                  <th style={{ textAlign: 'right' }}>Cost ($/Mcf)</th>
                </tr>
              </thead>
              <tbody>
                {balance.co2Sources.map((src, i) => (
                  <tr key={i}>
                    <td>{src.name}</td>
                    <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtNum(src.rate)}</td>
                    <td className="mono-cell" style={{ textAlign: 'right' }}>${src.cost.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="section-header">Storage & Constraints</div>
          {balance.storageSummary && (
            <div className="co2-flow-summary">{balance.storageSummary}</div>
          )}
          {constraints.length > 0 && (
            <div className="data-table-wrap" style={{ marginTop: 12 }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Facility</th>
                    <th style={{ textAlign: 'right' }}>Utilization</th>
                    <th style={{ textAlign: 'center' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {constraints.map((c) => (
                    <tr key={c.facilityId}>
                      <td>{c.facilityName}</td>
                      <td className="mono-cell" style={{ textAlign: 'right' }}>{(c.utilization * 100).toFixed(0)}%</td>
                      <td style={{ textAlign: 'center' }}>
                        <span className={`inline-badge ${c.flagged ? 'red' : 'green'}`}>
                          {c.flagged ? 'Constrained' : 'OK'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
