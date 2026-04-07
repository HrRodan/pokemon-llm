import pytest
from unittest.mock import patch, MagicMock
from ai_tools.agent import Agent


class DummyAgent(Agent):
    TOOL_NAME = "dummy_agent"
    TOOL_DESCRIPTION = "A dummy agent for testing."


def test_agent_initialization():
    agent = DummyAgent(
        name="TestAgent", model="openai/gpt-4o-mini", history_limit=10
    )
    assert agent.name == "TestAgent"
    assert agent.model == "openai/gpt-4o-mini"
    assert agent.history_limit == 10


@patch.object(Agent, "_create_chat_completion")
def test_agent_run_without_tools(mock_create):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked LLM Response"
    mock_response.choices[0].message.tool_calls = None
    mock_create.return_value = mock_response

    agent = DummyAgent(name="TestAgent", model="openai/gpt-4o-mini")

    response = agent.run("Hello", use_history=True)

    assert response == "Mocked LLM Response"
    # Verify _create_chat_completion was called (which query() uses)
    mock_create.assert_called_once()
    assert agent.response == "Mocked LLM Response"


@patch.object(Agent, "_create_chat_completion")
def test_agent_run_with_tools(mock_create):
    # Turn 1: returns tool call
    mock_resp_1 = MagicMock()
    tc = {"id": "call_1", "function": {"name": "test_tool", "arguments": "{}"}}
    mock_resp_1.choices = [MagicMock()]
    mock_resp_1.choices[0].message.content = "Tool call turn"
    mock_resp_1.choices[0].message.tool_calls = [tc]
    
    # Turn 2: returns final response
    mock_resp_2 = MagicMock()
    mock_resp_2.choices = [MagicMock()]
    mock_resp_2.choices[0].message.content = "Final Tool Response"
    mock_resp_2.choices[0].message.tool_calls = None
    
    mock_create.side_effect = [mock_resp_1, mock_resp_2]

    # Dummy tool implementation
    def test_tool(kwargs):
        return "Tool Output"

    agent = DummyAgent(name="TestAgent", model="openai/gpt-4o-mini", functions=[test_tool])

    response = agent.run("Do a tool call", use_history=False)

    assert response == "Final Tool Response"
    assert mock_create.call_count == 2


def test_agent_as_tool():
    agent = DummyAgent(name="TestAgent", model="openai/gpt-4o-mini")

    tool_callable = agent.as_tool()

    assert callable(tool_callable)
    assert tool_callable.__name__ == "dummy_agent"
    assert hasattr(tool_callable, "__tool_schema__")

    schema = tool_callable.__tool_schema__
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "dummy_agent"
    assert schema["function"]["description"] == "A dummy agent for testing."
    assert "query" in schema["function"]["parameters"]["properties"]


def test_agent_as_tool_raises_value_error_if_no_name():
    class InvalidAgent(Agent):
        # Missing TOOL_NAME
        pass

    agent = InvalidAgent(name="Test", model="openai/gpt-4o")
    with pytest.raises(ValueError):
        agent.as_tool()
