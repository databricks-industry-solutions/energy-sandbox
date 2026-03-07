"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const provider_1 = require("../twin/provider");
const router = (0, express_1.Router)();
const provider = new provider_1.InMemoryTwinDataProvider();
function wellColor(type) {
    switch (type) {
        case 'producer': return '#22c55e'; // green
        case 'injector': return '#3b82f6'; // blue
        case 'WAG': return '#06b6d4'; // cyan
        case 'monitor': return '#eab308'; // yellow
        case 'disposal': return '#9ca3af'; // gray
        default: return '#9ca3af';
    }
}
function facilityColor(utilization) {
    if (utilization > 0.85)
        return '#ef4444'; // red
    if (utilization > 0.70)
        return '#eab308'; // yellow
    return '#22c55e'; // green
}
function pipelineColor(product) {
    switch (product) {
        case 'oil': return '#22c55e';
        case 'gas': return '#ef4444';
        case 'water': return '#3b82f6';
        case 'CO2': return '#f8fafc'; // white
        case 'NGL': return '#a855f7'; // purple
        case 'mixed': return '#f97316'; // orange
        default: return '#9ca3af';
    }
}
function fleetIcon(type) {
    switch (type) {
        case 'truck': return 'truck';
        case 'frac_fleet': return 'frac';
        case 'rig': return 'rig';
        case 'workover': return 'workover';
        case 'pump_truck': return 'pump';
        case 'wireline': return 'wireline';
        case 'coiled_tubing': return 'ct';
        default: return 'default';
    }
}
router.get('/geospatial/assets', async (_req, res) => {
    const state = await provider.loadState();
    // Wells
    const wellsFC = {
        type: 'FeatureCollection',
        features: state.wells.map((w) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [w.lon, w.lat] },
            properties: {
                id: w.id,
                name: w.name,
                entityType: 'well',
                wellType: w.type,
                status: w.status,
                patternId: w.patternId,
                padId: w.padId,
                oilRate: w.oilRate,
                gasRate: w.gasRate,
                waterRate: w.waterRate,
                co2InjRate: w.co2InjRate,
                waterInjRate: w.waterInjRate,
                chokePercent: w.chokePercent,
                tubingPressure: w.tubingPressure,
                casingPressure: w.casingPressure,
                bottomholePressure: w.bottomholePressure,
                co2Concentration: w.co2Concentration,
                gor: w.gor,
                waterCut: w.waterCut,
                reservoirZone: w.reservoirZone,
                color: wellColor(w.type),
            },
        })),
    };
    // Facilities
    const facilitiesFC = {
        type: 'FeatureCollection',
        features: state.facilities.map((f) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [f.lon, f.lat] },
            properties: {
                id: f.id,
                name: f.name,
                entityType: 'facility',
                facilityType: f.type,
                utilization: f.utilization,
                currentOilRate: f.currentOilRate,
                currentGasRate: f.currentGasRate,
                currentWaterRate: f.currentWaterRate,
                currentCO2Rate: f.currentCO2Rate,
                oilCapacity: f.oilCapacity,
                gasCapacity: f.gasCapacity,
                waterCapacity: f.waterCapacity,
                co2Capacity: f.co2Capacity,
                emissions: f.emissions,
                color: facilityColor(f.utilization),
            },
        })),
    };
    // Pipelines
    const pipelinesFC = {
        type: 'FeatureCollection',
        features: state.pipelines.map((p) => ({
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: p.coordinates,
            },
            properties: {
                id: p.id,
                name: p.name,
                entityType: 'pipeline',
                product: p.product,
                capacity: p.capacity,
                currentFlow: p.currentFlow,
                pressure: p.pressure,
                diameter: p.diameter,
                utilization: p.capacity > 0 ? Math.round((p.currentFlow / p.capacity) * 100) : 0,
                color: pipelineColor(p.product),
            },
        })),
    };
    // CO2 Sources
    const co2SourcesFC = {
        type: 'FeatureCollection',
        features: state.co2Sources.map((s) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
            properties: {
                id: s.id,
                name: s.name,
                entityType: 'co2Source',
                sourceType: s.type,
                deliveryRate: s.deliveryRate,
                contractedRate: s.contractedRate,
                purity: s.purity,
                cost: s.cost,
                color: '#f8fafc',
            },
        })),
    };
    // Monitoring Points
    const monitoringFC = {
        type: 'FeatureCollection',
        features: state.monitoringPoints.map((m) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [m.lon, m.lat] },
            properties: {
                id: m.id,
                name: m.name,
                entityType: 'monitoringPoint',
                monitorType: m.type,
                value: m.value,
                unit: m.unit,
                threshold: m.threshold,
                status: m.status,
                color: m.status === 'alarm' ? '#ef4444' : m.status === 'warning' ? '#eab308' : '#22c55e',
            },
        })),
    };
    // Fleet
    const fleetFC = {
        type: 'FeatureCollection',
        features: state.fleet.map((f) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [f.lon, f.lat] },
            properties: {
                id: f.id,
                entityType: 'fleet',
                fleetType: f.type,
                status: f.status,
                assignedTo: f.assignedTo,
                eta: f.eta,
                icon: fleetIcon(f.type),
                color: f.status === 'on_site' ? '#22c55e' : f.status === 'en_route' ? '#3b82f6' : f.status === 'maintenance' ? '#ef4444' : '#9ca3af',
            },
        })),
    };
    // Flares
    const flaresFC = {
        type: 'FeatureCollection',
        features: state.flares.map((f) => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [f.lon, f.lat] },
            properties: {
                id: f.id,
                entityType: 'flare',
                facilityId: f.facilityId,
                currentRate: f.currentRate,
                maxRate: f.maxRate,
                status: f.status,
                color: f.status === 'active' ? '#f97316' : '#9ca3af',
            },
        })),
    };
    res.json({
        wells: wellsFC,
        facilities: facilitiesFC,
        pipelines: pipelinesFC,
        co2Sources: co2SourcesFC,
        monitoringPoints: monitoringFC,
        fleet: fleetFC,
        flares: flaresFC,
    });
});
exports.default = router;
