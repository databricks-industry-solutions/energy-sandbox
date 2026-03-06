import { TwinState } from './types';

// ------------------------------------------------------------------
// Facility Constraints Analysis
// ------------------------------------------------------------------
export interface FacilityConstraint {
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

export function analyzeFacilityConstraints(state: TwinState): FacilityConstraint[] {
  return state.facilities.map((f) => {
    const oilUtil = f.oilCapacity > 0 ? f.currentOilRate / f.oilCapacity : 0;
    const gasUtil = f.gasCapacity > 0 ? f.currentGasRate / f.gasCapacity : 0;
    const waterUtil = f.waterCapacity > 0 ? f.currentWaterRate / f.waterCapacity : 0;
    const co2Util = f.co2Capacity > 0 ? f.currentCO2Rate / f.co2Capacity : 0;
    const maxUtil = Math.max(oilUtil, gasUtil, waterUtil, co2Util);
    const flagged = maxUtil > 0.85;

    let bottleneck: string | null = null;
    if (flagged) {
      if (oilUtil === maxUtil) bottleneck = 'oil processing';
      else if (gasUtil === maxUtil) bottleneck = 'gas processing';
      else if (waterUtil === maxUtil) bottleneck = 'water handling';
      else if (co2Util === maxUtil) bottleneck = 'CO2 capacity';
    }

    return {
      facilityId: f.id,
      facilityName: f.name,
      type: f.type,
      utilization: Math.round(f.utilization * 100) / 100,
      oilUtilization: Math.round(oilUtil * 100) / 100,
      gasUtilization: Math.round(gasUtil * 100) / 100,
      waterUtilization: Math.round(waterUtil * 100) / 100,
      co2Utilization: Math.round(co2Util * 100) / 100,
      flagged,
      bottleneck,
    };
  });
}

// ------------------------------------------------------------------
// Flaring Risk Analysis
// ------------------------------------------------------------------
export interface FlaringRisk {
  flareId: string;
  facilityId: string;
  currentRate: number;
  maxRate: number;
  riskScore: number;    // 0-100
  status: string;
  recommendation: string;
}

export function analyzeFlaringRisk(state: TwinState): FlaringRisk[] {
  return state.flares.map((f) => {
    const utilizationPct = f.maxRate > 0 ? (f.currentRate / f.maxRate) * 100 : 0;
    // Risk escalates non-linearly: low baseline, spikes above 50% capacity
    let riskScore = utilizationPct * 0.6;
    if (f.currentRate > 500) riskScore += 20;
    if (f.currentRate > 2000) riskScore += 30;
    riskScore = Math.min(100, Math.round(riskScore));

    let recommendation = 'No action needed';
    if (riskScore > 60) recommendation = 'Investigate root cause — possible compressor trip or gas processing constraint';
    else if (riskScore > 30) recommendation = 'Monitor closely — consider diverting to gas sales or CO2 recycle';
    else if (f.currentRate > 0) recommendation = 'Routine flaring within limits — verify pilot is stable';

    return {
      flareId: f.id,
      facilityId: f.facilityId,
      currentRate: f.currentRate,
      maxRate: f.maxRate,
      riskScore,
      status: f.status,
      recommendation,
    };
  });
}

// ------------------------------------------------------------------
// Injection Efficiency Analysis
// ------------------------------------------------------------------
export interface InjectionEfficiency {
  patternId: string;
  patternName: string;
  co2InjectedMcf: number;
  co2ProducedMcf: number;
  co2Utilization: number;        // fraction stored
  breakthroughRisk: 'low' | 'medium' | 'high';
  daysToBreakthrough: number;
  recommendation: string;
}

export function analyzeInjectionEfficiency(state: TwinState): InjectionEfficiency[] {
  return state.patterns.map((pat) => {
    const injectors = state.wells.filter((w) => pat.injectorIds.includes(w.id));
    const producers = state.wells.filter((w) => pat.producerIds.includes(w.id));

    const co2Injected = injectors.reduce((s, w) => s + w.co2InjRate, 0);
    // CO2 produced = gas rate * CO2 concentration
    const co2Produced = producers.reduce((s, w) => s + (w.gasRate * w.co2Concentration / 100), 0);
    const utilization = co2Injected > 0 ? 1 - (co2Produced / co2Injected) : 1;

    const btDate = new Date(pat.estimatedBreakthrough);
    const now = new Date('2026-03-05');
    const daysToBreakthrough = Math.max(0, Math.round((btDate.getTime() - now.getTime()) / 86400000));

    let breakthroughRisk: 'low' | 'medium' | 'high' = 'low';
    if (daysToBreakthrough < 90) breakthroughRisk = 'medium';
    if (daysToBreakthrough < 45 || utilization < 0.5) breakthroughRisk = 'high';

    const avgCO2Conc = producers.length > 0
      ? producers.reduce((s, w) => s + w.co2Concentration, 0) / producers.length
      : 0;

    let recommendation = 'Pattern performing within expectations';
    if (breakthroughRisk === 'high') {
      recommendation = `High breakthrough risk — consider switching to water slug or reducing injection rate. Avg CO2 in produced gas: ${avgCO2Conc.toFixed(1)} mol%`;
    } else if (breakthroughRisk === 'medium') {
      recommendation = `Monitor CO2 concentration trend closely. Current avg: ${avgCO2Conc.toFixed(1)} mol%. Consider WAG cycle adjustment.`;
    }

    return {
      patternId: pat.id,
      patternName: pat.name,
      co2InjectedMcf: co2Injected,
      co2ProducedMcf: Math.round(co2Produced),
      co2Utilization: Math.round(utilization * 100) / 100,
      breakthroughRisk,
      daysToBreakthrough,
      recommendation,
    };
  });
}

// ------------------------------------------------------------------
// Choke Adjustment Proposals
// ------------------------------------------------------------------
export interface ChokeAdjustment {
  wellId: string;
  wellName: string;
  currentChoke: number;
  proposedChoke: number;
  rationale: string;
  estimatedOilChange: number;   // bbl/d
  estimatedWaterChange: number; // bbl/d
}

export function proposeChokeAdjustments(state: TwinState, facilityId: string): ChokeAdjustment[] {
  const constraints = analyzeFacilityConstraints(state);
  const facilityConstraint = constraints.find((c) => c.facilityId === facilityId);
  if (!facilityConstraint || !facilityConstraint.flagged) return [];

  // Find pads feeding this facility, then their wells
  const pads = state.pads.filter((p) => p.facilityId === facilityId);
  const wellIds = pads.flatMap((p) => p.wellIds);
  const producers = state.wells.filter((w) => wellIds.includes(w.id) && w.type === 'producer' && w.status === 'active');

  // Target: reduce facility utilization to 80%
  const targetReduction = facilityConstraint.utilization - 0.80;
  if (targetReduction <= 0) return [];

  // Sort by water cut descending — choke back high-water-cut wells first
  const sorted = [...producers].sort((a, b) => b.waterCut - a.waterCut);

  const adjustments: ChokeAdjustment[] = [];
  let remainingReduction = targetReduction;

  for (const well of sorted) {
    if (remainingReduction <= 0) break;
    const reduction = Math.min(15, Math.round(remainingReduction * 100));
    const proposedChoke = Math.max(30, well.chokePercent - reduction);
    const chokeRatio = proposedChoke / well.chokePercent;
    const estOilChange = -Math.round(well.oilRate * (1 - chokeRatio) * 0.7);   // oil drops less than total
    const estWaterChange = -Math.round(well.waterRate * (1 - chokeRatio));

    adjustments.push({
      wellId: well.id,
      wellName: well.name,
      currentChoke: well.chokePercent,
      proposedChoke,
      rationale: `Water cut ${(well.waterCut * 100).toFixed(0)}% — reducing choke to lower water load on ${facilityConstraint.bottleneck ?? 'facility'}`,
      estimatedOilChange: estOilChange,
      estimatedWaterChange: estWaterChange,
    });

    remainingReduction -= 0.03; // each well ~3% reduction
  }

  return adjustments;
}

// ------------------------------------------------------------------
// Pattern Performance Comparison
// ------------------------------------------------------------------
export interface PatternPerformance {
  patternId: string;
  patternName: string;
  totalOilRate: number;
  totalCO2InjRate: number;
  co2PerBblOil: number;        // mcf CO2 per bbl oil
  currentPhase: string;
  cycleNumber: number;
  pressureDeficit: number;     // target - current psi
  suggestion: string;
}

export function analyzePatternPerformance(state: TwinState): PatternPerformance[] {
  return state.patterns.map((pat) => {
    const producers = state.wells.filter((w) => pat.producerIds.includes(w.id));
    const injectors = state.wells.filter((w) => pat.injectorIds.includes(w.id));

    const totalOil = producers.reduce((s, w) => s + w.oilRate, 0);
    const totalCO2 = injectors.reduce((s, w) => s + w.co2InjRate, 0);
    const co2PerBbl = totalOil > 0 ? totalCO2 / totalOil : 0;
    const pressureDeficit = pat.targetPressure - pat.currentPressure;

    let suggestion = 'Continue current operations';
    if (pressureDeficit > 300) {
      suggestion = 'Pressure significantly below target — consider increasing injection rate or extending CO2 slug';
    } else if (pressureDeficit < 50 && pat.currentPhase === 'CO2_injection') {
      suggestion = 'Near target pressure — consider transitioning to water slug phase';
    }
    if (co2PerBbl > 15) {
      suggestion = `High CO2 usage (${co2PerBbl.toFixed(1)} mcf/bbl) — evaluate pattern sweep efficiency`;
    }

    return {
      patternId: pat.id,
      patternName: pat.name,
      totalOilRate: totalOil,
      totalCO2InjRate: totalCO2,
      co2PerBblOil: Math.round(co2PerBbl * 100) / 100,
      currentPhase: pat.currentPhase,
      cycleNumber: pat.cycleNumber,
      pressureDeficit,
      suggestion,
    };
  });
}

// ------------------------------------------------------------------
// CO2 Balance Analysis
// ------------------------------------------------------------------
export interface CO2Balance {
  totalInjected: number;       // mcf/d
  totalPurchased: number;      // mcf/d
  totalRecycled: number;       // mcf/d
  totalProduced: number;       // mcf/d (in produced gas)
  netStored: number;           // mcf/d
  netStoredTons: number;       // tCO2/d
  purchasedCost: number;       // $/d
  recycledSavings: number;     // $/d
  co2Sources: { name: string; rate: number; cost: number }[];
  storageSummary: string;
}

export function analyzeCO2Balance(state: TwinState): CO2Balance {
  const injectors = state.wells.filter((w) => w.type === 'injector' || w.type === 'WAG');
  const producers = state.wells.filter((w) => w.type === 'producer');

  const totalInjected = injectors.reduce((s, w) => s + w.co2InjRate, 0);
  const totalProduced = producers.reduce((s, w) => s + (w.gasRate * w.co2Concentration / 100), 0);
  const recyclePlant = state.facilities.find((f) => f.type === 'CO2_recycle');
  const totalRecycled = recyclePlant?.currentCO2Rate ?? 0;
  const totalPurchased = Math.max(0, totalInjected - totalRecycled);
  const netStored = totalInjected - totalProduced;
  const netStoredTons = netStored * 0.0541; // approx

  const avgPurchaseCost = state.co2Sources.length > 0
    ? state.co2Sources.reduce((s, c) => s + c.cost * c.deliveryRate, 0) / state.co2Sources.reduce((s, c) => s + c.deliveryRate, 0)
    : 1.0;

  const purchasedCost = totalPurchased * avgPurchaseCost;
  const recycledSavings = totalRecycled * avgPurchaseCost;

  return {
    totalInjected,
    totalPurchased: Math.round(totalPurchased),
    totalRecycled,
    totalProduced: Math.round(totalProduced),
    netStored: Math.round(netStored),
    netStoredTons: Math.round(netStoredTons * 10) / 10,
    purchasedCost: Math.round(purchasedCost),
    recycledSavings: Math.round(recycledSavings),
    co2Sources: state.co2Sources.map((s) => ({
      name: s.name,
      rate: s.deliveryRate,
      cost: s.cost,
    })),
    storageSummary: `Net CO2 storage: ${Math.round(netStoredTons)} tCO2/day (${Math.round(netStoredTons * 365)} tCO2/yr). Recycled ${totalRecycled} mcf/d saving $${Math.round(recycledSavings)}/d.`,
  };
}
