import { Router } from 'express';
import { requireRole, ROLES } from '../middleware/rbac';
import { InMemoryTwinDataProvider } from '../twin/provider';
import {
  getWellEconomics,
  getCO2Contracts,
  getCarbonCredits,
  getFieldEconomicsSummary,
} from '../commercial/economics';

const router = Router();
const provider = new InMemoryTwinDataProvider();

const auth = requireRole(ROLES.COMMERCIAL_ANALYST, ROLES.FINANCE, ROLES.AI_AGENT_COMM);

// Well-level economics
router.get('/well-economics', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(getWellEconomics(state));
});

// CO2 supply contracts
router.get('/co2-contracts', auth, async (_req, res) => {
  res.json(getCO2Contracts());
});

// Carbon credits
router.get('/carbon-credits', auth, async (_req, res) => {
  res.json(getCarbonCredits());
});

// Field-level economics summary
router.get('/field-summary', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(getFieldEconomicsSummary(state));
});

export default router;
