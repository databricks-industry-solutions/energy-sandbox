"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.runSchedulerAgent = runSchedulerAgent;
exports.getDailySummary = getDailySummary;
exports.getWorkOrders = getWorkOrders;
exports.createWorkOrder = createWorkOrder;
exports.patchWorkOrder = patchWorkOrder;
exports.getAuditLog = getAuditLog;
exports.getModelMetrics = getModelMetrics;
exports.postNotification = postNotification;

const assets_1 = require("./assets");
const technicians_1 = require("./technicians");
const compliance_1 = require("./compliance");

// ── In-memory state ─────────────────────────────────────────────────────
let _workOrders = [];
let _auditLog = [];
let _notifications = [];
let _lastRunAt = null;
let _runCount = 0;
let _modelMetrics = {
    precision: 0.84, recall: 0.78, f1: 0.81,
    falsePositives: 3, falseNegatives: 1,
    totalPredictions: 142, correctPredictions: 119,
    degraded: false, lastEvaluated: new Date().toISOString(),
    unplannedFailureReduction: 0.23,
    baselineUnplannedFailures: 18,
    currentUnplannedFailures: 14,
};

// Seed initial work orders on first load
let _seeded = false;
function _seedIfNeeded() {
    if (_seeded) return;
    _seeded = true;
    const now = new Date();
    const allAssets = assets_1.getAssets();
    // Create initial scheduled PMs
    allAssets.forEach((asset, i) => {
        const plans = compliance_1.getMaintenancePlans(asset.type);
        if (plans.length === 0) return;
        const plan = plans[0];
        const dueDate = new Date(asset.nextPmDate);
        const wo = {
            id: `WO-${String(1000 + i).padStart(5, '0')}`,
            assetId: asset.id,
            assetName: asset.name,
            assetType: asset.type,
            facilityId: asset.facilityId,
            facilityName: asset.facilityName,
            jobType: plan.planType,
            description: plan.description,
            priority: asset.criticality === 'critical' ? 1 : asset.criticality === 'high' ? 2 : 3,
            severity: asset.criticality,
            dueStart: dueDate.toISOString(),
            dueEnd: new Date(dueDate.getTime() + 2 * 86400000).toISOString(),
            estimatedHours: plan.estimatedHours,
            assignedTechnicianId: null,
            assignedTechnicianName: null,
            status: 'scheduled',
            createdBy: 'system',
            reason: `Scheduled ${plan.planType} per maintenance plan ${plan.id} — interval ${plan.intervalDays} days`,
            agentReasonUpdate: null,
            regulatoryId: plan.regulatoryId,
            safetyFlag: asset.safetyFlag,
            complianceFlag: !!plan.regulatoryId,
            fallbackMode: false,
            partsRequired: plan.partsRequired,
            createdAt: new Date(now.getTime() - 7 * 86400000).toISOString(),
            updatedAt: new Date(now.getTime() - 7 * 86400000).toISOString(),
        };
        _workOrders.push(wo);
    });
    // Run the agent once to generate predictive WOs
    runSchedulerAgent();
}

