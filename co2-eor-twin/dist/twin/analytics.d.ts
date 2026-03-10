import { TwinState } from './types';
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
export declare function analyzeFacilityConstraints(state: TwinState): FacilityConstraint[];
export interface FlaringRisk {
    flareId: string;
    facilityId: string;
    currentRate: number;
    maxRate: number;
    riskScore: number;
    status: string;
    recommendation: string;
}
export declare function analyzeFlaringRisk(state: TwinState): FlaringRisk[];
export interface InjectionEfficiency {
    patternId: string;
    patternName: string;
    co2InjectedMcf: number;
    co2ProducedMcf: number;
    co2Utilization: number;
    breakthroughRisk: 'low' | 'medium' | 'high';
    daysToBreakthrough: number;
    recommendation: string;
}
export declare function analyzeInjectionEfficiency(state: TwinState): InjectionEfficiency[];
export interface ChokeAdjustment {
    wellId: string;
    wellName: string;
    currentChoke: number;
    proposedChoke: number;
    rationale: string;
    estimatedOilChange: number;
    estimatedWaterChange: number;
}
export declare function proposeChokeAdjustments(state: TwinState, facilityId: string): ChokeAdjustment[];
export interface PatternPerformance {
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
export declare function analyzePatternPerformance(state: TwinState): PatternPerformance[];
export interface CO2Balance {
    totalInjected: number;
    totalPurchased: number;
    totalRecycled: number;
    totalProduced: number;
    netStored: number;
    netStoredTons: number;
    purchasedCost: number;
    recycledSavings: number;
    co2Sources: {
        name: string;
        rate: number;
        cost: number;
    }[];
    storageSummary: string;
}
export declare function analyzeCO2Balance(state: TwinState): CO2Balance;
