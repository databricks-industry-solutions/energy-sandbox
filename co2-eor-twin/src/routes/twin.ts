import { Router } from 'express';
import { requireRole, ROLES } from '../middleware/rbac';
import { InMemoryTwinDataProvider } from '../twin/provider';
import {
  analyzeFacilityConstraints,
  analyzeFlaringRisk,
  analyzeInjectionEfficiency,
  analyzePatternPerformance,
  analyzeCO2Balance,
} from '../twin/analytics';

const router = Router();
const provider = new InMemoryTwinDataProvider();

const auth = requireRole(ROLES.PROD_ENGINEER, ROLES.RESERVOIR_ENGINEER, ROLES.AI_AGENT_PROD);

// Full twin state
router.get('/state', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(state);
});

// Facility constraints
router.get('/facility-constraints', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(analyzeFacilityConstraints(state));
});

// Flaring risk
router.get('/flaring-risk', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(analyzeFlaringRisk(state));
});

// Injection efficiency
router.get('/injection-efficiency', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(analyzeInjectionEfficiency(state));
});

// Pattern performance
router.get('/pattern-performance', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(analyzePatternPerformance(state));
});

// CO2 balance
router.get('/co2-balance', auth, async (_req, res) => {
  const state = await provider.loadState();
  res.json(analyzeCO2Balance(state));
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

export default router;
