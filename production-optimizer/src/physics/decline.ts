/**
 * Arps Decline Curve Analysis — real petroleum engineering models.
 *
 * Three decline types:
 *   Exponential (b=0): q(t) = qi * exp(-Di * t)
 *   Hyperbolic (0<b<1): q(t) = qi / (1 + b * Di * t)^(1/b)
 *   Harmonic (b=1):     q(t) = qi / (1 + Di * t)
 *
 * Units: qi in bbl/d, Di in 1/month, t in months
 */

export interface DeclineParams {
  qi: number;    // initial production rate (bbl/d)
  Di: number;    // initial decline rate (1/month, nominal)
  b: number;     // decline exponent (0 = exponential, 0-1 = hyperbolic, 1 = harmonic)
}

export interface DeclinePoint {
  month: number;
  date: string;       // ISO date
  actual: number;     // actual production (bbl/d)
  predicted: number;  // Arps model prediction (bbl/d)
  cumulative: number; // cumulative production (bbl)
}

export interface DeclineCurveResult {
  wellId: string;
  wellName: string;
  params: DeclineParams;
  declineType: 'exponential' | 'hyperbolic' | 'harmonic';
  r2: number;              // goodness of fit
  eur: number;             // estimated ultimate recovery (bbl)
  remainingReserves: number;
  history: DeclinePoint[];
  forecast: DeclinePoint[];
}

/** Evaluate Arps equation at time t (months) */
export function arpsRate(params: DeclineParams, t: number): number {
  const { qi, Di, b } = params;
  if (t < 0) return qi;

  if (b === 0) {
    // Exponential
    return qi * Math.exp(-Di * t);
  } else if (b === 1) {
    // Harmonic
    return qi / (1 + Di * t);
  } else {
    // Hyperbolic
    return qi / Math.pow(1 + b * Di * t, 1 / b);
  }
}

/** Cumulative production from Arps (analytical integral) */
export function arpsCumulative(params: DeclineParams, t: number): number {
  const { qi, Di, b } = params;
  if (t <= 0) return 0;

  // Convert to daily (multiply by 30.44 days/month for cumulative)
  const daysPerMonth = 30.44;

  if (b === 0) {
    // Np = (qi / Di) * (1 - exp(-Di * t))
    return (qi / Di) * (1 - Math.exp(-Di * t)) * daysPerMonth;
  } else if (b === 1) {
    // Np = (qi / Di) * ln(1 + Di * t)
    return (qi / Di) * Math.log(1 + Di * t) * daysPerMonth;
  } else {
    // Np = (qi / ((1-b) * Di)) * (1 - (1 + b*Di*t)^((b-1)/b))
    const term = Math.pow(1 + b * Di * t, (b - 1) / b);
    return (qi / ((1 - b) * Di)) * (1 - term) * daysPerMonth;
  }
}

/** Effective decline rate at time t */
export function effectiveDeclineRate(params: DeclineParams, t: number): number {
  const { Di, b } = params;
  // De(t) = Di / (1 + b * Di * t)
  return Di / (1 + b * Di * t);
}

/**
 * Fit Arps parameters to production history using least-squares.
 * Uses grid search + refinement (no external dependencies).
 */
export function fitDeclineCurve(
  history: Array<{ month: number; rate: number }>
): { params: DeclineParams; r2: number; declineType: 'exponential' | 'hyperbolic' | 'harmonic' } {
  if (history.length < 3) {
    return {
      params: { qi: history[0]?.rate ?? 100, Di: 0.05, b: 0.5 },
      r2: 0,
      declineType: 'hyperbolic',
    };
  }

  // Find peak rate for qi estimate
  const peakRate = Math.max(...history.map(h => h.rate));
  const meanRate = history.reduce((s, h) => s + h.rate, 0) / history.length;

  let bestParams: DeclineParams = { qi: peakRate, Di: 0.05, b: 0.5 };
  let bestSSE = Infinity;

  // Grid search over parameter space
  const qiRange = [peakRate * 0.9, peakRate, peakRate * 1.1, peakRate * 1.2];
  const diRange = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20];
  const bRange = [0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0];

  for (const qi of qiRange) {
    for (const Di of diRange) {
      for (const b of bRange) {
        const params = { qi, Di, b };
        let sse = 0;
        for (const h of history) {
          const pred = arpsRate(params, h.month);
          sse += (h.rate - pred) ** 2;
        }
        if (sse < bestSSE) {
          bestSSE = sse;
          bestParams = params;
        }
      }
    }
  }

  // Refine with finer grid around best
  const refineQi = [bestParams.qi * 0.95, bestParams.qi, bestParams.qi * 1.05];
  const refineDi = [bestParams.Di * 0.8, bestParams.Di * 0.9, bestParams.Di, bestParams.Di * 1.1, bestParams.Di * 1.2];
  const refineB = [
    Math.max(0, bestParams.b - 0.1),
    bestParams.b,
    Math.min(1, bestParams.b + 0.1),
  ];

  for (const qi of refineQi) {
    for (const Di of refineDi) {
      for (const b of refineB) {
        const params = { qi, Di, b };
        let sse = 0;
        for (const h of history) {
          const pred = arpsRate(params, h.month);
          sse += (h.rate - pred) ** 2;
        }
        if (sse < bestSSE) {
          bestSSE = sse;
          bestParams = params;
        }
      }
    }
  }

  // Calculate R²
  const ssTot = history.reduce((s, h) => s + (h.rate - meanRate) ** 2, 0);
  const r2 = ssTot > 0 ? 1 - bestSSE / ssTot : 0;

  // Classify decline type
  let declineType: 'exponential' | 'hyperbolic' | 'harmonic';
  if (bestParams.b < 0.05) declineType = 'exponential';
  else if (bestParams.b > 0.95) declineType = 'harmonic';
  else declineType = 'hyperbolic';

  return { params: bestParams, r2, declineType };
}

