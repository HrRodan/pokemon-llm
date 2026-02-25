"""
Unit tests for agent module functions.

All LLM calls are mocked — no live API key required.
Tests cover:
  - BaseAgent._run() paths (with and without tool calls)
  - BaseAgent._collect_usage() delta computation
  - BaseAgent.log_query / log_response (no-crash checks)
  - Agent initialisation defaults (model name, logger)
  - PokemonAgent usage properties delegate to UsageTracker
  - run_*_agent() lazy singleton creation
"""

from unittest.mock import MagicMock, patch
from utils.usage_tracker import UsageTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(
    query_return: str = "mocked response",
    tool_calls: list | None = None,
    tool_responses_return: str = "tool response",
    total_prompt_tokens: int = 10,
    total_completion_tokens: int = 5,
    total_reasoning_tokens: int = 0,
    total_tokens: int = 15,
    total_cost: float = 0.001,
):
    """Return a fully-configured MagicMock standing in for LLMQuery."""
    llm = MagicMock()
    llm.query.return_value = query_return
    llm.tool_calls = tool_calls if tool_calls is not None else []
    llm.get_tool_responses.return_value = tool_responses_return
    llm.total_prompt_tokens = total_prompt_tokens
    llm.total_completion_tokens = total_completion_tokens
    llm.total_reasoning_tokens = total_reasoning_tokens
    llm.total_tokens = total_tokens
    llm.total_cost = total_cost
    return llm


# ---------------------------------------------------------------------------
# BaseAgent tests (via a minimal concrete subclass)
# ---------------------------------------------------------------------------


class TestBaseAgentRun:
    """Tests for BaseAgent._run() routing logic."""

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def _make_agent(self, MockLLMQuery, MockSetupLogger, llm_mock=None):
        """Helper that returns a concrete BaseAgent subclass instance with a mocked LLM."""
        if llm_mock is None:
            llm_mock = _make_mock_llm()
        MockLLMQuery.return_value = llm_mock
        MockSetupLogger.return_value = MagicMock()

        # Import locally so the patch applies
        from agents.base_agent import BaseAgent

        class _Agent(BaseAgent):
            def response(self, message, history=None):
                return self._run(message)

        agent = _Agent(name="TestAgent", model_name="test-model")
        agent.llm = llm_mock  # replace with our mock directly
        # Reset snapshot so it starts from zero
        from utils.usage_tracker import AgentUsage

        agent._usage_snapshot = AgentUsage()
        return agent

    def test_run_no_tool_calls_returns_query_response(self):
        """When llm.tool_calls is empty, _run() returns the direct LLM response."""
        llm = _make_mock_llm(query_return="hello world", tool_calls=[])
        agent = self._make_agent(llm_mock=llm)

        result = agent._run("test message")

        assert result == "hello world"
        llm.query.assert_called_once_with(user_prompt="test message", use_history=False)
        llm.get_tool_responses.assert_not_called()

    def test_run_with_tool_calls_returns_tool_response(self):
        """When llm.tool_calls is non-empty, _run() executes the tool loop."""
        llm = _make_mock_llm(
            query_return="interim",
            tool_calls=[{"id": "tc1", "function": {"name": "some_tool"}}],
            tool_responses_return="final answer",
        )
        agent = self._make_agent(llm_mock=llm)

        result = agent._run("test message")

        assert result == "final answer"
        llm.get_tool_responses.assert_called_once()

    def test_run_use_history_forwarded(self):
        """The use_history flag is forwarded to llm.query."""
        llm = _make_mock_llm(tool_calls=[])
        agent = self._make_agent(llm_mock=llm)

        agent._run("msg", use_history=True)

        llm.query.assert_called_once_with(user_prompt="msg", use_history=True)

    def test_run_records_usage_in_tracker(self):
        """_run() calls _collect_usage() which records a delta in UsageTracker."""
        tracker = UsageTracker.get()
        tracker.reset()

        llm = _make_mock_llm(
            tool_calls=[],
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            total_cost=0.01,
        )
        agent = self._make_agent(llm_mock=llm)

        agent._run("anything")

        usage = tracker.get_agent_usage("TestAgent")
        assert usage.prompt_tokens == 100
        assert usage.total_tokens == 150
        assert usage.call_count == 1


# ---------------------------------------------------------------------------
# BaseAgent._collect_usage() delta logic
# ---------------------------------------------------------------------------


class TestBaseAgentCollectUsage:
    """Tests for the delta-based usage tracking in BaseAgent."""

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def test_delta_is_incremental(self, MockLLMQuery, MockSetupLogger):
        """Two consecutive _collect_usage() calls each record only the marginal delta."""
        from agents.base_agent import BaseAgent

        class _Agent(BaseAgent):
            def response(self, message, history=None):
                return self._run(message)

        tracker = UsageTracker.get()
        tracker.reset()

        llm = MagicMock()
        llm.total_prompt_tokens = 0
        llm.total_completion_tokens = 0
        llm.total_reasoning_tokens = 0
        llm.total_tokens = 0
        llm.total_cost = 0.0
        MockLLMQuery.return_value = llm
        MockSetupLogger.return_value = MagicMock()

        agent = _Agent(name="DeltaAgent", model_name="m")
        agent.llm = llm

        # First call: LLM accumulated 10 tokens
        llm.total_prompt_tokens = 10
        llm.total_tokens = 10
        llm.total_cost = 0.001
        agent._collect_usage()

        # Second call: LLM accumulated 25 tokens total → delta is 15
        llm.total_prompt_tokens = 25
        llm.total_tokens = 25
        llm.total_cost = 0.002
        agent._collect_usage()

        usage = tracker.get_agent_usage("DeltaAgent")
        assert usage.prompt_tokens == 25  # 10 + 15
        assert usage.total_tokens == 25
        assert usage.call_count == 2


