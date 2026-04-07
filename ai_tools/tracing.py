"""
Langfuse Observability Integration for ai_tools.

This module provides thin wrappers and context managers for tracing LLM calls,
agent runs, and tool executions via Langfuse. Tracing is fully optional and
activates only when LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and
LANGFUSE_BASE_URL are present in the environment.
"""

import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Union
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraceContext:
    """Resolved trace identifiers for the current execution scope."""

    trace_id: Optional[str]
    observation_id: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]
    trace_name: Optional[str]
    environment: str


# --- Lazy singleton ---
_langfuse_client = None
_tracing_checked = False
_tracing_enabled = False


def is_tracing_enabled() -> bool:
    """Return True if required Langfuse env vars are present and OpenAI wrapper is importable."""
    global _tracing_enabled, _tracing_checked

    if _tracing_checked:
        return _tracing_enabled

    required = ("LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASE_URL")

    # If any required env var is missing, disable tracing.
    if not all(os.getenv(k) for k in required):
        _tracing_enabled = False
        _tracing_checked = True
        return False

    try:
        # We need the OpenAI wrapper for the simplified instrumentation to work safely.
        from langfuse.openai import OpenAI  # noqa: F401

        _tracing_enabled = True
    except ImportError:
        logger.debug("langfuse.openai package not available; tracing disabled.")
        _tracing_enabled = False

    _tracing_checked = True
    return _tracing_enabled


import contextvars

_thread_session_id = contextvars.ContextVar("thread_session_id", default=None)
_thread_user_id = contextvars.ContextVar("thread_user_id", default=None)


