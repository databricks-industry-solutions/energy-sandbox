import { Request, Response, NextFunction } from 'express';

export const ROLES = {
  PROD_ENGINEER: 'ROLE_PROD_ENGINEER',
  RESERVOIR_ENGINEER: 'ROLE_RESERVOIR_ENGINEER',
  COMMERCIAL_ANALYST: 'ROLE_COMMERCIAL_ANALYST',
  HSE: 'ROLE_HSE',
  SHIFT_SUPERVISOR: 'ROLE_SHIFT_SUPERVISOR',
  FINANCE: 'ROLE_FINANCE',
  AI_AGENT_PROD: 'ROLE_AI_AGENT_PROD',
  AI_AGENT_COMM: 'ROLE_AI_AGENT_COMM',
} as const;

declare global {
  namespace Express {
    interface Request {
      user?: { id: string; name: string; roles: string[] };
    }
  }
}

export function attachDemoUser(req: Request, _res: Response, next: NextFunction) {
  req.user = {
    id: 'demo-user',
    name: 'Demo Operator',
    roles: [
      ROLES.PROD_ENGINEER,
      ROLES.RESERVOIR_ENGINEER,
      ROLES.COMMERCIAL_ANALYST,
      ROLES.SHIFT_SUPERVISOR,
    ],
  };
  next();
}

export function requireRole(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) return res.status(401).json({ error: 'Unauthorized' });
    const hasRole = req.user.roles.some((r) => roles.includes(r));
    if (!hasRole) return res.status(403).json({ error: 'Forbidden' });
    next();
  };
}
