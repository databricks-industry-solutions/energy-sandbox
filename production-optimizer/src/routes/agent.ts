import { Router, Request, Response } from 'express';
import { requireRole, ROLES } from '../middleware/rbac';
import { InMemoryTwinDataProvider } from '../twin/provider';
import { genieClient } from './genie';

const router = Router();
const provider = new InMemoryTwinDataProvider();

const HIDDEN_PROP_KEYS = new Set(['color', 'geometry', 'layerType', '_vectorTileFeature']);

function describeFeature(f: Record<string, unknown>): string {
  const name = (f.name as string) || (f.id as string) || (f.well_id as string) || 'asset';
  const pairs = Object.entries(f)
    .filter(([k, v]) => !HIDDEN_PROP_KEYS.has(k) && v !== null && v !== undefined && v !== '' && k !== 'name')
    .slice(0, 8)
    .map(([k, v]) => `${k}=${v}`)
    .join(', ');
  return pairs ? `${name} (${pairs})` : name;
}

// POST /api/agent/query — delegates to Genie
router.post(
  '/query',
  requireRole(ROLES.PROD_ENGINEER, ROLES.RESERVOIR_ENGINEER, ROLES.COMMERCIAL_ANALYST, ROLES.AI_AGENT_PROD, ROLES.AI_AGENT_COMM),
  async (req: Request, res: Response) => {
    const { prompt, selectedEntities, conversation_id } = req.body as {
      prompt?: string;
      selectedEntities?: Array<Record<string, unknown>>;
      conversation_id?: string;
    };

    if (!prompt) {
      return res.status(400).json({ error: 'prompt is required' });
    }

    const features = Array.isArray(selectedEntities) ? selectedEntities : [];
    const contextLine = features.length
      ? `Context — selected ${features.length === 1 ? 'asset' : 'assets'}: ${features.map(describeFeature).join('; ')}.`
      : '';
    const question = contextLine ? `${contextLine}\n\n${prompt.trim()}` : prompt.trim();

    try {
      const result = await genieClient.askSync(question, conversation_id);
      const counts: Record<string, number> = { selected: features.length };
      if (Array.isArray(result.rows)) counts.rows = result.rows.length;
      res.json({
        summary: result.text || result.error || 'No response from Genie.',
        agentRole: 'genie',
        contextCounts: counts,
        conversation_id: result.conversation_id,
        sql: result.sql,
        columns: result.columns,
        rows: result.rows,
      });
    } catch (e: any) {
      console.error('[agent.query] genie error:', e?.message || e);
      res.status(502).json({
        summary: `Genie error: ${e?.message || e}`,
        agentRole: 'genie',
      });
    }
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
