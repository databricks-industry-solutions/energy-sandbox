/**
 * Darcy Flow & Reservoir Physics — real petroleum engineering models.
 *
 * Darcy's Law: Q = (k * A * ΔP) / (μ * L)
 * Injectivity Index: II = Q / (Pwf - Pr)
 * Material Balance: P/Z method for reservoir pressure tracking
 */

export interface ReservoirParams {
  permeability: number;      // md (millidarcies)
  porosity: number;          // fraction (0-1)
  thickness: number;         // ft (net pay)
  area: number;              // acres (drainage area)
  viscosityOil: number;      // cp
  viscosityCO2: number;      // cp (supercritical CO2 ~0.03-0.07 cp)
  compressibility: number;   // 1/psi (total system compressibility)
  initialPressure: number;   // psi (initial reservoir pressure)
  bubblePoint: number;       // psi
  temperature: number;       // °F
  waterSaturation: number;   // fraction (irreducible Sw)
  co2Saturation: number;     // fraction (current CO2 saturation)
}

export interface InjectivityResult {
  injectivityIndex: number;     // bbl/d/psi or mcf/d/psi
  maxInjectionRate: number;     // bbl/d or mcf/d (below fracture pressure)
  fracturePressure: number;     // psi
  currentBHP: number;           // psi
  pressureMargin: number;       // psi (to fracture)
  skinFactor: number;           // dimensionless
}

export interface MaterialBalanceResult {
  currentPressure: number;     // psi
  pressureDepletion: number;   // psi (from initial)
  recoveryFactor: number;      // fraction
  ooip: number;                // bbl (original oil in place)
  cumulativeProduction: number;
  driveIndex: {
    solution: number;          // solution gas drive contribution
    water: number;             // water drive
    co2Flood: number;          // CO2 flood contribution
    compaction: number;        // rock/fluid compaction
  };
}

export interface WhatIfScenario {
  injectionRateChange: number;  // fractional change (-0.5 to +0.5)
  wagRatioChange: number;       // fractional change
  chokeChange: number;          // fractional change
  co2PriceChange: number;       // $/mcf change
}

export interface WhatIfResult {
  wellId: string;
  wellName: string;
  baselineOilRate: number;
  predictedOilRate: number;
  oilRateChange: number;
  baselinePressure: number;
  predictedPressure: number;
  pressureChange: number;
  baselineNetback: number;
  predictedNetback: number;
  netbackChange: number;
  dailyRevenueImpact: number;
  annualRevenueImpact: number;
  breakthroughRisk: 'low' | 'medium' | 'high';
  explanation: string;
}

/** Delaware Basin CO2-EOR typical reservoir parameters */
export function getDefaultReservoirParams(patternId: string): ReservoirParams {
  // Vary slightly by pattern to reflect real geological heterogeneity
  const seed = patternId.charCodeAt(patternId.length - 1);
  const variation = (seed % 10) / 100; // 0-10% variation

  return {
    permeability: 8 + variation * 80,        // 8-16 md (Delaware Basin carbonates)
    porosity: 0.10 + variation * 0.5,         // 10-15%
    thickness: 45 + (seed % 20),              // 45-65 ft net pay
    area: 40 + (seed % 20),                   // 40-60 acres per pattern
    viscosityOil: 1.2 + variation * 5,        // 1.2-1.7 cp (light oil)
    viscosityCO2: 0.04 + variation * 0.3,     // 0.04-0.07 cp (supercritical)
    compressibility: 12e-6 + variation * 50e-6, // 12-17 × 10⁻⁶ 1/psi
    initialPressure: 3500 + (seed % 500),     // 3500-4000 psi
    bubblePoint: 2200 + (seed % 300),         // 2200-2500 psi
    temperature: 140 + (seed % 20),           // 140-160 °F
    waterSaturation: 0.25 + variation * 0.5,  // 25-30% Swi
    co2Saturation: 0.15 + variation * 1.0,    // 15-25% current CO2
  };
}

