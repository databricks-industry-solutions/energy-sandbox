"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getWellEconomics = getWellEconomics;
exports.getCO2Contracts = getCO2Contracts;
exports.getCarbonCredits = getCarbonCredits;
exports.getFieldEconomicsSummary = getFieldEconomicsSummary;
// ------------------------------------------------------------------
// Functions
// ------------------------------------------------------------------
const OIL_PRICE = 72; // $/bbl
const GAS_PRICE = 3.20; // $/mcf
function getWellEconomics(state) {
    const producers = state.wells.filter((w) => w.type === 'producer' && w.status === 'active');
    const totalOil = producers.reduce((s, w) => s + w.oilRate, 0);
    const totalCO2Inj = state.wells
        .filter((w) => w.type === 'injector' || w.type === 'WAG')
        .reduce((s, w) => s + w.co2InjRate, 0);
    const avgCO2Cost = 1.05; // $/mcf blended
    return producers.map((w) => {
        const oilRev = w.oilRate * OIL_PRICE;
        const gasRev = w.gasRate * GAS_PRICE;
        const boe = w.oilRate + w.gasRate / 6;
        // Allocate CO2 cost proportionally by oil rate
        const co2Alloc = totalOil > 0 ? (w.oilRate / totalOil) * totalCO2Inj * avgCO2Cost : 0;
        const loe = w.oilRate * 8.5 + w.waterRate * 0.45;
        const transport = w.oilRate * 2.5 + w.gasRate * 0.15;
        const netback = boe > 0 ? (oilRev + gasRev - co2Alloc - loe - transport) / boe : 0;
        const co2PerBoe = boe > 0 ? (totalOil > 0 ? (w.oilRate / totalOil) * totalCO2Inj / boe : 0) : 0;
        return {
            wellId: w.id,
            wellName: w.name,
            oilRevenue: Math.round(oilRev),
            gasRevenue: Math.round(gasRev),
            co2Cost: Math.round(co2Alloc),
            loe: Math.round(loe),
            transportCost: Math.round(transport),
            netbackPerBoe: Math.round(netback * 100) / 100,
            co2PerBoe: Math.round(co2PerBoe * 100) / 100,
        };
    });
}
function getCO2Contracts() {
    return [
        {
            id: 'CTR-001', supplier: 'Val Verde Gas Processing LLC',
            volume: 4000, price: 1.25, takeOrPay: 3200,
            deliveryPoint: 'CO2 Compression Station Inlet',
            startDate: '2024-01-01', endDate: '2029-12-31',
            status: 'active',
        },
        {
            id: 'CTR-002', supplier: 'Bravo Dome CO2 Partners',
            volume: 6000, price: 0.85, takeOrPay: 4500,
            deliveryPoint: 'CO2 Compression Station Inlet',
            startDate: '2023-06-01', endDate: '2033-05-31',
            status: 'active',
        },
        {
            id: 'CTR-003', supplier: 'Permian Carbon Capture Inc',
            volume: 2000, price: 1.50, takeOrPay: 0,
            deliveryPoint: 'CO2 Compression Station Inlet',
            startDate: '2026-07-01', endDate: '2031-06-30',
            status: 'pending',
        },
    ];
}
function getCarbonCredits() {
    return [
        {
            vintage: 2025, registry: 'ACR (American Carbon Registry)',
            pricePerTon: 28.50, volumeAvailable: 45000,
            projectId: 'ACR-EOR-2025-0412',
            methodology: 'ACR Methodology for CO2 EOR — Geologic Storage',
        },
        {
            vintage: 2026, registry: 'ACR (American Carbon Registry)',
            pricePerTon: 32.00, volumeAvailable: 52000,
            projectId: 'ACR-EOR-2026-0088',
            methodology: 'ACR Methodology for CO2 EOR — Geologic Storage',
        },
        {
            vintage: 2025, registry: 'Verra VCS',
            pricePerTon: 24.00, volumeAvailable: 30000,
            projectId: 'VCS-2345',
            methodology: 'VM0032 CO2 Utilization in Enhanced Oil Recovery',
        },
    ];
}
function getFieldEconomicsSummary(state) {
    const wellEcon = getWellEconomics(state);
    const totalRevenue = wellEcon.reduce((s, w) => s + w.oilRevenue + w.gasRevenue, 0);
    const totalOpex = wellEcon.reduce((s, w) => s + w.loe, 0);
    const totalCO2Cost = wellEcon.reduce((s, w) => s + w.co2Cost, 0);
    const totalTransport = wellEcon.reduce((s, w) => s + w.transportCost, 0);
    const producers = state.wells.filter((w) => w.type === 'producer' && w.status === 'active');
    const totalOil = producers.reduce((s, w) => s + w.oilRate, 0);
    const totalGas = producers.reduce((s, w) => s + w.gasRate, 0);
    const totalBoe = totalOil + totalGas / 6;
    const fieldNetback = totalBoe > 0 ? (totalRevenue - totalOpex - totalCO2Cost - totalTransport) / totalBoe : 0;
    const baselineOil = 2200;
    const incrementalOil = Math.max(0, totalOil - baselineOil);
    const incrementalBoe = incrementalOil * 1.15; // include associated gas
    const incrementalRevenue = incrementalOil * OIL_PRICE;
    const incrementalNetback = incrementalBoe > 0 ? (incrementalRevenue - totalCO2Cost * 0.6) / incrementalBoe : 0;
    // Carbon credit revenue based on net stored CO2
    const co2StoredTonsPerDay = state.kpis.environmental.co2Stored;
    const carbonCreditRevenue = co2StoredTonsPerDay * 28.5; // conservative credit price
    return {
        totalRevenue: Math.round(totalRevenue),
        totalOpex: Math.round(totalOpex),
        totalCO2Cost: Math.round(totalCO2Cost),
        totalTransport: Math.round(totalTransport),
        fieldNetback: Math.round(fieldNetback * 100) / 100,
        incrementalNetback: Math.round(incrementalNetback * 100) / 100,
        breakeven: 38,
        carbonCreditRevenue: Math.round(carbonCreditRevenue),
        totalBoe: Math.round(totalBoe),
        wellCount: producers.length,
    };
}