/**
 * Generate realistic production history for a well using Arps + noise.
 * This creates physics-based synthetic data (not random — follows real decline behavior).
 */
export function generateProductionHistory(
  wellId: string,
  wellName: string,
  currentRate: number,
  monthsOnProduction: number,
  seed: number
): DeclinePoint[] {
  // Derive Arps params from current state
  // Assume well started at higher rate and declined to current
  const rng = seededRandom(seed);

  // Delaware Basin CO2-EOR typical parameters
  const b = 0.4 + rng() * 0.4;           // 0.4-0.8 typical for CO2 flood
  const Di = 0.03 + rng() * 0.07;        // 3-10% monthly decline
  // Back-calculate qi from current rate: q(t) = qi / (1 + b*Di*t)^(1/b)
  // qi = q(t) * (1 + b*Di*t)^(1/b)
  const qi = currentRate * Math.pow(1 + b * Di * monthsOnProduction, 1 / b);

  const params: DeclineParams = { qi, Di, b };
  const history: DeclinePoint[] = [];
  let cumulative = 0;

  // Generate start date (monthsOnProduction months ago)
  const now = new Date();
  const startDate = new Date(now);
  startDate.setMonth(startDate.getMonth() - monthsOnProduction);

  for (let m = 0; m <= monthsOnProduction; m++) {
    const predicted = arpsRate(params, m);
    // Add realistic noise (±5-10% production variance)
    const noise = 1 + (rng() - 0.5) * 0.12;
    // CO2 flood response: add bump at ~40-60% of well life (tertiary recovery response)
    const floodResponse = m > monthsOnProduction * 0.3 && m < monthsOnProduction * 0.7
      ? 1 + 0.15 * Math.sin(Math.PI * (m - monthsOnProduction * 0.3) / (monthsOnProduction * 0.4))
      : 1;
    const actual = Math.max(10, predicted * noise * floodResponse);
    cumulative += actual * 30.44; // monthly cumulative

    const date = new Date(startDate);
    date.setMonth(date.getMonth() + m);

    history.push({
      month: m,
      date: date.toISOString().slice(0, 10),
      actual: Math.round(actual * 10) / 10,
      predicted: Math.round(predicted * 10) / 10,
      cumulative: Math.round(cumulative),
    });
  }

  return history;
}

/* ------------------------------------------------------------------ */
/*  Full well analytics — multi-stream production history              */
/* ------------------------------------------------------------------ */

export interface WellAnalyticsPoint {
  month: number;
  date: string;
  oilRate: number;
  oilPredicted: number;
  gasRate: number;
  waterRate: number;
  waterCut: number;
  gor: number;
  co2Concentration: number;
  tubingPressure: number;
  casingPressure: number;
  bhp: number;
  cumOil: number;
  cumGas: number;
  cumWater: number;
}

export interface WellAnalytics {
  wellId: string;
  wellName: string;
  declineParams: DeclineParams;
  declineType: 'exponential' | 'hyperbolic' | 'harmonic';
  r2: number;
  eur: number;
  remainingReserves: number;
  currentRate: number;
  expectedRate: number;
  performanceGap: number;       // actual - expected (negative = underperforming)
  healthScore: number;          // 0-100
  waterCutTrend: 'rising' | 'stable' | 'falling';
  co2Trend: 'rising' | 'stable' | 'falling';
  pressureTrend: 'rising' | 'stable' | 'falling';
  history: WellAnalyticsPoint[];
  forecast: WellAnalyticsPoint[];
}