/**
 * Calculate injectivity index using Darcy's radial flow equation.
 *
 * II = (0.00708 * k * h) / (μ * (ln(re/rw) + s))
 *
 * where:
 *   k = permeability (md)
 *   h = thickness (ft)
 *   μ = viscosity (cp) — use CO2 viscosity for injection
 *   re = drainage radius (ft)
 *   rw = wellbore radius (ft, typically 0.354)
 *   s = skin factor
 */
export function calculateInjectivity(
  reservoir: ReservoirParams,
  currentBHP: number,
  skinFactor: number = 0
): InjectivityResult {
  const rw = 0.354; // ft (8.5" hole)
  // re from drainage area: A = π * re²
  const re = Math.sqrt(reservoir.area * 43560 / Math.PI); // acres → ft²

  // Radial flow: II = 0.00708 * k * h / (μ * (ln(re/rw) + s))
  const II = (0.00708 * reservoir.permeability * reservoir.thickness) /
    (reservoir.viscosityCO2 * (Math.log(re / rw) + skinFactor));

  // Fracture pressure: ~0.7 psi/ft depth (typical Delaware Basin)
  const depth = 7500 + (reservoir.thickness * 10); // approximate depth
  const fracturePressure = depth * 0.7;

  // Max injection rate: don't exceed fracture pressure
  const pressureMargin = fracturePressure - currentBHP;
  const maxInjectionRate = II * pressureMargin;

  return {
    injectivityIndex: Math.round(II * 100) / 100,
    maxInjectionRate: Math.round(maxInjectionRate),
    fracturePressure: Math.round(fracturePressure),
    currentBHP,
    pressureMargin: Math.round(pressureMargin),
    skinFactor,
  };
}

/**
 * Material balance — simplified P/Z for gas-drive + CO2 flood.
 *
 * OOIP = (7758 * A * h * φ * (1 - Sw)) / Bo
 * RF = 1 - (P/Pi) * (Boi/Bo) + CO2 sweep contribution
 */
export function calculateMaterialBalance(
  reservoir: ReservoirParams,
  currentPressure: number,
  cumulativeOil: number,
  cumulativeCO2Injected: number
): MaterialBalanceResult {
  // Bo at initial conditions (undersaturated): Bo = 1.2 + 0.0001 * (Pi - Pb)
  const Boi = 1.2 + 0.0001 * Math.max(0, reservoir.initialPressure - reservoir.bubblePoint);
  const Bo = 1.2 + 0.0001 * Math.max(0, currentPressure - reservoir.bubblePoint);

  // OOIP (STB)
  const ooip = (7758 * reservoir.area * reservoir.thickness * reservoir.porosity *
    (1 - reservoir.waterSaturation)) / Boi;

  // Recovery factor
  const rf = cumulativeOil / ooip;

  // Drive indices (simplified)
  const pressureDepletion = reservoir.initialPressure - currentPressure;
  const totalExpansion = reservoir.compressibility * pressureDepletion;

  // CO2 flood contribution: mobility ratio improvement
  const co2Contribution = Math.min(0.4, cumulativeCO2Injected / (ooip * 5)); // 5 MCF/STB PV

  return {
    currentPressure,
    pressureDepletion: Math.round(pressureDepletion),
    recoveryFactor: Math.round(rf * 1000) / 1000,
    ooip: Math.round(ooip),
    cumulativeProduction: Math.round(cumulativeOil),
    driveIndex: {
      solution: Math.round(totalExpansion * 0.3 * 100) / 100,
      water: Math.round(totalExpansion * 0.2 * 100) / 100,
      co2Flood: Math.round(co2Contribution * 100) / 100,
      compaction: Math.round(totalExpansion * 0.1 * 100) / 100,
    },
  };
}

/**
 * What-if scenario analysis — predicts production/economic impact
 * of operational changes using reservoir physics.
 */
