"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rbac_1 = require("../middleware/rbac");
const provider_1 = require("../twin/provider");
const economics_1 = require("../commercial/economics");
const router = (0, express_1.Router)();
const provider = new provider_1.InMemoryTwinDataProvider();

function generateResponse(prompt, state, entities, economics) {
    const q = prompt.toLowerCase();
    const wells = state.wells;
    const facilities = state.facilities;
    const patterns = state.patterns;
    const producers = wells.filter(w => w.type === 'producer');
    const injectors = wells.filter(w => w.type === 'injector' || w.type === 'WAG');
    const totalOil = producers.reduce((s, w) => s + w.oilRate, 0);
    const totalGas = producers.reduce((s, w) => s + w.gasRate, 0);
    const totalWater = producers.reduce((s, w) => s + w.waterRate, 0);
    const totalCO2Inj = injectors.reduce((s, w) => s + w.co2InjRate, 0);
    const avgWaterCut = producers.length > 0 ? (producers.reduce((s, w) => s + w.waterCut, 0) / producers.length).toFixed(1) : 0;
    const avgGOR = producers.length > 0 ? (producers.reduce((s, w) => s + w.gor, 0) / producers.length).toFixed(0) : 0;

    // Well-specific query
    if (q.match(/well\s+\w+-?\w+/i) || entities.length > 0) {
        const wellId = entities[0]?.id || (q.match(/well\s+([\w-]+)/i) || [])[1];
        const well = wellId ? wells.find(w => w.id.toLowerCase() === wellId.toLowerCase() || w.name.toLowerCase() === wellId.toLowerCase()) : null;
        if (well) {
            if (well.type === 'producer') {
                return `**${well.name}** (${well.type}, Pattern ${well.patternId}, Pad ${well.padId})\n\nCurrent Production:\n- Oil: ${well.oilRate} bbl/d\n- Gas: ${well.gasRate} Mcf/d\n- Water: ${well.waterRate} bbl/d\n- Water Cut: ${(well.waterCut * 100).toFixed(1)}%\n- GOR: ${well.gor} scf/bbl\n\nPressures:\n- Tubing: ${well.tubingPressure} psi\n- Casing: ${well.casingPressure} psi\n- Bottomhole: ${well.bottomholePressure} psi\n- Choke: ${well.chokePercent}%\n\nCO₂ Concentration: ${(well.co2Concentration * 100).toFixed(1)}%\n\nStatus: ${well.status}`;
            } else {
                return `**${well.name}** (${well.type}, Pattern ${well.patternId})\n\nInjection Rates:\n- CO₂: ${well.co2InjRate} Mcf/d\n- Water: ${well.waterInjRate} bbl/d\n\nPressures:\n- Tubing: ${well.tubingPressure} psi\n- Casing: ${well.casingPressure} psi\n- Bottomhole: ${well.bottomholePressure} psi\n\nStatus: ${well.status}`;
            }
        }
    }

    // Production queries
    if (q.includes('production') || q.includes('oil') || q.includes('output')) {
        const topProducer = producers.sort((a, b) => b.oilRate - a.oilRate)[0];
        const lowProducer = producers.sort((a, b) => a.oilRate - b.oilRate)[0];
        return `**Field Production Summary**\n\nTotal Oil: ${totalOil.toFixed(0)} bbl/d across ${producers.length} producers\nTotal Gas: ${totalGas.toFixed(0)} Mcf/d\nTotal Water: ${totalWater.toFixed(0)} bbl/d\nAvg Water Cut: ${avgWaterCut}%\nAvg GOR: ${avgGOR} scf/bbl\n\nTop Producer: ${topProducer.name} at ${topProducer.oilRate} bbl/d\nLowest Producer: ${lowProducer.name} at ${lowProducer.oilRate} bbl/d\n\nRecommendation: Monitor ${lowProducer.name} for potential workover or choke adjustment to improve rate.`;
    }

    // CO2/injection queries
    if (q.includes('co2') || q.includes('injection') || q.includes('carbon') || q.includes('inject')) {
        const co2Recycled = facilities.find(f => f.type === 'CO2_recycle')?.currentCO2Rate ?? 0;
        const co2Purchased = totalCO2Inj - co2Recycled;
        const utilization = totalCO2Inj > 0 ? ((totalCO2Inj - co2Purchased * 0.3) / totalCO2Inj * 100).toFixed(1) : 0;
        return `**CO₂ Injection & Storage Summary**\n\nTotal CO₂ Injected: ${totalCO2Inj.toFixed(0)} Mcf/d\nCO₂ Recycled: ${co2Recycled.toFixed(0)} Mcf/d\nCO₂ Purchased: ${co2Purchased.toFixed(0)} Mcf/d\nEstimated CO₂ Utilization: ${utilization}%\n\nActive Injectors: ${injectors.filter(w => w.status === 'flowing').length} of ${injectors.length}\n\nPattern Breakdown:\n${patterns.map(p => `- ${p.name}: ${p.co2InjRate?.toFixed(0) || 'N/A'} Mcf/d, Utilization ${((p.co2Utilization || 0.65) * 100).toFixed(0)}%`).join('\n')}\n\nRecommendation: Focus on improving CO₂ utilization in patterns below 65% — consider reducing injection rates or adjusting WAG ratios.`;
    }

    // Water cut queries
    if (q.includes('water') || q.includes('watercut') || q.includes('water cut')) {
        const highWC = producers.filter(w => w.waterCut > 0.5).sort((a, b) => b.waterCut - a.waterCut);
        return `**Water Cut Analysis**\n\nField Avg Water Cut: ${avgWaterCut}%\nHigh Water Cut Wells (>50%): ${highWC.length}\n\n${highWC.length > 0 ? highWC.map(w => `- ${w.name}: ${(w.waterCut * 100).toFixed(1)}% WC, ${w.oilRate} bbl/d oil`).join('\n') : 'No wells above 50% water cut.'}\n\nRecommendation: ${highWC.length > 0 ? `Review ${highWC[0].name} for potential water shutoff or recompletion. Rising water cut may indicate CO₂ breakthrough or aquifer encroachment.` : 'Water cuts are within normal range across all producers.'}`;
    }

    // Pressure queries
    if (q.includes('pressure') || q.includes('psi')) {
        const highPressure = wells.filter(w => w.bottomholePressure > 3300).sort((a, b) => b.bottomholePressure - a.bottomholePressure);
        return `**Pressure Analysis**\n\nWells with BHP > 3300 psi: ${highPressure.length}\n\n${highPressure.map(w => `- ${w.name} (${w.type}): BHP ${w.bottomholePressure} psi, THP ${w.tubingPressure} psi`).join('\n')}\n\nFracture pressure threshold: ~3500 psi\n\nRecommendation: ${highPressure.some(w => w.bottomholePressure > 3400) ? 'CAUTION — wells approaching fracture pressure. Consider reducing injection rates in affected patterns to avoid induced fracturing.' : 'All wells within safe pressure limits. Continue monitoring Pattern D closely.'}`;
    }

    // Facility queries
    if (q.includes('facility') || q.includes('facilities') || q.includes('capacity') || q.includes('utilization')) {
        return `**Facility Status**\n\n${facilities.map(f => `**${f.name}** (${f.type})\n- Utilization: ${(f.utilization * 100).toFixed(0)}%\n- Oil: ${f.currentOilRate}/${f.oilCapacity} bbl/d\n- Gas: ${f.currentGasRate}/${f.gasCapacity} Mcf/d\n- Water: ${f.currentWaterRate}/${f.waterCapacity} bbl/d\n- CO₂: ${f.currentCO2Rate}/${f.co2Capacity} Mcf/d\n- Emissions: ${f.emissions} tCO₂/d`).join('\n\n')}\n\nRecommendation: ${facilities.some(f => f.utilization > 0.85) ? 'Compression station approaching capacity — consider throttling injection or scheduling maintenance window.' : 'All facilities within normal operating limits.'}`;
    }

    // Economics
    if (q.includes('economic') || q.includes('cost') || q.includes('revenue') || q.includes('netback') || q.includes('money') || q.includes('profit')) {
        const oilPrice = 72;
        const gasPrice = 3.2;
        const revenue = totalOil * oilPrice + totalGas * gasPrice;
        const opex = totalOil * 18 + totalWater * 0.8;
        const co2Cost = totalCO2Inj * 1.05;
        const totalBoe = totalOil + totalGas / 6;
        const netback = totalBoe > 0 ? ((revenue - opex - co2Cost) / totalBoe).toFixed(2) : 0;
        return `**Field Economics**\n\nRevenue: $${(revenue / 1000).toFixed(1)}k/d\n- Oil: $${(totalOil * oilPrice / 1000).toFixed(1)}k/d (${totalOil.toFixed(0)} bbl/d @ $${oilPrice}/bbl)\n- Gas: $${(totalGas * gasPrice / 1000).toFixed(1)}k/d (${totalGas.toFixed(0)} Mcf/d @ $${gasPrice}/Mcf)\n\nCosts:\n- OpEx: $${(opex / 1000).toFixed(1)}k/d\n- CO₂ Purchase: $${(co2Cost / 1000).toFixed(1)}k/d\n\nNetback: $${netback}/boe\nTotal BOE: ${totalBoe.toFixed(0)} boe/d\n\nIncremental oil from EOR: ~${(totalOil - 2200).toFixed(0)} bbl/d above baseline`;
    }

    // Alert queries
    if (q.includes('alert') || q.includes('alarm') || q.includes('warning') || q.includes('issue') || q.includes('problem')) {
        const alerts = state.alerts || [];
        return `**Active Alerts (${alerts.length})**\n\n${alerts.map(a => `- [${a.severity?.toUpperCase() || 'INFO'}] ${a.message} (${a.source || 'system'})`).join('\n')}\n\nRecommendation: ${alerts.some(a => a.severity === 'critical' || a.severity === 'emergency') ? 'Critical alerts require immediate attention. Dispatch field crew to investigate.' : 'No critical alerts. Continue routine monitoring.'}`;
    }

    // Pattern queries
    if (q.includes('pattern')) {
        return `**Injection Pattern Summary**\n\n${patterns.map(p => `**${p.name}** (${p.id})\n- Wells: ${p.wellCount || 'N/A'}\n- Oil Rate: ${p.oilRate?.toFixed(0) || 'N/A'} bbl/d\n- CO₂ Inj: ${p.co2InjRate?.toFixed(0) || 'N/A'} Mcf/d\n- Utilization: ${((p.co2Utilization || 0.65) * 100).toFixed(0)}%\n- Reservoir Pressure: ${p.reservoirPressure?.toFixed(0) || 'N/A'} psi`).join('\n\n')}\n\nRecommendation: Optimize patterns with utilization below 65% by adjusting injection-to-production ratios.`;
    }

    // Default — field overview
    return `**Field Overview — Delaware Basin CO₂-EOR**\n\nProduction: ${totalOil.toFixed(0)} bbl/d oil, ${totalGas.toFixed(0)} Mcf/d gas\nWater: ${totalWater.toFixed(0)} bbl/d (${avgWaterCut}% avg WC)\nCO₂ Injection: ${totalCO2Inj.toFixed(0)} Mcf/d across ${injectors.length} injectors\nWells: ${producers.length} producers, ${injectors.length} injectors, ${wells.length} total\nPatterns: ${patterns.length} active\nFacilities: ${facilities.length} online\n\nActive Alerts: ${(state.alerts || []).length}\n\nAsk me about specific topics:\n- "production" — oil/gas/water rates\n- "CO2 injection" — injection rates and storage\n- "water cut" — water cut analysis\n- "pressure" — reservoir pressure monitoring\n- "facilities" — facility utilization\n- "economics" — revenue and netback\n- "alerts" — active alarms\n- "pattern" — injection pattern details\n- Any well name (e.g. "W-A01") — well details`;
}

