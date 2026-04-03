import pytest
from unittest.mock import patch, MagicMock
import os
import sys
from ai_tools.tracing import (
    is_tracing_enabled,
    get_langfuse_client,
    trace_agent_run,
    trace_llm_generation,
    update_generation,
    trace_tool_execution,
    update_span,
    trace_subagent_call,
    flush_tracing,
)
from ai_tools.memory import MemoryHandler, InMemoryBackend

@pytest.fixture(autouse=True)
def reset_tracing_state():
    """Reset the lazy-loaded tracing state before each test."""
    import ai_tools.tracing as tracing
    tracing._tracing_checked = False
    tracing._tracing_enabled = False
    tracing._langfuse_client = None

@pytest.fixture
def mock_langfuse():
    """Mock the langfuse package in sys.modules."""
    mock_mod = MagicMock()
    with patch.dict(sys.modules, {"langfuse": mock_mod}):
        yield mock_mod

@pytest.fixture
def mock_otel():
    """Mock opentelemetry trace."""
    with patch("ai_tools.tracing.trace") as mock_trace:
        yield mock_trace

def test_tracing_disabled_no_env_vars():
    with patch.dict(os.environ, {}, clear=True):
        assert is_tracing_enabled() is False
        assert get_langfuse_client() is None

def test_tracing_disabled_no_package():
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with patch("builtins.__import__", side_effect=ImportError("No module named 'langfuse'")):
            assert is_tracing_enabled() is False

def test_tracing_enabled_with_env_vars(mock_langfuse):
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        assert is_tracing_enabled() is True
        assert get_langfuse_client() is not None

def test_trace_agent_run_creates_span(mock_langfuse, mock_otel):
    mock_client = MagicMock()
    mock_langfuse.get_client.return_value = mock_client
    # Mock no active span
    mock_otel.get_current_span.return_value.get_span_context.return_value.is_valid = False
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with trace_agent_run("TestAgent", "Hello", user_id="user1", session_id="sess1") as span:
            mock_client.start_as_current_observation.assert_called()
            args, kwargs = mock_client.start_as_current_observation.call_args
            assert kwargs["as_type"] == "agent"
            assert kwargs["name"] == "TestAgent"
            assert kwargs["input"] == {"message": "Hello"}
            mock_langfuse.propagate_attributes.assert_called_once()
            args, kwargs = mock_langfuse.propagate_attributes.call_args
            assert kwargs["user_id"] == "user1"
            assert kwargs["session_id"] == "sess1"

def test_trace_agent_run_nested(mock_langfuse, mock_otel):
    mock_client = MagicMock()
    mock_langfuse.get_client.return_value = mock_client
    # Mock active span
    mock_otel.get_current_span.return_value.get_span_context.return_value.is_valid = True
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with trace_agent_run("SubAgent", "Hello") as span:
            mock_client.start_as_current_observation.assert_called_once_with(
                as_type="agent",
                name="agent:run:SubAgent",
                input={"message": "Hello"},
                metadata={}
            )
            # Should NOT call propagate_attributes when nested
            assert mock_langfuse.propagate_attributes.call_count == 0

def test_trace_llm_generation_creates_generation(mock_langfuse):
    mock_client = MagicMock()
    mock_langfuse.get_client.return_value = mock_client
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        messages = [{"role": "user", "content": "Hello"}]
        with trace_llm_generation("llm-query", "openai/gpt-4o", messages) as gen:
            mock_client.start_as_current_observation.assert_called_once_with(
                as_type="generation",
                name="generation:gpt-4o",
                model="gpt-4o",
                input=messages,
                metadata={}
            )

def test_update_generation_with_usage():
    mock_gen = MagicMock()
    usage = {"prompt_tokens": 10, "completion_tokens": 20}
    update_generation(mock_gen, output="Bye", usage=usage)
    
    mock_gen.update.assert_called_once_with(
        output="Bye",
        usage_details={"input": 10, "output": 20}
    )

def test_trace_tool_execution_records_error(mock_langfuse):
    mock_client = MagicMock()
    mock_langfuse.get_client.return_value = mock_client
    mock_span = MagicMock()
    mock_client.start_as_current_observation.return_value.__enter__.return_value = mock_span
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with pytest.raises(ValueError, match="Tool failed"):
            with trace_tool_execution("get_weather", {"city": "Berlin"}):
                raise ValueError("Tool failed")
        
        mock_span.update.assert_called_once_with(
            level="ERROR",
            status_message="Tool failed"
        )

def test_memory_handler_user_id_property():
    memory = MemoryHandler(backend=InMemoryBackend(), user_id="user123")
    assert memory.user_id == "user123"
    
    memory.user_id = "newuser"
    assert memory.user_id == "newuser"

def test_memory_handler_root_thread_id():
    memory = MemoryHandler(backend=InMemoryBackend())
    root_id = memory.thread_id
    assert memory.root_thread_id == root_id
    
    scoped = memory.create_scoped_handler("subagent")
    assert scoped.thread_id != root_id
    assert scoped.root_thread_id == root_id
    
    memory.new_thread("new-root")
    assert memory.thread_id == "new-root"
    assert memory.root_thread_id == "new-root"
    
    memory.switch_thread("switched")
    assert memory.thread_id == "switched"
    assert memory.root_thread_id == "switched"

def test_scoped_handler_inherits_user_id():
    memory = MemoryHandler(backend=InMemoryBackend(), user_id="parent_user")
    scoped = memory.create_scoped_handler("subagent")
    
    assert scoped.user_id == "parent_user"

def test_flush_tracing_calls_client_flush(mock_langfuse):
    mock_client = MagicMock()
    mock_langfuse.get_client.return_value = mock_client
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        flush_tracing()
        mock_client.flush.assert_called_once()