// ═════════════════════════════════════════════════════════════════════════
// PERCEIVE — gather asset telemetry, condition, and context
// ═════════════════════════════════════════════════════════════════════════
function _perceive() {
    const allAssets = assets_1.getAssets();
    const rules = compliance_1.getConstraintRules();
    const perceptions = [];

    for (const asset of allAssets) {
        const s = asset.sensors;
        const history = assets_1.getAssetMaintenanceHistory(asset.id);
        const plans = compliance_1.getMaintenancePlans(asset.type);
        const existingWOs = _workOrders.filter(wo => wo.assetId === asset.id && wo.status !== 'completed' && wo.status !== 'cancelled');
        const inventory = compliance_1.getInventory(asset.type, asset.facilityId);

        // Calculate risk score from live sensors
        let risk = asset.riskScore;
        let failProb = asset.failureProbability;
        let faults = [];
        let dataQuality = 'good';

        // Check for missing/out-of-range data
        if (s.vibration === 0 && s.temperature === 0 && s.pressure === 0) {
            dataQuality = 'missing';
        } else if (s.vibration > 10 || s.temperature > 300 || s.current > 150) {
            dataQuality = 'out_of_range';
        }

        // Fault detection rules
        if (s.vibration > 4.0) {
            faults.push({ code: 'HIGH_VIBRATION', severity: 'CRITICAL', value: s.vibration, threshold: 4.0 });
            risk = Math.min(1.0, risk + 0.25);
            failProb = Math.min(1.0, failProb + 0.20);
        } else if (s.vibration > 3.0) {
            faults.push({ code: 'ELEVATED_VIBRATION', severity: 'HIGH', value: s.vibration, threshold: 3.0 });
            risk = Math.min(1.0, risk + 0.15);
            failProb = Math.min(1.0, failProb + 0.10);
        }
        if (s.temperature > 200) {
            faults.push({ code: 'CRITICAL_TEMP', severity: 'CRITICAL', value: s.temperature, threshold: 200 });
            risk = Math.min(1.0, risk + 0.25);
            failProb = Math.min(1.0, failProb + 0.15);
        } else if (s.temperature > 185) {
            faults.push({ code: 'HIGH_TEMP', severity: 'HIGH', value: s.temperature, threshold: 185 });
            risk = Math.min(1.0, risk + 0.10);
        }
        if (s.current > 100) {
            faults.push({ code: 'OVERLOAD', severity: 'CRITICAL', value: s.current, threshold: 100 });
            risk = Math.min(1.0, risk + 0.20);
            failProb = Math.min(1.0, failProb + 0.15);
        } else if (s.current > 92) {
            faults.push({ code: 'HIGH_LOAD', severity: 'HIGH', value: s.current, threshold: 92 });
            risk = Math.min(1.0, risk + 0.08);
        }

        perceptions.push({
            assetId: asset.id, assetName: asset.name, assetType: asset.type,
            facilityId: asset.facilityId, facilityName: asset.facilityName,
            criticality: asset.criticality,
            sensors: s, riskScore: +risk.toFixed(3), failureProbability: +failProb.toFixed(3),
            faults, dataQuality,
            existingWOs: existingWOs.length,
            nextPmDate: asset.nextPmDate, lastPmDate: asset.lastPmDate,
            daysSinceLastPm: Math.floor((Date.now() - new Date(asset.lastPmDate).getTime()) / 86400000),
            plans, inventory,
            isCriticalAsset: rules.criticalAssets.includes(asset.id),
        });
    }
    return perceptions;
}