// POST /api/agent/query
router.post('/query', (0, rbac_1.requireRole)(rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.RESERVOIR_ENGINEER, rbac_1.ROLES.COMMERCIAL_ANALYST, rbac_1.ROLES.AI_AGENT_PROD, rbac_1.ROLES.AI_AGENT_COMM), async (req, res) => {
    const { prompt, selectedEntities, agentRole } = req.body;
    if (!prompt) {
        return res.status(400).json({ error: 'prompt is required' });
    }
    const state = await provider.loadState();
    const entities = selectedEntities ?? [];
    const relevantWells = state.wells.filter((w) => entities.includes(w.id));
    const relevantFacilities = state.facilities.filter((f) => entities.includes(f.id));
    const relevantPatterns = state.patterns.filter((p) => entities.includes(p.id));
    const relevantAlerts = state.alerts.filter((a) => entities.includes(a.source));
    let economics = null;
    if (!agentRole || agentRole === 'commercial') {
        const wellEcon = (0, economics_1.getWellEconomics)(state).filter((e) => entities.includes(e.wellId));
        const fieldSummary = (0, economics_1.getFieldEconomicsSummary)(state);
        economics = { wellEcon, fieldSummary };
    }

    // Determine which agent role responds
    const q = prompt.toLowerCase();
    let responseRole = agentRole || 'general';
    if (!agentRole) {
        if (q.includes('cost') || q.includes('revenue') || q.includes('economic') || q.includes('netback') || q.includes('profit')) responseRole = 'commercial';
        else if (q.includes('co2') || q.includes('injection') || q.includes('pattern') || q.includes('pressure') || q.includes('reservoir')) responseRole = 'reservoir';
        else if (q.includes('maintenance') || q.includes('esp') || q.includes('failure') || q.includes('workover')) responseRole = 'maintenance';
        else if (q.includes('alert') || q.includes('alarm') || q.includes('safety') || q.includes('emission')) responseRole = 'monitoring';
        else responseRole = 'optimization';
    }

    const summary = generateResponse(prompt, state, entities, economics);

    res.json({
        summary,
        agentRole: responseRole,
        prompt,
        contextCounts: {
            wells: relevantWells.length,
            facilities: relevantFacilities.length,
            patterns: relevantPatterns.length,
            alerts: relevantAlerts.length,
            hasEconomics: economics !== null,
        },
    });
});
// POST /api/agent/proposal/:id/approve
router.post('/proposal/:id/approve', (0, rbac_1.requireRole)(rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.SHIFT_SUPERVISOR), async (req, res) => {
    const { id } = req.params;
    const state = await provider.loadState();
    for (const agent of state.agents) {
        const proposal = agent.pendingProposals.find((p) => p.id === id);
        if (proposal) {
            proposal.status = 'approved';
            proposal.approvedBy = req.user?.name ?? 'unknown';
            return res.json({ success: true, proposal });
        }
    }
    return res.status(404).json({ error: `Proposal ${id} not found` });
});
// POST /api/agent/proposal/:id/reject
router.post('/proposal/:id/reject', (0, rbac_1.requireRole)(rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.SHIFT_SUPERVISOR), async (req, res) => {
    const { id } = req.params;
    const state = await provider.loadState();
    for (const agent of state.agents) {
        const proposal = agent.pendingProposals.find((p) => p.id === id);
        if (proposal) {
            proposal.status = 'rejected';
            return res.json({ success: true, proposal });
        }
    }
    return res.status(404).json({ error: `Proposal ${id} not found` });
});
// GET /api/agent/proposals
router.get('/proposals', (0, rbac_1.requireRole)(rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.SHIFT_SUPERVISOR, rbac_1.ROLES.AI_AGENT_PROD), async (_req, res) => {
    const state = await provider.loadState();
    const allProposals = state.agents.flatMap((a) => a.pendingProposals.map((p) => ({ ...p, agentRole: a.role })));
    res.json(allProposals);
});
exports.default = router;
