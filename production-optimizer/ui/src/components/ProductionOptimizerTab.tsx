import { useState, useEffect, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface DeclineParams { qi: number; Di: number; b: number; }

interface DeclinePoint {
  month: number; date: string; actual: number; predicted: number; cumulative: number;
}

interface DeclineCurve {
  wellId: string; wellName: string; params: DeclineParams; declineType: string;
  r2: number; eur: number; remainingReserves: number;
  history: DeclinePoint[]; forecast: DeclinePoint[];
}

interface WhatIfResult {
  wellId: string; wellName: string;
  baselineOilRate: number; predictedOilRate: number; oilRateChange: number;
  baselinePressure: number; predictedPressure: number; pressureChange: number;
  baselineNetback: number; predictedNetback: number; netbackChange: number;
  dailyRevenueImpact: number; annualRevenueImpact: number;
  breakthroughRisk: string; explanation: string;
}

interface WhatIfResponse {
  results: WhatIfResult[];
  summary: {
    totalDailyImpact: number; totalAnnualImpact: number;
    wellsAffected: number; avgOilRateChange: number; highRiskWells: number;
  };
}

interface Recommendation {
  id: string; priority: 'high' | 'medium' | 'low';
  title: string; description: string; affectedEntities: string[];
  estimatedImpact: { oilRateChange: number; dailyRevenue: number; annualRevenue: number; };
  physicsRationale: string; risk: string;
}

interface RecsResponse {
  recommendations: Recommendation[];
  summary: { count: number; highPriority: number; totalAnnualImpact: number; };
}

interface FieldEconomics {
  totalRevenue: number; totalOpex: number; totalCO2Cost: number;
  totalTransport: number; fieldNetback: number; incrementalNetback: number;
  breakeven: number; carbonCreditRevenue: number; totalBoe: number; wellCount: number;
}

/* ------------------------------------------------------------------ */
/*  Decline Chart (SVG)                                                */
/* ------------------------------------------------------------------ */

function DeclineChart({ curve, large }: { curve: DeclineCurve; large?: boolean }) {
  const allPoints = [...curve.history, ...curve.forecast];
  if (allPoints.length < 2) return null;

  const W = large ? 600 : 340;
  const H = large ? 240 : 130;
  const pad = { top: 12, right: 12, bottom: 22, left: 44 };
  const cw = W - pad.left - pad.right;
  const ch = H - pad.top - pad.bottom;

  const maxRate = Math.max(...allPoints.map(p => Math.max(p.actual, p.predicted))) * 1.1;
  const minMonth = allPoints[0].month;
  const maxMonth = allPoints[allPoints.length - 1].month;
  const monthRange = maxMonth - minMonth || 1;

  const x = (m: number) => pad.left + ((m - minMonth) / monthRange) * cw;
  const y = (r: number) => pad.top + ch - (r / maxRate) * ch;

  const predLine = allPoints.filter(p => p.predicted > 0)
    .map(p => `${x(p.month)},${y(p.predicted)}`).join(' ');

  const forecastStart = curve.history.length > 0
    ? curve.history[curve.history.length - 1].month : 0;

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1={pad.left} y1={y(maxRate * f)} x2={W - pad.right} y2={y(maxRate * f)}
          stroke="#1e293b" strokeWidth={0.5} />
      ))}
      <rect x={x(forecastStart)} y={pad.top} width={x(maxMonth) - x(forecastStart)} height={ch}
        fill="rgba(234,179,8,0.06)" />
      <text x={x(forecastStart) + 4} y={pad.top + 12} fill="#a16207" fontSize={large ? 9 : 7}
        fontFamily="monospace">FORECAST</text>
      <polyline points={predLine} fill="none" stroke="#3b82f6" strokeWidth={large ? 2 : 1.5} />
      {curve.history.filter(p => p.actual > 0).map((p, i) => (
        <circle key={i} cx={x(p.month)} cy={y(p.actual)} r={large ? 2.5 : 1.5} fill="#10b981" />
      ))}
      {/* CO2 flood response zone */}
      {large && (
        <text x={x(forecastStart * 0.5)} y={H - 4} fill="#64748b" fontSize={8} fontFamily="monospace"
          textAnchor="middle">CO₂ flood response</text>
      )}
      <text x={pad.left} y={H - 3} fill="#64748b" fontSize={large ? 9 : 7} fontFamily="monospace">
        {curve.history[0]?.date?.slice(0, 7) || ''}
      </text>
      <text x={W - pad.right} y={H - 3} fill="#64748b" fontSize={large ? 9 : 7}
        fontFamily="monospace" textAnchor="end">
        {allPoints[allPoints.length - 1]?.date?.slice(0, 7) || ''}
      </text>
      <text x={2} y={H / 2} fill="#64748b" fontSize={large ? 9 : 7} fontFamily="monospace"
        transform={`rotate(-90, 2, ${H / 2})`} textAnchor="middle">bbl/d</text>
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Multi-stream SVG chart                                             */
/* ------------------------------------------------------------------ */

