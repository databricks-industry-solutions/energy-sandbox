import { useState, useEffect, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types (matching actual API responses)                              */
/* ------------------------------------------------------------------ */

interface InjectionEfficiency {
  patternId: string;
  patternName: string;
  co2InjectedMcf: number;
  co2ProducedMcf: number;
  co2Utilization: number; // fraction 0-1
  breakthroughRisk: string;
  daysToBreakthrough: number;
  recommendation: string;
}

interface PatternPerformance {
  patternId: string;
  patternName: string;
  totalOilRate: number;
  totalCO2InjRate: number;
  co2PerBblOil: number;
  currentPhase: string;
  cycleNumber: number;
  pressureDeficit: number;
  suggestion: string;
}

interface MergedPattern {
  patternId: string;
  patternName: string;
  co2Utilization: number;
  breakthroughRisk: string;
  daysToBreakthrough: number;
  recommendation: string;
  co2InjectedMcf: number;
  co2ProducedMcf: number;
  totalOilRate: number;
  totalCO2InjRate: number;
  co2PerBblOil: number;
  currentPhase: string;
  cycleNumber: number;
  pressureDeficit: number;
  suggestion: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function utilizationColor(frac: number): string {
  if (frac >= 0.6) return 'var(--success)';
  if (frac >= 0.4) return 'var(--warning)';
  return 'var(--danger)';
}

function riskColor(risk: string): { bg: string; fg: string } {
  const r = risk?.toLowerCase() ?? '';
  if (r === 'high' || r === 'critical') return { bg: 'var(--danger-dim)', fg: 'var(--danger)' };
  if (r === 'medium' || r === 'moderate') return { bg: 'var(--warning-dim)', fg: 'var(--warning)' };
  return { bg: 'var(--success-dim)', fg: 'var(--success)' };
}

function phaseColor(phase: string): { bg: string; fg: string } {
  const p = phase?.toLowerCase() ?? '';
  if (p.includes('co2') || p.includes('inject')) return { bg: 'var(--co2-dim)', fg: 'var(--co2)' };
  if (p.includes('soak')) return { bg: 'var(--blue-dim)', fg: 'var(--blue)' };
  if (p.includes('water')) return { bg: 'var(--blue-dim)', fg: 'var(--blue)' };
  if (p.includes('produc')) return { bg: 'var(--accent-dim)', fg: 'var(--accent)' };
  return { bg: 'var(--bg-card)', fg: 'var(--text-secondary)' };
}

function fmtNum(n: number, d = 0): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: d });
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function InjectionPatternsTab() {
  const [patterns, setPatterns] = useState<MergedPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [effRes, perfRes] = await Promise.all([
        fetch('/api/twin/injection-efficiency'),
        fetch('/api/twin/pattern-performance'),
      ]);
      if (!effRes.ok) throw new Error(`HTTP ${effRes.status}`);
      if (!perfRes.ok) throw new Error(`HTTP ${perfRes.status}`);
      const effData: InjectionEfficiency[] = await effRes.json();
      const perfData: PatternPerformance[] = await perfRes.json();

      const perfMap = new Map(perfData.map((p) => [p.patternId, p]));
      const merged: MergedPattern[] = effData.map((e) => {
        const p = perfMap.get(e.patternId);
        return {
          ...e,
          totalOilRate: p?.totalOilRate ?? 0,
          totalCO2InjRate: p?.totalCO2InjRate ?? 0,
          co2PerBblOil: p?.co2PerBblOil ?? 0,
          currentPhase: p?.currentPhase ?? 'unknown',
          cycleNumber: p?.cycleNumber ?? 0,
          pressureDeficit: p?.pressureDeficit ?? 0,
          suggestion: p?.suggestion ?? '',
        };
      });
      setPatterns(merged);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
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
    return (
      <div className="tab-loading">
        <div className="loading-spinner" />
        <span>Loading injection patterns...</span>
      </div>
    );
  }
  if (error) {
    return <div className="tab-loading" style={{ color: 'var(--danger)' }}>Error: {error}</div>;
  }

  const avgUtil = patterns.length > 0
    ? patterns.reduce((s, p) => s + p.co2Utilization, 0) / patterns.length
    : 0;
  const highRisks = patterns.filter((p) => ['high', 'critical'].includes(p.breakthroughRisk?.toLowerCase())).length;

  return (
    <div className="tab-scroll-layout">
      {/* Summary cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-card-label">Total Patterns</div>
          <div className="summary-card-value accent">{patterns.length}</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Avg CO₂ Utilization</div>
          <div className="summary-card-value" style={{ color: utilizationColor(avgUtil) }}>
            {(avgUtil * 100).toFixed(1)}%
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Breakthrough Risks</div>
          <div className={`summary-card-value ${highRisks > 0 ? 'danger' : 'success'}`}>{highRisks}</div>
        </div>
        <div className="summary-card">
          <div className="summary-card-label">Total Oil Rate</div>
          <div className="summary-card-value accent">{fmtNum(patterns.reduce((s, p) => s + p.totalOilRate, 0))}</div>
          <div className="summary-card-unit">bbl/d</div>
        </div>
      </div>

      {/* Pattern cards */}
      <div className="section-header">Pattern Details</div>
      {patterns.map((p) => {
        const rc = riskColor(p.breakthroughRisk);
        const pc = phaseColor(p.currentPhase);
        const utilPct = p.co2Utilization * 100;
        return (
          <div key={p.patternId} className="pattern-card">
            <div className="pattern-card-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="pattern-card-title">{p.patternName}</span>
                <span className="inline-badge" style={{ background: pc.bg, color: pc.fg }}>
                  {p.currentPhase.replace(/_/g, ' ')}
                </span>
                <span className="inline-badge" style={{ background: rc.bg, color: rc.fg }}>
                  Risk: {p.breakthroughRisk}
                </span>
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
                Cycle #{p.cycleNumber}
              </span>
            </div>

            <div className="pattern-card-grid">
              <div className="pattern-metric">
                <span className="pattern-metric-label">CO₂ Utilization</span>
                <span className="pattern-metric-value" style={{ color: utilizationColor(p.co2Utilization) }}>
                  {utilPct.toFixed(1)}%
                </span>
                <div className="progress-bar-bg">
                  <div className="progress-bar-fill" style={{ width: `${Math.min(100, utilPct)}%`, background: utilizationColor(p.co2Utilization) }} />
                </div>
              </div>
              <div className="pattern-metric">
                <span className="pattern-metric-label">Oil Rate</span>
                <span className="pattern-metric-value">{fmtNum(p.totalOilRate)} bbl/d</span>
              </div>
              <div className="pattern-metric">
                <span className="pattern-metric-label">CO₂ Injected</span>
                <span className="pattern-metric-value" style={{ color: 'var(--co2)' }}>{fmtNum(p.co2InjectedMcf)} Mcf/d</span>
              </div>
              <div className="pattern-metric">
                <span className="pattern-metric-label">CO₂/bbl Oil</span>
                <span className="pattern-metric-value">{p.co2PerBblOil.toFixed(2)} Mcf</span>
              </div>
              <div className="pattern-metric">
                <span className="pattern-metric-label">Days to Breakthrough</span>
                <span className="pattern-metric-value">{p.daysToBreakthrough > 0 ? `${p.daysToBreakthrough} d` : 'N/A'}</span>
              </div>
              <div className="pattern-metric">
                <span className="pattern-metric-label">Pressure Deficit</span>
                <span className="pattern-metric-value">{fmtNum(p.pressureDeficit)} psi</span>
              </div>
            </div>

            {(p.suggestion || p.recommendation) && (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4, padding: '8px 10px', background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', borderLeft: '3px solid var(--co2)' }}>
                <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--co2)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Analytics
                </span>
                <div style={{ marginTop: 4 }}>{p.suggestion || p.recommendation}</div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
