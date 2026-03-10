"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rbac_1 = require("../middleware/rbac");
const provider_1 = require("../twin/provider");
const analytics_1 = require("../twin/analytics");
const router = (0, express_1.Router)();
const provider = new provider_1.InMemoryTwinDataProvider();
const auth = (0, rbac_1.requireRole)(rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.RESERVOIR_ENGINEER, rbac_1.ROLES.AI_AGENT_PROD);
// Full twin state
router.get('/state', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json(state);
});
// Facility constraints
router.get('/facility-constraints', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, analytics_1.analyzeFacilityConstraints)(state));
});
// Flaring risk
router.get('/flaring-risk', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, analytics_1.analyzeFlaringRisk)(state));
});
// Injection efficiency
router.get('/injection-efficiency', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, analytics_1.analyzeInjectionEfficiency)(state));
});
// Pattern performance
router.get('/pattern-performance', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, analytics_1.analyzePatternPerformance)(state));
});
// CO2 balance
router.get('/co2-balance', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, analytics_1.analyzeCO2Balance)(state));
});
// Alerts
router.get('/alerts', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json(state.alerts);
});
// Agent states
router.get('/agents', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json(state.agents);
});
exports.default = router;