export function evaluateWhatIf(
  wellId: string,
  wellName: string,
  currentOilRate: number,
  currentPressure: number,
  currentInjRate: number,
  currentNetback: number,
  reservoir: ReservoirParams,
  scenario: WhatIfScenario,
  oilPrice: number = 72,
  co2Price: number = 1.05
): WhatIfResult {
  // 1. Calculate new injection rate
  const newInjRate = currentInjRate * (1 + scenario.injectionRateChange);

  // 2. Pressure response: ΔP ∝ ΔQ / II
  const II = calculateInjectivity(reservoir, currentPressure).injectivityIndex;
  const injRateChangeMcf = (newInjRate - currentInjRate);
  const pressureResponse = II > 0 ? injRateChangeMcf / II * 0.15 : 0; // damped response
  const newPressure = currentPressure + pressureResponse;

  // 3. Production response: Productivity Index × ΔP (drawdown change)
  // PI = q / (Pr - Pwf), assume Pwf = 0.7 * Pr
  const drawdown = currentPressure * 0.3;
  const PI = currentOilRate / drawdown;

  // Choke effect: linear relationship to production
  const chokeEffect = 1 + scenario.chokeChange * 0.8; // 80% of choke change translates to rate

  // Pressure maintenance effect
  const pressureEffect = newPressure / currentPressure;

  const newOilRate = currentOilRate * chokeEffect * pressureEffect;

  // 4. Economics
  const newCo2Cost = co2Price * (1 + scenario.co2PriceChange) * newInjRate;
  const oldCo2Cost = co2Price * currentInjRate;
  const newRevenue = newOilRate * oilPrice;
  const oldRevenue = currentOilRate * oilPrice;

  // Simplified netback
  const loe = newOilRate * 8.5;
  const transport = newOilRate * 2.5;
  const boe = newOilRate + (newOilRate * 2.5) / 6; // assume GOR ~ 2.5 mcf/bbl
  const newNetback = boe > 0 ? (newRevenue - newCo2Cost - loe - transport) / boe : 0;

  const dailyImpact = newRevenue - oldRevenue - (newCo2Cost - oldCo2Cost);

  // 5. Breakthrough risk
  let breakthroughRisk: 'low' | 'medium' | 'high';
  if (scenario.injectionRateChange > 0.2 || newPressure > reservoir.initialPressure * 0.95) {
    breakthroughRisk = 'high';
  } else if (scenario.injectionRateChange > 0.1 || newPressure > reservoir.initialPressure * 0.85) {
    breakthroughRisk = 'medium';
  } else {
    breakthroughRisk = 'low';
  }

  // 6. Explanation
  const parts: string[] = [];
  if (scenario.injectionRateChange !== 0) {
    const dir = scenario.injectionRateChange > 0 ? 'Increasing' : 'Decreasing';
    parts.push(`${dir} CO2 injection by ${Math.abs(scenario.injectionRateChange * 100).toFixed(0)}% → reservoir pressure ${pressureResponse > 0 ? 'increases' : 'decreases'} by ${Math.abs(pressureResponse).toFixed(0)} psi`);
  }
  if (scenario.chokeChange !== 0) {
    const dir = scenario.chokeChange > 0 ? 'Opening' : 'Closing';
    parts.push(`${dir} choke by ${Math.abs(scenario.chokeChange * 100).toFixed(0)}% → production ${chokeEffect > 1 ? 'increases' : 'decreases'} by ${Math.abs((chokeEffect - 1) * 100).toFixed(0)}%`);
  }
  if (breakthroughRisk === 'high') {
    parts.push('⚠ High breakthrough risk — CO2 may channel to producers prematurely');
  }

  return {
    wellId,
    wellName,
    baselineOilRate: Math.round(currentOilRate * 10) / 10,
    predictedOilRate: Math.round(newOilRate * 10) / 10,
    oilRateChange: Math.round((newOilRate - currentOilRate) * 10) / 10,
    baselinePressure: Math.round(currentPressure),
    predictedPressure: Math.round(newPressure),
    pressureChange: Math.round(newPressure - currentPressure),
    baselineNetback: Math.round(currentNetback * 100) / 100,
    predictedNetback: Math.round(newNetback * 100) / 100,
    netbackChange: Math.round((newNetback - currentNetback) * 100) / 100,
    dailyRevenueImpact: Math.round(dailyImpact),
    annualRevenueImpact: Math.round(dailyImpact * 365),
    breakthroughRisk,
    explanation: parts.join('. ') || 'No changes applied.',
  };
}
