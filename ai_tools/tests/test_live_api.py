"""
Live API Integration Tests for ai_tools.

These tests actually call the Gemini API to verify that the
network layer, payload formatting, tool dispatch, and streaming
work as intended in real-world scenarios.

If the GEMINI_API_KEY environment variable is missing, these
tests are skipped gracefully to prevent CI failures on
unauthenticated environments.
"""

import os
import pytest

from ai_tools.tools import LLMQuery
from ai_tools.tool_definition import tool

# Skip all tests in this file if no GEMINI_API_KEY is available
pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY is not set. Skipping live API tests.",
)

# Use a fast, cheap model for testing
TEST_MODEL = "gemini-flash-latest"


class TestLiveAPIBasic:
    def test_basic_query(self):
        """Test a simple synchronous query."""
        llm = LLMQuery(model=TEST_MODEL, system_prompt="Answer briefly.")
        response = llm.query("What is 1+1?")

        assert isinstance(response, str)
        assert len(response) > 0
        assert "2" in response or "two" in response.lower()

        # Verify history was updated
        assert len(llm.chat_history) == 2
        assert llm.chat_history[0]["role"] == "user"
        assert llm.chat_history[0]["content"] == "What is 1+1?"
        assert llm.chat_history[1]["role"] == "assistant"
        assert llm.chat_history[1]["content"] == response

    def test_basic_stream(self):
        """Test streaming responses."""
        llm = LLMQuery(model=TEST_MODEL, stream=True)
        chunks = []
        for chunk in llm.stream("Print testing 1 2 3"):
            chunks.append(chunk)

        full_response = "".join(chunks)
        assert len(chunks) > 1  # Should arrive in multiple chunks
        assert "testing" in full_response.lower()

    @pytest.mark.asyncio
    async def test_async_query(self):
        """Test simple asynchronous query."""
        llm = LLMQuery(model=TEST_MODEL)
        response = await llm.aquery("Say 'async testing works'")
        assert "async" in response.lower()


class TestLiveAPITools:
    def test_tool_dispatch(self):
        """Test that the LLM can correctly decide to call a tool and we parse it."""

        # We need a tracker to prove the tool was actually executed
        tracker = {"called": False, "args": {}}

        @tool(description="Adds two integers together.")
        def add_numbers(a: int, b: int) -> int:
            tracker["called"] = True
            tracker["args"] = {"a": a, "b": b}
            return a + b

        llm = LLMQuery(
            model=TEST_MODEL,
            tools=[add_numbers],
            system_prompt="You have a tool to add numbers. Use it if asked to add.",
        )

        # get_tool_responses does the full loop: user -> LLM -> Tool -> LLM -> user
        response = llm.get_tool_responses("What is 42 plus 58?")

        assert tracker["called"] is True
        assert tracker["args"] == {"a": 42, "b": 58}
        assert "100" in response

    def test_parallel_tool_calls(self):
        """Test that the LLM can call multiple tools at once (or sequentially, but properly handled)."""
        calls = []

        @tool(description="Get weather for a city.")
        def get_weather(city: str) -> str:
            calls.append(city)
            return f"Sunny in {city}"

        llm = LLMQuery(
            model=TEST_MODEL,
            tools=[get_weather],
            system_prompt="You are a weather bot. Provide the weather.",
        )

        # Asking for two cities should prompt multiple tool calls if the model supports it
        response = llm.get_tool_responses("What's the weather in Tokyo and Paris?")

        assert len(calls) == 2
        assert "Tokyo" in calls or "Paris" in calls  # Depending on parallel order
        assert "Sunny" in response