// ═════════════════════════════════════════════════════════════════════════
// REASON — rank, predict, decide maintenance timing
// ═════════════════════════════════════════════════════════════════════════
function _reason(perceptions) {
    const rules = compliance_1.getConstraintRules();
    const decisions = [];

    for (const p of perceptions) {
        // Skip if no faults and PM is not overdue
        const pmDue = new Date(p.nextPmDate);
        const now = new Date();
        const daysUntilPm = (pmDue.getTime() - now.getTime()) / 86400000;
        const hasFaults = p.faults.length > 0;
        const pmOverdue = daysUntilPm < 0;
        const pmSoon = daysUntilPm <= 7;

        if (!hasFaults && !pmOverdue && !pmSoon) continue;

        // Fallback mode if data quality is bad
        const fallbackMode = p.dataQuality === 'missing' || p.dataQuality === 'out_of_range';

        // Build decision
        let action = 'none';
        let reason = '';
        let priority = 3;
        let dueWindow = 7;
        let jobType = 'PM';

        if (fallbackMode) {
            action = 'keep_schedule';
            reason = `FALLBACK MODE: Data quality "${p.dataQuality}" for ${p.assetName}. Maintaining fixed preventive schedule. Human review required.`;
            priority = 2;
        } else if (hasFaults) {
            const topFault = p.faults[0];
            if (topFault.severity === 'CRITICAL') {
                action = p.existingWOs > 0 ? 'reschedule' : 'create';
                priority = 1;
                dueWindow = 1;
                jobType = 'CBM';
                reason = `${p.assetName}: ${topFault.code} detected (${topFault.value} > ${topFault.threshold} threshold). ` +
                    `Risk score ${(p.riskScore * 100).toFixed(0)}%, failure probability ${(p.failureProbability * 100).toFixed(0)}%. ` +
                    `${action === 'create' ? 'Creating urgent predictive work order.' : 'Rescheduling existing WO to immediate window.'}`;
            } else {
                action = p.existingWOs > 0 ? 'adjust' : 'create';
                priority = 2;
                dueWindow = 3;
                jobType = 'CBM';
                const prevRisk = p.riskScore - 0.15;
                reason = `${p.assetName}: ${topFault.code} — risk increased from ${(prevRisk * 100).toFixed(0)}% to ${(p.riskScore * 100).toFixed(0)}%. ` +
                    `Moved PM forward by ${Math.floor(daysUntilPm - dueWindow)} days based on condition trend.`;
            }
        } else if (pmOverdue) {
            action = 'escalate';
            priority = 1;
            dueWindow = 0;
            reason = `${p.assetName}: PM overdue by ${Math.abs(Math.floor(daysUntilPm))} days. Escalating to immediate scheduling.`;
        } else if (pmSoon) {
            action = 'confirm';
            priority = 3;
            dueWindow = Math.ceil(daysUntilPm);
            reason = `${p.assetName}: Scheduled PM in ${Math.ceil(daysUntilPm)} days. Confirmed — no condition-based changes needed.`;
        }

        // Check parts availability
        const partsAvailable = p.inventory.every(inv => inv.available > 0);
        if (!partsAvailable && (action === 'create' || action === 'reschedule')) {
            const missing = p.inventory.filter(inv => inv.available <= 0);
            const maxLead = Math.max(...missing.map(m => m.leadTimeDays));
            reason += ` Parts constraint: ${missing.map(m => m.description).join(', ')} unavailable (${maxLead}d lead time).`;
            if (priority > 1) dueWindow = Math.max(dueWindow, maxLead);
        }

        // Determine required skill
        const plan = p.plans[0];
        const requiredSkills = plan ? plan.requiredSkills : ['mechanical'];

        decisions.push({
            assetId: p.assetId, assetName: p.assetName, assetType: p.assetType,
            facilityId: p.facilityId, facilityName: p.facilityName,
            criticality: p.criticality,
            action, jobType, priority, dueWindowDays: dueWindow,
            riskScore: p.riskScore, failureProbability: p.failureProbability,
            faults: p.faults, reason, fallbackMode,
            requiredSkills, regulatoryId: plan?.regulatoryId || null,
            safetyFlag: p.isCriticalAsset || p.faults.some(f => f.severity === 'CRITICAL'),
            existingWOs: p.existingWOs,
        });
    }

    // Sort by priority (1 = most urgent)
    decisions.sort((a, b) => a.priority - b.priority || b.riskScore - a.riskScore);
    return decisions;
}

