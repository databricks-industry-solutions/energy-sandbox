"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAssets = getAssets;
exports.getAssetById = getAssetById;
exports.getAssetTelemetry = getAssetTelemetry;
exports.getAssetMaintenanceHistory = getAssetMaintenanceHistory;

// ── CO2 EOR Facility Assets for Delaware Basin ──────────────────────────
// Equipment across CPF, CO2 Recycle Plant, Compression Station, SWD, and wellheads

const ASSETS = [
    // ── CO2 Compression Station (FAC-COMP) ──────────────────────────────
    {
        id: 'COMP-001', name: 'CO2 Compressor Stage 1', type: 'compressor',
        facilityId: 'FAC-COMP', facilityName: 'CO2 Compression Station',
        criticality: 'critical', manufacturer: 'Ariel Corp', model: 'JGK/4',
        installDate: '2023-06-15', runHours: 18420, lastPmDate: '2026-02-10',
        nextPmDate: '2026-03-10', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: true,
        sensors: { vibration: 2.1, temperature: 185, pressure: 1850, current: 88, runHoursToday: 22 },
        riskScore: 0.28, failureProbability: 0.12,
    },
    {
        id: 'COMP-002', name: 'CO2 Compressor Stage 2', type: 'compressor',
        facilityId: 'FAC-COMP', facilityName: 'CO2 Compression Station',
        criticality: 'critical', manufacturer: 'Ariel Corp', model: 'JGK/4',
        installDate: '2023-06-15', runHours: 18390, lastPmDate: '2026-02-12',
        nextPmDate: '2026-03-12', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: true,
        sensors: { vibration: 3.8, temperature: 198, pressure: 2100, current: 94, runHoursToday: 22 },
        riskScore: 0.62, failureProbability: 0.37,
    },
    {
        id: 'COMP-003', name: 'Compressor Lube Oil System', type: 'lube_system',
        facilityId: 'FAC-COMP', facilityName: 'CO2 Compression Station',
        criticality: 'high', manufacturer: 'Parker Kittyhawk', model: 'LOS-500',
        installDate: '2023-06-15', runHours: 18420, lastPmDate: '2026-01-20',
        nextPmDate: '2026-03-20', pmIntervalDays: 60,
        regulatoryFlag: false, safetyFlag: false,
        sensors: { vibration: 0.8, temperature: 145, pressure: 65, current: 0, runHoursToday: 22 },
        riskScore: 0.15, failureProbability: 0.05,
    },
    // ── Central Processing Facility (FAC-CPF) ───────────────────────────
    {
        id: 'SEP-001', name: '3-Phase Separator Train A', type: 'separator',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'critical', manufacturer: 'Exterran', model: 'VS-3P-2000',
        installDate: '2022-11-01', runHours: 24100, lastPmDate: '2026-02-01',
        nextPmDate: '2026-04-01', pmIntervalDays: 60,
        regulatoryFlag: true, safetyFlag: true,
        sensors: { vibration: 1.2, temperature: 165, pressure: 650, current: 72, runHoursToday: 24 },
        riskScore: 0.18, failureProbability: 0.08,
    },
    {
        id: 'SEP-002', name: '3-Phase Separator Train B', type: 'separator',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'critical', manufacturer: 'Exterran', model: 'VS-3P-2000',
        installDate: '2022-11-01', runHours: 23800, lastPmDate: '2026-01-15',
        nextPmDate: '2026-03-15', pmIntervalDays: 60,
        regulatoryFlag: true, safetyFlag: true,
        sensors: { vibration: 1.5, temperature: 172, pressure: 680, current: 75, runHoursToday: 24 },
        riskScore: 0.22, failureProbability: 0.10,
    },
    {
        id: 'HTR-001', name: 'Line Heater / Heater Treater', type: 'heater',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'high', manufacturer: 'Natco Group', model: 'HT-1500',
        installDate: '2022-11-01', runHours: 22500, lastPmDate: '2026-02-20',
        nextPmDate: '2026-03-20', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: true,
        sensors: { vibration: 0.5, temperature: 210, pressure: 120, current: 65, runHoursToday: 24 },
        riskScore: 0.20, failureProbability: 0.09,
    },
    {
        id: 'PMP-001', name: 'Injection Booster Pump A', type: 'pump',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'high', manufacturer: 'Flowserve', model: 'MBN-340',
        installDate: '2023-03-10', runHours: 19800, lastPmDate: '2026-02-25',
        nextPmDate: '2026-03-25', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: false,
        sensors: { vibration: 4.2, temperature: 192, pressure: 2400, current: 96, runHoursToday: 20 },
        riskScore: 0.55, failureProbability: 0.31,
    },
    {
        id: 'PMP-002', name: 'Injection Booster Pump B', type: 'pump',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'high', manufacturer: 'Flowserve', model: 'MBN-340',
        installDate: '2023-03-10', runHours: 19600, lastPmDate: '2026-01-28',
        nextPmDate: '2026-02-28', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: false,
        sensors: { vibration: 2.8, temperature: 178, pressure: 2350, current: 85, runHoursToday: 20 },
        riskScore: 0.35, failureProbability: 0.18,
    },
    {
        id: 'VLV-001', name: 'Emergency Shutdown Valve ESD-1', type: 'valve',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'critical', manufacturer: 'Cameron', model: 'T31-ESD',
        installDate: '2022-11-01', runHours: 0, lastPmDate: '2026-01-05',
        nextPmDate: '2026-04-05', pmIntervalDays: 90,
        regulatoryFlag: true, safetyFlag: true,
        sensors: { vibration: 0, temperature: 85, pressure: 0, current: 0, runHoursToday: 0 },
        riskScore: 0.10, failureProbability: 0.02,
    },
    // ── CO2 Recycle Plant (FAC-CO2R) ────────────────────────────────────
    {
        id: 'DEH-001', name: 'CO2 Dehydration Unit', type: 'dehydrator',
        facilityId: 'FAC-CO2R', facilityName: 'CO2 Recycle Plant',
        criticality: 'high', manufacturer: 'Prosernat', model: 'GlyDHY-2000',
        installDate: '2023-06-15', runHours: 17200, lastPmDate: '2026-02-05',
        nextPmDate: '2026-03-05', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: false,
        sensors: { vibration: 1.0, temperature: 155, pressure: 1100, current: 68, runHoursToday: 24 },
        riskScore: 0.30, failureProbability: 0.14,
    },
    {
        id: 'MEM-001', name: 'CO2 Membrane Separation Unit', type: 'membrane',
        facilityId: 'FAC-CO2R', facilityName: 'CO2 Recycle Plant',
        criticality: 'critical', manufacturer: 'Air Liquide', model: 'MEDAL-800',
        installDate: '2023-06-15', runHours: 17200, lastPmDate: '2026-02-15',
        nextPmDate: '2026-04-15', pmIntervalDays: 60,
        regulatoryFlag: false, safetyFlag: false,
        sensors: { vibration: 0.3, temperature: 130, pressure: 900, current: 55, runHoursToday: 24 },
        riskScore: 0.12, failureProbability: 0.04,
    },
    // ── Salt Water Disposal (FAC-SWD) ───────────────────────────────────
    {
        id: 'SWD-PMP-001', name: 'SWD Injection Pump', type: 'pump',
        facilityId: 'FAC-SWD', facilityName: 'Salt Water Disposal',
        criticality: 'high', manufacturer: 'Gardner Denver', model: 'PAH-Triplex',
        installDate: '2023-01-20', runHours: 21000, lastPmDate: '2026-02-18',
        nextPmDate: '2026-03-18', pmIntervalDays: 30,
        regulatoryFlag: true, safetyFlag: false,
        sensors: { vibration: 3.5, temperature: 188, pressure: 1200, current: 91, runHoursToday: 22 },
        riskScore: 0.48, failureProbability: 0.25,
    },
    {
        id: 'SWD-FLT-001', name: 'SWD Water Filter System', type: 'filter',
        facilityId: 'FAC-SWD', facilityName: 'Salt Water Disposal',
        criticality: 'medium', manufacturer: 'Pall Corp', model: 'Aria-AP',
        installDate: '2023-01-20', runHours: 21000, lastPmDate: '2026-02-28',
        nextPmDate: '2026-03-28', pmIntervalDays: 30,
        regulatoryFlag: false, safetyFlag: false,
        sensors: { vibration: 0.4, temperature: 95, pressure: 45, current: 30, runHoursToday: 22 },
        riskScore: 0.08, failureProbability: 0.03,
    },
    // ── Wellhead Equipment ──────────────────────────────────────────────
    {
        id: 'WH-A05', name: 'Wellhead CO2 Injector W-A05', type: 'wellhead',
        facilityId: 'FAC-CPF', facilityName: 'Pattern A Wellhead',
        criticality: 'high', manufacturer: 'FMC Technologies', model: 'UWS-15K',
        installDate: '2023-06-01', runHours: 0, lastPmDate: '2026-01-10',
        nextPmDate: '2026-04-10', pmIntervalDays: 90,
        regulatoryFlag: true, safetyFlag: true,
        sensors: { vibration: 0.2, temperature: 95, pressure: 2800, current: 0, runHoursToday: 0 },
        riskScore: 0.14, failureProbability: 0.06,
    },
    {
        id: 'WH-D05', name: 'Wellhead CO2 Injector W-D05', type: 'wellhead',
        facilityId: 'FAC-CPF', facilityName: 'Pattern D Wellhead',
        criticality: 'high', manufacturer: 'FMC Technologies', model: 'UWS-15K',
        installDate: '2023-06-01', runHours: 0, lastPmDate: '2026-01-12',
        nextPmDate: '2026-04-12', pmIntervalDays: 90,
        regulatoryFlag: true, safetyFlag: true,
        sensors: { vibration: 0.3, temperature: 98, pressure: 2750, current: 0, runHoursToday: 0 },
        riskScore: 0.16, failureProbability: 0.07,
    },
    // ── Metering / Instrumentation ──────────────────────────────────────
    {
        id: 'MTR-001', name: 'Fiscal Meter - Oil Sales', type: 'meter',
        facilityId: 'FAC-CPF', facilityName: 'Delaware Basin CPF',
        criticality: 'high', manufacturer: 'Emerson', model: 'CMF400',
        installDate: '2022-11-01', runHours: 0, lastPmDate: '2026-03-01',
        nextPmDate: '2026-06-01', pmIntervalDays: 90,
        regulatoryFlag: true, safetyFlag: false,
        sensors: { vibration: 0, temperature: 82, pressure: 0, current: 0, runHoursToday: 0 },
        riskScore: 0.05, failureProbability: 0.01,
    },
    {
        id: 'MTR-002', name: 'CO2 Injection Meter Trunk', type: 'meter',
        facilityId: 'FAC-COMP', facilityName: 'CO2 Compression Station',
        criticality: 'high', manufacturer: 'Emerson', model: 'CMF400',
        installDate: '2023-06-15', runHours: 0, lastPmDate: '2026-02-01',
        nextPmDate: '2026-05-01', pmIntervalDays: 90,
        regulatoryFlag: true, safetyFlag: false,
        sensors: { vibration: 0, temperature: 78, pressure: 0, current: 0, runHoursToday: 0 },
        riskScore: 0.05, failureProbability: 0.01,
    },
];

