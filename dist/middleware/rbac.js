"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ROLES = void 0;
exports.attachDemoUser = attachDemoUser;
exports.requireRole = requireRole;
exports.ROLES = {
    PROD_ENGINEER: 'ROLE_PROD_ENGINEER',
    RESERVOIR_ENGINEER: 'ROLE_RESERVOIR_ENGINEER',
    COMMERCIAL_ANALYST: 'ROLE_COMMERCIAL_ANALYST',
    HSE: 'ROLE_HSE',
    SHIFT_SUPERVISOR: 'ROLE_SHIFT_SUPERVISOR',
    FINANCE: 'ROLE_FINANCE',
    AI_AGENT_PROD: 'ROLE_AI_AGENT_PROD',
    AI_AGENT_COMM: 'ROLE_AI_AGENT_COMM',
};
function attachDemoUser(req, _res, next) {
    req.user = {
        id: 'demo-user',
        name: 'Demo Operator',
        roles: [
            exports.ROLES.PROD_ENGINEER,
            exports.ROLES.RESERVOIR_ENGINEER,
            exports.ROLES.COMMERCIAL_ANALYST,
            exports.ROLES.SHIFT_SUPERVISOR,
        ],
    };
    next();
}
function requireRole(...roles) {
    return (req, res, next) => {
        if (!req.user)
            return res.status(401).json({ error: 'Unauthorized' });
        const hasRole = req.user.roles.some((r) => roles.includes(r));
        if (!hasRole)
            return res.status(403).json({ error: 'Forbidden' });
        next();
    };
}
