"""Tests for the LLM integration module."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.simulator import simulate_tick
from app.agent import GuardianAgent


class TestSystemPromptBuilder:
    def setup_method(self):
        self.agent = GuardianAgent()
        self.state = simulate_tick()
        self.agent.analyze_tick(self.state)

    def test_builds_prompt_with_all_sections(self):
        from app.llm import _build_system_prompt
        prompt = _build_system_prompt(self.state, self.agent.state)
        assert "Guardian AI" in prompt
        assert "Component Health" in prompt
        assert "Active Anomalies" in prompt
        assert "RUL Predictions" in prompt
        assert "SAP Work Orders" in prompt
        assert "Spare Parts" in prompt
        assert "Crew On Rig" in prompt

    def test_prompt_includes_rig_info(self):
        from app.llm import _build_system_prompt
        prompt = _build_system_prompt(self.state, self.agent.state)
        assert "Deepwater Sentinel" in prompt
        assert str(self.state["tick"]) in prompt

    def test_prompt_includes_all_components(self):
        from app.llm import _build_system_prompt
        prompt = _build_system_prompt(self.state, self.agent.state)
        for comp in ("BOP-ANN-01", "BOP-BSR-01", "POD-A", "PMP-01", "ACC-01", "PLC-01"):
            assert comp in prompt

    def test_prompt_includes_all_crew(self):
        from app.llm import _build_system_prompt
        prompt = _build_system_prompt(self.state, self.agent.state)
        assert "McAllister" in prompt
        assert "Santos" in prompt


class TestChatFallback:
    def test_returns_none_when_no_client(self):
        """chat() returns None when WorkspaceClient is unavailable."""
        import app.llm as llm_mod
        llm_mod._client = None

        with patch("app.llm._get_client", return_value=None):
            from app.llm import chat
            state = simulate_tick()
            agent = GuardianAgent()
            result = chat("test query", state, agent.state)
            assert result is None

    def test_returns_none_on_api_error(self):
        """chat() returns None when the API call raises an exception."""
        mock_client = MagicMock()
        mock_client.serving_endpoints.query.side_effect = Exception("API error")

        with patch("app.llm._get_client", return_value=mock_client):
            from app.llm import chat
            state = simulate_tick()
            agent = GuardianAgent()
            result = chat("test query", state, agent.state)
            assert result is None

    def test_returns_content_on_success(self):
        """chat() returns LLM content when API succeeds."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response from LLM"

        mock_client = MagicMock()
        mock_client.serving_endpoints.query.return_value = mock_response

        with patch("app.llm._get_client", return_value=mock_client):
            from app.llm import chat
            state = simulate_tick()
            agent = GuardianAgent()
            result = chat("test query", state, agent.state)
            assert result == "Test response from LLM"


class TestHandleQueryIntegration:
    def test_falls_back_to_rules_when_llm_unavailable(self):
        """handle_query returns rule-based response when LLM fails."""
        agent = GuardianAgent()
        state = simulate_tick()
        agent.analyze_tick(state)

        with patch("app.llm.chat", return_value=None):
            resp = agent.handle_query("Give me a situation report", state)
            assert "SITUATION REPORT" in resp

    def test_uses_llm_when_available(self):
        """handle_query returns LLM response when available."""
        agent = GuardianAgent()
        state = simulate_tick()
        agent.analyze_tick(state)

        with patch("app.llm.chat", return_value="LLM-powered analysis of BOP status"):
            resp = agent.handle_query("How is the BOP?", state)
            assert resp == "LLM-powered analysis of BOP status"


class TestModelConfig:
    def test_default_model(self):
        from app.llm import MODEL_NAME, MAX_TOKENS, TEMPERATURE
        assert "llama" in MODEL_NAME.lower() or "databricks" in MODEL_NAME.lower()
        assert MAX_TOKENS > 0
        assert 0 <= TEMPERATURE <= 2