function _jitter(val, mag) {
    return val + (Math.random() - 0.5) * 2 * mag;
}

function _driftSensors(asset) {
    const s = { ...asset.sensors };
    s.vibration = Math.max(0, +(s.vibration + (Math.random() - 0.5) * 0.4).toFixed(2));
    s.temperature = Math.max(50, +(s.temperature + (Math.random() - 0.5) * 3).toFixed(1));
    s.pressure = Math.max(0, +(s.pressure + (Math.random() - 0.5) * 20).toFixed(0));
    s.current = Math.max(0, +(s.current + (Math.random() - 0.5) * 3).toFixed(1));
    return s;
}

function getAssets(filters) {
    let result = [...ASSETS];
    if (filters) {
        if (filters.facility_id) result = result.filter(a => a.facilityId === filters.facility_id);
        if (filters.criticality) result = result.filter(a => a.criticality === filters.criticality);
        if (filters.type) result = result.filter(a => a.type === filters.type);
    }
    return result.map(a => ({ ...a, sensors: _driftSensors(a) }));
}

function getAssetById(assetId) {
    const a = ASSETS.find(a => a.id === assetId);
    if (!a) return null;
    return { ...a, sensors: _driftSensors(a) };
}

function getAssetTelemetry(assetId, from, to) {
    const asset = ASSETS.find(a => a.id === assetId);
    if (!asset) return [];
    // Generate 24h of hourly readings
    const now = new Date();
    const readings = [];
    for (let h = 23; h >= 0; h--) {
        const ts = new Date(now.getTime() - h * 3600000);
        const base = asset.sensors;
        readings.push({
            timestamp: ts.toISOString(),
            vibration: +_jitter(base.vibration, 0.5).toFixed(2),
            temperature: +_jitter(base.temperature, 4).toFixed(1),
            pressure: +_jitter(base.pressure, 25).toFixed(0),
            current: +_jitter(base.current, 4).toFixed(1),
        });
    }
    return readings;
}

