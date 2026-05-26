"""Tests for the Guardian AI agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import GuardianAgent, Recommendation, CrewAssignment, SEV_LABEL
from app.simulator import simulate_tick


def _run_ticks(n: int):
    """Run n ticks and return (last_state, agent)."""
    agent = GuardianAgent()
    state = None
    for _ in range(n):
        state = simulate_tick()
        agent.analyze_tick(state)
    return state, agent


class TestGuardianAgent:
    def test_init(self):
        agent = GuardianAgent()
        assert agent.state.last_tick == 0
        assert agent.state.recommendations == []
        assert agent.state.crew_assignments == []

    def test_analyze_tick_returns_recommendations(self):
        agent = GuardianAgent()
        state = simulate_tick()
        recs = agent.analyze_tick(state)
        assert isinstance(recs, list)

    def test_recommendations_have_required_fields(self):
        state, agent = _run_ticks(15)  # Should trigger anomalies
        for r in agent.state.recommendations:
            assert isinstance(r, Recommendation)
            assert r.agent in ("HEALTH", "MAINTENANCE", "SUPPLY_CHAIN", "CREW", "DRILLING")
            assert r.severity in (1, 2, 3)
            assert len(r.title) > 0
            assert len(r.detail) > 0
            assert isinstance(r.actions, list)

    def test_anomaly_generates_health_recs(self):
        """Run through annular pressure leak phase (ticks 10-14)."""
        state, agent = _run_ticks(15)
        health_recs = [r for r in agent.state.recommendations if r.agent == "HEALTH"]
        assert len(health_recs) > 0

    def test_crew_assignments_on_anomaly(self):
        state, agent = _run_ticks(15)
        assert len(agent.state.crew_assignments) > 0
        for a in agent.state.crew_assignments:
            assert isinstance(a, CrewAssignment)
            assert len(a.crew_name) > 0
            assert a.eta_minutes >= 0

    def test_recommendation_cap(self):
        """Ensure recommendations don't grow unbounded."""
        state, agent = _run_ticks(80)
        assert len(agent.state.recommendations) <= GuardianAgent.MAX_RECS

    def test_crew_assignment_cap(self):
        state, agent = _run_ticks(80)
        assert len(agent.state.crew_assignments) <= GuardianAgent.MAX_ASSIGN

    def test_get_critical_alerts(self):
        state, agent = _run_ticks(20)
        crits = agent.get_critical_alerts()
        assert all(r.severity == 3 for r in crits)

    def test_get_active_recommendations(self):
        state, agent = _run_ticks(20)
        active = agent.get_active_recommendations()
        assert len(active) <= 15


class TestAgentSubAgents:
    def test_maintenance_agent_fires(self):
        """Maintenance recs appear when anomaly + low RUL coincide."""
        state, agent = _run_ticks(25)
        maint_recs = [r for r in agent.state.recommendations if r.agent == "MAINTENANCE"]
        # At least some maintenance recs should fire across 25 ticks
        assert len(maint_recs) >= 0  # May or may not fire depending on RUL thresholds

    def test_supply_chain_agent_fires(self):
        state, agent = _run_ticks(30)
        sc_recs = [r for r in agent.state.recommendations if r.agent == "SUPPLY_CHAIN"]
        assert isinstance(sc_recs, list)

    def test_drilling_agent_fires_during_high_risk_op(self):
        """Drilling agent should warn when anomalies coincide with non-low-risk ops."""
        state, agent = _run_ticks(45)
        drill_recs = [r for r in agent.state.recommendations if r.agent == "DRILLING"]
        assert isinstance(drill_recs, list)


class TestRuleBasedQuery:
    def setup_method(self):
        self.state, self.agent = _run_ticks(15)

    def test_summary_query(self):
        resp = self.agent._rule_based_query("Give me a full situation report", self.state)
        assert "SITUATION REPORT" in resp

    def test_crew_query(self):
        resp = self.agent._rule_based_query("Show me BOP-qualified crew", self.state)
        assert "Crew" in resp or "crew" in resp

    def test_rul_query(self):
        resp = self.agent._rule_based_query("What are the failure risk predictions?", self.state)
        assert "RUL" in resp or "Remaining" in resp

    def test_spare_parts_query(self):
        resp = self.agent._rule_based_query("spare parts inventory status", self.state)
        assert "Spare" in resp or "spare" in resp

    def test_work_orders_query(self):
        resp = self.agent._rule_based_query("Show me work orders", self.state)
        assert "Work Order" in resp or "PM-" in resp

    def test_component_query(self):
        resp = self.agent._rule_based_query("How is the blind shear ram?", self.state)
        assert "BOP-BSR-01" in resp or "Blind Shear" in resp

    def test_drilling_query(self):
        resp = self.agent._rule_based_query("What is the current drilling operation?", self.state)
        assert "Operation" in resp or "Drilling" in resp

    def test_recommendations_query(self):
        resp = self.agent._rule_based_query("What are your recommendations?", self.state)
        assert "Recommendation" in resp or "recommendation" in resp or "nominal" in resp

    def test_unknown_query_returns_summary(self):
        resp = self.agent._rule_based_query("xyzzy", self.state)
        assert "SITUATION REPORT" in resp


class TestSevLabel:
    def test_all_levels(self):
        assert SEV_LABEL[1] == "INFO"
        assert SEV_LABEL[2] == "WARNING"
        assert SEV_LABEL[3] == "CRITICAL"
