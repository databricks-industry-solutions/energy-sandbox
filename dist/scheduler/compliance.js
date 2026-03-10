"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getConstraintRules = getConstraintRules;
exports.checkCompliance = checkCompliance;
exports.getMaintenancePlans = getMaintenancePlans;
exports.getInventory = getInventory;

// ── Compliance & Regulatory Rules ───────────────────────────────────────
// Based on API, OSHA, EPA, and NACE standards for CO2 injection facilities

const CONSTRAINT_RULES = {
    guardrails: {
        maxMoveDays: 7,
        minLeadTimeHours: 4,
        criticalAssetThreshold: 0.65,
        urgentInsertionThreshold: 0.80,
        noMoveWindowMinutes: 30,
        approvalRequiredBeyondDays: 7,
    },
    regulatory: [
        {
            id: 'REG-001', code: 'API-510', description: 'Pressure Vessel Inspection',
            assetTypes: ['separator', 'dehydrator'], intervalDays: 365,
            maxToleranceDays: 30, authority: 'API / State RRC',
            penaltyRisk: 'Facility shutdown order if overdue',
        },
        {
            id: 'REG-002', code: 'API-570', description: 'Piping Inspection',
            assetTypes: ['pipeline'], intervalDays: 365,
            maxToleranceDays: 30, authority: 'API / PHMSA',
            penaltyRisk: 'PHMSA enforcement action',
        },
        {
            id: 'REG-003', code: 'OSHA-PSM', description: 'Process Safety Management Audit',
            assetTypes: ['compressor', 'separator', 'valve'], intervalDays: 365,
            maxToleranceDays: 0, authority: 'OSHA 29 CFR 1910.119',
            penaltyRisk: 'OSHA citation — up to $156,259 per willful violation',
        },
        {
            id: 'REG-004', code: 'EPA-UIC-VI', description: 'CO2 Injection Well MIT (Mechanical Integrity Test)',
            assetTypes: ['wellhead'], intervalDays: 365,
            maxToleranceDays: 14, authority: 'EPA UIC Class VI / State RRC',
            penaltyRisk: 'Injection permit suspension',
        },
        {
            id: 'REG-005', code: 'API-RP-14C', description: 'Safety System Function Test',
            assetTypes: ['valve'], intervalDays: 180,
            maxToleranceDays: 14, authority: 'API RP 14C / BSEE',
            penaltyRisk: 'Production shutdown order',
        },
        {
            id: 'REG-006', code: 'NACE-SP0775', description: 'Internal Corrosion Inspection',
            assetTypes: ['separator', 'pump', 'pipeline'], intervalDays: 365,
            maxToleranceDays: 30, authority: 'NACE / Operator SOP',
            penaltyRisk: 'Equipment failure / environmental release',
        },
        {
            id: 'REG-007', code: 'EPA-LDAR', description: 'Leak Detection and Repair Survey',
            assetTypes: ['compressor', 'separator', 'valve', 'pump'], intervalDays: 90,
            maxToleranceDays: 7, authority: 'EPA 40 CFR 60 Subpart OOOOa',
            penaltyRisk: 'EPA NOV — up to $113,268/day per violation',
        },
        {
            id: 'REG-008', code: 'FISCAL-CAL', description: 'Fiscal Meter Calibration',
            assetTypes: ['meter'], intervalDays: 90,
            maxToleranceDays: 7, authority: 'Custody Transfer Agreement / API MPMS',
            penaltyRisk: 'Revenue allocation dispute',
        },
    ],
    criticalAssets: ['COMP-001', 'COMP-002', 'SEP-001', 'SEP-002', 'VLV-001', 'MEM-001'],
    safetyFlags: {
        tagTypes: ['compressor', 'separator', 'valve', 'wellhead', 'heater'],
        alwaysTagCritical: true,
    },
};

