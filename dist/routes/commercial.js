"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rbac_1 = require("../middleware/rbac");
const provider_1 = require("../twin/provider");
const economics_1 = require("../commercial/economics");
const router = (0, express_1.Router)();
const provider = new provider_1.InMemoryTwinDataProvider();
const auth = (0, rbac_1.requireRole)(rbac_1.ROLES.COMMERCIAL_ANALYST, rbac_1.ROLES.FINANCE, rbac_1.ROLES.AI_AGENT_COMM);
// Well-level economics
router.get('/well-economics', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, economics_1.getWellEconomics)(state));
});
// CO2 supply contracts
router.get('/co2-contracts', auth, async (_req, res) => {
    res.json((0, economics_1.getCO2Contracts)());
});
// Carbon credits
router.get('/carbon-credits', auth, async (_req, res) => {
    res.json((0, economics_1.getCarbonCredits)());
});
// Field-level economics summary
router.get('/field-summary', auth, async (_req, res) => {
    const state = await provider.loadState();
    res.json((0, economics_1.getFieldEconomicsSummary)(state));
});
exports.default = router;
