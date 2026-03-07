"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DatabricksTwinDataProvider = exports.InMemoryTwinDataProvider = void 0;
const mock_1 = require("../data/mock");
/* ------------------------------------------------------------------ */
/*  Drift helpers — add realistic random variation to simulate live    */
/*  SCADA telemetry without leaving physically plausible bounds.       */
/* ------------------------------------------------------------------ */
/** Random float in [-mag, +mag] */
function jitter(mag) {
    return (Math.random() - 0.5) * 2 * mag;
}
/** Clamp to [min, max] */
function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
}
/** Round to n decimal places */
function rd(v, n = 1) {
    const f = 10 ** n;
    return Math.round(v * f) / f;
}
function driftWell(w, base) {
    if (w.type === 'producer') {
        w.oilRate = rd(clamp(w.oilRate + jitter(8), base.oilRate * 0.85, base.oilRate * 1.15), 0);
        w.gasRate = rd(clamp(w.gasRate + jitter(20), base.gasRate * 0.85, base.gasRate * 1.15), 0);
        w.waterRate = rd(clamp(w.waterRate + jitter(15), base.waterRate * 0.85, base.waterRate * 1.15), 0);
        w.tubingPressure = rd(clamp(w.tubingPressure + jitter(5), base.tubingPressure - 30, base.tubingPressure + 30), 0);
        w.casingPressure = rd(clamp(w.casingPressure + jitter(3), base.casingPressure - 15, base.casingPressure + 15), 0);
        w.bottomholePressure = rd(clamp(w.bottomholePressure + jitter(15), base.bottomholePressure - 80, base.bottomholePressure + 80), 0);
        w.co2Concentration = rd(clamp(w.co2Concentration + jitter(0.8), base.co2Concentration - 5, base.co2Concentration + 5), 1);
        w.chokePercent = rd(clamp(w.chokePercent + jitter(1), Math.max(base.chokePercent - 8, 0), Math.min(base.chokePercent + 8, 100)), 0);
        const totalFluid = w.oilRate + w.waterRate;
        w.waterCut = totalFluid > 0 ? rd(w.waterRate / totalFluid, 2) : 0;
        w.gor = w.oilRate > 0 ? Math.round((w.gasRate * 1000) / w.oilRate) : 0;
    }
    else if (w.type === 'injector' || w.type === 'WAG') {
        w.co2InjRate = rd(clamp(w.co2InjRate + jitter(30), base.co2InjRate * 0.9, base.co2InjRate * 1.1), 0);
        if (w.type === 'WAG') {
            w.waterInjRate = rd(clamp(w.waterInjRate + jitter(20), base.waterInjRate * 0.9, base.waterInjRate * 1.1), 0);
        }
        w.tubingPressure = rd(clamp(w.tubingPressure + jitter(15), base.tubingPressure - 60, base.tubingPressure + 60), 0);
        w.bottomholePressure = rd(clamp(w.bottomholePressure + jitter(20), base.bottomholePressure - 80, base.bottomholePressure + 80), 0);
    }
    else if (w.type === 'disposal') {
        w.waterInjRate = rd(clamp(w.waterInjRate + jitter(100), base.waterInjRate * 0.9, base.waterInjRate * 1.1), 0);
        w.tubingPressure = rd(clamp(w.tubingPressure + jitter(10), base.tubingPressure - 40, base.tubingPressure + 40), 0);
    }
    // monitor wells: drift BHP only
    if (w.type === 'monitor') {
        w.bottomholePressure = rd(clamp(w.bottomholePressure + jitter(10), base.bottomholePressure - 50, base.bottomholePressure + 50), 0);
    }
}
function driftFacility(f, base) {
    if (base.oilCapacity > 0) {
        f.currentOilRate = rd(clamp(f.currentOilRate + jitter(30), base.currentOilRate * 0.9, base.oilCapacity), 0);
    }
    if (base.gasCapacity > 0) {
        f.currentGasRate = rd(clamp(f.currentGasRate + jitter(50), base.currentGasRate * 0.85, base.gasCapacity), 0);
    }
    if (base.waterCapacity > 0) {
        f.currentWaterRate = rd(clamp(f.currentWaterRate + jitter(40), base.currentWaterRate * 0.85, base.waterCapacity), 0);
    }
    if (base.co2Capacity > 0) {
        f.currentCO2Rate = rd(clamp(f.currentCO2Rate + jitter(40), base.currentCO2Rate * 0.85, base.co2Capacity), 0);
    }
    // Recalc utilization from the dominant stream
    const cap = Math.max(f.oilCapacity, f.gasCapacity, f.waterCapacity, f.co2Capacity);
    const cur = Math.max(f.currentOilRate, f.currentGasRate, f.currentWaterRate, f.currentCO2Rate);
    f.utilization = cap > 0 ? rd(cur / cap, 2) : 0;
    f.emissions = rd(clamp(f.emissions + jitter(1.5), Math.max(base.emissions - 8, 0), base.emissions + 8), 1);
}
function driftPipeline(p, base) {
    p.currentFlow = rd(clamp(p.currentFlow + jitter(40), base.currentFlow * 0.9, base.capacity), 0);
    p.pressure = rd(clamp(p.pressure + jitter(8), base.pressure - 40, base.pressure + 40), 0);
}
function driftFlare(f, base) {
    if (f.status === 'active') {
        f.currentRate = rd(clamp(f.currentRate + jitter(15), 0, base.maxRate * 0.15), 0);
    }
}
function driftMonitor(m, base) {
    m.value = rd(clamp(m.value + jitter(m.type === 'pressure' ? 12 : 5), 0, base.threshold * 1.05), 1);
    m.status = m.value > base.threshold ? 'alarm' : m.value > base.threshold * 0.9 ? 'warning' : 'normal';
}
function recalcKPIs(s) {
    const producers = s.wells.filter((w) => w.type === 'producer');
    const injectors = s.wells.filter((w) => w.type === 'injector' || w.type === 'WAG');
    const totalOil = producers.reduce((a, w) => a + w.oilRate, 0);
    const totalGas = producers.reduce((a, w) => a + w.gasRate, 0);
    const totalWater = producers.reduce((a, w) => a + w.waterRate, 0);
    const co2Injected = injectors.reduce((a, w) => a + w.co2InjRate, 0);
    const co2Recycled = s.facilities.find((f) => f.type === 'CO2_recycle')?.currentCO2Rate ?? 0;
    const co2Purchased = Math.max(0, co2Injected - co2Recycled);
    const avgWaterCut = producers.length > 0 ? producers.reduce((a, w) => a + w.waterCut, 0) / producers.length : 0;
    const baselineOil = 2200;
    const incrementalOil = Math.max(0, totalOil - baselineOil);
    const oilPrice = 72;
    const gasPrice = 3.2;
    const revenue = totalOil * oilPrice + totalGas * gasPrice;
    const opex = totalOil * 18 + totalWater * 0.8;
    const co2Cost = co2Purchased * 1.05;
    const totalBoe = totalOil + totalGas / 6;
    const netback = totalBoe > 0 ? (revenue - opex - co2Cost) / totalBoe : 0;
    const flaringRate = s.flares.reduce((a, f) => a + f.currentRate, 0);
    const facilityEmissions = s.facilities.reduce((a, f) => a + f.emissions, 0);
    const producedCO2 = producers.reduce((a, w) => a + (w.gasRate * w.co2Concentration / 100), 0);
    const co2StoredTons = (co2Injected - producedCO2) * 0.0541;
    s.kpis.production = {
        totalOil: rd(totalOil, 0),
        totalGas: rd(totalGas, 0),
        totalWater: rd(totalWater, 0),
        co2Injected: rd(co2Injected, 0),
        co2Recycled: rd(co2Recycled, 0),
        co2Purchased: rd(co2Purchased, 0),
        co2Utilization: co2Injected > 0 ? rd(co2Recycled / co2Injected, 2) : 0,
        incrementalOil: rd(incrementalOil, 0),
        gor: totalOil > 0 ? Math.round((totalGas * 1000) / totalOil) : 0,
        waterCut: rd(avgWaterCut, 2),
        uptime: 0.96,
    };
    s.kpis.economics = {
        revenue: Math.round(revenue),
        opex: Math.round(opex),
        co2Cost: Math.round(co2Cost),
        netback: rd(netback, 2),
        incrementalNetback: s.kpis.economics.incrementalNetback, // keep stable
        co2CostPerBoe: totalBoe > 0 ? rd(co2Cost / totalBoe, 2) : 0,
        breakeven: 38,
    };
    s.kpis.environmental = {
        co2Stored: rd(co2StoredTons, 2),
        co2Emitted: rd(facilityEmissions, 1),
        flaring: rd(flaringRate, 0),
        carbonIntensity: totalBoe > 0 ? rd((facilityEmissions * 1000 / totalBoe), 2) : 0,
        methaneLeaks: 0,
        complianceScore: 94,
    };
}
/** Apply random drift to an existing TwinState, keeping values physically plausible */
function applyDrift(state, baseline) {
    for (let i = 0; i < state.wells.length; i++) {
        driftWell(state.wells[i], baseline.wells[i]);
    }
    for (let i = 0; i < state.facilities.length; i++) {
        driftFacility(state.facilities[i], baseline.facilities[i]);
    }
    for (let i = 0; i < state.pipelines.length; i++) {
        driftPipeline(state.pipelines[i], baseline.pipelines[i]);
    }
    for (let i = 0; i < state.flares.length; i++) {
        driftFlare(state.flares[i], baseline.flares[i]);
    }
    for (let i = 0; i < state.monitoringPoints.length; i++) {
        driftMonitor(state.monitoringPoints[i], baseline.monitoringPoints[i]);
    }
    // Update pattern pressures from their injector wells
    for (const pat of state.patterns) {
        const injWells = pat.injectorIds.map((id) => state.wells.find((w) => w.id === id)).filter(Boolean);
        if (injWells.length > 0) {
            const avgBHP = injWells.reduce((a, w) => a + w.bottomholePressure, 0) / injWells.length;
            pat.currentPressure = Math.round(avgBHP * 0.85); // pattern pressure < BHP
        }
    }
    recalcKPIs(state);
}
class InMemoryTwinDataProvider {
    state;
    baseline;
    constructor() {
        this.baseline = (0, mock_1.createMockState)();
        this.state = (0, mock_1.createMockState)();
    }
    async loadState() {
        applyDrift(this.state, this.baseline);
        return this.state;
    }
}
exports.InMemoryTwinDataProvider = InMemoryTwinDataProvider;
// TODO: Wire to Databricks Lakehouse
class DatabricksTwinDataProvider {
    async loadState() {
        throw new Error('Not implemented — wire to Databricks SQL / Lakebase');
    }
}
exports.DatabricksTwinDataProvider = DatabricksTwinDataProvider;
