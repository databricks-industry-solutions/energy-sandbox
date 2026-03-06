import { Router, Request, Response } from 'express';
import { requireRole, ROLES } from '../middleware/rbac';
import { InMemoryTwinDataProvider } from '../twin/provider';
import { ShiftLogEntry } from '../twin/types';

const router = Router();
const provider = new InMemoryTwinDataProvider();

// GET /api/shift/current
router.get(
  '/current',
  requireRole(ROLES.SHIFT_SUPERVISOR, ROLES.PROD_ENGINEER, ROLES.AI_AGENT_PROD),
  async (_req: Request, res: Response) => {
    const state = await provider.loadState();
    res.json(state.shiftLog);
  },
);

// POST /api/shift/log — add entry
router.post(
  '/log',
  requireRole(ROLES.SHIFT_SUPERVISOR, ROLES.PROD_ENGINEER),
  async (req: Request, res: Response) => {
    const { category, message, entityId, agentId } = req.body as {
      category?: ShiftLogEntry['category'];
      message?: string;
      entityId?: string;
      agentId?: string;
    };

    if (!category || !message) {
      return res.status(400).json({ error: 'category and message are required' });
    }

    const state = await provider.loadState();
    const entry: ShiftLogEntry = {
      timestamp: new Date().toISOString(),
      category,
      message,
      entityId: entityId ?? null,
      agentId: agentId ?? null,
    };

    state.shiftLog.entries.push(entry);
    res.json({ success: true, entry });
  },
);

// POST /api/shift/handoff — create handoff entry
router.post(
  '/handoff',
  requireRole(ROLES.SHIFT_SUPERVISOR),
  async (req: Request, res: Response) => {
    const { incomingOperator, notes } = req.body as {
      incomingOperator?: string;
      notes?: string;
    };

    if (!incomingOperator) {
      return res.status(400).json({ error: 'incomingOperator is required' });
    }

    const state = await provider.loadState();
    const outgoing = state.shiftLog.operator;
    const handoffEntry: ShiftLogEntry = {
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
  },
);

export default router;