function getAssetMaintenanceHistory(assetId, from, to) {
    const asset = ASSETS.find(a => a.id === assetId);
    if (!asset) return [];
    // Generate realistic maintenance history
    const history = [];
    const types = ['PM', 'CM', 'INSPECTION', 'CALIBRATION'];
    const now = new Date();
    for (let i = 0; i < 8; i++) {
        const daysAgo = 30 * (i + 1) + Math.floor(Math.random() * 10);
        const dt = new Date(now.getTime() - daysAgo * 86400000);
        const type = types[i % types.length];
        history.push({
            woId: `WO-${asset.id}-${String(i + 1).padStart(3, '0')}`,
            assetId: asset.id,
            date: dt.toISOString().split('T')[0],
            type,
            description: type === 'PM' ? `Scheduled preventive maintenance — ${asset.type}`
                : type === 'CM' ? `Corrective maintenance — ${asset.type} repair`
                : type === 'INSPECTION' ? `Regulatory inspection — ${asset.type}`
                : `Instrument calibration — ${asset.type}`,
            duration_hrs: type === 'PM' ? 4 : type === 'CM' ? 8 : 2,
            cost_usd: type === 'PM' ? 2500 : type === 'CM' ? 12000 : type === 'INSPECTION' ? 800 : 500,
            outcome: i === 2 ? 'failure_found' : 'completed',
            downtime_hrs: type === 'CM' ? 12 : 0,
        });
    }
    return history;
}