/**
 * Generate comprehensive well analytics with all production streams.
 * Physics-based: oil follows Arps, gas/water/pressure follow correlated models.
 */
export function generateWellAnalytics(
  wellId: string,
  wellName: string,
  well: { oilRate: number; gasRate: number; waterRate: number; waterCut: number;
    gor: number; co2Concentration: number; tubingPressure: number;
    casingPressure: number; bottomholePressure: number },
  monthsOnProduction: number,
  seed: number
): WellAnalytics {
  const rng = seededRandom(seed);

  // Arps parameters for oil
  const b = 0.3 + rng() * 0.4;           // 0.3-0.7 (realistic CO2-EOR)
  const Di = 0.01 + rng() * 0.03;        // 1-4% monthly (10-35% annual)
  const qi = well.oilRate * Math.pow(1 + b * Di * monthsOnProduction, 1 / b);
  const params: DeclineParams = { qi, Di, b };

  // Initial conditions (back-calculated)
  const initialGOR = well.gor * 0.6;             // GOR increases over time
  const initialWaterCut = Math.max(0.05, well.waterCut * 0.3);  // water cut rises
  const initialCO2 = Math.max(0.5, well.co2Concentration * 0.1); // CO2 starts low
  const initialTP = well.tubingPressure * 1.3;    // pressure declines
  const initialCP = well.casingPressure * 1.2;
  const initialBHP = well.bottomholePressure * 1.15;

  const history: WellAnalyticsPoint[] = [];
  let cumOil = 0, cumGas = 0, cumWater = 0;

  const startDate = new Date();
  startDate.setMonth(startDate.getMonth() - monthsOnProduction);

  for (let m = 0; m <= monthsOnProduction; m++) {
    const t = m / monthsOnProduction; // 0 to 1 normalized time

    // Oil: Arps + noise + CO2 flood response
    const oilPredicted = arpsRate(params, m);
    const floodResponse = t > 0.3 && t < 0.7
      ? 1 + 0.12 * Math.sin(Math.PI * (t - 0.3) / 0.4)
      : 1;
    const oilRate = Math.max(5, oilPredicted * (1 + (rng() - 0.5) * 0.1) * floodResponse);

    // GOR: increases as reservoir depletes (solution gas liberation)
    const gor = initialGOR + (well.gor - initialGOR) * Math.pow(t, 0.8) + (rng() - 0.5) * 30;

    // Gas: GOR × oil rate
    const gasRate = oilRate * Math.max(100, gor) / 1000; // mcf/d

    // Water cut: S-curve increase (Buckley-Leverett inspired)
    const wcBase = initialWaterCut + (well.waterCut - initialWaterCut) / (1 + Math.exp(-8 * (t - 0.5)));
    const waterCut = Math.min(0.95, Math.max(0, wcBase + (rng() - 0.5) * 0.03));

    // Water rate: from water cut and total liquid
    const waterRate = oilRate * waterCut / (1 - waterCut);

    // CO2 concentration: rises after breakthrough (~40% of well life)
    const co2Base = t < 0.35 ? initialCO2 * (1 + t)
      : initialCO2 + (well.co2Concentration - initialCO2) * Math.pow((t - 0.35) / 0.65, 1.5);
    const co2Concentration = Math.min(80, Math.max(0, co2Base + (rng() - 0.5) * 1.5));

    // Pressures: gradual decline with depletion
    const pDecay = 1 - t * 0.25; // 25% decline over well life
    const tubingPressure = Math.max(100, initialTP * pDecay + (rng() - 0.5) * 20);
    const casingPressure = Math.max(200, initialCP * pDecay + (rng() - 0.5) * 15);
    const bhp = Math.max(500, initialBHP * (1 - t * 0.15) + (rng() - 0.5) * 30);

    cumOil += oilRate * 30.44;
    cumGas += gasRate * 30.44;
    cumWater += waterRate * 30.44;

    const date = new Date(startDate);
    date.setMonth(date.getMonth() + m);

    history.push({
      month: m, date: date.toISOString().slice(0, 10),
      oilRate: rd(oilRate), oilPredicted: rd(oilPredicted),
      gasRate: rd(gasRate), waterRate: rd(waterRate),
      waterCut: rd(waterCut, 3), gor: rd(gor),
      co2Concentration: rd(co2Concentration, 1),
      tubingPressure: rd(tubingPressure), casingPressure: rd(casingPressure), bhp: rd(bhp),
      cumOil: Math.round(cumOil), cumGas: Math.round(cumGas), cumWater: Math.round(cumWater),
    });
  }

  // Forecast 24 months
  const forecast: WellAnalyticsPoint[] = [];
  for (let m = 1; m <= 24; m++) {
    const ft = monthsOnProduction + m;
    const t = ft / (monthsOnProduction + 24);
    const oilPredicted = arpsRate(params, ft);
    const gor = well.gor + m * 3;
    const gasRate = oilPredicted * gor / 1000;
    const wc = Math.min(0.95, well.waterCut + m * 0.005);
    const waterRate = oilPredicted * wc / (1 - wc);

    cumOil += oilPredicted * 30.44;
    cumGas += gasRate * 30.44;
    cumWater += waterRate * 30.44;

    const date = new Date();
    date.setMonth(date.getMonth() + m);

    forecast.push({
      month: ft, date: date.toISOString().slice(0, 10),
      oilRate: 0, oilPredicted: rd(oilPredicted),
      gasRate: rd(gasRate), waterRate: rd(waterRate),
      waterCut: rd(wc, 3), gor: rd(gor),
      co2Concentration: rd(well.co2Concentration + m * 0.5, 1),
      tubingPressure: 0, casingPressure: 0, bhp: 0,
      cumOil: Math.round(cumOil), cumGas: Math.round(cumGas), cumWater: Math.round(cumWater),
    });
  }

  // Fit quality
  const histForFit = history.map(h => ({ month: h.month, rate: h.oilRate }));
  const fit = fitDeclineCurve(histForFit);
  const eur = calculateEUR(fit.params, 5);
  const lastActual = history[history.length - 1]?.oilRate ?? 0;
  const lastPredicted = arpsRate(fit.params, monthsOnProduction);
  const gap = lastActual - lastPredicted;

  // Trends (compare last 3 months vs prior 3 months)
  const recent3 = history.slice(-3);
  const prior3 = history.slice(-6, -3);
  const avgRecent = (arr: WellAnalyticsPoint[], fn: (p: WellAnalyticsPoint) => number) =>
    arr.length ? arr.reduce((s, p) => s + fn(p), 0) / arr.length : 0;

  const wcRecent = avgRecent(recent3, p => p.waterCut);
  const wcPrior = avgRecent(prior3, p => p.waterCut);
  const co2Recent = avgRecent(recent3, p => p.co2Concentration);
  const co2Prior = avgRecent(prior3, p => p.co2Concentration);
  const pRecent = avgRecent(recent3, p => p.bhp);
  const pPrior = avgRecent(prior3, p => p.bhp);

  const trend = (recent: number, prior: number, threshold: number): 'rising' | 'stable' | 'falling' =>
    recent > prior + threshold ? 'rising' : recent < prior - threshold ? 'falling' : 'stable';

  // Health score: 100 = perfect, penalize for underperformance, high wc, high co2
  let health = 100;
  if (gap < 0) health -= Math.min(30, Math.abs(gap) / lastPredicted * 100);
  if (well.waterCut > 0.7) health -= 20;
  else if (well.waterCut > 0.5) health -= 10;
  if (well.co2Concentration > 15) health -= 15;
  else if (well.co2Concentration > 8) health -= 5;
  health = Math.max(0, Math.min(100, Math.round(health)));

  return {
    wellId, wellName,
    declineParams: fit.params,
    declineType: fit.declineType,
    r2: fit.r2,
    eur, remainingReserves: Math.max(0, eur - cumOil + forecast.reduce((s, f) => s + f.oilPredicted * 30.44, 0)),
    currentRate: lastActual,
    expectedRate: rd(lastPredicted),
    performanceGap: rd(gap),
    healthScore: health,
    waterCutTrend: trend(wcRecent, wcPrior, 0.02),
    co2Trend: trend(co2Recent, co2Prior, 1),
    pressureTrend: trend(pRecent, pPrior, 10),
    history, forecast,
  };
}

function rd(v: number, n = 1): number {
  const f = 10 ** n;
  return Math.round(v * f) / f;
}

/** Simple seeded PRNG for reproducible results */
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/**
 * Calculate EUR (Estimated Ultimate Recovery) to economic limit.
 */
export function calculateEUR(params: DeclineParams, economicLimit: number = 5): number {
  // Find time when rate drops to economic limit
  // q(t) = economicLimit → solve for t
  const { qi, Di, b } = params;
  let tMax: number;

  if (b === 0) {
    tMax = -Math.log(economicLimit / qi) / Di;
  } else {
    tMax = (Math.pow(qi / economicLimit, b) - 1) / (b * Di);
  }

  // Cap at 600 months (50 years)
  tMax = Math.min(tMax, 600);

  return arpsCumulative(params, tMax);
}
