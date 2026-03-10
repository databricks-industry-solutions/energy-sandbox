import { TwinState } from '../twin/types';
export interface WellEconomics {
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
export interface CO2Contract {
    id: string;
    supplier: string;
    volume: number;
    price: number;
    takeOrPay: number;
    deliveryPoint: string;
    startDate: string;
    endDate: string;
    status: 'active' | 'pending' | 'expired';
}
export interface CarbonCredit {
    vintage: number;
    registry: string;
    pricePerTon: number;
    volumeAvailable: number;
    projectId: string;
    methodology: string;
}
export interface FieldEconomicsSummary {
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
export declare function getWellEconomics(state: TwinState): WellEconomics[];
export declare function getCO2Contracts(): CO2Contract[];
export declare function getCarbonCredits(): CarbonCredit[];
export declare function getFieldEconomicsSummary(state: TwinState): FieldEconomicsSummary;