// ═════════════════════════════════════════════════════════════════════════
// ACT — create/update work orders, assign technicians, notify
// ═════════════════════════════════════════════════════════════════════════
function _act(decisions) {
    const now = new Date();
    const techs = technicians_1.getTechnicians();
    const rules = compliance_1.getConstraintRules();
    const changes = [];

    for (const dec of decisions) {
        if (dec.action === 'none' || dec.action === 'confirm') continue;

        // Check compliance before acting
        if (dec.action === 'reschedule' || dec.action === 'adjust') {
            const existing = _workOrders.find(wo => wo.assetId === dec.assetId && wo.status === 'scheduled');
            if (existing) {
                const compCheck = compliance_1.checkCompliance(dec.assetId, {
                    type: 'move', regulatoryId: existing.regulatoryId,
                    moveDays: -dec.dueWindowDays,
                });
                if (!compCheck.compliant) {
                    _auditLog.push({
                        timestamp: now.toISOString(), type: 'compliance_exception',
                        assetId: dec.assetId, action: dec.action,
                        reason: compCheck.violations.map(v => v.message).join('; '),
                        agentDecision: 'BLOCKED',
                    });
                    changes.push({ type: 'blocked', assetId: dec.assetId, reason: compCheck.violations[0].message });
                    continue;
                }
                // Update existing WO
                const newDue = new Date(now.getTime() + dec.dueWindowDays * 86400000);
                existing.dueStart = newDue.toISOString();
                existing.dueEnd = new Date(newDue.getTime() + 2 * 86400000).toISOString();
                existing.priority = dec.priority;
                existing.agentReasonUpdate = dec.reason;
                existing.safetyFlag = dec.safetyFlag || existing.safetyFlag;
                existing.fallbackMode = dec.fallbackMode;
                existing.updatedAt = now.toISOString();
                changes.push({ type: 'rescheduled', woId: existing.id, assetId: dec.assetId, reason: dec.reason });
                continue;
            }
        }

        if (dec.action === 'create' || dec.action === 'escalate') {
            // Assign best technician
            let assignedTech = null;
            for (const tech of techs) {
                if (tech.remainingHours < (dec.jobType === 'CBM' ? 4 : 6)) continue;
                const hasSkill = dec.requiredSkills.some(sk => tech.skills.includes(sk));
                if (hasSkill) { assignedTech = tech; break; }
            }
            if (!assignedTech) {
                // Fallback: any tech with capacity
                assignedTech = techs.find(t => t.remainingHours >= 4) || null;
            }

            const newDue = new Date(now.getTime() + dec.dueWindowDays * 86400000);
            const woId = `WO-AI-${String(2000 + _workOrders.length).padStart(5, '0')}`;
            const wo = {
                id: woId,
                assetId: dec.assetId, assetName: dec.assetName, assetType: dec.assetType,
                facilityId: dec.facilityId, facilityName: dec.facilityName,
                jobType: dec.jobType,
                description: `AI-generated ${dec.jobType} — ${dec.faults.map(f => f.code).join(', ') || 'PM escalation'}`,
                priority: dec.priority,
                severity: dec.criticality,
                dueStart: newDue.toISOString(),
                dueEnd: new Date(newDue.getTime() + 2 * 86400000).toISOString(),
                estimatedHours: dec.jobType === 'CBM' ? 4 : 6,
                assignedTechnicianId: assignedTech?.id || null,
                assignedTechnicianName: assignedTech?.name || 'UNASSIGNED',
                status: 'scheduled',
                createdBy: 'agent',
                reason: dec.reason,
                agentReasonUpdate: null,
                regulatoryId: dec.regulatoryId,
                safetyFlag: dec.safetyFlag,
                complianceFlag: !!dec.regulatoryId,
                fallbackMode: dec.fallbackMode,
                partsRequired: [],
                createdAt: now.toISOString(),
                updatedAt: now.toISOString(),
            };
            _workOrders.push(wo);
            changes.push({ type: 'created', woId, assetId: dec.assetId, reason: dec.reason, techName: assignedTech?.name });

            // Update tech schedule
            if (assignedTech) {
                const sched = technicians_1.getTechnicianSchedule(assignedTech.id);
                const jobs = sched?.jobs || [];
                jobs.push({
                    woId, assetId: dec.assetId, assetName: dec.assetName,
                    description: wo.description, estimatedHours: wo.estimatedHours,
                    priority: wo.priority, sequence: jobs.length + 1,
                });
                technicians_1.updateTechnicianSchedule(assignedTech.id, null, jobs);
            }

            // Generate notification for urgent items
            if (dec.priority === 1 || dec.safetyFlag) {
                _notifications.push({
                    id: `NOTIF-${_notifications.length + 1}`,
                    timestamp: now.toISOString(),
                    target: assignedTech?.id || 'supervisor',
                    targetName: assignedTech?.name || 'Supervisor',
                    channel: 'mobile',
                    type: dec.safetyFlag ? 'safety_critical' : 'urgent_insertion',
                    message: `New job added: ${dec.assetName} — ${dec.faults[0]?.code || 'PM escalation'} ` +
                        `(risk ${(dec.riskScore * 100).toFixed(0)}%). Due within ${dec.dueWindowDays} day(s).`,
                    woId, read: false,
                });
            }
        }

        // Audit log
        _auditLog.push({
            timestamp: now.toISOString(), type: 'agent_action',
            assetId: dec.assetId, action: dec.action,
            reason: dec.reason,
            riskScore: dec.riskScore, failureProbability: dec.failureProbability,
            faults: dec.faults.map(f => f.code),
            fallbackMode: dec.fallbackMode,
            agentDecision: dec.action.toUpperCase(),
            modelVersion: 'v2.3.1',
            inputSnapshot: { sensors: dec.faults, dataQuality: dec.fallbackMode ? 'degraded' : 'good' },
        });
    }

    return changes;
}

