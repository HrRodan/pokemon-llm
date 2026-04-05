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
from typing import Any, Dict, Generator, List, Optional

from opentelemetry import trace

logger = logging.getLogger(__name__)

# --- Lazy singleton ---
_langfuse_client = None
_tracing_checked = False
_tracing_enabled = False


def is_tracing_enabled() -> bool:
    """Return True if required Langfuse env vars are present and OpenAI wrapper is importable."""
    global _tracing_checked, _tracing_enabled
    if _tracing_checked:
        return _tracing_enabled

    _tracing_checked = True
    required = ("LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASE_URL")
    
    # If any required env var is missing, disable tracing.
    if not all(os.getenv(k) for k in required):
        _tracing_enabled = False
        return False

    try:
        # We need the OpenAI wrapper for the simplified instrumentation to work safely.
        from langfuse.openai import OpenAI  # noqa: F401
        _tracing_enabled = True
    except ImportError:
        logger.debug("langfuse.openai package not available; tracing disabled.")
        _tracing_enabled = False

    return _tracing_enabled


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
    if is_tracing_enabled():
        try:
            from langfuse import propagate_attributes
            with propagate_attributes(user_id=user_id, session_id=session_id, tags=tags):
                yield
        except ImportError:
            yield
    else:
        yield


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
            logger.debug("langfuse.openai not available; falling back to standard openai.")
    
    from openai import OpenAI
    return OpenAI


def get_langfuse_params(
    *,
    model: str,
    agent_name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return a dictionary of Langfuse-specific parameters for OpenAI calls.
    
    This centralizes the generation naming logic: generation:<AgentName>:<Model>
    or generation:LLMQuery:<Model> if no agent name is provided.
    """
    if not is_tracing_enabled():
        return {}

    name_parts = ["generation"]
    if agent_name:
        name_parts.append(agent_name)
    else:
        name_parts.append("LLMQuery")
    trace_name = ":".join(name_parts)

    params = {"name": trace_name}
    if metadata:
        params["metadata"] = metadata
        
    return params



def annotate_llm_response(response: Any, original_model: str) -> None:
    """
    [DEPRECATED] Metadata annotation logic removed as per user request.
    """
    pass


def get_langfuse_client():
    """Return the Langfuse singleton, initializing on first call."""
    global _langfuse_client
    if not is_tracing_enabled():
        return None
    if _langfuse_client is None:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse()
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
    current_span = trace.get_current_span()
    is_nested = current_span.get_span_context().is_valid

    resolved_name = name
    if is_nested and _is_agent_run:
        resolved_name = f"agent:run:{name}"

    if is_nested:
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
        with propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            trace_name=resolved_name,
            metadata=metadata or {},
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
def trace_llm_generation(
    name: str,
    model: str,
    input_messages: List[Dict[str, Any]],
    *,
    model_parameters: Optional[Dict[str, Any]] = None,
    tool_definitions: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Generator[Optional[Any], None, None]:
    """
    [DEPRECATED] Manual tracing of LLM generations.
    
    Prefer using get_openai_class() and get_langfuse_params() for 
    automatic instrumentation via the Langfuse OpenAI wrapper.
    """
    if not is_tracing_enabled():
        yield None
        return

    client = get_langfuse_client()
    if not client:
        yield None
        return

    display_model = model

    # Use a descriptive name if it's generic
    obs_name = name
    if obs_name == "llm-query":
        obs_name = f"generation:{display_model}"

    from opentelemetry import trace

    current_span = trace.get_current_span()
    is_nested = current_span.get_span_context().is_valid

    # Ensure tool_definitions are always included in metadata as "tools"
    # following the pattern in the minimal example.
    _metadata = metadata.copy() if metadata else {}
    if tool_definitions is not None:
        _metadata["tools"] = tool_definitions

    if is_nested:
        with client.start_as_current_observation(
            as_type="generation",
            name=obs_name,
            model=display_model,
            model_parameters=model_parameters or {},
            input=input_messages,
            metadata=_metadata,
        ) as gen:
            try:
                yield gen
            except Exception as e:
                gen.update(level="ERROR", status_message=str(e))
                raise
    else:
        from langfuse import propagate_attributes
        with propagate_attributes(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
            trace_name=obs_name,
            metadata=_metadata,
        ):
            with client.start_as_current_observation(
                as_type="generation",
                name=obs_name,
                model=display_model,
                model_parameters=model_parameters or {},
                input=input_messages,
                metadata=_metadata,
            ) as gen:
                try:
                    yield gen
                except Exception as e:
                    gen.update(level="ERROR", status_message=str(e))
                    raise


def update_generation(
    generation: Optional[Any],
    *,
    output: Optional[Any] = None,
    usage: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    tool_call_names: Optional[List[str]] = None,
    tool_definitions: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    level: Optional[str] = None,
    status_message: Optional[str] = None,
) -> None:
    """
    Update a generation span with the LLM response data.
    """
    if generation is None:
        return
    update_kwargs: Dict[str, Any] = {}
    if output is not None:
        update_kwargs["output"] = output
    if model is not None:
        update_kwargs["model"] = model
    
    # Ensure tool calls and names are captured in metadata for UI visibility
    _metadata = metadata.copy() if metadata else {}
    if tool_definitions is not None:
        _metadata["tools"] = tool_definitions
    if tool_calls is not None:
        update_kwargs["tool_calls"] = tool_calls
        _metadata["tool_calls"] = tool_calls
    if tool_call_names is not None:
        update_kwargs["tool_call_names"] = tool_call_names
        _metadata["tool_call_names"] = tool_call_names
    
    if _metadata:
        update_kwargs["metadata"] = _metadata
        
    if level:
        update_kwargs["level"] = level
    if status_message:
        update_kwargs["status_message"] = status_message

    if usage:
        update_kwargs["usage_details"] = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
        }
        if "total_cost" in usage:
            update_kwargs["cost_details"] = {
                "total": usage["total_cost"]
            }
    if update_kwargs:
        generation.update(**update_kwargs)


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
