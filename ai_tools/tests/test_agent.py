import pytest
from unittest.mock import patch
from ai_tools.agent import LLMAgent, AgentConfig
from ai_tools.tools import LLMQuery


class DummyAgent(LLMAgent):
    TOOL_NAME = "dummy_agent"
    TOOL_DESCRIPTION = "A dummy agent for testing."


def test_llm_agent_initialization():
    agent = DummyAgent(
        config=AgentConfig(name="TestAgent", model_name="gpt-4o-mini", history_limit=10)
    )
    assert agent.name == "TestAgent"
    assert agent.model_name == "gpt-4o-mini"
    assert isinstance(agent.llm, LLMQuery)
    assert agent.llm.history_limit == 10
    assert agent.usage.prompt_tokens == 0
    assert agent.usage.call_count == 0


@patch.object(LLMQuery, "query")
@patch.object(LLMQuery, "get_tool_responses")
def test_llm_agent_run_without_tools(mock_get_tools, mock_query):
    mock_query.return_value = "Mocked LLM Response"
    agent = DummyAgent(config=AgentConfig(name="TestAgent", model_name="gpt-4o-mini"))

    # Simulate LLMQuery state
    agent.llm.tool_calls = []
    agent.llm.total_prompt_tokens = 10
    agent.llm.total_completion_tokens = 20
    agent.llm.total_tokens = 30
    agent.llm.total_cost = 0.001

    response = agent.run("Hello", use_history=True)

    assert response == "Mocked LLM Response"
    mock_query.assert_called_once_with(user_prompt="Hello", use_history=True)
    mock_get_tools.assert_not_called()

    # Assert usage was updated
    assert agent.usage.call_count == 1
    assert agent.usage.total_tokens == 30
    assert agent.usage.cost == 0.001


@patch.object(LLMQuery, "query")
@patch.object(LLMQuery, "get_tool_responses")
def test_llm_agent_run_with_tools(mock_get_tools, mock_query):
    mock_query.return_value = "Initial Response"
    mock_get_tools.return_value = "Final Tool Response"

    agent = DummyAgent(config=AgentConfig(name="TestAgent", model_name="gpt-4o-mini"))

    # Force tool calls
    agent.llm.tool_calls = [{"id": "call_1", "function": {"name": "test"}}]

    response = agent.run("Do a tool call", use_history=False)

    assert response == "Final Tool Response"
    mock_query.assert_called_once_with(user_prompt="Do a tool call", use_history=False)
    mock_get_tools.assert_called_once()
    assert agent.usage.call_count == 1


def test_llm_agent_as_tool():
    agent = DummyAgent(config=AgentConfig(name="TestAgent", model_name="gpt-4o-mini"))

    tool_callable = agent.as_tool()

    assert callable(tool_callable)
    assert tool_callable.__name__ == "dummy_agent"
    assert hasattr(tool_callable, "__tool_schema__")

    schema = tool_callable.__tool_schema__
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "dummy_agent"
    assert schema["function"]["description"] == "A dummy agent for testing."
    assert "query" in schema["function"]["parameters"]["properties"]


def test_llm_agent_as_tool_raises_value_error_if_no_name():
    class InvalidAgent(LLMAgent):
        # Missing TOOL_NAME
        pass

    agent = InvalidAgent(config=AgentConfig(name="Test", model_name="gpt-4o"))
    with pytest.raises(ValueError):
        agent.as_tool()
