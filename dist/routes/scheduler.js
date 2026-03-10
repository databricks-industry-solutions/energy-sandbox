"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const rbac_1 = require("../middleware/rbac");
const agent_1 = require("../scheduler/agent");
const assets_1 = require("../scheduler/assets");
const technicians_1 = require("../scheduler/technicians");
const compliance_1 = require("../scheduler/compliance");

const router = (0, express_1.Router)();
const auth = (0, rbac_1.requireRole)(rbac_1.ROLES.PROD_ENGINEER, rbac_1.ROLES.SHIFT_SUPERVISOR, rbac_1.ROLES.AI_AGENT_PROD);

// ── 1) Asset and condition data ─────────────────────────────────────────

// GET /assets
router.get('/assets', auth, (req, res) => {
    const { facility_id, criticality, type } = req.query;
    res.json(assets_1.getAssets({ facility_id, criticality, type }));
});

// GET /assets/:id/telemetry
router.get('/assets/:id/telemetry', auth, (req, res) => {
    const { from, to } = req.query;
    const data = assets_1.getAssetTelemetry(req.params.id, from, to);
    if (!data.length) return res.status(404).json({ error: 'Asset not found' });
    res.json(data);
});

// GET /assets/:id/maintenance-history
router.get('/assets/:id/maintenance-history', auth, (req, res) => {
    const { from, to } = req.query;
    const data = assets_1.getAssetMaintenanceHistory(req.params.id, from, to);
    if (!data.length) return res.status(404).json({ error: 'Asset not found' });
    res.json(data);
});

// ── 2) Maintenance plans and work orders ────────────────────────────────

// GET /maintenance-plans
router.get('/maintenance-plans', auth, (req, res) => {
    res.json(compliance_1.getMaintenancePlans(req.query.asset_type));
});

// POST /workorders
router.post('/workorders', auth, (req, res) => {
    const wo = agent_1.createWorkOrder(req.body);
    res.status(201).json(wo);
});

// PATCH /workorders/:id
router.patch('/workorders/:id', auth, (req, res) => {
    const result = agent_1.patchWorkOrder(req.params.id, req.body);
    if (!result) return res.status(404).json({ error: 'Work order not found' });
    if (result.error) return res.status(409).json(result);
    res.json(result);
});

// GET /workorders
router.get('/workorders', auth, (req, res) => {
    const { status, technician_id, date, facility_id, safety } = req.query;
    res.json(agent_1.getWorkOrders({ status, technician_id, date, facility_id, safety: safety === 'true' }));
});

// ── 3) Technicians, routes, availability ────────────────────────────────

// GET /technicians
router.get('/technicians', auth, (_req, res) => {
    res.json(technicians_1.getTechnicians());
});

// GET /technicians/:id/schedule
router.get('/technicians/:id/schedule', auth, (req, res) => {
    const sched = technicians_1.getTechnicianSchedule(req.params.id, req.query.date);
    if (!sched) return res.status(404).json({ error: 'Technician not found' });
    res.json(sched);
});

// PATCH /technicians/:id/schedule
router.patch('/technicians/:id/schedule', auth, (req, res) => {
    const result = technicians_1.updateTechnicianSchedule(req.params.id, req.body.date, req.body.jobs);
    res.json(result);
});

// ── 4) Inventory and constraints ────────────────────────────────────────

// GET /inventory/parts
router.get('/inventory/parts', auth, (req, res) => {
    res.json(compliance_1.getInventory(req.query.asset_type, req.query.facility_id));
});

// GET /constraints/rules
router.get('/constraints/rules', auth, (_req, res) => {
    res.json(compliance_1.getConstraintRules());
});

// ── 5) Notifications and summaries ──────────────────────────────────────

// POST /notifications
router.post('/notifications', auth, (req, res) => {
    res.status(201).json(agent_1.postNotification(req.body));
});

// GET /agent/daily-summary
router.get('/agent/daily-summary', auth, (req, res) => {
    res.json(agent_1.getDailySummary(req.query.date, req.query.facility_id));
});

// POST /agent/run — trigger agent cycle
router.post('/agent/run', auth, (_req, res) => {
    const result = agent_1.runSchedulerAgent();
    res.json(result);
});

// GET /agent/audit-log
router.get('/agent/audit-log', auth, (req, res) => {
    res.json(agent_1.getAuditLog(req.query.from, req.query.to, req.query.limit ? parseInt(req.query.limit) : 50));
});

// GET /agent/model-metrics
router.get('/agent/model-metrics', auth, (_req, res) => {
    res.json(agent_1.getModelMetrics());
});

// GET /compliance/report
router.get('/compliance/report', auth, (req, res) => {
    const wos = agent_1.getWorkOrders({ safety: true });
    const rules = compliance_1.getConstraintRules();
    const auditLog = agent_1.getAuditLog(req.query.from, req.query.to, 200);
    const exceptions = auditLog.filter(l => l.type === 'compliance_exception');
    res.json({
        safetyCriticalTasks: wos.filter(wo => wo.safetyFlag),
        complianceTasks: wos.filter(wo => wo.complianceFlag),
        regulatoryRules: rules.regulatory,
        complianceExceptions: exceptions,
        generatedAt: new Date().toISOString(),
    });
});

exports.default = router;