interface StreamChartProps {
  data: Array<Record<string, number>>;
  streams: Array<{ key: string; color: string; label: string }>;
  yLabel: string;
  height?: number;
}

function StreamChart({ data, streams, yLabel, height = 160 }: StreamChartProps) {
  if (data.length < 2) return null;
  const W = 600, H = height;
  const pad = { top: 10, right: 12, bottom: 22, left: 48 };
  const cw = W - pad.left - pad.right;
  const ch = H - pad.top - pad.bottom;

  let maxVal = 0;
  for (const d of data) for (const s of streams) maxVal = Math.max(maxVal, d[s.key] || 0);
  maxVal *= 1.1 || 1;

  const x = (i: number) => pad.left + (i / (data.length - 1)) * cw;
  const y = (v: number) => pad.top + ch - (v / maxVal) * ch;

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1={pad.left} y1={y(maxVal * f)} x2={W - pad.right} y2={y(maxVal * f)}
          stroke="#1e293b" strokeWidth={0.5} />
      ))}
      {streams.map(s => {
        const pts = data.map((d, i) => `${x(i)},${y(d[s.key] || 0)}`).join(' ');
        return <polyline key={s.key} points={pts} fill="none" stroke={s.color} strokeWidth={1.5} opacity={0.85} />;
      })}
      <text x={2} y={H / 2} fill="#64748b" fontSize={8} fontFamily="monospace"
        transform={`rotate(-90, 2, ${H / 2})`} textAnchor="middle">{yLabel}</text>
      {/* Legend */}
      {streams.map((s, i) => (
        <g key={s.key} transform={`translate(${pad.left + i * 90}, ${H - 3})`}>
          <line x1={0} y1={-3} x2={12} y2={-3} stroke={s.color} strokeWidth={2} />
          <text x={15} y={0} fill="#64748b" fontSize={8} fontFamily="monospace">{s.label}</text>
        </g>
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Trend arrow helper                                                 */
/* ------------------------------------------------------------------ */

function TrendArrow({ trend }: { trend: string }) {
  if (trend === 'rising') return <span style={{ color: '#f85149' }}>↑</span>;
  if (trend === 'falling') return <span style={{ color: '#3fb950' }}>↓</span>;
  return <span style={{ color: '#6e7681' }}>→</span>;
}

/* ------------------------------------------------------------------ */
/*  Health bar                                                         */
/* ------------------------------------------------------------------ */

function HealthBar({ score }: { score: number }) {
  const color = score >= 80 ? '#3fb950' : score >= 60 ? '#d29922' : '#f85149';
  return (
    <div className="health-bar-wrap">
      <div className="health-bar-bg">
        <div className="health-bar-fill" style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="health-bar-label" style={{ color }}>{score}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-tab: Deep Dive (Well Analytics)                                */
/* ------------------------------------------------------------------ */

interface WellAnalyticsData {
  wellId: string; wellName: string;
  declineParams: { qi: number; Di: number; b: number };
  declineType: string; r2: number; eur: number; remainingReserves: number;
  currentRate: number; expectedRate: number; performanceGap: number;
  healthScore: number;
  waterCutTrend: string; co2Trend: string; pressureTrend: string;
  history: Array<Record<string, number>>;
  forecast: Array<Record<string, number>>;
}

function WellsView() {
  const [wells, setWells] = useState<WellAnalyticsData[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/production/well-analytics').then(r => r.json())
      .then(d => { setWells(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="opt-empty">Loading well analytics...</div>;

  const sel = selected ? wells.find(w => w.wellId === selected) : null;

  if (sel) {
    return (
      <div className="deep-dive-detail">
        <button className="back-btn" onClick={() => setSelected(null)}>← All Wells</button>

        {/* Header */}
        <div className="dd-header">
          <div>
            <h3 className="dd-well-name">{sel.wellName}</h3>
            <span className={`decline-type type-${sel.declineType}`}>{sel.declineType} decline</span>
          </div>
          <HealthBar score={sel.healthScore} />
        </div>

        {/* KPI row */}
        <div className="dd-kpis">
          <div className="stat">
            <span className="stat-label">Current Rate</span>
            <span className="stat-value">{sel.currentRate.toFixed(0)} <small>bbl/d</small></span>
          </div>
          <div className="stat">
            <span className="stat-label">Expected</span>
            <span className="stat-value">{sel.expectedRate.toFixed(0)} <small>bbl/d</small></span>
          </div>
          <div className={`stat ${sel.performanceGap < 0 ? 'stat-warn' : ''}`}>
            <span className="stat-label">Gap</span>
            <span className="stat-value">{sel.performanceGap >= 0 ? '+' : ''}{sel.performanceGap.toFixed(1)} <small>bbl/d</small></span>
          </div>
          <div className="stat">
            <span className="stat-label">EUR</span>
            <span className="stat-value">{(sel.eur / 1000).toFixed(0)} <small>K bbl</small></span>
          </div>
          <div className="stat">
            <span className="stat-label">Remaining</span>
            <span className="stat-value">{(sel.remainingReserves / 1000).toFixed(0)} <small>K bbl</small></span>
          </div>
          <div className="stat">
            <span className="stat-label">R²</span>
            <span className="stat-value">{sel.r2.toFixed(3)}</span>
          </div>
        </div>

        {/* Production chart: oil actual vs predicted */}
        <div className="dd-chart-section">
          <h4>Oil Production — Actual vs Arps Model</h4>
          <StreamChart
            data={[...sel.history, ...sel.forecast]}
            streams={[
              { key: 'oilRate', color: '#10b981', label: 'Actual' },
              { key: 'oilPredicted', color: '#3b82f6', label: 'Model' },
            ]}
            yLabel="bbl/d"
            height={180}
          />
        </div>

        {/* Multi-stream: gas + water */}
        <div className="dd-chart-row">
          <div className="dd-chart-section">
            <h4>Gas Rate &amp; GOR</h4>
            <StreamChart
              data={sel.history}
              streams={[
                { key: 'gasRate', color: '#f59e0b', label: 'Gas (mcf/d)' },
                { key: 'gor', color: '#a855f7', label: 'GOR (scf/bbl)' },
              ]}
              yLabel="mcf/d"
              height={140}
            />
          </div>
          <div className="dd-chart-section">
            <h4>Water Cut &amp; Water Rate</h4>
            <StreamChart
              data={sel.history}
              streams={[
                { key: 'waterRate', color: '#3b82f6', label: 'Water (bbl/d)' },
                { key: 'waterCut', color: '#ef4444', label: 'WC (frac)' },
              ]}
              yLabel="bbl/d"
              height={140}
            />
          </div>
        </div>

        {/* Pressure + CO2 */}
        <div className="dd-chart-row">
          <div className="dd-chart-section">
            <h4>Pressures</h4>
            <StreamChart
              data={sel.history}
              streams={[
                { key: 'bhp', color: '#ef4444', label: 'BHP' },
                { key: 'tubingPressure', color: '#10b981', label: 'THP' },
                { key: 'casingPressure', color: '#f59e0b', label: 'CP' },
              ]}
              yLabel="psi"
              height={140}
            />
          </div>
          <div className="dd-chart-section">
            <h4>CO₂ Concentration</h4>
            <StreamChart
              data={sel.history}
              streams={[
                { key: 'co2Concentration', color: '#06b6d4', label: 'CO₂ (mol%)' },
              ]}
              yLabel="mol%"
              height={140}
            />
          </div>
        </div>

        {/* Decline parameters */}
        <div className="dd-params">
          <h4>Decline Curve Parameters</h4>
          <div className="dd-params-row">
            <span>q<sub>i</sub> = {sel.declineParams.qi.toFixed(0)} bbl/d</span>
            <span>D<sub>i</sub> = {(sel.declineParams.Di * 100).toFixed(2)}%/month</span>
            <span>b = {sel.declineParams.b.toFixed(3)}</span>
            <span>Type: {sel.declineType}</span>
          </div>
        </div>
      </div>
    );
  }

  // Ranking list
  return (
    <div className="deep-dive-list">
      <table className="dd-table">
        <thead>
          <tr>
            <th>Well</th>
            <th>Health</th>
            <th>Rate (bbl/d)</th>
            <th>Expected</th>
            <th>Gap</th>
            <th>EUR (K bbl)</th>
            <th>Water Cut</th>
            <th>CO₂</th>
            <th>Pressure</th>
          </tr>
        </thead>
        <tbody>
          {wells.map(w => (
            <tr key={w.wellId} className="dd-row" onClick={() => setSelected(w.wellId)}>
              <td className="well-name">{w.wellName}</td>
              <td><HealthBar score={w.healthScore} /></td>
              <td>{w.currentRate.toFixed(0)}</td>
              <td>{w.expectedRate.toFixed(0)}</td>
              <td className={w.performanceGap >= 0 ? 'val-pos' : 'val-neg'}>
                {w.performanceGap >= 0 ? '+' : ''}{w.performanceGap.toFixed(1)}
              </td>
              <td>{(w.eur / 1000).toFixed(0)}</td>
              <td><TrendArrow trend={w.waterCutTrend} /> {w.waterCutTrend}</td>
              <td><TrendArrow trend={w.co2Trend} /> {w.co2Trend}</td>
              <td><TrendArrow trend={w.pressureTrend} /> {w.pressureTrend}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-tab: Optimize                                                  */
/* ------------------------------------------------------------------ */

function OptimizeView({ recs }: { recs: RecsResponse | null }) {
  const [selectedRec, setSelectedRec] = useState<string | null>(null);
  const [injChange, setInjChange] = useState(0);
  const [chokeChange, setChokeChange] = useState(0);
  const [co2PriceChange, setCo2PriceChange] = useState(0);
  const [whatIf, setWhatIf] = useState<WhatIfResponse | null>(null);
  const [econ, setEcon] = useState<FieldEconomics | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoRan, setAutoRan] = useState(false);

  useEffect(() => {
    fetch('/api/commercial/field-summary')
      .then(r => r.ok ? r.json() : null)
      .then(d => setEcon(d && typeof d.fieldNetback === 'number' ? d : null))
      .catch(() => {});
  }, []);

  // When a recommendation is selected, pre-populate sliders and auto-run
  const selectRec = useCallback((rec: Recommendation) => {
    setSelectedRec(rec.id);
    // Parse the recommendation to set sliders
    const title = rec.title.toLowerCase();
    if (title.includes('increase') && title.includes('injection')) {
      setInjChange(15);
      setChokeChange(0);
    } else if (title.includes('reduce') || title.includes('decrease')) {
      setInjChange(-10);
      setChokeChange(0);
    } else if (title.includes('switch') && title.includes('water')) {
      setInjChange(-30); // switching to water = reducing CO2
      setChokeChange(0);
    } else if (title.includes('choke')) {
      setInjChange(0);
      setChokeChange(-15);
    } else {
      setInjChange(10);
      setChokeChange(5);
    }
    setCo2PriceChange(0);
    setAutoRan(false);
  }, []);

  // Auto-run when recommendation changes sliders
  useEffect(() => {
    if (selectedRec && !autoRan && (injChange !== 0 || chokeChange !== 0)) {
      setAutoRan(true);
      runScenario();
    }
  }, [selectedRec, injChange, chokeChange, autoRan]);

  const runScenario = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/production/what-if', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          injectionRateChange: injChange / 100,
          chokeChange: chokeChange / 100,
          co2PriceChange,
          wagRatioChange: 0,
        }),
      });
      const j = await r.json();
      setWhatIf(j && j.summary && Array.isArray(j.results) ? j : null);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [injChange, chokeChange, co2PriceChange]);

  const activeRec = selectedRec ? recs?.recommendations.find(r => r.id === selectedRec) : null;

  return (
    <div className="scenario-view">
      {/* Step 1: Pick a recommendation */}
      <div className="scenario-picker">
        <h3>Select a recommended action to simulate</h3>
        <div className="scenario-chips">
          {(recs?.recommendations ?? []).map(rec => (
            <button
              key={rec.id}
              className={`scenario-chip ${selectedRec === rec.id ? 'active' : ''} scenario-chip-${rec.priority}`}
              onClick={() => selectRec(rec)}
            >
              <span className={`priority-badge priority-${rec.priority}`}>{rec.priority}</span>
              <span className="scenario-chip-title">{rec.title}</span>
              <span className="scenario-chip-value">${(rec.estimatedImpact.annualRevenue / 1000).toFixed(0)}K/yr</span>
            </button>
          ))}
        </div>
      </div>

      {activeRec && (
        <>
          {/* Active recommendation context */}
          <div className="scenario-context">
            <div className="agent-icon">AI</div>
            <div className="agent-message">
              <strong>{activeRec.title}</strong> — {activeRec.description}
              <br /><em>Adjust the sliders below to fine-tune, or run as-is.</em>
            </div>
          </div>

          {/* Economics bar */}
          {econ && (
            <div className="econ-bar">
              <div className="econ-kpi">
                <span className="econ-label">Revenue</span>
                <span className="econ-value">${(econ.totalRevenue / 1000).toFixed(0)}K<small>/d</small></span>
                {whatIf && <span className={`econ-delta ${whatIf.summary.totalDailyImpact >= 0 ? 'impact-pos' : 'impact-neg'}`}>
                  {whatIf.summary.totalDailyImpact >= 0 ? '+' : ''}${(whatIf.summary.totalDailyImpact / 1000).toFixed(1)}K
                </span>}
              </div>
              <div className="econ-kpi">
                <span className="econ-label">OpEx</span>
                <span className="econ-value">${(econ.totalOpex / 1000).toFixed(0)}K<small>/d</small></span>
              </div>
              <div className="econ-kpi">
                <span className="econ-label">CO₂ Cost</span>
                <span className="econ-value">${(econ.totalCO2Cost / 1000).toFixed(0)}K<small>/d</small></span>
              </div>
              <div className="econ-kpi">
                <span className="econ-label">Netback</span>
                <span className="econ-value">${econ.fieldNetback.toFixed(2)}<small>/boe</small></span>
              </div>
              <div className="econ-kpi">
                <span className="econ-label">Breakeven</span>
                <span className="econ-value">${econ.breakeven}<small>/bbl</small></span>
              </div>
            </div>
          )}

          {/* Tuning sliders */}
          <div className="scenario-tuning">
            <div className="opt-sliders">
              <div className="opt-slider">
                <div className="opt-slider-label">
                  <span>CO₂ Injection</span>
                  <span className={`slider-val ${injChange > 0 ? 'pos' : injChange < 0 ? 'neg' : ''}`}>
                    {injChange > 0 ? '+' : ''}{injChange}%
                  </span>
                </div>
                <input type="range" min={-30} max={30} step={5} value={injChange}
                  onChange={e => { setInjChange(Number(e.target.value)); setAutoRan(false); }} />
              </div>
              <div className="opt-slider">
                <div className="opt-slider-label">
                  <span>Choke Position</span>
                  <span className={`slider-val ${chokeChange > 0 ? 'pos' : chokeChange < 0 ? 'neg' : ''}`}>
                    {chokeChange > 0 ? '+' : ''}{chokeChange}%
                  </span>
                </div>
                <input type="range" min={-30} max={30} step={5} value={chokeChange}
                  onChange={e => { setChokeChange(Number(e.target.value)); setAutoRan(false); }} />
              </div>
              <div className="opt-slider">
                <div className="opt-slider-label">
                  <span>CO₂ Price</span>
                  <span className={`slider-val ${co2PriceChange > 0 ? 'pos' : co2PriceChange < 0 ? 'neg' : ''}`}>
                    {co2PriceChange > 0 ? '+' : ''}{co2PriceChange.toFixed(2)} $/mcf
                  </span>
                </div>
                <input type="range" min={-0.5} max={0.5} step={0.05} value={co2PriceChange}
                  onChange={e => { setCo2PriceChange(Number(e.target.value)); setAutoRan(false); }} />
              </div>
            </div>
            <button className="run-btn" onClick={runScenario} disabled={loading}>
              {loading ? 'Computing...' : 'Re-run Scenario'}
            </button>
          </div>

          {/* Results */}
          {whatIf && (
            <div className="opt-results">
              <div className="opt-impact-row">
                <div className={`opt-impact-card ${whatIf.summary.totalDailyImpact >= 0 ? 'positive' : 'negative'}`}>
                  <span className="opt-impact-label">Daily Impact</span>
                  <span className="opt-impact-value">
                    {whatIf.summary.totalDailyImpact >= 0 ? '+' : ''}${whatIf.summary.totalDailyImpact.toLocaleString()}/d
                  </span>
                </div>
                <div className={`opt-impact-card ${whatIf.summary.totalAnnualImpact >= 0 ? 'positive' : 'negative'}`}>
                  <span className="opt-impact-label">Annual Impact</span>
                  <span className="opt-impact-value">
                    {whatIf.summary.totalAnnualImpact >= 0 ? '+' : ''}${(whatIf.summary.totalAnnualImpact / 1000).toFixed(0)}K
                  </span>
                </div>
                <div className="opt-impact-card">
                  <span className="opt-impact-label">Avg Oil Change</span>
                  <span className="opt-impact-value">
                    {whatIf.summary.avgOilRateChange >= 0 ? '+' : ''}{whatIf.summary.avgOilRateChange} bbl/d
                  </span>
                </div>
                <div className={`opt-impact-card ${whatIf.summary.highRiskWells > 0 ? 'negative' : ''}`}>
                  <span className="opt-impact-label">Risk</span>
                  <span className="opt-impact-value">{whatIf.summary.highRiskWells} high-risk</span>
                </div>
              </div>

              <table className="opt-table">
                <thead>
                  <tr>
                    <th>Well</th><th>Current</th><th>Predicted</th><th>Δ Oil</th>
                    <th>Pressure</th><th>Δ Revenue</th><th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {whatIf.results.map(r => (
                    <tr key={r.wellId}>
                      <td className="well-name">{r.wellName}</td>
                      <td>{r.baselineOilRate.toFixed(0)}</td>
                      <td>{r.predictedOilRate.toFixed(0)}</td>
                      <td className={r.oilRateChange >= 0 ? 'val-pos' : 'val-neg'}>
                        {r.oilRateChange >= 0 ? '+' : ''}{r.oilRateChange.toFixed(1)} bbl/d
                      </td>
                      <td>{r.predictedPressure} psi</td>
                      <td className={r.dailyRevenueImpact >= 0 ? 'val-pos' : 'val-neg'}>
                        {r.dailyRevenueImpact >= 0 ? '+' : ''}${r.dailyRevenueImpact}/d
                      </td>
                      <td><span className={`risk-badge risk-${r.breakthroughRisk}`}>{r.breakthroughRisk}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {whatIf.results[0]?.explanation && (
                <div className="opt-explanation">
                  <strong>Physics:</strong> {whatIf.results[0].explanation}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {!activeRec && (
        <div className="opt-empty">
          Select a recommended action above to simulate its impact across all wells.
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-tab: Recommendations                                           */
/* ------------------------------------------------------------------ */

function RecommendationsView({ recs }: { recs: RecsResponse | null }) {
  if (!recs || recs.recommendations.length === 0) {
    return <div className="opt-empty">No recommendations at this time.</div>;
  }

  return (
    <div className="actions-view">
      {/* Agent intro */}
      <div className="agent-intro">
        <div className="agent-icon">AI</div>
        <div className="agent-message">
          I've analyzed live SCADA data across <strong>{recs.summary.count} patterns</strong> using
          Darcy flow, material balance, and decline curve models.
          Found <strong>{recs.summary.count} optimization actions</strong> worth
          <strong className="impact-pos"> ${(recs.summary.totalAnnualImpact / 1000).toFixed(0)}K/yr</strong> in
          combined upside. {recs.summary.highPriority} require immediate attention.
        </div>
      </div>

      {/* Action cards */}
      <div className="actions-list">
        {recs.recommendations.map((rec, i) => (
          <div key={rec.id} className={`action-card action-${rec.priority}`}>
            <div className="action-rank">#{i + 1}</div>
            <div className="action-body">
              <div className="action-top">
                <span className={`priority-badge priority-${rec.priority}`}>{rec.priority}</span>
                <h4 className="action-title">{rec.title}</h4>
              </div>
              <p className="action-desc">{rec.description}</p>
              <div className="action-numbers">
                <div className="action-number">
                  <span className="action-number-label">Annual Impact</span>
                  <span className={`action-number-value ${rec.estimatedImpact.annualRevenue >= 0 ? 'impact-pos' : 'impact-neg'}`}>
                    ${(rec.estimatedImpact.annualRevenue / 1000).toFixed(0)}K
                  </span>
                </div>
                <div className="action-number">
                  <span className="action-number-label">Daily</span>
                  <span className={`action-number-value ${rec.estimatedImpact.dailyRevenue >= 0 ? 'impact-pos' : 'impact-neg'}`}>
                    {rec.estimatedImpact.dailyRevenue >= 0 ? '+' : ''}${rec.estimatedImpact.dailyRevenue}
                  </span>
                </div>
                <div className="action-number">
                  <span className="action-number-label">Oil Change</span>
                  <span className={`action-number-value ${rec.estimatedImpact.oilRateChange >= 0 ? 'impact-pos' : 'impact-neg'}`}>
                    {rec.estimatedImpact.oilRateChange >= 0 ? '+' : ''}{rec.estimatedImpact.oilRateChange} bbl/d
                  </span>
                </div>
                <div className="action-number">
                  <span className="action-number-label">Risk</span>
                  <span className="action-number-value">{rec.risk.split('—')[0].trim()}</span>
                </div>
              </div>
              <details className="action-physics">
                <summary>Why — Physics Rationale</summary>
                <p>{rec.physicsRationale}</p>
              </details>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main: Sub-tab navigation                                           */
/* ------------------------------------------------------------------ */

const SUB_TABS = [
  { id: 'actions', label: 'Actions' },
  { id: 'wells', label: 'Deep Dive' },
  { id: 'scenario', label: 'Scenario' },
] as const;

type SubTabId = (typeof SUB_TABS)[number]['id'];

export default function ProductionOptimizerTab() {
  const [subTab, setSubTab] = useState<SubTabId>('actions');
  const [curves, setCurves] = useState<DeclineCurve[]>([]);
  const [recs, setRecs] = useState<RecsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/production/decline-curves').then(r => r.json()),
      fetch('/api/production/recommendations').then(r => r.json()),
    ]).then(([dc, rec]) => {
      setCurves(dc);
      setRecs(rec);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="tab-loading">Loading production optimizer...</div>;
  }

  return (
    <div className="prod-opt-tab">
      <nav className="sub-tabs">
        {SUB_TABS.map(t => (
          <button
            key={t.id}
            className={`sub-tab-btn ${subTab === t.id ? 'active' : ''}`}
            onClick={() => setSubTab(t.id)}
          >
            {t.label}
            {t.id === 'actions' && recs && recs.summary.highPriority > 0 && (
              <span className="sub-tab-badge">{recs.summary.highPriority}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="sub-tab-content">
        {subTab === 'actions' && <RecommendationsView recs={recs} />}
        {subTab === 'wells' && <WellsView />}
        {subTab === 'scenario' && <OptimizeView recs={recs} />}
      </div>
    </div>
  );
}