// ═════════════════════════════════════════════════════════════════════════
// PUBLIC API
// ═════════════════════════════════════════════════════════════════════════

function runSchedulerAgent() {
    _seedIfNeeded();
    const perceptions = _perceive();
    const decisions = _reason(perceptions);
    const changes = _act(decisions);
    _lastRunAt = new Date().toISOString();
    _runCount++;

    return {
        runAt: _lastRunAt,
        runCount: _runCount,
        perceptionsCount: perceptions.length,
        decisionsCount: decisions.length,
        changesCount: changes.length,
        changes,
        modelMetrics: _modelMetrics,
    };
}

function getDailySummary(date, facilityId) {
    _seedIfNeeded();
    const d = date || new Date().toISOString().split('T')[0];
    const startOfDay = new Date(d + 'T00:00:00Z').getTime();
    const endOfDay = startOfDay + 86400000;

    let wos = _workOrders.filter(wo => {
        const t = new Date(wo.updatedAt).getTime();
        return t >= startOfDay && t < endOfDay;
    });
    if (facilityId) wos = wos.filter(wo => wo.facilityId === facilityId);

    let logs = _auditLog.filter(l => {
        const t = new Date(l.timestamp).getTime();
        return t >= startOfDay && t < endOfDay;
    });

    // Group by facility
    const byFacility = {};
    for (const wo of wos) {
        const key = wo.facilityId;
        if (!byFacility[key]) byFacility[key] = { facilityId: key, facilityName: wo.facilityName, workOrders: [], changes: 0, created: 0, rescheduled: 0, cancelled: 0 };
        byFacility[key].workOrders.push(wo);
        if (wo.createdBy === 'agent') byFacility[key].created++;
    }

    const notifs = _notifications.filter(n => {
        const t = new Date(n.timestamp).getTime();
        return t >= startOfDay && t < endOfDay;
    });

    return {
        date: d,
        generatedAt: new Date().toISOString(),
        lastAgentRun: _lastRunAt,
        totalRunsToday: _runCount,
        totalWorkOrders: wos.length,
        agentCreatedWOs: wos.filter(wo => wo.createdBy === 'agent').length,
        criticalActions: wos.filter(wo => wo.priority === 1).length,
        safetyFlagged: wos.filter(wo => wo.safetyFlag).length,
        fallbackModeCount: wos.filter(wo => wo.fallbackMode).length,
        facilitySummary: Object.values(byFacility),
        notifications: notifs,
        auditEntries: logs.length,
        modelHealth: {
            ..._modelMetrics,
            status: _modelMetrics.degraded ? 'DEGRADED — human review required' : 'HEALTHY',
        },
        complianceExceptions: logs.filter(l => l.type === 'compliance_exception').length,
    };
}