// ── PM/CBM Templates ────────────────────────────────────────────────────
const MAINTENANCE_PLANS = [
    { id: 'MP-001', assetType: 'compressor', planType: 'PM', description: 'Compressor full PM — oil change, valve inspection, packing check', intervalDays: 30, estimatedHours: 6, requiredSkills: ['compressor', 'mechanical'], partsRequired: ['oil-filter', 'valve-packing', 'compressor-oil'], regulatoryId: null },
    { id: 'MP-002', assetType: 'compressor', planType: 'CBM', description: 'Vibration-triggered bearing inspection', triggerCondition: 'vibration > 3.5 mm/s', estimatedHours: 4, requiredSkills: ['compressor', 'vibration_analysis'], partsRequired: ['bearing-set'], regulatoryId: null },
    { id: 'MP-003', assetType: 'separator', planType: 'PM', description: 'Separator PM — level controls, dump valves, corrosion coupon', intervalDays: 60, estimatedHours: 4, requiredSkills: ['separator', 'mechanical'], partsRequired: ['gasket-set', 'corrosion-coupon'], regulatoryId: 'REG-001' },
    { id: 'MP-004', assetType: 'pump', planType: 'PM', description: 'Injection pump PM — packing, plunger, valve inspection', intervalDays: 30, estimatedHours: 5, requiredSkills: ['pump', 'mechanical'], partsRequired: ['pump-packing', 'plunger-seal'], regulatoryId: null },
    { id: 'MP-005', assetType: 'pump', planType: 'CBM', description: 'Pump vibration-triggered maintenance', triggerCondition: 'vibration > 4.0 mm/s OR current > 95%', estimatedHours: 6, requiredSkills: ['pump', 'bearing'], partsRequired: ['bearing-set', 'pump-packing'], regulatoryId: null },
    { id: 'MP-006', assetType: 'valve', planType: 'PM', description: 'ESD valve function test and overhaul', intervalDays: 180, estimatedHours: 3, requiredSkills: ['valve', 'pressure_test'], partsRequired: ['valve-seal-kit'], regulatoryId: 'REG-005' },
    { id: 'MP-007', assetType: 'wellhead', planType: 'PM', description: 'Wellhead MIT and pressure test', intervalDays: 365, estimatedHours: 8, requiredSkills: ['wellhead', 'pressure_test'], partsRequired: ['test-plug', 'seal-ring'], regulatoryId: 'REG-004' },
    { id: 'MP-008', assetType: 'meter', planType: 'PM', description: 'Fiscal meter calibration and proving', intervalDays: 90, estimatedHours: 3, requiredSkills: ['instrumentation', 'meter'], partsRequired: ['cal-gas', 'seal-set'], regulatoryId: 'REG-008' },
    { id: 'MP-009', assetType: 'dehydrator', planType: 'PM', description: 'Glycol system PM — filter, glycol analysis, reboiler check', intervalDays: 30, estimatedHours: 4, requiredSkills: ['dehydrator', 'chemical'], partsRequired: ['glycol-filter', 'glycol-sample-kit'], regulatoryId: null },
    { id: 'MP-010', assetType: 'heater', planType: 'PM', description: 'Heater treater — burner, firebox, safety shutoff test', intervalDays: 30, estimatedHours: 3, requiredSkills: ['heater', 'mechanical'], partsRequired: ['burner-nozzle', 'thermocouple'], regulatoryId: null },
];

