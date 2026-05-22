/**
 * Production Optimizer API routes.
 *
 * Serves decline curves, what-if scenarios, and optimization recommendations
 * using real Arps decline models and Darcy flow physics.
 */

import { Router, Request, Response } from 'express';
import { InMemoryTwinDataProvider } from '../twin/provider';
import { executeQuery, table, isDatabricksAvailable } from '../databricks/sql';
import {
  fitDeclineCurve,
  generateProductionHistory,
  generateWellAnalytics,
  arpsRate,
  calculateEUR,
  DeclineCurveResult,
  WellAnalytics,
} from '../physics/decline';
import {
  getDefaultReservoirParams,
  calculateInjectivity,
  calculateMaterialBalance,
  evaluateWhatIf,
  WhatIfScenario,
  WhatIfResult,
} from '../physics/darcy';

const router = Router();
const provider = new InMemoryTwinDataProvider();
const DATABRICKS_AVAILABLE = isDatabricksAvailable();
let databricksWorking = false; // tracks if DB queries actually succeed
if (DATABRICKS_AVAILABLE) console.log('Databricks detected — will attempt Unity Catalog tables');
else console.log('No Databricks credentials — using in-memory mock data');

/** Try Databricks, fall back to mock on any failure */
async function tryDatabricks<T>(dbFn: () => Promise<T>, mockFn: () => Promise<T>): Promise<T> {
  if (DATABRICKS_AVAILABLE) {
    try {
      const result = await dbFn();
      if (!databricksWorking) {
        databricksWorking = true;
        console.log('Databricks SQL queries working — using live data');
      }
      return result;
    } catch (err: any) {
      console.warn('Databricks query failed, falling back to mock:', err?.message || err);
    }
  }
  return mockFn();
}