@contextmanager
def propagate_langfuse_attributes(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """
    Context manager to propagate Langfuse attributes (user_id, session_id, tags)
    to all nested observations and generations.
    """
    token_session = _thread_session_id.set(session_id)
    token_user = _thread_user_id.set(user_id)

    try:
        if is_tracing_enabled():
            try:
                from langfuse import propagate_attributes

                with propagate_attributes(
                    user_id=user_id, session_id=session_id, tags=tags
                ):
                    yield
            except ImportError:
                yield
        else:
            yield
    finally:
        _thread_session_id.reset(token_session)
        _thread_user_id.reset(token_user)


def get_thread_session_id() -> Optional[str]:
    """Return the current thread-local session ID."""
    return _thread_session_id.get()


def get_thread_user_id() -> Optional[str]:
    """Return the current thread-local user ID."""
    return _thread_user_id.get()


def get_openai_class():
    """
    Return the OpenAI client class, instrumented with Langfuse if enabled.

    This allows a drop-in replacement in tools.py while maintaining optional
    tracing and fallbacks.
    """
    if is_tracing_enabled():
        try:
            from langfuse.openai import OpenAI

            return OpenAI
        except ImportError:
            logger.debug(
                "langfuse.openai not available; falling back to standard openai."
            )

    from openai import OpenAI

    return OpenAI


def get_langfuse_params(
    *,
    model: str,
    agent_name: Optional[str] = None,
    name_prefix: str = "generation",
    include_model: bool = False,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return a dictionary of Langfuse-specific parameters for OpenAI calls.

    This centralizes the generation naming logic: {prefix}:<AgentName>[:<Model>]
    or {prefix}:LLMQuery[:<Model>] if no agent name is provided.

    NOTE: tags and user_id are NOT included in the returned dict because
    some versions of the OpenAI client/Langfuse wrapper fail to strip them,
    causing TypeError. We rely on propagate_langfuse_attributes context manager instead.
    """
    if not is_tracing_enabled():
        return {}

    name_parts = [name_prefix]
    if agent_name:
        name_parts.append(agent_name)
    else:
        name_parts.append("LLMQuery")

    if include_model:
        name_parts.append(model)

    trace_name = ":".join(name_parts)

    params = {"name": trace_name}
    if metadata:
        params["metadata"] = metadata

    # We DO NOT include user_id, session_id, tags here anymore to avoid TypeError.
    # They should be handled by propagate_langfuse_attributes.
    return params


def get_langfuse_client():
    """Return the Langfuse singleton, initializing on first call."""
    global _langfuse_client
    if not is_tracing_enabled():
        return None
    if _langfuse_client is None:
        try:
            from langfuse import get_client

            _langfuse_client = get_client()
        except ImportError:
            return None
    return _langfuse_client


@contextmanager
def trace_turn(
    name: str,
    input_message: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[Optional[Any], None, None]:
    """
    Open a root trace span for a complete user turn (query + tool calls).

    This ensures that multiple subsequent calls to LLM methods within the same
    turn are consolidated into a single trace hierarchy.
    """
    with trace_span(
        name=name,
        input={"message": input_message},
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        metadata=metadata,
        as_type="agent",
    ) as span:
        yield span


@contextmanager
def trace_agent_run(
    agent_name: str,
    input_message: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[Optional[Any], None, None]:
    """
    Open a span for an LLMAgent.run() invocation.

    If no trace is active, it becomes the root trace.
    """
    with trace_span(
        name=agent_name,
        input={"message": input_message},
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        metadata=metadata,
        _is_agent_run=True,
        as_type="agent",
    ) as span:
        yield span


@contextmanager
def trace_span(
    name: str,
    *,
    input: Optional[Any] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    _is_agent_run: bool = False,
    as_type: str = "span",
) -> Generator[Optional[Any], None, None]:
    """
    Generic context manager for a tracing span.
    Handles root trace context propagation if no trace is active.
    """
    if not is_tracing_enabled():
        yield None
        return

    from langfuse import propagate_attributes

    client = get_langfuse_client()
    if not client:
        yield None
        return

    # Check if we are already inside an active trace
    current_obs_id = client.get_current_observation_id()
    is_nested = current_obs_id is not None

    resolved_name = name
    if is_nested and _is_agent_run:
        resolved_name = f"agent:run:{name}"

    if is_nested:
        with propagate_langfuse_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
        ):
            with client.start_as_current_observation(
                as_type=as_type,
                name=resolved_name,
                input=input,
                metadata=metadata or {},
            ) as span:
                try:
                    yield span
                except Exception as e:
                    span.update(level="ERROR", status_message=str(e))
                    raise
    else:
        with propagate_langfuse_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            # Note: propagate_langfuse_attributes doesn't currently take trace_name/metadata
            # but Langfuse's propagate_attributes does. We only care about user/session/tags for now.
        ):
            with client.start_as_current_observation(
                as_type=as_type,
                name=resolved_name,
                input=input,
                metadata=metadata or {},
            ) as span:
                try:
                    yield span
                except Exception as e:
                    span.update(
                        level="ERROR",
                        status_message=str(e),
                    )
                    raise


@contextmanager
def trace_tool_execution(
    tool_name: str, arguments: Dict[str, Any]
) -> Generator[Optional[Any], None, None]:
    """
    Open a 'span' observation for a single tool call execution.
    """
    if not is_tracing_enabled():
        yield None
        return

    client = get_langfuse_client()
    if not client:
        yield None
        return

    with client.start_as_current_observation(
        as_type="tool",
        name=f"tool:{tool_name}",
        input=arguments,
    ) as span:
        try:
            yield span
        except Exception as e:
            span.update(level="ERROR", status_message=str(e))
            raise


def update_span(
    span: Optional[Any],
    *,
    output: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    level: Optional[str] = None,
    status_message: Optional[str] = None,
) -> None:
    """
    Update a span with output data.
    """
    if span is None:
        return
    update_kwargs: Dict[str, Any] = {}
    if output is not None:
        update_kwargs["output"] = output
    if metadata:
        update_kwargs["metadata"] = metadata
    if level:
        update_kwargs["level"] = level
    if status_message:
        update_kwargs["status_message"] = status_message
    if update_kwargs:
        span.update(**update_kwargs)


def flush_tracing() -> None:
    """Flush all pending Langfuse events."""
    client = get_langfuse_client()
    if client:
        client.flush()


def get_current_trace_context(
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    trace_name: Optional[str] = None,
) -> Optional[TraceContext]:
    """Read current Langfuse trace/observation IDs and return a TraceContext.

    Returns None if tracing is disabled or no Langfuse context is active.
    """
    if session_id is None:
        session_id = _thread_session_id.get()

    if user_id is None:
        user_id = _thread_user_id.get()

    if not is_tracing_enabled():
        return None

    client = get_langfuse_client()
    if not client:
        return None

    try:
        trace_id = client.get_current_trace_id()
        observation_id = client.get_current_observation_id()
    except AttributeError:
        # Older langfuse versions might not have these methods or client might be different
        return None

    if not trace_id:
        return None

    return TraceContext(
        trace_id=trace_id,
        observation_id=observation_id,
        session_id=session_id,
        user_id=user_id,
        trace_name=trace_name,
        environment=os.getenv("ENVIRONMENT", "development"),
    )


def build_openrouter_trace_dict(
    ctx: Optional[TraceContext],
    *,
    generation_name: Optional[str] = None,
    span_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build the OpenRouter trace dict from a TraceContext.

    Returns None if ctx is None (tracing disabled).
    """
    if ctx is None:
        return None

    trace = {
        "trace_id": ctx.trace_id,
        "environment": ctx.environment,
    }

    if ctx.observation_id:
        trace["parent_span_id"] = ctx.observation_id
    if ctx.session_id:
        trace["session_id"] = ctx.session_id
    if ctx.user_id:
        trace["user_id"] = ctx.user_id
    if ctx.trace_name:
        trace["trace_name"] = ctx.trace_name
    if generation_name:
        trace["generation_name"] = generation_name
    if span_name:
        trace["span_name"] = span_name

    return trace
