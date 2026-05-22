import { useState, useEffect, useCallback, useMemo } from 'react';

/* ------------------------------------------------------------------ */
/*  Types (matching actual API responses)                              */
/* ------------------------------------------------------------------ */

interface WellEconomics {
  wellId: string;
  wellName: string;
  oilRevenue: number;
  gasRevenue: number;
  co2Cost: number;
  loe: number;
  transportCost: number;
  netbackPerBoe: number;
  co2PerBoe: number;
}

interface CO2Contract {
  id: string;
  supplier: string;
  volume: number;
  price: number;
  takeOrPay: number | boolean | string;
  deliveryPoint: string;
  status?: string;
}

interface CarbonCredit {
  vintage: number | string;
  registry: string;
  pricePerTon: number;
  volumeAvailable: number;
}

interface FieldSummary {
  totalRevenue: number;
  totalOpex: number;
  totalCO2Cost: number;
  totalTransport: number;
  fieldNetback: number;
  incrementalNetback: number;
  breakeven: number;
  carbonCreditRevenue: number;
  totalBoe: number;
  wellCount: number;
}

type SortKey = 'wellName' | 'oilRevenue' | 'co2Cost' | 'loe' | 'transportCost' | 'netbackPerBoe' | 'co2PerBoe';

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtNum(n: number, d = 0): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: d });
}

function fmtCur(n: number, d = 0): string {
  return '$' + fmtNum(n, d);
}