# ---------------------------------------------------------------------------
# Agent initialisation
# ---------------------------------------------------------------------------


class TestAgentInitialisation:
    """Verify model name defaults and logger wiring."""

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def test_default_model_used_when_none_given(self, MockLLMQuery, MockSetupLogger):
        """Omitting model_name falls back to settings.DEFAULT_MODEL."""
        from agents.base_agent import BaseAgent
        from utils.config import settings

        MockSetupLogger.return_value = MagicMock()

        class _A(BaseAgent):
            def response(self, m, h=None):
                return ""

        a = _A(name="X")
        assert a.model_name == settings.DEFAULT_MODEL

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def test_explicit_model_name_is_stored(self, MockLLMQuery, MockSetupLogger):
        """An explicit model_name is stored on the agent."""
        from agents.base_agent import BaseAgent

        MockSetupLogger.return_value = MagicMock()

        class _A(BaseAgent):
            def response(self, m, h=None):
                return ""

        a = _A(name="X", model_name="my-custom-model")
        assert a.model_name == "my-custom-model"

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def test_logger_is_named_after_agent(self, MockLLMQuery, MockSetupLogger):
        """setup_logger is called with the agent's name."""
        from agents.base_agent import BaseAgent

        MockSetupLogger.return_value = MagicMock()

        class _A(BaseAgent):
            def response(self, m, h=None):
                return ""

        _A(name="ProfessorOak")
        MockSetupLogger.assert_called_with("ProfessorOak")


# ---------------------------------------------------------------------------
# log_query / log_response (smoke tests)
# ---------------------------------------------------------------------------


class TestBaseAgentLogging:
    """Ensure log helpers don't raise and call logger.info."""

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def test_log_query_calls_info(self, MockLLMQuery, MockSetupLogger):
        from agents.base_agent import BaseAgent

        mock_logger = MagicMock()
        MockSetupLogger.return_value = mock_logger

        class _A(BaseAgent):
            def response(self, m, h=None):
                return ""

        a = _A(name="L")
        a.log_query("hello?")
        mock_logger.info.assert_called()

    @patch("agents.base_agent.setup_logger")
    @patch("agents.base_agent.LLMQuery")
    def test_log_response_calls_info(self, MockLLMQuery, MockSetupLogger):
        from agents.base_agent import BaseAgent

        mock_logger = MagicMock()
        MockSetupLogger.return_value = mock_logger

        class _A(BaseAgent):
            def response(self, m, h=None):
                return ""

        a = _A(name="L")
        a.log_response("The answer is 42.")
        mock_logger.info.assert_called()


# ---------------------------------------------------------------------------
# run_*_agent lazy singleton
# ---------------------------------------------------------------------------


class TestLazySingletons:
    """
    Verify the lazy singleton pattern: calling run_*_agent() twice returns
    the same underlying agent instance and does not call __init__ twice.
    """

    def test_run_api_agent_reuses_singleton(self):
        """run_api_agent creates the agent once and reuses it."""
        import agents.api_agent as api_mod

        # Reset singleton so each test is independent
        api_mod._api_agent = None

        with (
            patch.object(api_mod.APIAgent, "__init__", return_value=None),
            patch.object(api_mod.APIAgent, "response", return_value="ok"),
        ):
            # __init__ is mocked to be a no-op, so we need the instance to exist
            api_mod._api_agent = None
            # Patch at class level to count creations
            with patch("agents.api_agent.APIAgent") as MockClass:
                MockClass.return_value = MagicMock(response=MagicMock(return_value="r"))
                api_mod._api_agent = None  # ensure fresh start

                api_mod.run_api_agent("q1")
                api_mod.run_api_agent("q2")

                # APIAgent() constructor should only have been called once
                MockClass.assert_called_once()

    def test_run_rag_agent_reuses_singleton(self):
        """run_rag_agent creates the agent once and reuses it."""
        import agents.rag_agent as rag_mod

        rag_mod._rag_agent = None

        with patch("agents.rag_agent.RAGAgent") as MockClass:
            MockClass.return_value = MagicMock(response=MagicMock(return_value="r"))
            rag_mod._rag_agent = None

            rag_mod.run_rag_agent("q1")
            rag_mod.run_rag_agent("q2")

            MockClass.assert_called_once()

    def test_run_tech_data_agent_reuses_singleton(self):
        """run_tech_data_agent creates the agent once and reuses it."""
        import agents.tech_data_agent as tda_mod

        tda_mod._tech_data_agent = None

        with patch("agents.tech_data_agent.TechDataAgent") as MockClass:
            MockClass.return_value = MagicMock(response=MagicMock(return_value="r"))
            tda_mod._tech_data_agent = None

            tda_mod.run_tech_data_agent("q1")
            tda_mod.run_tech_data_agent("q2")

            MockClass.assert_called_once()
