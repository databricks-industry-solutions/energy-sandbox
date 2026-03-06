import { Router, Request, Response } from 'express';
import { requireRole, ROLES } from '../middleware/rbac';
import { InMemoryTwinDataProvider } from '../twin/provider';
import { getWellEconomics, getFieldEconomicsSummary } from '../commercial/economics';

const router = Router();
const provider = new InMemoryTwinDataProvider();

// POST /api/agent/query
router.post(
  '/query',
  requireRole(ROLES.PROD_ENGINEER, ROLES.RESERVOIR_ENGINEER, ROLES.COMMERCIAL_ANALYST, ROLES.AI_AGENT_PROD, ROLES.AI_AGENT_COMM),
  async (req: Request, res: Response) => {
    const { prompt, selectedEntities, agentRole } = req.body as {
      prompt?: string;
      selectedEntities?: string[];
      agentRole?: string;
    };

    if (!prompt) {
      return res.status(400).json({ error: 'prompt is required' });
    }

    const state = await provider.loadState();

    // Gather context for selected entities
    const entities = selectedEntities ?? [];
    const relevantWells = state.wells.filter((w) => entities.includes(w.id));
    const relevantFacilities = state.facilities.filter((f) => entities.includes(f.id));
    const relevantPatterns = state.patterns.filter((p) => entities.includes(p.id));
    const relevantAlerts = state.alerts.filter((a) => entities.includes(a.source));

    // Gather economics if commercial role
    let economics = null;
    if (!agentRole || agentRole === 'commercial') {
      const wellEcon = getWellEconomics(state).filter((e) => entities.includes(e.wellId));
      const fieldSummary = getFieldEconomicsSummary(state);
      economics = { wellEcon, fieldSummary };
    }

    res.json({
      summary: 'TODO: Claude API integration — this endpoint will forward the prompt and context to Claude for analysis',
      prompt,
      agentRole: agentRole ?? 'general',
      contextCounts: {
        wells: relevantWells.length,
        facilities: relevantFacilities.length,
        patterns: relevantPatterns.length,
        alerts: relevantAlerts.length,
        hasEconomics: economics !== null,
      },
      context: {
        wells: relevantWells,
        facilities: relevantFacilities,
        patterns: relevantPatterns,
        alerts: relevantAlerts,
        economics,
      },
    });
  },
);

// POST /api/agent/proposal/:id/approve
router.post(
  '/proposal/:id/approve',
  requireRole(ROLES.PROD_ENGINEER, ROLES.SHIFT_SUPERVISOR),
  async (req: Request, res: Response) => {
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
  },
);

// POST /api/agent/proposal/:id/reject
router.post(
  '/proposal/:id/reject',
  requireRole(ROLES.PROD_ENGINEER, ROLES.SHIFT_SUPERVISOR),
  async (req: Request, res: Response) => {
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
  },
);

// GET /api/agent/proposals
router.get(
  '/proposals',
  requireRole(ROLES.PROD_ENGINEER, ROLES.SHIFT_SUPERVISOR, ROLES.AI_AGENT_PROD),
  async (_req: Request, res: Response) => {
    const state = await provider.loadState();
    const allProposals = state.agents.flatMap((a) =>
      a.pendingProposals.map((p) => ({ ...p, agentRole: a.role })),
    );
    res.json(allProposals);
  },
);

export default router;
