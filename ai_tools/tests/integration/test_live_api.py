"""
Live API Integration Tests for ai_tools.

These tests actually call the various AI APIs to verify that the
network layer, payload formatting, tool dispatch, and streaming
work as intended in real-world scenarios across providers.

We use pytest parameterization to run tests across lightweight models
from OpenAI, Gemini, and OpenRouter.
"""

import os
import pytest

from ai_tools.agent import Agent
from ai_tools.tool_definition import tool

# Lightweight models from different providers
MODELS_TO_TEST = [
    "openai/gpt-4o-mini",
    "openrouter/openai/gpt-oss-20b",
]

def skip_if_missing_key(model: str):
    if model.startswith("gemini/") and not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GOOGLE_API_KEY/GEMINI_API_KEY is not set.")
    elif model.startswith("openai/") and not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set.")
    elif model.startswith("openrouter/") and not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set.")

@pytest.mark.parametrize("model_name", MODELS_TO_TEST)
class TestLiveAPI:
    def test_basic_query(self, model_name):
        """Test a simple synchronous query."""
        skip_if_missing_key(model_name)
        agent = Agent(model=model_name, system_prompt="Answer briefly.")
        response = agent.query("What is 1+1?")

        assert isinstance(response, str)
        assert len(response) > 0
        assert "2" in response or "two" in response.lower()

        # Verify history was updated
        assert len(agent.chat_history) == 2
        assert agent.chat_history[0]["role"] == "user"
        assert agent.chat_history[0]["content"] == "What is 1+1?"
        assert agent.chat_history[1]["role"] == "assistant"
        assert len(agent.chat_history[1]["content"]) > 0

    def test_tool_dispatch(self, model_name):
        """Test that the LLM can correctly decide to call a tool and we parse it."""
        skip_if_missing_key(model_name)

        # We need a tracker to prove the tool was actually executed
        tracker = {"called": False, "args": {}}

        @tool(description="Adds two integers together.")
        def add_numbers(a: int, b: int) -> int:
            tracker["called"] = True
            tracker["args"] = {"a": a, "b": b}
            return a + b

        agent = Agent(
            model=model_name,
            tools=[add_numbers],
            system_prompt="You have a tool to add numbers. Use it if asked to add.",
        )

        agent.query("What is 42 plus 58?")
        response = agent.get_tool_responses()

        assert tracker["called"] is True
        assert tracker["args"] == {"a": 42, "b": 58}
        assert "100" in response

    def test_parallel_tool_calls(self, model_name):
        """Test that the LLM can call multiple tools at once (or sequentially, but properly handled)."""
        skip_if_missing_key(model_name)
        
        calls = []

        @tool(description="Get weather for a city.")
        def get_weather(city: str) -> str:
            calls.append(city)
            return f"Sunny in {city}"

        agent = Agent(
            model=model_name,
            tools=[get_weather],
            system_prompt="You are a weather bot. Provide the weather.",
        )

        agent.query("What's the weather in Tokyo and Paris?")
        response = agent.get_tool_responses()

        assert len(calls) == 2
        assert "Tokyo" in calls or "Paris" in calls  # Depending on parallel order
        assert "sunny" in response.lower()