function getWorkOrders(filters) {
    _seedIfNeeded();
    let result = [..._workOrders];
    if (filters) {
        if (filters.status) result = result.filter(wo => wo.status === filters.status);
        if (filters.technician_id) result = result.filter(wo => wo.assignedTechnicianId === filters.technician_id);
        if (filters.date) {
            const d = filters.date;
            result = result.filter(wo => wo.dueStart?.startsWith(d) || wo.createdAt?.startsWith(d));
        }
        if (filters.facility_id) result = result.filter(wo => wo.facilityId === filters.facility_id);
        if (filters.safety) result = result.filter(wo => wo.safetyFlag);
    }
    return result;
}

function createWorkOrder(body) {
    _seedIfNeeded();
    const now = new Date();
    const woId = `WO-MAN-${String(3000 + _workOrders.length).padStart(5, '0')}`;
    const wo = {
        id: woId,
        assetId: body.asset, assetName: body.assetName || body.asset,
        assetType: body.assetType || 'unknown',
        facilityId: body.facilityId || '', facilityName: body.facilityName || '',
        jobType: body.jobType || 'PM',
        description: body.description || '',
        priority: body.priority || 2,
        severity: body.severity || 'medium',
        dueStart: body.dueStart || now.toISOString(),
        dueEnd: body.dueEnd || new Date(now.getTime() + 2 * 86400000).toISOString(),
        estimatedHours: body.estimatedHours || 4,
        assignedTechnicianId: body.assignedTechnicianId || null,
        assignedTechnicianName: body.assignedTechnicianName || null,
        status: 'scheduled',
        createdBy: body.created_by || 'manual',
        reason: body.reason || '',
        agentReasonUpdate: null,
        regulatoryId: body.regulatoryId || null,
        safetyFlag: body.safetyFlag || false,
        complianceFlag: body.complianceFlag || false,
        fallbackMode: false,
        partsRequired: body.partsRequired || [],
        createdAt: now.toISOString(),
        updatedAt: now.toISOString(),
    };
    _workOrders.push(wo);
    return wo;
}

function patchWorkOrder(woId, updates) {
    _seedIfNeeded();
    const wo = _workOrders.find(w => w.id === woId);
    if (!wo) return null;

    // Compliance check for reschedules
    if (updates.dueStart && wo.regulatoryId) {
        const origDue = new Date(wo.dueStart);
        const newDue = new Date(updates.dueStart);
        const moveDays = (newDue.getTime() - origDue.getTime()) / 86400000;
        const check = compliance_1.checkCompliance(wo.assetId, {
            type: 'move', regulatoryId: wo.regulatoryId, moveDays,
        });
        if (!check.compliant) {
            return { error: 'COMPLIANCE_BLOCKED', violations: check.violations };
        }
    }

    const allowed = ['dueStart', 'dueEnd', 'priority', 'assignedTechnicianId', 'assignedTechnicianName', 'status', 'agentReasonUpdate', 'safetyFlag'];
    for (const key of allowed) {
        if (updates[key] !== undefined) wo[key] = updates[key];
    }
    wo.updatedAt = new Date().toISOString();
    return wo;
}

function getAuditLog(from, to, limit) {
    _seedIfNeeded();
    let result = [..._auditLog];
    if (from) result = result.filter(l => l.timestamp >= from);
    if (to) result = result.filter(l => l.timestamp <= to);
    result.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    if (limit) result = result.slice(0, limit);
    return result;
}

function getModelMetrics() {
    return _modelMetrics;
}

function postNotification(body) {
    const notif = {
        id: `NOTIF-${_notifications.length + 1}`,
        timestamp: new Date().toISOString(),
        target: body.target,
        targetName: body.targetName || body.target,
        channel: body.channel || 'mobile',
        type: body.type || 'info',
        message: body.message,
        woId: body.woId || null,
        read: false,
    };
    _notifications.push(notif);
    return notif;
}