// Cache decline curves (expensive to compute)
let declineCurveCache: DeclineCurveResult[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 60_000; // 1 minute

/**
 * GET /api/production/decline-curves
 *
 * Returns Arps decline curve analysis for all producer wells.
 * Each well has fitted parameters, production history, and forecast.
 */
router.get('/decline-curves', async (_req: Request, res: Response) => {
  const now = Date.now();
  if (declineCurveCache && now - cacheTimestamp < CACHE_TTL) {
    return res.json(declineCurveCache);
  }

  try {
    // Get twin state for current well data
    const state = await provider.loadState();
    const producers = state.wells.filter((w: any) => w.type === 'producer');

    const results: DeclineCurveResult[] = producers.map((well: any, idx: number) => {
      // Generate physics-based production history
      const monthsOn = 24 + (idx * 3); // 24-72 months on production
      const seed = well.id.charCodeAt(2) * 1000 + well.id.charCodeAt(3);
      const history = generateProductionHistory(
        well.id,
        well.name,
        well.oilRate,
        monthsOn,
        seed
      );

      // Fit Arps model to the generated history
      const historyForFit = history.map(h => ({ month: h.month, rate: h.actual }));
      const fit = fitDeclineCurve(historyForFit);

      // Generate 36-month forecast
      const forecast = [];
      const lastMonth = history[history.length - 1].month;
      const lastCumulative = history[history.length - 1].cumulative;
      let cumulative = lastCumulative;

      for (let m = 1; m <= 36; m++) {
        const t = lastMonth + m;
        const predicted = arpsRate(fit.params, t);
        cumulative += predicted * 30.44;

        const forecastDate = new Date();
        forecastDate.setMonth(forecastDate.getMonth() + m);

        forecast.push({
          month: t,
          date: forecastDate.toISOString().slice(0, 10),
          actual: 0, // no actual data for forecast
          predicted: Math.round(predicted * 10) / 10,
          cumulative: Math.round(cumulative),
        });
      }

      // EUR calculation
      const eur = calculateEUR(fit.params, 5); // 5 bbl/d economic limit
      const remainingReserves = eur - lastCumulative;

      return {
        wellId: well.id,
        wellName: well.name,
        params: fit.params,
        declineType: fit.declineType,
        r2: Math.round(fit.r2 * 1000) / 1000,
        eur: Math.round(eur),
        remainingReserves: Math.round(Math.max(0, remainingReserves)),
        history,
        forecast,
      };
    });

    declineCurveCache = results;
    cacheTimestamp = now;
    res.json(results);
  } catch (err) {
    console.error('Decline curve error:', err);
    res.status(500).json({ error: 'Failed to compute decline curves' });
  }
});

/**
 * GET /api/production/well-analytics
 *
 * Full multi-stream analytics for all producer wells:
 * oil, gas, water, pressures, CO2 concentration, water cut, GOR,
 * health scores, trends, and performance vs model.
 */
let analyticsCache: WellAnalytics[] | null = null;
let analyticsCacheTs = 0;

router.get('/well-analytics', async (_req: Request, res: Response) => {
  const now = Date.now();
  if (analyticsCache && now - analyticsCacheTs < CACHE_TTL) {
    return res.json(analyticsCache);
  }

  try {
    let results: WellAnalytics[];
    let usedDatabricks = false;

    if (DATABRICKS_AVAILABLE) {
      try {
      // Query production history from Databricks
      const wells = await executeQuery(`SELECT * FROM ${table('bronze_wells')} WHERE well_type = 'producer'`);
      const historyRows = await executeQuery(
        `SELECT * FROM ${table('silver_production_history')} ORDER BY well_id, month`
      );

      // Group history by well
      const histByWell: Record<string, any[]> = {};
      for (const r of historyRows) {
        const wid = r.well_id;
        if (!histByWell[wid]) histByWell[wid] = [];
        histByWell[wid].push(r);
      }

      results = wells.map((well: any) => {
        const hist = histByWell[well.well_id] || [];
        const monthsOn = hist.length > 0 ? hist.length - 1 : 24;

        // Fit Arps to actual Databricks data
        const histForFit = hist.map((h: any) => ({ month: h.month, rate: h.oil_rate }));
        const fit = fitDeclineCurve(histForFit);
        const eur = calculateEUR(fit.params, 5);

        const lastActual = hist.length > 0 ? hist[hist.length - 1].oil_rate : well.oil_rate;
        const lastPredicted = arpsRate(fit.params, monthsOn);
        const gap = lastActual - lastPredicted;

        // Trends from last 3 vs prior 3
        const recent3 = hist.slice(-3);
        const prior3 = hist.slice(-6, -3);
        const avg = (arr: any[], key: string) => arr.length ? arr.reduce((s: number, r: any) => s + (r[key] || 0), 0) / arr.length : 0;
        const trend = (recent: number, prior: number, threshold: number) =>
          recent > prior + threshold ? 'rising' as const : recent < prior - threshold ? 'falling' as const : 'stable' as const;

        // Health score
        let health = 100;
        if (gap < 0) health -= Math.min(30, Math.abs(gap) / lastPredicted * 100);
        if (well.water_cut > 0.7) health -= 20;
        else if (well.water_cut > 0.5) health -= 10;
        if (well.co2_concentration > 15) health -= 15;
        else if (well.co2_concentration > 8) health -= 5;
        health = Math.max(0, Math.min(100, Math.round(health)));

        // Map DB rows to analytics points
        const history = hist.map((h: any) => ({
          month: h.month, date: h.production_date,
          oilRate: h.oil_rate, oilPredicted: arpsRate(fit.params, h.month),
          gasRate: h.gas_rate, waterRate: h.water_rate,
          waterCut: h.water_cut, gor: h.gor,
          co2Concentration: h.co2_concentration,
          tubingPressure: h.tubing_pressure, casingPressure: h.casing_pressure, bhp: h.bhp,
          cumOil: h.cum_oil, cumGas: h.cum_gas, cumWater: h.cum_water,
        }));

        // 24-month forecast
        const forecast = [];
        let cumOil = hist.length > 0 ? hist[hist.length - 1].cum_oil : 0;
        for (let m = 1; m <= 24; m++) {
          const ft = monthsOn + m;
          const oilPredicted = arpsRate(fit.params, ft);
          cumOil += oilPredicted * 30.44;
          const date = new Date();
          date.setMonth(date.getMonth() + m);
          forecast.push({
            month: ft, date: date.toISOString().slice(0, 10),
            oilRate: 0, oilPredicted: Math.round(oilPredicted * 10) / 10,
            gasRate: 0, waterRate: 0, waterCut: 0, gor: 0, co2Concentration: 0,
            tubingPressure: 0, casingPressure: 0, bhp: 0,
            cumOil: Math.round(cumOil), cumGas: 0, cumWater: 0,
          });
        }

        const cumProd = hist.length > 0 ? hist[hist.length - 1].cum_oil : 0;

        return {
          wellId: well.well_id, wellName: well.well_name,
          declineParams: fit.params, declineType: fit.declineType,
          r2: Math.round(fit.r2 * 1000) / 1000,
          eur, remainingReserves: Math.max(0, eur - cumProd),
          currentRate: lastActual, expectedRate: Math.round(lastPredicted * 10) / 10,
          performanceGap: Math.round(gap * 10) / 10,
          healthScore: health,
          waterCutTrend: trend(avg(recent3, 'water_cut'), avg(prior3, 'water_cut'), 0.02),
          co2Trend: trend(avg(recent3, 'co2_concentration'), avg(prior3, 'co2_concentration'), 1),
          pressureTrend: trend(avg(recent3, 'bhp'), avg(prior3, 'bhp'), 10),
          history, forecast,
        } as WellAnalytics;
      });
      usedDatabricks = true;
      } catch (dbErr: any) {
        console.warn('Databricks well-analytics failed, using mock:', dbErr?.message);
      }
    }

    if (!usedDatabricks) {
      // Fallback: mock data
      const state = await provider.loadState();
      const producers = state.wells.filter((w: any) => w.type === 'producer');
      results = producers.map((well: any, idx: number) => {
        const monthsOn = 24 + (idx * 3);
        const seed = well.id.charCodeAt(2) * 1000 + well.id.charCodeAt(3);
        return generateWellAnalytics(well.id, well.name, well, monthsOn, seed);
      });
    }

    results.sort((a, b) => a.performanceGap - b.performanceGap);
    analyticsCache = results;
    analyticsCacheTs = now;
    res.json(results);
  } catch (err) {
    console.error('Well analytics error:', err);
    res.status(500).json({ error: 'Failed to compute well analytics' });
  }
});

/**
 * POST /api/production/what-if
 *
 * Evaluates a what-if scenario using Darcy flow and material balance.
 *
 * Body: {
 *   injectionRateChange: number (-0.5 to 0.5),
 *   wagRatioChange: number (-0.5 to 0.5),
 *   chokeChange: number (-0.5 to 0.5),
 *   co2PriceChange: number ($/mcf change),
 *   patternId?: string (optional, defaults to all patterns)
 * }
 */
router.post('/what-if', async (req: Request, res: Response) => {
  try {
    const scenario: WhatIfScenario = {
      injectionRateChange: Number(req.body.injectionRateChange) || 0,
      wagRatioChange: Number(req.body.wagRatioChange) || 0,
      chokeChange: Number(req.body.chokeChange) || 0,
      co2PriceChange: Number(req.body.co2PriceChange) || 0,
    };
    const targetPattern = req.body.patternId as string | undefined;

    const state = await provider.loadState();

    // Get patterns and their wells
    const patterns = targetPattern
      ? state.patterns.filter((p: any) => p.id === targetPattern)
      : state.patterns;

    const results: WhatIfResult[] = [];
    let totalDailyImpact = 0;

    for (const pattern of patterns) {
      const reservoir = getDefaultReservoirParams(pattern.id);
      const producers = state.wells.filter(
        (w: any) => w.type === 'producer' && w.patternId === pattern.id
      );
      const injectors = state.wells.filter(
        (w: any) => (w.type === 'injector' || w.type === 'WAG') && w.patternId === pattern.id
      );

      const totalInjRate = injectors.reduce((s: number, w: any) => s + (w.co2InjRate || 0), 0);

      // Calculate economics for each producer
      const fieldOilRate = state.wells
        .filter((w: any) => w.type === 'producer')
        .reduce((s: number, w: any) => s + w.oilRate, 0);

      for (const well of producers) {
        // Compute current netback
        const co2Alloc = fieldOilRate > 0
          ? (well.oilRate / fieldOilRate) * totalInjRate * 1.05
          : 0;
        const revenue = well.oilRate * 72 + well.gasRate * 3.2;
        const loe = well.oilRate * 8.5 + well.waterRate * 0.45;
        const transport = well.oilRate * 2.5 + well.gasRate * 0.15;
        const boe = well.oilRate + well.gasRate / 6;
        const netback = boe > 0 ? (revenue - co2Alloc - loe - transport) / boe : 0;

        const result = evaluateWhatIf(
          well.id,
          well.name,
          well.oilRate,
          pattern.currentPressure,
          totalInjRate / Math.max(1, producers.length), // per-well allocation
          netback,
          reservoir,
          scenario
        );

        results.push(result);
        totalDailyImpact += result.dailyRevenueImpact;
      }
    }

    res.json({
      scenario,
      targetPattern: targetPattern || 'all',
      results,
      summary: {
        totalDailyImpact: Math.round(totalDailyImpact),
        totalAnnualImpact: Math.round(totalDailyImpact * 365),
        wellsAffected: results.length,
        avgOilRateChange: Math.round(
          results.reduce((s, r) => s + r.oilRateChange, 0) / results.length * 10
        ) / 10,
        highRiskWells: results.filter(r => r.breakthroughRisk === 'high').length,
      },
    });
  } catch (err) {
    console.error('What-if error:', err);
    res.status(500).json({ error: 'Failed to evaluate scenario' });
  }
});

/**
 * GET /api/production/reservoir-status
 *
 * Returns reservoir physics status per pattern:
 * injectivity, material balance, pressure status.
 */
router.get('/reservoir-status', async (_req: Request, res: Response) => {
  try {
    const state = await provider.loadState();

    const patternStatus = state.patterns.map((pattern: any) => {
      const reservoir = getDefaultReservoirParams(pattern.id);
      const injectivity = calculateInjectivity(reservoir, pattern.currentPressure, 2);

      const producers = state.wells.filter(
        (w: any) => w.type === 'producer' && w.patternId === pattern.id
      );
      const totalOil = producers.reduce((s: number, w: any) => s + w.oilRate, 0);

      // Estimate cumulative production (rate × months × 30.44)
      const monthsOn = pattern.cycleNumber * 6; // ~6 months per cycle
      const estCumulativeOil = totalOil * monthsOn * 30.44;
      const estCumulativeCO2 = pattern.co2Slug || 0;

      const mb = calculateMaterialBalance(
        reservoir,
        pattern.currentPressure,
        estCumulativeOil,
        estCumulativeCO2
      );

      return {
        patternId: pattern.id,
        patternName: pattern.name,
        reservoir: {
          permeability: reservoir.permeability,
          porosity: reservoir.porosity,
          thickness: reservoir.thickness,
          initialPressure: reservoir.initialPressure,
        },
        injectivity,
        materialBalance: mb,
        currentPhase: pattern.currentPhase,
        cycleNumber: pattern.cycleNumber,
        pressureDeficit: pattern.targetPressure - pattern.currentPressure,
      };
    });

    res.json(patternStatus);
  } catch (err) {
    console.error('Reservoir status error:', err);
    res.status(500).json({ error: 'Failed to compute reservoir status' });
  }
});

/**
 * GET /api/production/recommendations
 *
 * AI-driven optimization recommendations with $ impact,
 * backed by reservoir physics (not LLM — deterministic engineering rules).
 */
router.get('/recommendations', async (_req: Request, res: Response) => {
  try {
    let state: any;
    if (DATABRICKS_AVAILABLE) {
      try {
      // Build state from Databricks tables
      const wells = await executeQuery(`SELECT * FROM ${table('bronze_wells')}`);
      const patterns = await executeQuery(`SELECT * FROM ${table('bronze_patterns')}`);
      state = {
        wells: wells.map((w: any) => ({
          id: w.well_id, name: w.well_name, type: w.well_type, status: w.status,
          patternId: w.pattern_id, padId: w.pad_id,
          oilRate: w.oil_rate, gasRate: w.gas_rate, waterRate: w.water_rate,
          co2InjRate: w.co2_inj_rate, waterInjRate: w.water_inj_rate,
          chokePercent: w.choke_percent, tubingPressure: w.tubing_pressure,
          casingPressure: w.casing_pressure, bottomholePressure: w.bottomhole_pressure,
          co2Concentration: w.co2_concentration, gor: w.gor, waterCut: w.water_cut,
        })),
        patterns: patterns.map((p: any) => ({
          id: p.pattern_id, name: p.pattern_name, type: p.pattern_type,
          currentPhase: p.current_phase, cycleNumber: p.cycle_number,
          targetPressure: p.target_pressure, currentPressure: p.current_pressure,
          co2Slug: p.co2_slug, waterSlug: p.water_slug,
          producerIds: [], injectorIds: [], monitorIds: [],
        })),
      };
      // Link wells to patterns
      for (const p of state.patterns) {
        p.producerIds = state.wells.filter((w: any) => w.patternId === p.id && w.type === 'producer').map((w: any) => w.id);
        p.injectorIds = state.wells.filter((w: any) => w.patternId === p.id && (w.type === 'injector' || w.type === 'WAG')).map((w: any) => w.id);
      }
      } catch (dbErr: any) {
        console.warn('Databricks recommendations failed, using mock:', dbErr?.message);
        state = await provider.loadState();
      }
    } else {
      state = await provider.loadState();
    }

    const recommendations: Array<{
      id: string;
      priority: 'high' | 'medium' | 'low';
      title: string;
      description: string;
      affectedEntities: string[];
      estimatedImpact: {
        oilRateChange: number;
        dailyRevenue: number;
        annualRevenue: number;
      };
      physicsRationale: string;
      risk: string;
    }> = [];

    // Analyze each pattern for optimization opportunities
    for (const pattern of state.patterns) {
      const reservoir = getDefaultReservoirParams(pattern.id);
      const producers = state.wells.filter(
        (w: any) => w.type === 'producer' && w.patternId === pattern.id
      );
      const injectors = state.wells.filter(
        (w: any) => (w.type === 'injector' || w.type === 'WAG') && w.patternId === pattern.id
      );

      const pressureDeficit = pattern.targetPressure - pattern.currentPressure;
      const totalOilRate = producers.reduce((s: number, w: any) => s + w.oilRate, 0);
      const totalInjRate = injectors.reduce((s: number, w: any) => s + (w.co2InjRate || 0), 0);

      // Rule 1: Pressure below target — increase injection
      if (pressureDeficit > 100) {
        const inj = calculateInjectivity(reservoir, pattern.currentPressure);
        const rateIncrease = Math.min(pressureDeficit * inj.injectivityIndex * 0.1, totalInjRate * 0.15);
        const oilResponse = totalOilRate * (rateIncrease / totalInjRate) * 0.4; // 40% conversion
        recommendations.push({
          id: `REC-${pattern.id}-INJ`,
          priority: pressureDeficit > 200 ? 'high' : 'medium',
          title: `Increase CO2 injection on ${pattern.name}`,
          description: `Reservoir pressure is ${pressureDeficit} psi below target. Increase injection by ${Math.round(rateIncrease)} mcf/d to restore pressure support and improve sweep efficiency.`,
          affectedEntities: [...injectors.map((w: any) => w.id), ...producers.map((w: any) => w.id)],
          estimatedImpact: {
            oilRateChange: Math.round(oilResponse),
            dailyRevenue: Math.round(oilResponse * 72 - rateIncrease * 1.05),
            annualRevenue: Math.round((oilResponse * 72 - rateIncrease * 1.05) * 365),
          },
          physicsRationale: `Darcy flow: II = ${inj.injectivityIndex.toFixed(2)} bbl/d/psi. Pressure margin to fracture: ${inj.pressureMargin} psi. Rate increase within safe operating envelope.`,
          risk: pressureDeficit > 300 ? 'Medium — significant pressure deficit may indicate conformance issues' : 'Low — routine pressure maintenance adjustment',
        });
      }

      // Rule 2: High water cut wells — candidates for choke optimization
      for (const well of producers) {
        if (well.waterCut > 0.6) {
          const chokeReduction = well.waterCut > 0.75 ? 0.2 : 0.1;
          const oilLoss = well.oilRate * chokeReduction * 0.3; // oil drops less than choke change
          const waterSaved = well.waterRate * chokeReduction * 0.8;
          const netSavings = waterSaved * 0.45 - oilLoss * 72; // water disposal cost vs oil revenue

          if (netSavings > 0) {
            recommendations.push({
              id: `REC-${well.id}-CHOKE`,
              priority: 'medium',
              title: `Optimize choke on ${well.name}`,
              description: `Water cut at ${(well.waterCut * 100).toFixed(0)}%. Reducing choke by ${(chokeReduction * 100).toFixed(0)}% saves $${Math.round(netSavings)}/d in water disposal while limiting oil impact.`,
              affectedEntities: [well.id],
              estimatedImpact: {
                oilRateChange: -Math.round(oilLoss),
                dailyRevenue: Math.round(netSavings),
                annualRevenue: Math.round(netSavings * 365),
              },
              physicsRationale: `Water cut = ${(well.waterCut * 100).toFixed(1)}% indicates water coning or channeling. Choke-back reduces drawdown, improving oil/water ratio. Kv/Kh ratio suggests ${well.waterCut > 0.75 ? 'significant coning' : 'moderate channeling'}.`,
              risk: 'Low — reversible choke adjustment with 48-hour monitoring period',
            });
          }
        }
      }

      // Rule 3: WAG cycle timing
      if (pattern.currentPhase === 'CO2_injection' && pattern.cycleNumber > 3) {
        const avgCO2Concentration = producers.reduce(
          (s: number, w: any) => s + (w.co2Concentration || 0), 0
        ) / producers.length;

        if (avgCO2Concentration > 8) {
          recommendations.push({
            id: `REC-${pattern.id}-WAG`,
            priority: 'high',
            title: `Switch ${pattern.name} to water injection`,
            description: `Average produced CO2 concentration at ${avgCO2Concentration.toFixed(1)} mol% indicates early breakthrough. Switch to water slug to improve conformance and reduce CO2 recycling costs.`,
            affectedEntities: injectors.map((w: any) => w.id),
            estimatedImpact: {
              oilRateChange: Math.round(totalOilRate * 0.05), // slight improvement from better sweep
              dailyRevenue: Math.round(totalInjRate * 1.05 * 0.3), // 30% CO2 cost savings during water slug
              annualRevenue: Math.round(totalInjRate * 1.05 * 0.3 * 180), // ~6 month water slug
            },
            physicsRationale: `CO2 concentration ${avgCO2Concentration.toFixed(1)} mol% exceeds 8% threshold. Mobility ratio M = μ_oil/μ_CO2 = ${(reservoir.viscosityOil / reservoir.viscosityCO2).toFixed(0)} indicates viscous fingering risk. Water slug will improve areal sweep.`,
            risk: 'Low — standard WAG cycle transition per pattern optimization plan',
          });
        }
      }
    }

    // Sort by priority
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    recommendations.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

    const totalAnnualImpact = recommendations.reduce(
      (s, r) => s + r.estimatedImpact.annualRevenue, 0
    );

    res.json({
      recommendations,
      summary: {
        count: recommendations.length,
        highPriority: recommendations.filter(r => r.priority === 'high').length,
        totalAnnualImpact: Math.round(totalAnnualImpact),
      },
    });
  } catch (err) {
    console.error('Recommendations error:', err);
    res.status(500).json({ error: 'Failed to generate recommendations' });
  }
});

export default router;
