import pytest
from unittest.mock import patch, MagicMock
import os
from contextlib import contextmanager

# Import the module to access its private variables
import ai_tools.tracing as tracing
from ai_tools.tracing import (
    is_tracing_enabled,
    get_langfuse_client,
    trace_agent_run,
    trace_tool_execution,
    flush_tracing,
    get_current_trace_context,
    build_openrouter_trace_dict,
    TraceContext,
)
from ai_tools.memory import MemoryHandler, InMemoryBackend

@pytest.fixture(autouse=True)
def reset_tracing_state():
    """Forcefully reset the module-level state of the tracing module."""
    tracing._tracing_checked = False
    tracing._tracing_enabled = False
    tracing._langfuse_client = None

@pytest.fixture
def mock_langfuse():
    """Mock the langfuse package components."""
    # We need to patch the package itself because tracing.py imports from it inside functions
    mock_client = MagicMock()
    
    with patch("langfuse.Langfuse", return_value=mock_client), \
         patch("langfuse.propagate_attributes") as mock_propagate:
        
        @contextmanager
        def mock_propagate_cm(*args, **kwargs):
            yield
        mock_propagate.side_effect = mock_propagate_cm
        
        yield {
            "client": mock_client,
            "propagate": mock_propagate
        }

@pytest.fixture
def mock_response():
    """Provide a standard mock LLM response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Standard AI response"
    response.choices[0].message.tool_calls = []
    response.choices[0].message.model_extra = {}
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return response

def test_tracing_disabled_no_env_vars():
    with patch.dict(os.environ, {}, clear=True):
        tracing._tracing_checked = False
        assert is_tracing_enabled() is False
        assert get_langfuse_client() is None

def test_tracing_disabled_no_package():
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        # Reset checked state to force a re-check
        tracing._tracing_checked = False
        # Mocking the missing 'langfuse.openai' by making the import fail
        with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: 
                   (exec('raise ImportError("No module named langfuse.openai")') if name == "langfuse.openai" else 
                    __import__(name, *args, **kwargs))):
            assert is_tracing_enabled() is False

def test_tracing_enabled_with_env_vars(mock_langfuse):
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        # Mocking the presence of langfuse.openai check
        with patch("langfuse.openai.OpenAI", create=True):
            assert is_tracing_enabled() is True
            assert get_langfuse_client() is not None

def test_trace_agent_run_creates_span(mock_langfuse):
    mock_client = mock_langfuse["client"]
    mock_client.get_current_observation_id.return_value = None

    with patch.dict(os.environ, {        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
             patch("ai_tools.tracing.get_langfuse_client", return_value=mock_client):
                with trace_agent_run("TestAgent", "Hello", user_id="user1", session_id="sess1"):
                    mock_client.start_as_current_observation.assert_called()
                    args, kwargs = mock_client.start_as_current_observation.call_args
                    assert kwargs["as_type"] == "agent"
                    assert kwargs["name"] == "TestAgent"
                    mock_langfuse["propagate"].assert_called()

def test_trace_agent_run_nested(mock_langfuse):
    mock_client = mock_langfuse["client"]
    mock_client.get_current_observation_id.return_value = "parent-obs-id"
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
             patch("ai_tools.tracing.get_langfuse_client", return_value=mock_client):
                 with trace_agent_run("SubAgent", "Hello", session_id="sess1", user_id="u1"):
                    mock_client.start_as_current_observation.assert_called_once_with(
                        as_type="agent",
                        name="agent:run:SubAgent",
                        input={"message": "Hello"},
                        metadata={}
                    )
                    # Nested spans now propagate attributes to ensure session_id/user_id
                    # reach subagent LLM calls via Langfuse context
                    mock_langfuse["propagate"].assert_called_once()





def test_trace_tool_execution_records_error(mock_langfuse):
    mock_client = mock_langfuse["client"]
    mock_span = MagicMock()
    mock_client.start_as_current_observation.return_value.__enter__.return_value = mock_span
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
             patch("ai_tools.tracing.get_langfuse_client", return_value=mock_client):
                with pytest.raises(ValueError, match="Tool failed"):
                    with trace_tool_execution("get_weather", {"city": "Berlin"}):
                        raise ValueError("Tool failed")
                mock_span.update.assert_called()
                args, kwargs = mock_span.update.call_args
                assert kwargs["level"] == "ERROR"

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

def test_scoped_handler_inherits_user_id():
    memory = MemoryHandler(backend=InMemoryBackend(), user_id="parent_user")
    scoped = memory.create_scoped_handler("subagent")
    
    assert scoped.user_id == "parent_user"

def test_flush_tracing_calls_client_flush(mock_langfuse):
    mock_client = mock_langfuse["client"]
    
    with patch.dict(os.environ, {
        "LANGFUSE_SECRET_KEY": "sk-123",
        "LANGFUSE_PUBLIC_KEY": "pk-123",
        "LANGFUSE_BASE_URL": "http://localhost:3000"
    }):
        with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
             patch("ai_tools.tracing.get_langfuse_client", return_value=mock_client):
                flush_tracing()
                mock_client.flush.assert_called_once()


def test_get_current_trace_context_disabled():
    with patch("ai_tools.tracing.is_tracing_enabled", return_value=False):
        assert get_current_trace_context() is None


def test_get_current_trace_context_no_active_trace(mock_langfuse):
    mock_client = mock_langfuse["client"]
    mock_client.get_current_trace_id.return_value = None

    with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
         patch("ai_tools.tracing.get_langfuse_client", return_value=mock_client):
        assert get_current_trace_context() is None


def test_get_current_trace_context_complete(mock_langfuse):
    mock_client = mock_langfuse["client"]
    mock_client.get_current_trace_id.return_value = "trace-123"
    mock_client.get_current_observation_id.return_value = "obs-456"

    with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
        with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
             patch("ai_tools.tracing.get_langfuse_client", return_value=mock_client):
            ctx = get_current_trace_context(
                session_id="sess-789", user_id="user-000", trace_name="TestTrace"
            )
            assert ctx.trace_id == "trace-123"
            assert ctx.observation_id == "obs-456"
            assert ctx.session_id == "sess-789"
            assert ctx.user_id == "user-000"
            assert ctx.trace_name == "TestTrace"
            assert ctx.environment == "prod"


def test_build_openrouter_trace_dict_complete():
    ctx = TraceContext(
        trace_id="t1",
        observation_id="o1",
        session_id="s1",
        user_id="u1",
        trace_name="tn1",
        environment="dev",
    )
    d = build_openrouter_trace_dict(ctx, generation_name="gen1", span_name="span1")
    assert d["trace_id"] == "t1"
    assert d["parent_span_id"] == "o1"
    assert d["session_id"] == "s1"
    assert d["user_id"] == "u1"
    assert d["trace_name"] == "tn1"
    assert d["generation_name"] == "gen1"
    assert d["span_name"] == "span1"
    assert d["environment"] == "dev"


def test_build_openrouter_trace_dict_none():
    assert build_openrouter_trace_dict(None) is None


def test_trace_dict_injected_for_openrouter(mock_response):
    from ai_tools.tools import LLMQuery

    q = LLMQuery(model="openrouter/google/gemini-pro")
    
    # Mocking trace context
    ctx = TraceContext("t1", "o1", "s1", "u1", "tn1", "dev")

    with patch.object(q, "_create_chat_completion", return_value=mock_response) as mock_create:
        with patch("ai_tools.tracing.get_current_trace_context", return_value=ctx):
            q.query("hi")
            mock_create.assert_called()
            # Check if extra_body.trace was passed in the call
            call_kwargs = mock_create.call_args[1]
            assert "extra_body" in call_kwargs
            assert "trace" in call_kwargs["extra_body"]
            assert call_kwargs["extra_body"]["trace"]["trace_id"] == "t1"


def test_trace_dict_not_injected_for_openai(mock_response):
    from ai_tools.tools import LLMQuery

    q = LLMQuery(model="openai/gpt-4o")
    ctx = TraceContext("t1", "o1", "s1", "u1", "tn1", "dev")

    with patch.object(q, "_create_chat_completion", return_value=mock_response) as mock_create:
        with patch("ai_tools.tracing.get_current_trace_context", return_value=ctx):
            q.query("hi")
            mock_create.assert_called()
            call_kwargs = mock_create.call_args[1]
            if "extra_body" in call_kwargs:
                assert "trace" not in call_kwargs["extra_body"]


def test_checkpoint_stores_trace_id(mock_response):
    from ai_tools.tools import LLMQuery
    from ai_tools.memory import MemoryHandler, InMemoryBackend

    mem = MemoryHandler(backend=InMemoryBackend())
    q = LLMQuery(model="openai/gpt-4o", memory=mem)
    ctx = TraceContext("trace-id-abc", "o1", "s1", "u1", "tn1", "dev")

    with patch("ai_tools.tracing.get_current_trace_context", return_value=ctx), \
         patch.object(q, "_create_chat_completion", return_value=mock_response):
        q.query("hi")
        
        # Check if latest checkpoint has the trace_id
        last_cp = mem.backend.load_checkpoint(mem.thread_id)
        assert last_cp.state.trace_id == "trace-id-abc"


def test_sqlite_migration_idempotent(tmp_path):
    from ai_tools.memory import SQLiteBackend
    db_file = str(tmp_path / "test_migration.db")
    
    # Init first time
    be = SQLiteBackend(db_file)
    
    # Init second time - should not crash
    be2 = SQLiteBackend(db_file)
    assert be2 is not None
