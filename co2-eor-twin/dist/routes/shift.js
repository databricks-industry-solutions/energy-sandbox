"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rbac_1 = require("../middleware/rbac");
const provider_1 = require("../twin/provider");
const router = (0, express_1.Router)();
const provider = new provider_1.InMemoryTwinDataProvider();
// GET /api/shift/current
router.get('/current', (0, rbac_1.requireRole)(rbac_1.ROLES.SHIFT_SUPERVISOR, rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.AI_AGENT_PROD), async (_req, res) => {
    const state = await provider.loadState();
    res.json(state.shiftLog);
});
// POST /api/shift/log — add entry
router.post('/log', (0, rbac_1.requireRole)(rbac_1.ROLES.SHIFT_SUPERVISOR, rbac_1.ROLES.PROD_ENGINEER), async (req, res) => {
    const { category, message, entityId, agentId } = req.body;
    if (!category || !message) {
        return res.status(400).json({ error: 'category and message are required' });
    }
    const state = await provider.loadState();
    const entry = {
        timestamp: new Date().toISOString(),
        category,
        message,
        entityId: entityId ?? null,
        agentId: agentId ?? null,
    };
    state.shiftLog.entries.push(entry);
    res.json({ success: true, entry });
});
// POST /api/shift/handoff — create handoff entry
router.post('/handoff', (0, rbac_1.requireRole)(rbac_1.ROLES.SHIFT_SUPERVISOR), async (req, res) => {
    const { incomingOperator, notes } = req.body;
    if (!incomingOperator) {
        return res.status(400).json({ error: 'incomingOperator is required' });
    }
    const state = await provider.loadState();
    const outgoing = state.shiftLog.operator;
    const handoffEntry = {
        timestamp: new Date().toISOString(),
        category: 'handoff',
        message: `Shift handoff: ${outgoing} -> ${incomingOperator}. ${notes ?? 'No additional notes.'}`,
        entityId: null,
        agentId: null,
    };
    state.shiftLog.entries.push(handoffEntry);
    // Update shift operator
    state.shiftLog.operator = incomingOperator;
    const currentHour = new Date().getUTCHours();
    state.shiftLog.shift = currentHour >= 6 && currentHour < 18 ? 'day' : 'night';
    res.json({
        success: true,
        handoff: {
            from: outgoing,
            to: incomingOperator,
            shift: state.shiftLog.shift,
            timestamp: handoffEntry.timestamp,
        },
    });
});
exports.default = router;
