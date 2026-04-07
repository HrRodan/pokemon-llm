import threading
import pytest
from unittest.mock import patch, MagicMock
from ai_tools.agent import Agent

class DummyAgent(Agent):
    TOOL_NAME = "dummy_agent"
    TOOL_DESCRIPTION = "A dummy agent for testing concurrency."

def test_agent_as_tool_concurrency():
    """
    Test that Agent.as_tool() is thread-safe.
    Multiple concurrent calls should not bleed state (chat_history) 
    and should correctly aggregate usage.
    """
    agent = DummyAgent(model="openai/gpt-4o-mini", system_prompt="Base System Prompt")
    
    # Release threads simultaneously
    start_event = threading.Event()
    
    # Mock the API call so we can control usage and timing
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 20
    mock_usage.total_tokens = 30
    mock_usage.model_extra = {"cost": 0.001}
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Mocked Content", tool_calls=None))]
    mock_response.usage = mock_usage

    def slow_create_completion(*args, **kwargs):
        start_event.wait(timeout=2)
        return mock_response

    # Mock the client factory and tracing
    dummy_client = MagicMock()
    dummy_client.chat.completions.create.side_effect = slow_create_completion

    with patch("ai_tools.agent.get_client", return_value=dummy_client), \
         patch("ai_tools.tracing.trace_span", return_value=MagicMock()), \
         patch("ai_tools.tracing.propagate_langfuse_attributes", return_value=MagicMock()):
        
        tool_fn = agent.as_tool()
        
        results = [None] * 5
        threads = []
        
        def call_tool(idx):
            results[idx] = tool_fn(query=f"Prompt {idx}")

        for i in range(5):
            t = threading.Thread(target=call_tool, args=(i,))
            threads.append(t)
            t.start()
        
        start_event.set() 
        for t in threads:
            t.join()
    
    # Verify results
    assert all(r == "Mocked Content" for r in results)
    
    # Verify usage aggregation: 5 calls * 10 tokens = 50 tokens
    assert agent.usage.total_prompt_tokens == 50
    assert agent.usage.total_completion_tokens == 100
    assert agent.usage.total_tokens == 150
    assert pytest.approx(agent.usage.total_cost) == 0.005
