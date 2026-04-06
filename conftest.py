"""
conftest.py — shared pytest configuration.

Ensures the project root is on sys.path so all tests can use absolute
imports (e.g. `from agents.base_agent import BaseAgent`) without
needing manual sys.path hacks inside individual test files.
"""

import sys
import os
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pytest
from utils.config import settings
from ai_tools import tracing

@pytest.fixture(autouse=True)
def force_small_models(monkeypatch):
    """
    Forces all tests to use the small, fast models specified by the user.
    Main agent: openrouter/google/gemini-3.1-flash-lite-preview
    Sub agents: openrouter/openai/gpt-oss-20b
    """
    monkeypatch.setattr(settings, "DEFAULT_MODEL", "openrouter/google/gemini-3.1-flash-lite-preview")
    monkeypatch.setattr(settings, "SUB_AGENT_MODEL", "openrouter/openai/gpt-oss-20b")


@pytest.fixture(autouse=True)
def ensure_langfuse_test_tags(monkeypatch):
    """
    Globally patches Langfuse tracing to ensure 'test' tags and 'test-user' id.
    This ensures all tests that might trigger Langfuse observability (actual calls
    or simulations) are correctly labeled in the Langfuse dashboard.
    """
    orig_get_params = tracing.get_langfuse_params
    orig_trace_span = tracing.trace_span
    orig_propagate = tracing.propagate_langfuse_attributes

    def patched_get_params(*args, **kwargs):
        # We no longer inject here because it causes TypeError in some environments
        # when passed to OpenAI client. Tracing.py now also excludes them.
        return orig_get_params(*args, **kwargs)

    @contextmanager
    def patched_trace_span(name, **kwargs):
        if tracing.is_tracing_enabled():
            # Intercept kwargs to add tags and user_id
            tags = list(kwargs.get("tags") or [])
            if "test" not in tags:
                tags.append("test")
            kwargs["tags"] = tags
            kwargs["user_id"] = "test-user"
        
        with orig_trace_span(name, **kwargs) as span:
            yield span

    @contextmanager
    def patched_propagate(user_id=None, session_id=None, tags=None):
        if tracing.is_tracing_enabled():
            # Force user_id and tags for propagation
            tags_list = list(tags or [])
            if "test" not in tags_list:
                tags_list.append("test")
            user_id = "test-user"
            tags = tags_list

        with orig_propagate(user_id=user_id, session_id=session_id, tags=tags):
            yield

    # Apply the monkeypatches to the ai_tools.tracing module
    monkeypatch.setattr(tracing, "get_langfuse_params", patched_get_params)
    monkeypatch.setattr(tracing, "trace_span", patched_trace_span)
    monkeypatch.setattr(tracing, "propagate_langfuse_attributes", patched_propagate)
