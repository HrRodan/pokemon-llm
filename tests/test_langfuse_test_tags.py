import pytest
from ai_tools import tracing
import os

def test_get_langfuse_params_no_injection():
    """Verify that get_langfuse_params NO LONGER includes tags/user_id directly."""
    with pytest.MonkeyPatch().context() as m:
        m.setenv("LANGFUSE_SECRET_KEY", "sk-123")
        m.setenv("LANGFUSE_PUBLIC_KEY", "pk-123")
        m.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")
        m.setattr(tracing, "is_tracing_enabled", lambda: True)
        
        params = tracing.get_langfuse_params(model="gpt-4")
        
        # Should contain name and maybe metadata, but NOT user_id/tags
        assert "name" in params
        assert "user_id" not in params
        assert "tags" not in params

def test_trace_span_injection():
    """Verify that trace_span is patched to include test tags."""
    from unittest.mock import MagicMock, patch
    
    mock_client = MagicMock()
    # Mock get_current_observation_id to return None (so it uses propagate_attributes)
    mock_client.get_current_observation_id.return_value = None
    
    with pytest.MonkeyPatch().context() as m:
        m.setattr(tracing, "is_tracing_enabled", lambda: True)
        m.setattr(tracing, "get_langfuse_client", lambda: mock_client)
        
        # Mock propagate_attributes inside the tracing module (it's imported inside trace_span)
        # Actually it's easier to mock the one in langfuse if we can
        with patch("langfuse.propagate_attributes") as mock_propagate:
            from contextlib import contextmanager
            @contextmanager
            def fake_propagate(**kwargs):
                yield
            mock_propagate.side_effect = fake_propagate
            
            with tracing.trace_span("test-span"):
                pass
            
            # Check if propagate_attributes was called with our injected values
            mock_propagate.assert_called()
            args, kwargs = mock_propagate.call_args
            assert kwargs["user_id"] == "test-user"
            assert "test" in kwargs["tags"]

def test_propagate_attributes_injection():
    """Verify that propagate_langfuse_attributes is patched."""
    from unittest.mock import patch
    
    with pytest.MonkeyPatch().context() as m:
        m.setattr(tracing, "is_tracing_enabled", lambda: True)
        
        with patch("langfuse.propagate_attributes") as mock_propagate:
            from contextlib import contextmanager
            @contextmanager
            def fake_propagate(**kwargs):
                yield
            mock_propagate.side_effect = fake_propagate
            
            with tracing.propagate_langfuse_attributes(user_id="original-user", tags=["orig"]):
                pass
            
            mock_propagate.assert_called()
            args, kwargs = mock_propagate.call_args
            assert kwargs["user_id"] == "test-user"
            assert "test" in kwargs["tags"]
            assert "orig" in kwargs["tags"]
