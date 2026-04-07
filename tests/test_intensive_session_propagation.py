import pytest
from unittest.mock import patch, MagicMock
import os
from ai_tools.agent import AgentConfig
from ai_tools.memory import MemoryHandler, InMemoryBackend
from agents.pokemon_agent import PokemonAgent
from agents.api_agent import APIAgent
from ai_tools.tracing import TraceContext

class MockToolCall:
    def __init__(self, id, name, args):
        self.id = id
        self.type = "function"
        self.function = MagicMock()
        self.function.name = name
        self.function.arguments = args
    
    def model_dump(self):
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments
            }
        }

class MockMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.model_extra = {}

class MockChoice:
    def __init__(self, message):
        self.message = message

class MockResponse:
    def __init__(self, content, tool_calls=None):
        self.choices = [MockChoice(MockMessage(content, tool_calls))]
        self.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

@pytest.fixture
def mock_tracing_env():
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }), patch("ai_tools.tracing.is_tracing_enabled", return_value=True):
        yield

@pytest.fixture
def mock_llm_responses():
    """
    Mock the LLM response sequence using custom objects with model_dump.
    """
    responses = []
    
    # 1. PokemonAgent -> run_api_agent tool call
    responses.append(MockResponse("", [MockToolCall("call_api_agent", "run_api_agent", '{"query": "Pikachu stats"}')]))
    
    # 2. APIAgent -> get_pokemon_details tool call
    responses.append(MockResponse("", [MockToolCall("call_details", "get_pokemon_details", '{"pokemon_name": "pikachu"}')]))
    
    # 3. APIAgent final
    responses.append(MockResponse("Pikachu has 35 Speed."))
    
    # 4. PokemonAgent final
    responses.append(MockResponse("According to the API, Pikachu is fast."))
    
    return responses

def test_pokemon_api_session_propagation_intensive(mock_tracing_env, mock_llm_responses):
    """
    Intensive test of session_id and user_id propagation from PokemonAgent to APIAgent.
    """
    from ai_tools.tools import LLMQuery
    
    captured_calls = []
    
    def mock_create(*args, **kwargs):
        captured_calls.append(kwargs)
        if mock_llm_responses:
            return mock_llm_responses.pop(0)
        return MagicMock()

    # We mock get_current_trace_context to return a consistent root trace but ALLOW session_id override
    def mock_get_ctx(session_id=None, user_id=None, trace_name=None):
        return TraceContext(
            trace_id="t-root",
            observation_id="o-root",
            session_id=session_id or "fallback-sess",
            user_id=user_id or "fallback-user",
            trace_name=trace_name or "root",
            environment="test"
        )

    with patch.object(LLMQuery, "_create_chat_completion", side_effect=mock_create), \
         patch("ai_tools.tracing.get_current_trace_context", side_effect=mock_get_ctx):
        
        agent = PokemonAgent(user_id="trainer_oak")
        agent.llm.memory = MemoryHandler(backend=InMemoryBackend(), agent_name="PokemonAgent", user_id="trainer_oak")
        root_session_id = agent.llm.memory.root_thread_id
        agent.llm.model = "openrouter/google/gemini-flash"
        
        result = agent.run("Tell me Pikachu stats")
        
        assert "fast" in result.lower()
        assert len(captured_calls) >= 4
        
        for i, call in enumerate(captured_calls):
            extra_body = call.get("extra_body", {})
            trace = extra_body.get("trace", {})
            
            # Print for debugging
            print(f"\nCall {i+1} Model: {call.get('model')}")
            print(f"Call {i+1} Trace: {trace}")
            
            # All calls should carry the same session_id and user_id
            assert trace.get("session_id") == root_session_id, f"Call {i+1} missing or wrong session_id: expected {root_session_id}, got {trace.get("session_id")}"
            assert trace.get("user_id") == "trainer_oak", f"Call {i+1} missing or wrong user_id"

if __name__ == "__main__":
    pytest.main([__file__])