// ── Parts Inventory ─────────────────────────────────────────────────────
const INVENTORY = [
    { partId: 'oil-filter', description: 'Compressor oil filter', assetTypes: ['compressor'], qtyOnHand: 12, qtyReserved: 2, leadTimeDays: 3, facilityId: 'FAC-COMP' },
    { partId: 'valve-packing', description: 'Compressor valve packing set', assetTypes: ['compressor'], qtyOnHand: 6, qtyReserved: 0, leadTimeDays: 5, facilityId: 'FAC-COMP' },
    { partId: 'compressor-oil', description: 'Synthetic compressor oil (5 gal)', assetTypes: ['compressor'], qtyOnHand: 8, qtyReserved: 1, leadTimeDays: 2, facilityId: 'FAC-COMP' },
    { partId: 'bearing-set', description: 'Radial bearing set', assetTypes: ['compressor', 'pump'], qtyOnHand: 4, qtyReserved: 1, leadTimeDays: 7, facilityId: 'FAC-COMP' },
    { partId: 'gasket-set', description: 'Separator gasket set', assetTypes: ['separator'], qtyOnHand: 10, qtyReserved: 0, leadTimeDays: 3, facilityId: 'FAC-CPF' },
    { partId: 'corrosion-coupon', description: 'Corrosion monitoring coupon', assetTypes: ['separator'], qtyOnHand: 20, qtyReserved: 0, leadTimeDays: 1, facilityId: 'FAC-CPF' },
    { partId: 'pump-packing', description: 'Triplex pump packing set', assetTypes: ['pump'], qtyOnHand: 3, qtyReserved: 1, leadTimeDays: 5, facilityId: 'FAC-CPF' },
    { partId: 'plunger-seal', description: 'Pump plunger seal kit', assetTypes: ['pump'], qtyOnHand: 2, qtyReserved: 0, leadTimeDays: 10, facilityId: 'FAC-CPF' },
    { partId: 'valve-seal-kit', description: 'ESD valve seal kit', assetTypes: ['valve'], qtyOnHand: 5, qtyReserved: 0, leadTimeDays: 4, facilityId: 'FAC-CPF' },
    { partId: 'test-plug', description: 'Wellhead test plug', assetTypes: ['wellhead'], qtyOnHand: 3, qtyReserved: 0, leadTimeDays: 7, facilityId: 'FAC-CPF' },
    { partId: 'seal-ring', description: 'Wellhead seal ring', assetTypes: ['wellhead'], qtyOnHand: 6, qtyReserved: 0, leadTimeDays: 3, facilityId: 'FAC-CPF' },
    { partId: 'cal-gas', description: 'Calibration gas cylinder', assetTypes: ['meter'], qtyOnHand: 4, qtyReserved: 0, leadTimeDays: 5, facilityId: 'FAC-CPF' },
    { partId: 'seal-set', description: 'Meter seal set', assetTypes: ['meter'], qtyOnHand: 8, qtyReserved: 0, leadTimeDays: 2, facilityId: 'FAC-CPF' },
    { partId: 'glycol-filter', description: 'Glycol dehydrator filter', assetTypes: ['dehydrator'], qtyOnHand: 6, qtyReserved: 0, leadTimeDays: 3, facilityId: 'FAC-CO2R' },
    { partId: 'glycol-sample-kit', description: 'Glycol analysis sample kit', assetTypes: ['dehydrator'], qtyOnHand: 10, qtyReserved: 0, leadTimeDays: 1, facilityId: 'FAC-CO2R' },
    { partId: 'burner-nozzle', description: 'Heater burner nozzle', assetTypes: ['heater'], qtyOnHand: 2, qtyReserved: 0, leadTimeDays: 7, facilityId: 'FAC-CPF' },
    { partId: 'thermocouple', description: 'Type K thermocouple', assetTypes: ['heater', 'separator'], qtyOnHand: 15, qtyReserved: 0, leadTimeDays: 1, facilityId: 'FAC-CPF' },
];

function getConstraintRules() {
    return CONSTRAINT_RULES;
}

function checkCompliance(assetId, proposedAction) {
    const { regulatory, guardrails } = CONSTRAINT_RULES;
    const violations = [];

    if (proposedAction.type === 'move' || proposedAction.type === 'cancel') {
        // Check regulatory rules
        for (const rule of regulatory) {
            if (proposedAction.regulatoryId === rule.id) {
                if (proposedAction.type === 'cancel') {
                    violations.push({
                        ruleId: rule.id, code: rule.code, severity: 'BLOCKED',
                        message: `Cannot cancel regulatory maintenance: ${rule.description} (${rule.authority})`,
                    });
                }
                if (proposedAction.type === 'move' && proposedAction.moveDays > rule.maxToleranceDays) {
                    violations.push({
                        ruleId: rule.id, code: rule.code, severity: 'BLOCKED',
                        message: `Cannot move ${rule.description} by ${proposedAction.moveDays} days — max tolerance is ${rule.maxToleranceDays} days (${rule.authority})`,
                    });
                }
            }
        }
        // Check guardrails
        if (proposedAction.type === 'move' && Math.abs(proposedAction.moveDays) > guardrails.maxMoveDays) {
            violations.push({
                ruleId: 'GUARDRAIL-001', code: 'MAX_MOVE', severity: 'REQUIRES_APPROVAL',
                message: `Move exceeds ±${guardrails.maxMoveDays} day guardrail — supervisor approval required`,
            });
        }
    }
    return {
        compliant: violations.filter(v => v.severity === 'BLOCKED').length === 0,
        requiresApproval: violations.some(v => v.severity === 'REQUIRES_APPROVAL'),
        violations,
    };
}

function getMaintenancePlans(assetType) {
    if (assetType) return MAINTENANCE_PLANS.filter(p => p.assetType === assetType);
    return MAINTENANCE_PLANS;
}

function getInventory(assetType, facilityId) {
    let result = [...INVENTORY];
    if (assetType) result = result.filter(p => p.assetTypes.includes(assetType));
    if (facilityId) result = result.filter(p => p.facilityId === facilityId);
    return result.map(p => ({
        ...p,
        available: p.qtyOnHand - p.qtyReserved,
        inStock: (p.qtyOnHand - p.qtyReserved) > 0,
    }));
}