function netbackColor(nb: number): string {
  if (nb >= 30) return 'var(--success)';
  if (nb >= 15) return 'var(--warning)';
  return 'var(--danger)';
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function EconomicsTab() {
  const [wells, setWells] = useState<WellEconomics[]>([]);
  const [contracts, setContracts] = useState<CO2Contract[]>([]);
  const [credits, setCredits] = useState<CarbonCredit[]>([]);
  const [summary, setSummary] = useState<FieldSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('netbackPerBoe');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const fetchData = useCallback(async () => {
    try {
      const [wRes, cRes, crRes, sRes] = await Promise.all([
        fetch('/api/commercial/well-economics'),
        fetch('/api/commercial/co2-contracts'),
        fetch('/api/commercial/carbon-credits'),
        fetch('/api/commercial/field-summary'),
      ]);
      if (!wRes.ok) throw new Error(`HTTP ${wRes.status}`);
      if (!sRes.ok) throw new Error(`HTTP ${sRes.status}`);
      setWells(await wRes.json());
      setContracts(cRes.ok ? await cRes.json() : []);
      setCredits(crRes.ok ? await crRes.json() : []);
      setSummary(await sRes.json());
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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  const sortedWells = useMemo(() => {
    const copy = [...wells];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'asc' ? av - bv : bv - av;
      return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [wells, sortKey, sortDir]);

  const arrow = (key: SortKey) => sortKey === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';

  if (loading) {
    return <div className="tab-loading"><div className="loading-spinner" /><span>Loading economics...</span></div>;
  }
  if (error || !summary) {
    return <div className="tab-loading" style={{ color: 'var(--danger)' }}>Error: {error || 'No data'}</div>;
  }

  return (
    <div className="tab-scroll-layout">
      {/* Summary cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-card-label">Total Revenue</div>
          <div className="summary-card-value accent">{fmtCur(summary.totalRevenue)}</div>
          <div className="summary-card-unit">$/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Total Opex</div>
          <div className="summary-card-value warning">{fmtCur(summary.totalOpex)}</div>
          <div className="summary-card-unit">$/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">CO₂ Cost</div>
          <div className="summary-card-value co2">{fmtCur(summary.totalCO2Cost)}</div>
          <div className="summary-card-unit">$/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Field Netback</div>
          <div className="summary-card-value" style={{ color: netbackColor(summary.fieldNetback) }}>{fmtCur(summary.fieldNetback, 2)}</div>
          <div className="summary-card-unit">$/boe</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Breakeven</div>
          <div className="summary-card-value">{fmtCur(summary.breakeven)}</div>
          <div className="summary-card-unit">$/bbl WTI</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Carbon Credit Rev</div>
          <div className="summary-card-value success">{fmtCur(summary.carbonCreditRevenue)}</div>
          <div className="summary-card-unit">$/d</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Total BOE</div>
          <div className="summary-card-value accent">{fmtNum(summary.totalBoe)}</div>
          <div className="summary-card-unit">boe/d · {summary.wellCount} wells</div>
        </div>
      </div>

      {/* Well Economics Table */}
      <div className="section-header">Well Economics</div>
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('wellName')}>Well{arrow('wellName')}</th>
              <th className="sortable" onClick={() => handleSort('oilRevenue')} style={{ textAlign: 'right' }}>Revenue{arrow('oilRevenue')}</th>
              <th className="sortable" onClick={() => handleSort('co2Cost')} style={{ textAlign: 'right' }}>CO₂ Cost{arrow('co2Cost')}</th>
              <th className="sortable" onClick={() => handleSort('loe')} style={{ textAlign: 'right' }}>LOE{arrow('loe')}</th>
              <th className="sortable" onClick={() => handleSort('transportCost')} style={{ textAlign: 'right' }}>Transport{arrow('transportCost')}</th>
              <th className="sortable" onClick={() => handleSort('netbackPerBoe')} style={{ textAlign: 'right' }}>Netback/boe{arrow('netbackPerBoe')}</th>
              <th className="sortable" onClick={() => handleSort('co2PerBoe')} style={{ textAlign: 'right' }}>CO₂/boe{arrow('co2PerBoe')}</th>
            </tr>
          </thead>
          <tbody>
            {sortedWells.map((w) => (
              <tr key={w.wellId}>
                <td>{w.wellName}</td>
                <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtCur(w.oilRevenue + (w.gasRevenue || 0))}</td>
                <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtCur(w.co2Cost)}</td>
                <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtCur(w.loe)}</td>
                <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtCur(w.transportCost)}</td>
                <td className="mono-cell" style={{ textAlign: 'right', color: netbackColor(w.netbackPerBoe), fontWeight: 600 }}>{fmtCur(w.netbackPerBoe, 2)}</td>
                <td className="mono-cell" style={{ textAlign: 'right' }}>{w.co2PerBoe.toFixed(2)} Mcf</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Bottom: Contracts + Credits */}
      <div className="two-col">
        <div>
          <div className="section-header">CO₂ Contracts</div>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th style={{ textAlign: 'right' }}>Volume</th>
                  <th style={{ textAlign: 'right' }}>Price</th>
                  <th>Take-or-Pay</th>
                  <th>Delivery</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((c) => (
                  <tr key={c.id}>
                    <td>{c.supplier}</td>
                    <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtNum(c.volume)} Mcf/d</td>
                    <td className="mono-cell" style={{ textAlign: 'right' }}>${typeof c.price === 'number' ? c.price.toFixed(2) : c.price}/Mcf</td>
                    <td>
                      <span className={`inline-badge ${typeof c.takeOrPay === 'number' && c.takeOrPay > 0 ? 'yellow' : 'blue'}`}>
                        {typeof c.takeOrPay === 'number' ? `${fmtNum(c.takeOrPay)} Mcf/d` : String(c.takeOrPay)}
                      </span>
                    </td>
                    <td style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{c.deliveryPoint}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="section-header">Carbon Credits</div>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Vintage</th>
                  <th>Registry</th>
                  <th style={{ textAlign: 'right' }}>Price/ton</th>
                  <th style={{ textAlign: 'right' }}>Volume</th>
                </tr>
              </thead>
              <tbody>
                {credits.map((cr, i) => (
                  <tr key={i}>
                    <td className="mono-cell">{cr.vintage}</td>
                    <td>{cr.registry}</td>
                    <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtCur(cr.pricePerTon, 2)}</td>
                    <td className="mono-cell" style={{ textAlign: 'right' }}>{fmtNum(cr.volumeAvailable)} tCO₂</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
