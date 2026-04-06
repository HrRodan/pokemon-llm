import threading
import pytest
from unittest.mock import patch, MagicMock
from ai_tools.tools import LLMQuery
from ai_tools.agent import LLMAgent, AgentConfig

class DummyAgent(LLMAgent):
    TOOL_NAME = "dummy_agent"
    TOOL_DESCRIPTION = "A dummy agent for testing concurrency."

def test_llm_query_as_tool_concurrency():
    """
    Test that LLMQuery.as_tool() is thread-safe.
    Multiple concurrent calls should not bleed state (chat_history) 
    and should correctly aggregate usage.
    """
    llm = LLMQuery(model="openai/gpt-4o-mini", system_prompt="Base System Prompt")
    
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

    # Mock the client and tracing to avoid SSL/network issues in test env
    dummy_client = MagicMock()

    with patch.object(LLMQuery, "_get_client_for_model", return_value=dummy_client), \
         patch.object(LLMQuery, "_create_chat_completion", side_effect=slow_create_completion), \
         patch.object(LLMQuery, "get_tool_responses", side_effect=lambda: "Final result"), \
         patch("ai_tools.tracing.trace_agent_run", side_effect=lambda **kwargs: MagicMock()), \
         patch("ai_tools.tracing.trace_span", side_effect=lambda **kwargs: MagicMock()):
        
        schema, tool_fn = llm.as_tool(name="test_tool", description="test desc")
        
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
    assert all(r == "Final result" for r in results)
    
    # Verify usage aggregation: 5 calls * 10 tokens = 50 tokens
    assert llm.total_prompt_tokens == 50
    assert llm.total_completion_tokens == 100
    assert llm.total_tokens == 150
    assert pytest.approx(llm.total_cost) == 0.005

def test_llm_agent_as_tool_concurrency():
    """
    Test that LLMAgent.as_tool() is thread-safe.
    """
    agent = DummyAgent(config=AgentConfig(name="TestAgent", model_name="openai/gpt-4o-mini"))
    
    start_event = threading.Event()
    
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 10
    mock_usage.model_extra = {"cost": 0.0001}
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Mocked Content", tool_calls=None))]
    mock_response.usage = mock_usage

    def slow_create_completion(*args, **kwargs):
        start_event.wait(timeout=2)
        return mock_response

    dummy_client = MagicMock()

    tool_fn = agent.as_tool()
    
    with patch.object(LLMQuery, "_get_client_for_model", return_value=dummy_client), \
         patch.object(LLMQuery, "_create_chat_completion", side_effect=slow_create_completion), \
         patch("ai_tools.agent.trace_agent_run", side_effect=lambda **kwargs: MagicMock()), \
         patch("ai_tools.tracing.trace_agent_run", side_effect=lambda **kwargs: MagicMock()), \
         patch("ai_tools.tracing.trace_span", side_effect=lambda **kwargs: MagicMock()):
        results = [None] * 5
        threads = []
        
        def call_agent_tool(idx):
            results[idx] = tool_fn(query=f"Agent Prompt {idx}")
            
        for i in range(5):
            t = threading.Thread(target=call_agent_tool, args=(i,))
            threads.append(t)
            t.start()
        
        start_event.set()
        for t in threads:
            t.join()
            
        # Verify usage aggregated to parent agent.llm
        assert agent.llm.total_prompt_tokens == 25
        assert agent.llm.total_completion_tokens == 25
        assert agent.llm.total_tokens == 50
        assert pytest.approx(agent.llm.total_cost) == 0.0005
