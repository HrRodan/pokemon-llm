# Langfuse Observability Integration — Implementation Plan

> **Goal:** Provide complete visibility into all `LLMQuery` and `LLMAgent` interactions — including nested subagent calls and tool dispatches — via [Langfuse](https://langfuse.com/docs/observability/overview). Tracking is **fully optional** and activates automatically when `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_BASE_URL` are present in `.env`.

---

## Table of Contents

- [1. Background & Motivation](#1-background--motivation)
- [2. Architecture Overview](#2-architecture-overview)
- [3. SDK & API Reference Summary](#3-sdk--api-reference-summary)
- [4. Proposed Changes](#4-proposed-changes)
  - [4.1 NEW — `ai_tools/tracing.py`](#41-new--ai_toolstracingpy)
  - [4.2 MODIFY — `ai_tools/config.py`](#42-modify--ai_toolsconfigpy)
  - [4.3 MODIFY — `ai_tools/tools.py` (LLMQuery)](#43-modify--ai_toolstoolspy-llmquery)
  - [4.4 MODIFY — `ai_tools/agent.py` (LLMAgent)](#44-modify--ai_toolsagentpy-llmagent)
  - [4.5 MODIFY — `ai_tools/utils.py`](#45-modify--ai_toolsutilspy)
  - [4.6 MODIFY — `ai_tools/memory/handler.py` (MemoryHandler)](#46-modify--ai_toolsmemoryhandlerpy-memoryhandler)
  - [4.7 MODIFY — `ai_tools/memory/types.py`](#47-modify--ai_toolsmemorytypespy)
  - [4.8 MODIFY — `ai_tools/__init__.py`](#48-modify--ai_tools__init__py)
  - [4.9 UPDATE — `pyproject.toml`](#49-update--pyprojecttoml)
- [5. Trace Hierarchy Design](#5-trace-hierarchy-design)
- [6. Feature Coverage Matrix](#6-feature-coverage-matrix)
- [7. Import Order & Initialization Safety](#7-import-order--initialization-safety)
- [8. Verification Plan](#8-verification-plan)
- [9. Documentation Updates](#9-documentation-updates)
- [10. Resolved Decisions](#10-resolved-decisions)

---

## 1. Background & Motivation

The `ai_tools` framework provides `LLMQuery` (low-level LLM client with tool use, pipelines) and `LLMAgent` (higher-level orchestration loop). Both classes already track **token usage** and **cost** internally, but this data is not exported for analysis.

Langfuse provides:

- **Trace hierarchies** — structured view of every LLM call, tool execution, and sub-agent invocation
- **Session grouping** — link all traces from a conversation (maps naturally to `memory.thread_id`)
- **User attribution** — attach a user ID so cost and quality can be filtered per-user
- **Cost & token tracking** — automatic when using the OpenAI drop-in or manual `usage_details`
- **Metal data / Tags** — filterable context on every trace (agent name, model, provider)
- **Latency monitoring** — automatic start/end timings on every span and generation
- **Error tracking** — surface errors as `level=ERROR` with `status_message`

### Design Principles

1. **Zero-change opt-in:** No code changes for users. Presence of `LANGFUSE_*` env vars activates tracing.
2. **No performance penalty when disabled:** All tracing logic short-circuits with a fast `is_enabled` boolean check.
3. **Minimal coupling:** Tracing logic is encapsulated in a single new module (`tracing.py`). Core classes call thin helper methods; they never import `langfuse` directly.
4. **Full hierarchy:** Parent→child relationships between orchestrator → subagent → tool calls are preserved via Langfuse's context manager nesting.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ai_tools Package                         │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ config.py│───►│tracing.py│◄───│ tools.py │◄───│ agent.py │  │
│  │(env vars)│    │ (NEW)    │    │(LLMQuery)│    │(LLMAgent)│  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                       │                  │                       │
│                       │           ┌──────┴──────┐               │
│                       │           │  utils.py   │               │
│                       │           │(tool disp.) │               │
│                       │           └─────────────┘               │
│                       ▼                                         │
│                 ┌──────────────┐                                │
│                 │ langfuse SDK │  (optional dependency)         │
│                 │ get_client() │                                │
│                 │ @observe()   │                                │
│                 │ context mgrs │                                │
│                 └──────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. SDK & API Reference Summary

**Target SDK version:** `langfuse >= 4.0.0` (latest v4 Python SDK, OpenTelemetry-backed; current PyPI release: **4.0.6**)

The Langfuse Python SDK v4 provides three instrumentation approaches:

| Approach | API | When to Use |
|---|---|---|
| **Context Manager** | `langfuse.start_as_current_observation()` | Full lifecycle control, auto-nesting |
| **Observe wrapper** | `@observe()` decorator | Wrap functions, auto-capture I/O |
| **Manual observations** | `langfuse.start_observation()` | Parallel/side tasks, explicit `.end()` |

### Key APIs We Will Use

```python
from langfuse import get_client, observe, propagate_attributes

langfuse = get_client()

# Set user/session for the trace
with propagate_attributes(
    user_id="...", session_id="...", tags=[...], trace_name="..."
):
    # Create root trace span — context manager auto-ends
    with langfuse.start_as_current_observation(
        as_type="span", name="agent-run", input={...}
    ) as root:
        # Nested generation for LLM call
        with langfuse.start_as_current_observation(
            as_type="generation", name="llm-query", model="gpt-4o",
            input={...}
        ) as gen:
            gen.update(
                output={...},
                usage_details={"input": N, "output": M},
                metadata={"provider": "openai"}
            )

        # Nested span for tool execution
        with langfuse.start_as_current_observation(
            as_type="span", name="tool:get_weather", input={...}
        ) as tool_span:
            tool_span.update(output={...})

    root.update(output={...})
```

### Observation Types

| Type | Use Case | Our Mapping |
|---|---|---|
| `span` | Generic processing step | `LLMAgent.run()`, `get_tool_responses()` loop, tool execution |
| `generation` | LLM API call | Every `_create_chat_completion()` invocation |

### Correlating Attributes via `propagate_attributes()`

```python
with propagate_attributes(
    user_id="user_123",          # maps to Optional user_id
    session_id="thread_abc",     # maps to memory.thread_id
    tags=["PokemonAgent"],       # agent name as tag
    trace_name="agent-run",      # descriptive trace name
    metadata={"model": "gpt-4o", "provider": "openai"}
):
    ...
```

---

## 4. Proposed Changes

### 4.1 NEW — `ai_tools/tracing.py`

**Purpose:** Single module encapsulating all Langfuse interaction. No other module in `ai_tools` imports `langfuse` directly.

#### Public API

```python
# --- Singleton / Initialization ---
def is_tracing_enabled() -> bool:
    """Check if all LANGFUSE_* env vars are set and langfuse is importable."""

def get_langfuse_client() -> Optional["Langfuse"]:
    """Return the singleton Langfuse client, or None if tracing is disabled."""

# --- Context Managers (used by LLMQuery / LLMAgent) ---
@contextmanager
def trace_agent_run(
    agent_name: str,
    input_message: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Generator[Optional["LangfuseSpan"], None, None]:
    """
    Open a root trace span for an LLMAgent.run() invocation.

    Creates a 'span' observation named '<agent_name>' with the user message
    as input. All nested observations (LLM calls, tool executions) are
    automatically parented under this span via OTel context.

    If tracing is disabled, yields None and is a no-op.
    """

@contextmanager
def trace_llm_generation(
    name: str,
    model: str,
    input_messages: List[Dict],
    *,
    metadata: Optional[Dict[str, str]] = None,
) -> Generator[Optional["LangfuseGeneration"], None, None]:
    """
    Open a 'generation' observation for a single LLM API call.

    Caller MUST call `update_generation()` after receiving the response
    to record the output, token usage, and cost.

    If tracing is disabled, yields None and is a no-op.
    """

def update_generation(
    generation: Optional[Any],
    *,
    output: Optional[str] = None,
    usage: Optional[Dict] = None,
    model: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    level: Optional[str] = None,
    status_message: Optional[str] = None,
) -> None:
    """
    Update a generation span with the LLM response data.

    Safe to call with generation=None (tracing disabled).
    """

@contextmanager
def trace_tool_execution(
    tool_name: str,
    arguments: Dict[str, Any],
) -> Generator[Optional["LangfuseSpan"], None, None]:
    """
    Open a 'span' observation for a single tool call execution.

    Named 'tool:<tool_name>' with the arguments as input.
    Caller updates output after execution completes.

    If tracing is disabled, yields None and is a no-op.
    """

def update_span(
    span: Optional[Any],
    *,
    output: Optional[Any] = None,
    metadata: Optional[Dict[str, str]] = None,
    level: Optional[str] = None,
    status_message: Optional[str] = None,
) -> None:
    """
    Update a span with output data.

    Safe to call with span=None (tracing disabled).
    """

@contextmanager
def trace_subagent_call(
    subagent_name: str,
    query: str,
) -> Generator[Optional["LangfuseSpan"], None, None]:
    """
    Open a 'span' observation for a subagent tool invocation.

    Creates a nested span named 'subagent:<subagent_name>' under the
    current parent, preserving the full agent→subagent hierarchy.

    If tracing is disabled, yields None and is a no-op.
    """

def flush_tracing() -> None:
    """Flush all pending Langfuse events. Call in short-lived scripts."""
```

#### Internal Implementation Details

```python
import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# --- Lazy singleton ---
_langfuse_client = None
_tracing_checked = False
_tracing_enabled = False


def is_tracing_enabled() -> bool:
    """Return True if all required Langfuse env vars are present and SDK is importable."""
    global _tracing_checked, _tracing_enabled
    if _tracing_checked:
        return _tracing_enabled

    _tracing_checked = True
    required = ("LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_BASE_URL")
    if not all(os.getenv(k) for k in required):
        _tracing_enabled = False
        return False

    try:
        import langfuse  # noqa: F401
        _tracing_enabled = True
    except ImportError:
        logger.debug("langfuse package not installed; tracing disabled.")
        _tracing_enabled = False

    return _tracing_enabled


def get_langfuse_client():
    """Return the Langfuse singleton, initializing on first call."""
    global _langfuse_client
    if not is_tracing_enabled():
        return None
    if _langfuse_client is None:
        from langfuse import get_client
        _langfuse_client = get_client()
    return _langfuse_client


@contextmanager
def trace_agent_run(
    agent_name: str,
    input_message: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Generator:
    if not is_tracing_enabled():
        yield None
        return

    from langfuse import propagate_attributes

    client = get_langfuse_client()
    resolved_tags = [agent_name] + (tags or [])
    resolved_metadata = metadata or {}

    with propagate_attributes(
        user_id=user_id,
        session_id=session_id,
        tags=resolved_tags,
        trace_name=agent_name,
        metadata=resolved_metadata,
    ):
        with client.start_as_current_observation(
            as_type="span",
            name=agent_name,
            input={"message": input_message},
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
    input_messages: List[Dict],
    *,
    metadata: Optional[Dict[str, str]] = None,
) -> Generator:
    if not is_tracing_enabled():
        yield None
        return

    client = get_langfuse_client()

    # Strip provider prefix for cleaner display
    display_model = model
    for prefix in ("openai/", "gemini/", "openrouter/", "ollama/"):
        if display_model.startswith(prefix):
            display_model = display_model[len(prefix):]
            break

    with client.start_as_current_observation(
        as_type="generation",
        name=name,
        model=display_model,
        input=input_messages,
        metadata=metadata or {},
    ) as gen:
        try:
            yield gen
        except Exception as e:
            gen.update(level="ERROR", status_message=str(e))
            raise


def update_generation(generation, *, output=None, usage=None, model=None,
                      metadata=None, level=None, status_message=None):
    if generation is None:
        return
    update_kwargs = {}
    if output is not None:
        update_kwargs["output"] = output
    if metadata:
        update_kwargs["metadata"] = metadata
    if level:
        update_kwargs["level"] = level
    if status_message:
        update_kwargs["status_message"] = status_message
    if usage:
        update_kwargs["usage_details"] = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
        }
    if update_kwargs:
        generation.update(**update_kwargs)


@contextmanager
def trace_tool_execution(tool_name: str, arguments: Dict[str, Any]) -> Generator:
    if not is_tracing_enabled():
        yield None
        return

    client = get_langfuse_client()
    with client.start_as_current_observation(
        as_type="span",
        name=f"tool:{tool_name}",
        input=arguments,
    ) as span:
        try:
            yield span
        except Exception as e:
            span.update(level="ERROR", status_message=str(e))
            raise


@contextmanager
def trace_subagent_call(subagent_name: str, query: str) -> Generator:
    if not is_tracing_enabled():
        yield None
        return

    client = get_langfuse_client()
    with client.start_as_current_observation(
        as_type="span",
        name=f"subagent:{subagent_name}",
        input={"query": query},
    ) as span:
        try:
            yield span
        except Exception as e:
            span.update(level="ERROR", status_message=str(e))
            raise


def update_span(span, *, output=None, metadata=None, level=None, status_message=None):
    if span is None:
        return
    update_kwargs = {}
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


def flush_tracing():
    client = get_langfuse_client()
    if client:
        client.flush()
```

#### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Singleton client via `get_client()`** | Langfuse SDK manages its own batching/flush lifecycle; one client per process is correct. |
| **Context managers (not decorators)** | `LLMQuery.query()` and `get_tool_responses()` have complex control flow (retry loops, recursive re-queries). Context managers integrate cleanly without refactoring. |
| **No direct `langfuse` import anywhere except `tracing.py`** | Keeps the dependency truly optional. If `langfuse` is not installed but env vars are absent, everything works. |
| **`is_tracing_enabled()` cached after first check** | Prevents repeated `os.getenv` + import probing on every call. The on/off state is fixed for the process lifetime. |
| **provider prefix stripped from model name** | Langfuse's model field should show `gpt-4o`, not `openai/gpt-4o`, for correct cost calculation and filtering. |

---

### 4.2 MODIFY — `ai_tools/config.py`

**Minimal changes.** The Langfuse SDK reads `LANGFUSE_*` env vars automatically from the process environment. Since `config.py` already calls `load_dotenv(override=True)` at import time, the env vars from `.env` are available before any `langfuse` import occurs.

**No code changes needed in `config.py`.**

> **Critical: import order.** `config.py` must be imported (and thus `load_dotenv()` executed) BEFORE any `langfuse` call. This is already the case: `tools.py` imports `config.py` at line 44, and `tracing.py` will only call `get_client()` lazily on first use (which happens inside `query()` / `run()`).

---

### 4.3 MODIFY — `ai_tools/tools.py` (LLMQuery)

#### 4.3.0 — Add `user_id` attribute

Add `user_id: Optional[str] = None` to `LLMQuery.__init__()`. Stored as `self.user_id`. This is a lightweight pass-through — `LLMQuery` itself does not use `user_id` for any logic; it exists so that `LLMAgent` and `tracing.py` can read it from the LLMQuery instance without coupling.

```python
def __init__(self, ..., user_id: Optional[str] = None, ...):
    self.user_id = user_id
    # ... existing init ...
```

#### 4.3.1 — Trace `query()` calls

Wrap the core of `query()` in `trace_llm_generation()`:

```python
# In LLMQuery.query(), around the _create_chat_completion call:

from .tracing import trace_llm_generation, update_generation

# After building messages and request_kwargs:
with trace_llm_generation(
    name=f"llm-query",
    model=cfg["model"],
    input_messages=messages,
    metadata={"provider": cfg["model"].split("/")[0] if "/" in cfg["model"] else "unknown"},
) as generation:
    response = self._create_chat_completion(client, **request_kwargs)

    # Extract usage for Langfuse
    usage_data = None
    if hasattr(response, "usage") and response.usage:
        self._update_usage(response.usage)
        usage_data = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }

    message = response.choices[0].message
    content = message.content
    # ... existing extraction logic ...

    update_generation(
        generation,
        output=content or "[tool_calls_only]",
        usage=usage_data,
        model=cfg["model"],
        metadata={"tool_calls": str(len(self.tool_calls))} if self.tool_calls else None,
    )
```

#### 4.3.2 — Trace `get_tool_responses()` loop

Wrap each iteration of the tool loop with a parent span and individual tool execution spans:

```python
# In LLMQuery.get_tool_responses():
from .tracing import trace_tool_execution, update_span

# Inside the while loop, wrapping the tool dispatch:
# The individual tool_call tracing is done inside handle_tool_call / handle_tool_call_async
# (see section 4.5). The loop itself does not need a separate span since the
# parent span from LLMAgent.run() already contains the iterations.
```

#### 4.3.3 — Trace `as_tool()` (LLMQuery wrapped as tool)

Wrap the tool wrapper function with `trace_subagent_call()`:

```python
# In LLMQuery.as_tool():
from .tracing import trace_subagent_call, update_span

def _wrapper(**kwargs) -> str:
    prompt = kwargs.get(input_arg, "")
    with trace_subagent_call(name, prompt) as span:
        # ... existing logic ...
        result = llm_ref.get_tool_responses()
        update_span(span, output=result[:500] if result else "")
        return result
```

---

### 4.4 MODIFY — `ai_tools/agent.py` (LLMAgent)

#### 4.4.0 — Add `user_id` parameter

Add `user_id: Optional[str] = None` to `LLMAgent.__init__()`. This is stored as `self.user_id` and passed to both the `MemoryHandler` (for checkpoint metadata) and to `trace_agent_run()` for Langfuse attribution.

```python
def __init__(
    self,
    name: str,
    model_name: str,
    system_prompt: str = "",
    tools: Optional[List] = None,
    functions: Optional[List] = None,
    memory: Optional["MemoryHandler"] = None,
    user_id: Optional[str] = None,    # <-- NEW
    **kwargs,
) -> None:
    self.user_id = user_id
    # ... existing init ...
    # Propagate user_id to the LLMQuery
    self.llm.user_id = user_id
    # Propagate user_id to the MemoryHandler
    if self.llm.memory:
        self.llm.memory.user_id = user_id
```

#### 4.4.1 — Trace `run()` with root span + session/user propagation

```python
# In LLMAgent.run():
from .tracing import trace_agent_run, update_span

def run(self, message: str, use_history: bool = True) -> str:
    self.logger.info(f"QUERY: {message}")

    # Derive session_id from memory thread if available
    session_id = None
    if self.llm.memory and hasattr(self.llm.memory, "thread_id"):
        session_id = self.llm.memory.thread_id

    with trace_agent_run(
        agent_name=self.name,
        input_message=message,
        user_id=self.user_id,           # <-- propagated to Langfuse
        session_id=session_id,
        tags=[self.name, self.model_name.split("/")[0]],
        metadata={"model": self.model_name},
    ) as span:
        response = self.llm.query(user_prompt=message, use_history=use_history)

        if self.llm.tool_calls:
            response = self.llm.get_tool_responses()

        self.logger.info(f"🧠 RESPONSE: {response}")
        self._update_usage()

        update_span(span, output=response[:1000] if response else "")

    return response
```

#### 4.4.2 — Trace `as_tool()` (LLMAgent wrapped as subagent tool)

```python
# In LLMAgent.as_tool() wrapper:
from .tracing import trace_subagent_call, update_span

def _wrapper(**kwargs) -> str:
    query = kwargs.get("query", "")
    with trace_subagent_call(agent_ref.TOOL_NAME, query) as span:
        # ... existing scoped memory logic ...
        result = agent_ref.run(query)
        update_span(span, output=result[:500] if result else "")
        # ... existing restore logic ...
        return result
```

---

### 4.5 MODIFY — `ai_tools/utils.py`

#### 4.5.1 — Trace individual tool executions in `handle_tool_call()`

Each tool call gets its own `trace_tool_execution()` span:

```python
from .tracing import trace_tool_execution, update_span

def handle_tool_call(tool_calls, functions, logger=None):
    tool_response = []
    function_map = {f.__name__: f for f in functions}

    for tool_call in tool_calls:
        tool_id = tool_call.get("id", "unknown_id")
        function_name = sanitize_tool_name(...)
        arguments = ...  # existing parsing

        with trace_tool_execution(function_name, arguments) as span:
            try:
                # ... existing execution logic ...
                result = function_to_call(**arguments)
                update_span(span, output=str(result)[:500])
            except Exception as e:
                result = f"Error: {str(e)}"
                update_span(span, output=result, level="ERROR", status_message=str(e))

        tool_response.append({...})

    return tool_response
```

#### 4.5.2 — Trace individual tool executions in `handle_tool_call_async()`

Same pattern but within the async `_dispatch_one()`:

```python
from .tracing import trace_tool_execution, update_span

async def _dispatch_one(tool_call):
    # ... existing parsing ...
    with trace_tool_execution(function_name, arguments) as span:
        try:
            result = await asyncio.to_thread(function_to_call, **arguments)
            update_span(span, output=str(result)[:500])
        except Exception as e:
            result = f"Error: {str(e)}"
            update_span(span, output=result, level="ERROR", status_message=str(e))

    return {...}
```

---

### 4.6 MODIFY — `ai_tools/memory/handler.py` (MemoryHandler)

**Purpose:** Add `user_id` as a first-class property on `MemoryHandler`. This allows the Streamlit app (or any caller) to set the user identity once, and it automatically flows into both Langfuse traces (via `trace_agent_run`) and memory checkpoint metadata.

#### Changes

1. Add `user_id: Optional[str] = None` parameter to `__init__()`.
2. Expose as a settable `user_id` property (so it can be set after construction, e.g. after Streamlit login).
3. Pass `user_id` in checkpoint metadata when persisting.
4. Include `user_id` in `create_scoped_handler()` so subagents inherit the parent's user identity.

```python
class MemoryHandler:
    def __init__(
        self,
        backend: Optional[MemoryBackend] = None,
        thread_id: Optional[str] = None,
        agent_name: str = "",
        user_id: Optional[str] = None,    # <-- NEW
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._backend = backend or InMemoryBackend()
        self._agent_name = agent_name
        self._user_id = user_id               # <-- NEW
        self._logger = logger
        # ... existing thread init ...

    @property
    def user_id(self) -> Optional[str]:
        """The user ID associated with this memory context."""
        return self._user_id

    @user_id.setter
    def user_id(self, value: Optional[str]) -> None:
        """Set the user ID (e.g. after Streamlit login)."""
        self._user_id = value

    def create_scoped_handler(self, subagent_name: str) -> "MemoryHandler":
        # ... existing logic ...
        # Propagate user_id to scoped handler
        handler = MemoryHandler._from_scoped_id(...)
        handler._user_id = self._user_id  # Inherit parent's user identity
        return handler
```

---

### 4.7 MODIFY — `ai_tools/memory/types.py`

**Purpose:** Add `user_id` field to `ThreadInfo` so threads can be filtered/grouped by user.

```python
@dataclass
class ThreadInfo:
    thread_id: str
    agent_name: str
    user_id: Optional[str] = None         # <-- NEW
    parent_thread_id: Optional[str] = None
    parent_step_id: Optional[int] = None
    message_count: int = 0
    initial_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None
```

> [!NOTE]
> The `user_id` field is added to `ThreadInfo` only (metadata). The `Checkpoint` and `ConversationState` dataclasses remain unchanged — user identity is a **thread-level** concern, not a per-step concern.

---

### 4.8 MODIFY — `ai_tools/__init__.py`

Add tracing exports:

```python
from .tracing import is_tracing_enabled, flush_tracing

__all__ = [
    # ... existing exports ...
    "is_tracing_enabled",
    "flush_tracing",
]
```

---

### 4.9 UPDATE — `pyproject.toml`

Add `langfuse` as an **optional** dependency:

```toml
[project.optional-dependencies]
tracing = ["langfuse>=4.0.0"]
```

Users install with: `uv add langfuse` or `pip install ai_tools[tracing]`.

---

## 5. Trace Hierarchy Design

### Simple query (no tools)

```
Trace: "agent-run"
 └─ Generation: "llm-query" (model=gpt-4o, tokens, cost)
```

### Single-level tool use

```
Trace: "PokemonAgent"
 ├─ Generation: "llm-query" (initial call → requests tool)
 ├─ Span: "tool:get_pokemon_data" (input=args, output=result)
 └─ Generation: "llm-query" (final response after tool result)
```

### Multi-level with subagents

```
Trace: "Orchestrator"
 ├─ Generation: "llm-query" (decides to call subagent)
 ├─ Span: "tool:run_web_search_agent"
 │   └─ Span: "subagent:WebSearchAgent"
 │       ├─ Generation: "llm-query" (subagent initial call)
 │       ├─ Span: "tool:brave_search" (actual search)
 │       └─ Generation: "llm-query" (subagent final response)
 └─ Generation: "llm-query" (orchestrator final response)
```

### Pipeline chains

```
Trace: (auto-created by first query)
 ├─ Generation: "llm-query" (step 1: translate)
 └─ Generation: "llm-query" (step 2: uppercase)
```

### Session grouping (via memory thread_id)

```
Session: "thread_abc123"
 ├─ Trace: "PokemonAgent"  (turn 1)
 ├─ Trace: "PokemonAgent"  (turn 2)
 └─ Trace: "PokemonAgent"  (turn 3)
```

---

## 6. Feature Coverage Matrix

| ai_tools Feature | Langfuse Mapping | Observation Type | Data Captured |
|---|---|---|---|
| `LLMQuery.query()` | Generation | `generation` | Model, messages, response, tokens, cost, reasoning |
| `LLMQuery.get_tool_responses()` | Multiple tool spans + generations | `span` + `generation` | Tool args, results, subsequent LLM calls |
| `LLMAgent.run()` | Root trace span | `span` | Agent name, **user_id**, message in, response out |
| `LLMAgent.as_tool()` (subagent) | Nested subagent span | `span` | Subagent name, query, result |
| `LLMQuery.as_tool()` (subquery) | Nested subagent span | `span` | Name, query, result |
| `handle_tool_call()` | Per-tool span | `span` | Function name, args, output, errors |
| `handle_tool_call_async()` | Per-tool span (concurrent) | `span` | Same as sync, parallel execution visible |
| Memory `thread_id` | Session ID | `session_id` | Groups all turns of a conversation |
| Memory `user_id` | User ID | `user_id` | Filters cost/quality per user |
| Retry logic (`tenacity`) | Visible via repeated generations | `generation` | Each retry = separate generation span |
| Reasoning-only re-query | Recursive generation | `generation` | Shows the reasoning → re-query chain |
| Pipeline (`\|` operator) | Sequential generation spans | `generation` | Each step visible as separate generation |
| Multi-modal (image, TTS, etc.) | **Not traced** | — | Excluded (confirmed: not LLM calls) |
| Error in tool execution | Error-level span | `span` | `level=ERROR`, `status_message` |
| Error in LLM call | Error-level generation | `generation` | `level=ERROR`, `status_message` |

---

## 7. Import Order & Initialization Safety

### Critical Requirement

Langfuse **must** be imported AFTER `load_dotenv()` has executed. Otherwise it initializes with missing/wrong credentials.

### How We Satisfy This

1. `config.py` calls `load_dotenv(override=True)` at module level (line 25).
2. `tracing.py` **never** imports `langfuse` at module level. All imports are deferred inside functions (inside `is_tracing_enabled()` and `get_langfuse_client()`).
3. `tools.py` imports `config.py` at line 44, long before any tracing function is called.
4. The first tracing function call happens inside `query()` or `run()`, which is always after all imports have completed.

**Result:** By the time `get_client()` is called, the env vars are guaranteed to be loaded. This avoids the [common mistake #7 from the instrumentation guide](references/instrumentation.md).

### When Langfuse Is Not Installed

If `langfuse` is not installed:

- `is_tracing_enabled()` returns `False` (catches `ImportError`)
- All context managers yield `None` immediately
- All `update_*` functions return immediately when `span=None`
- **Zero overhead:** one `bool` check per context manager entry

---

## 8. Verification Plan

### Unit Tests (`tests/test_tracing.py`)

| Test | Assertion |
|---|---|
| `test_tracing_disabled_no_env_vars` | `is_tracing_enabled()` returns `False`, all context managers are no-ops |
| `test_tracing_disabled_no_package` | Mock `ImportError`, verify graceful fallback |
| `test_tracing_enabled_with_env_vars` | Mock env vars + langfuse import, verify `is_tracing_enabled()` returns `True` |
| `test_trace_agent_run_creates_span` | Mock `get_client()`, verify `start_as_current_observation()` called with expected args |
| `test_trace_llm_generation_creates_generation` | Mock client, verify generation created with model/messages |
| `test_update_generation_with_usage` | Verify `usage_details` is correctly formatted |
| `test_trace_tool_execution_records_error` | Simulate tool error, verify `level=ERROR` set |
| `test_session_id_from_memory_thread` | Verify thread_id is passed as session_id to `propagate_attributes()` |
| `test_user_id_propagated_to_trace` | Verify `user_id` from `LLMAgent` is passed to `propagate_attributes()` |
| `test_subagent_creates_nested_span` | Verify subagent span is created with correct name |
| `test_flush_tracing_calls_client_flush` | Verify `flush()` is forwarded to the client |
| `test_memory_handler_user_id_property` | Verify `user_id` getter/setter on `MemoryHandler` |
| `test_scoped_handler_inherits_user_id` | Verify subagent scoped handler inherits parent's `user_id` |

### Integration Smoke Test (`tests/test_tracing_integration.py`)

A single end-to-end test that:

1. Sets `LANGFUSE_*` env vars (from `.env`)
2. Creates an `LLMAgent` with a `@tool`-decorated function
3. Calls `agent.run("Use the tool")` 
4. Verifies traces appear in Langfuse via `langfuse-cli api traces list`
5. Validates trace structure: root span → generation → tool span → generation

> **Note:** Integration test is run manually (requires live Langfuse credentials), not in CI.

---

## 9. Documentation Updates

| File | Changes |
|---|---|
| `ai_tools/README.md` | New section: **Langfuse Tracing (Optional)** with setup instructions, trace hierarchy diagram, and examples |
| `ai_tools/tracing.py` | Full module docstring + Google-style docstrings on all public functions |
| `ai_tools/memory/README.md` | Note that `thread_id` maps to Langfuse `session_id` for conversation grouping |
| `.env.example` | Add `LANGFUSE_*` vars with comments |

---

## 10. Resolved Decisions

All open questions have been resolved:

| # | Question | Decision | Impact |
|---|---|---|---|
| Q1 | **User ID propagation** | **Add `user_id` to `LLMQuery.__init__()`, `LLMAgent.__init__()`, and `MemoryHandler.__init__()`**. The Streamlit app sets it after login. It flows through to Langfuse `user_id` and memory `ThreadInfo.user_id`. | New `user_id` attribute on 3 classes; new field on `ThreadInfo`; `MemoryHandler.user_id` has getter/setter for post-construction assignment. |
| Q2 | **Multi-modal tracing** | **Excluded.** Multi-modal operations (`generate_image`, `generate_tts`, `transcribe_audio`, `generate_embedding`) are not LLM calls and are not traced. | No changes to `multimodal.py`. |
| Q3 | **Custom trace names** | Use `agent_name` as trace name (default). No per-call override for now. | No additional parameters. |
| Q4 | **Langfuse SDK version** | **Pin `langfuse>=4.0.0`** (latest: 4.0.6). The v4 SDK (`get_client()`, `start_as_current_observation()`, `propagate_attributes()`) is the current stable API. | `pyproject.toml` optional dep uses `>=4.0.0`. |

### user_id Flow Diagram

```
Streamlit App (login)
  │
  ├──► LLMAgent(user_id="user_123")
  │      ├──► self.user_id = "user_123"
  │      ├──► self.llm.user_id = "user_123"         (LLMQuery)
  │      └──► self.llm.memory.user_id = "user_123"  (MemoryHandler)
  │              ├──► ThreadInfo.user_id = "user_123"  (persisted)
  │              └──► scoped_handler.user_id = "user_123" (subagents inherit)
  │
  └──► trace_agent_run(user_id="user_123")          (Langfuse trace)
         └──► propagate_attributes(user_id="user_123")
```

---

## Implementation Order

1. **`memory/types.py`** — Add `user_id` field to `ThreadInfo`
2. **`memory/handler.py`** — Add `user_id` property with getter/setter, propagate to scoped handlers
3. **`tracing.py`** — New module with all helpers (no external dependencies touched)
4. **`tools.py`** — Add `user_id` attribute, wrap `query()` with generation spans, wrap `as_tool()` wrapper
5. **`agent.py`** — Add `user_id` parameter, propagate to LLMQuery/MemoryHandler, wrap `run()` with root span, wrap `as_tool()` wrapper
6. **`utils.py`** — Wrap `handle_tool_call` / `handle_tool_call_async` with tool spans
7. **`__init__.py`** — Export new public API
8. **`pyproject.toml`** — Add `langfuse>=4.0.0` optional dependency
9. **Tests** — Unit tests + integration smoke test
10. **Documentation** — README updates, docstrings
