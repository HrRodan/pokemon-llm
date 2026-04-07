# Detailed Implementation Plan: `ai_tools` Refactoring

> **Goal:** Unify `LLMQuery` and `LLMAgent` into a single `Agent` class.
> **Source of Truth:** `ai_tools/task_streamline.md`
> **Backward compatibility:** Not required.

---

## Pre-Requisites

Before starting, ensure all existing tests pass:
```bash
uv run pytest ai_tools/tests/ -v
```

Create a feature branch:
```bash
git checkout -b refactor/unified-agent
```

---

## Phase 0: Unify Agent and LLMQuery

### Step 0.1 — Create `ai_tools/usage.py`

**Purpose:** Thread-safe token/cost accumulator. Currently duplicated in `LLMQuery._update_usage()` (tools.py:755-790) and aggregated manually in both `LLMQuery.as_tool()` (tools.py:1491-1496) and `LLMAgent.as_tool()` (agent.py:216-221).

**Create** `ai_tools/usage.py` with:

```python
"""Thread-safe token and cost tracker for LLM usage."""

import threading
from typing import Any, Optional


class UsageTracker:
    """Accumulates token counts and cost across multiple LLM calls.

    Thread-safe: uses a lock for all mutations, safe for concurrent tool dispatch.

    Example::
        tracker = UsageTracker()
        tracker.update(api_response.usage)
        print(tracker.total_cost)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_cost: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_reasoning_tokens: int = 0
        self.total_tokens: int = 0

    def update(self, usage: Any) -> None:
        """Accumulate token counts and cost from an API usage object.

        Handles two cost locations:
        - ``usage.model_extra["cost"]`` — OpenRouter injects cost here.
        - ``usage["cost"]`` — fallback for dict-shaped usage objects.

        Handles two reasoning-token locations:
        - ``usage.completion_tokens_details`` as dict or object attribute.
        """
        if not usage:
            return

        with self._lock:
            # Handle both object attributes and dictionary keys safely
            if isinstance(usage, dict):
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                self.total_tokens += usage.get("total_tokens", 0)
                self.total_cost += usage.get("cost", 0.0)
                
                details = usage.get("completion_tokens_details")
                if isinstance(details, dict):
                    self.total_reasoning_tokens += details.get("reasoning_tokens", 0)
            else:
                self.total_prompt_tokens += getattr(usage, "prompt_tokens", 0)
                self.total_completion_tokens += getattr(usage, "completion_tokens", 0)
                self.total_tokens += getattr(usage, "total_tokens", 0)
                
                model_extra = getattr(usage, "model_extra", None)
                if model_extra:
                    self.total_cost += model_extra.get("cost", 0.0)
                elif hasattr(usage, "cost"):
                    self.total_cost += getattr(usage, "cost", 0.0)

                details = getattr(usage, "completion_tokens_details", None)
                if details:
                    if isinstance(details, dict):
                        self.total_reasoning_tokens += details.get("reasoning_tokens", 0)
                    elif hasattr(details, "reasoning_tokens"):
                        self.total_reasoning_tokens += details.reasoning_tokens

    def aggregate_from(self, other: "UsageTracker") -> None:
        """Merge another tracker's totals into this one. Thread-safe."""
        with self._lock:
            self.total_cost += other.total_cost
            self.total_prompt_tokens += other.total_prompt_tokens
            self.total_completion_tokens += other.total_completion_tokens
            self.total_reasoning_tokens += other.total_reasoning_tokens
            self.total_tokens += other.total_tokens

    def reset(self) -> None:
        """Zero all counters. Does NOT reset the lock."""
        with self._lock:
            self.total_cost = 0.0
            self.total_prompt_tokens = 0
            self.total_completion_tokens = 0
            self.total_reasoning_tokens = 0
            self.total_tokens = 0

    @property
    def snapshot(self) -> dict:
        """Return a dict snapshot of current usage."""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.total_reasoning_tokens,
            "cost": self.total_cost,
        }
```

**Verification:** Write `ai_tools/tests/test_usage.py` with basic tests for `update()`, `aggregate_from()`, `reset()`, and `snapshot`.

---

### Step 0.2 — Create `ai_tools/client.py`

**Purpose:** Stateless provider client factory. Currently at tools.py:509-542.

**Create** `ai_tools/client.py` with:

```python
"""Stateless provider client factory."""

from openai import OpenAI

from . import config as _cfg
from .tracing import get_openai_class


def get_client(model: str) -> OpenAI:
    """Return an OpenAI-compatible client for the given prefixed model name.

    Supports: openai/, gemini/, openrouter/, ollama/
    
    Args:
        model: Full model name with provider prefix (e.g. "gemini/gemini-flash-latest").
    
    Raises:
        ValueError: If the model lacks a recognized provider prefix.
    """
    OpenAIClass = get_openai_class()
    provider, _ = _cfg.strip_provider_prefix(model)

    if provider == "openai":
        return OpenAIClass(api_key=_cfg.get_api_key("OPENAI_API_KEY"))
    elif provider == "ollama":
        return OpenAIClass(base_url=_cfg.OLLAMA_BASE_URL, api_key="ollama")
    elif provider == "gemini":
        return OpenAIClass(
            base_url=_cfg.GEMINI_BASE_URL,
            api_key=_cfg.get_api_key("GOOGLE_API_KEY"),
        )
    elif provider == "openrouter":
        return OpenAIClass(
            base_url=_cfg.OPENROUTER_BASE_URL,
            api_key=_cfg.get_api_key("OPENROUTER_API_KEY"),
        )
    raise ValueError(
        f"Model '{model}' lacks a recognized provider prefix (openai/, ollama/, gemini/, openrouter/)."
    )
```

**Verification:** Ensure tests that mock `_get_client_for_model` still pass when redirected to `get_client()`.

---

### Step 0.3 — Add `strip_provider_prefix()` to `ai_tools/config.py`

**Purpose:** Eliminate the 6× duplicated prefix-stripping pattern across tools.py and multimodal.py.

**Append** to the end of `ai_tools/config.py`:

```python
PROVIDER_PREFIXES = ("openai/", "ollama/", "gemini/", "openrouter/")

def strip_provider_prefix(model: str) -> tuple[str, str]:
    """Return (provider, api_model_name) from a prefixed model string.

    Example::
        >>> strip_provider_prefix("gemini/gemini-flash-latest")
        ("gemini", "gemini-flash-latest")
    """
    for prefix in PROVIDER_PREFIXES:
        if model.startswith(prefix):
            return prefix.rstrip("/"), model[len(prefix):]
    return "unknown", model
```

---

### Step 0.4 — Create `ai_tools/parsing.py`

**Purpose:** Pure-function XML/token tool-call parsers. Currently at tools.py:359-507.

**Create** `ai_tools/parsing.py`, moving these functions from `LLMQuery`:
- `_parse_xml_tool_calls(content, functions_list)` → `parse_xml_tool_calls(content, known_function_names)` 
  - Source: tools.py:359-486
  - Change: Instead of accessing `self.functions`, accept a `known_function_names: list[str]` parameter for Path 5
- `_sanitize_tool_id(tool_id)` → `sanitize_tool_id(tool_id)`
  - Source: tools.py:488-507
- `_extract_and_sanitize_tool_calls(message_tool_calls, content)` → `extract_and_sanitize_tool_calls(message_tool_calls, content, known_function_names)`
  - Source: tools.py:840-859
  - Change: Accept `known_function_names` parameter instead of using `self`
- `_extract_reasoning(message)` → `extract_reasoning(message)`
  - Source: tools.py:792-838

All functions must be **pure** — no `self` references. Import `generate_short_id` and `sanitize_tool_name` from `utils.py`.

**Verification:** The existing `test_handle_tool_call.py` should still pass. Write focused unit tests for `parse_xml_tool_calls()` covering all 5 XML formats.

---

### Step 0.5 — Create unified `Agent` class in `ai_tools/agent.py`

**This is the core step.** Rewrite `ai_tools/agent.py` to contain the unified `Agent` class.

**Source material to merge:**
- `LLMQuery.__init__()` — tools.py:92-216 — constructor args and state initialization
- `LLMQuery.query()` — tools.py:945-1176 — core query method
- `LLMQuery.get_tool_responses()` — tools.py:1345-1420 — tool execution loop
- `LLMAgent.run()` — agent.py:99-139 — agentic loop with tracing
- `LLMAgent.as_tool()` — agent.py:141-229 — tool wrapper
- `LLMQuery.clone()` — tools.py:234-257 — state isolation for sub-agent calls
- `LLMQuery._resolve_tools()` — tools.py:260-297 — tool schema normalization
- `LLMQuery._prepare_messages()` — tools.py:586-616 — message list builder
- `LLMQuery._prepare_request_kwargs()` — tools.py:618-730 — API payload builder
- `LLMQuery._resolve_overrides()` — tools.py:732-753 — per-call override merging
- `LLMQuery._create_chat_completion()` — tools.py:299-357 — retry-wrapped API call
- `LLMQuery._get_consistent_history()` — tools.py:544-584 — safe history slicing
- `LLMQuery._log_response()` — tools.py:861-903 — logging helper
- `LLMQuery._update_history()` — tools.py:905-943 — history append
- `LLMQuery.append_tool_result()` — tools.py:1213-1244 — tool result append
- `LLMQuery.inject_system_message()` — tools.py:1246-1266 — mid-conversation directive
- `LLMQuery.clear_history()` — tools.py:218-232 — reset state
- `LLMQuery.clean_chat_history` — tools.py:1302-1315 — filtered history property
- `LLMQuery.get_chat_history_as_string()` — tools.py:1275-1300 — string representation
- `LLMQuery.invoke()` — tools.py:1178-1211 — LangChain-compatible entry point
- `LLMQuery._run_async()` — tools.py:1321-1343 — async-from-sync helper

**What to EXCLUDE (deleted features per user decision):**
- `display_response()` — tools.py:1268-1273 — IPython display **(REMOVE)**
- `display_chat_history()` — tools.py:1317-1319 — IPython display **(REMOVE)**
- `__call__`, `__ror__`, `__or__` — tools.py:1505-1534 — pipeline operators **(REMOVE)**
- `LLMQuery.as_tool()` — tools.py:1422-1503 — duplicate **(REMOVE, keep only Agent version)**
- `AgentConfig` dataclass — agent.py:20-45 **(REMOVE, absorb into constructor)**

**New `Agent` constructor signature:**

```python
class Agent(MultiModalMixin):
    TOOL_NAME: str = ""
    TOOL_DESCRIPTION: str = ""

    def __init__(
        self,
        model: Optional[ModelName] = None,
        system_prompt: str = "",
        *,
        name: str = "",
        tools: Optional[List[ToolInput]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        functions: Optional[List[Callable]] = None,
        memory: Optional["MemoryHandler"] = None,
        user_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        # query behavior
        stream: bool = False,
        json_format: bool = False,
        reasoning_effort: Optional[str] = None,
        history_limit: Optional[int] = None,
        use_history: bool = True,
        response_format: Union[Dict[str, Any], Type[BaseModel], None] = None,
        concurrent_tool_calls: bool = True,
        # multimodal models
        image_model: Optional[str] = None,
        tts_model: Optional[str] = None,
        transcription_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
```

**Key architectural decisions for the Agent class:**

1. **State lives directly on Agent** — `self.chat_history`, `self.usage` (UsageTracker), `self.response`, `self.reasoning_history`, `self.tool_calls`
2. **`self.name`** defaults to `self.__class__.__name__` if not provided (so `RAGAgent()` auto-names itself "RAGAgent")
3. **`self.session_id`** is a `@property` — single source of truth: `self.memory.root_thread_id` if memory exists, else `self._session_id`
4. **Usage tracking** uses `self.usage = UsageTracker()` — replace all `self._usage_lock` and `self.total_*` fields
5. **Client factory** uses `get_client()` from `client.py` — replace `self._get_client_for_model()`
6. **Parsing** uses functions from `parsing.py` — replace `self._parse_xml_tool_calls()` etc.
7. **Provider prefix** uses `strip_provider_prefix()` from `config.py` — replace inline stripping in `_prepare_request_kwargs()`

**Key methods to implement:**

```python
def query(self, user_prompt=None, model=None, ..., **kwargs) -> str:
    """Single LLM call. Updates history. No tool loop."""
    # Merge from LLMQuery.query() (tools.py:945-1176)
    # Use self._resolve_tracing_context() instead of inline tracing setup
    # Use get_client() from client.py
    # Use extract_and_sanitize_tool_calls() from parsing.py
    # Use self.usage.update() instead of self._update_usage()
    ...

def run(self, message: str, use_history: bool = True, **kwargs) -> str:
    """Full agentic loop: query → tool calls → re-query → done.
    
    Automatically traced via trace_span.
    """
    # Merge from LLMAgent.run() (agent.py:99-139) and LLMQuery.get_tool_responses() (tools.py:1345-1420)
    # Wrap entire execution in self._trace_run_span(message)
    ...

@property
def session_id(self) -> Optional[str]:
    """Single source of truth for session identity."""
    if self.memory and hasattr(self.memory, "root_thread_id"):
        return self.memory.root_thread_id
    return self._session_id

@session_id.setter
def session_id(self, value: Optional[str]) -> None:
    self._session_id = value

def clone(self) -> "Agent":
    """Create a fresh run-state copy for isolated sub-agent execution."""
    # Adapted from LLMQuery.clone() (tools.py:234-257)
    # Reset: chat_history, tool_calls, response, reasoning_history, usage
    ...

def as_tool(self) -> Callable:
    """Expose this agent as a @tool-compatible callable.
    
    Thread-safe: clones the agent for each invocation.
    Propagates tracing context (session_id, user_id) via contextvars.
    Aggregates usage back to parent agent.
    """
    # Merge from LLMAgent.as_tool() (agent.py:141-229)
    # Use self.usage.aggregate_from(local_agent.usage) instead of manual lock
    ...

def _resolve_tracing_context(self, model: str) -> "_TracingContext":
    """Single method to resolve all tracing artifacts.
    
    Replaces the 40-line inline tracing setup from LLMQuery.query().
    """
    # Consolidate: session_id resolution, langfuse_params, openrouter trace dict
    ...

def get_tool_responses(self, max_iterations: int = 20) -> str:
    """Public tool loop handling iterative tool execution.
    
    Renamed from _get_tool_responses to get_tool_responses to permit
    the UI to properly poll tool execution.
    """
    # Adapted from LLMQuery.get_tool_responses() (tools.py:1345-1420)
    ...
```

**Memory integration points (CRITICAL to preserve):**
1. In `__init__`: Load history from memory if present (`self.chat_history = self.memory.load_history()`)
2. In `query()`: Save checkpoint after successful query (when no tool_calls pending) — tools.py:1139-1151
3. In `clone()`: Do NOT clone memory — sub-agent gets scoped handler via `as_tool()`
4. In `as_tool()._wrapper()`: Create scoped memory handler via `original_memory.create_scoped_handler(self.TOOL_NAME)` — agent.py:194-199
5. In `clear_history()`: Create new memory thread via `self.memory.new_thread()` — tools.py:227-228

**Tracing integration points (CRITICAL to preserve):**
1. In `query()`: Use `propagate_langfuse_attributes()` context manager around API call — tools.py:1100-1106
2. In `query()`: Pass `langfuse_params` to `_create_chat_completion()` — tools.py:1105
3. In `run()`: Wrap with `trace_span()` (replaces `trace_agent_run`) — agent.py:122-129
4. In `get_tool_responses()`: Use `propagate_langfuse_attributes()` — tools.py:1377-1380
5. In `as_tool()._wrapper()`: Propagate `session_id` and `user_id` from contextvars — agent.py:201-211

---

### Step 0.6 — Delete `ai_tools/tools.py`

After Step 0.5 is complete and tested, **delete** `ai_tools/tools.py` entirely. All its code has been absorbed into:
- `agent.py` — Agent class (state, orchestration, query, run)
- `client.py` — `get_client()`
- `parsing.py` — XML/token parsers
- `usage.py` — `UsageTracker`
- `config.py` — `strip_provider_prefix()`

---

### Step 0.7 — Delete `ai_tools/pipeline.py`

**Delete** `ai_tools/pipeline.py`. Pipeline syntax is removed per user decision.

---

### Step 0.8 — Update `ai_tools/__init__.py`

**Replace** the entire contents of `ai_tools/__init__.py`:

```python
from .agent import Agent, ToolInput
from .config import ModelName
from .utils import clean_json
from .tool_definition import tool, get_tool_schema
from .usage import UsageTracker
from .client import get_client
from .logger import setup_agent_logger
from .memory import MemoryHandler, InMemoryBackend, SQLiteBackend, SubagentMemoryMode
from .tracing import is_tracing_enabled, flush_tracing, trace_span

__all__ = [
    "Agent",
    "ToolInput",
    "ModelName",
    "clean_json",
    "tool",
    "get_tool_schema",
    "UsageTracker",
    "get_client",
    "setup_agent_logger",
    "MemoryHandler",
    "InMemoryBackend",
    "SQLiteBackend",
    "SubagentMemoryMode",
    "is_tracing_enabled",
    "flush_tracing",
    "trace_span",
]
```

**Key removals from exports:**
- `LLMQuery` → replaced by `Agent`
- `LLMAgent`, `AgentConfig` → absorbed into `Agent`
- `handle_tool_call`, `handle_tool_call_async` → internal (used by Agent, not public API)
- `pretty_print_json` → removed (IPython)
- `trace_turn` → removed (use `trace_span`)

---

### Step 0.9 — Update consumer agents

> **Current inheritance chain:** `APIAgent → BaseAgent → LLMAgent → (owns LLMQuery)`
> **Target inheritance chain:** `APIAgent → Agent`

All consumer agents follow the **same pattern**: they inherit `BaseAgent`, pass an `AgentConfig` to it, and `BaseAgent` injects a logger and default model before delegating to `LLMAgent`.

After this step, every agent inherits `Agent` directly, passes constructor kwargs, and the `BaseAgent` shim + `AgentConfig` dataclass are eliminated entirely.

---

#### 0.9.1 — Delete `agents/base_agent.py`

**Delete** this file entirely (25 lines). Its two responsibilities are absorbed:

| BaseAgent responsibility | Absorbed by |
|---|---|
| `config.logger = config.logger or setup_logger(config.name)` | Each agent passes `logger=setup_logger("Name")` directly |
| `config.model_name = config.model_name or settings.DEFAULT_MODEL` | Each agent passes `model=model_name or settings.SUB_AGENT_MODEL` directly |

---

#### 0.9.2 — Update `agents/__init__.py`

**Current** (5 lines):
```python
from .base_agent import BaseAgent
from .pokemon_agent import PokemonAgent

__all__ = ["BaseAgent", "PokemonAgent"]
```

**Target:**
```python
from .pokemon_agent import PokemonAgent

__all__ = ["PokemonAgent"]
```

---

#### 0.9.3 — Rewrite `agents/rag_agent.py`

**Current** (46 lines):
```python
from ai_tools.agent import AgentConfig                    # DELETE
from agents.base_agent import BaseAgent                   # DELETE
from tools.vector_db import TOOL_FUNCTIONS as RAG_TOOL_FUNCTIONS
from utils.config import settings

class RAGAgent(BaseAgent):                                # → Agent
    TOOL_NAME = "run_rag_agent"
    TOOL_DESCRIPTION = "..."

    def __init__(self, model_name=None):
        super().__init__(
            config=AgentConfig(                           # → flat kwargs
                name="RAGAgent",
                model_name=model_name or settings.SUB_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT_RAG_AGENT,
                tools=RAG_TOOL_FUNCTIONS,
                history_limit=20,
            )
        )
```

**Target:**
```python
from ai_tools.agent import Agent
from tools.vector_db import TOOL_FUNCTIONS as RAG_TOOL_FUNCTIONS
from utils.config import settings
from utils.logger import setup_logger

SYSTEM_PROMPT_RAG_AGENT = """..."""  # Keep existing prompt text unchanged


class RAGAgent(Agent):
    TOOL_NAME = "run_rag_agent"
    TOOL_DESCRIPTION = "..."  # Keep existing description text unchanged

    def __init__(self, model_name=None):
        super().__init__(
            name="RAGAgent",
            model=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_RAG_AGENT,
            tools=RAG_TOOL_FUNCTIONS,
            history_limit=20,
            logger=setup_logger("RAGAgent"),
        )
```

**Changes summary:**
- Import: `AgentConfig` → removed, `BaseAgent` → `Agent`
- Add: `from utils.logger import setup_logger`
- Class: `BaseAgent` → `Agent`
- Constructor: `config=AgentConfig(...)` → flat keyword args
- `model_name=` → `model=`
- Add: `logger=setup_logger("RAGAgent")`

---

#### 0.9.4 — Rewrite `agents/api_agent.py`

**Current** (70 lines):
```python
from ai_tools.agent import AgentConfig                    # DELETE
from agents.base_agent import BaseAgent                   # DELETE
from tools.api_client import TOOL_FUNCTIONS
from tools.fuzzy_search import TOOL_FUNCTIONS as FUZZY_FUNCTIONS
from utils.config import settings

class APIAgent(BaseAgent):                                # → Agent
    TOOL_NAME = "run_api_agent"
    TOOL_DESCRIPTION = "..."

    def __init__(self, model_name=None):
        super().__init__(
            config=AgentConfig(                           # → flat kwargs
                name="APIAgent",
                model_name=model_name or settings.SUB_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT_API_AGENT,
                tools=TOOL_FUNCTIONS + FUZZY_FUNCTIONS,
                history_limit=40,
            )
        )

    def run(self, message, use_history=False):             # DELETE
        return super().run(message, use_history=use_history)
```

**Target:**
```python
from typing import Optional
from ai_tools.agent import Agent
from tools.api_client import TOOL_FUNCTIONS
from tools.fuzzy_search import TOOL_FUNCTIONS as FUZZY_FUNCTIONS
from utils.config import settings
from utils.logger import setup_logger

SYSTEM_PROMPT_API_AGENT = """..."""  # Keep existing prompt text unchanged


class APIAgent(Agent):
    TOOL_NAME = "run_api_agent"
    TOOL_DESCRIPTION = "..."  # Keep existing description text unchanged

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(
            name="APIAgent",
            model=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_API_AGENT,
            tools=TOOL_FUNCTIONS + FUZZY_FUNCTIONS,
            history_limit=40,
            logger=setup_logger("APIAgent"),
        )
```

**Changes summary (vs. current):**
- Same pattern as RAGAgent
- **DELETE** the `run()` override entirely — it was a pass-through to `super().run()` with just `use_history=False`. If `use_history=False` is desired as default, this is a behavioral detail: `Agent.run()` defaults to `use_history=True`. If the API agent needs `use_history=False`, the user should pass it explicitly at call site, or we can override `run()` with a one-liner that flips the default. For now, **delete** it; sub-agents called via `as_tool()._wrapper()` always get a cloned agent with empty history anyway.

---

#### 0.9.5 — Rewrite `agents/tech_data_agent.py`

**Current** (146 lines):
```python
from ai_tools.agent import AgentConfig                    # DELETE
from agents.base_agent import BaseAgent                   # DELETE
from tools.tech_data_tools import TOOL_FUNCTIONS as TECH_DATA_FUNCTIONS
from tools.fuzzy_search import TOOL_FUNCTIONS as FUZZY_FUNCTIONS
from utils.config import settings

class TechDataAgent(BaseAgent):                           # → Agent
    TOOL_NAME = "run_tech_data_agent"
    TOOL_DESCRIPTION = "..."

    def __init__(self):
        super().__init__(
            config=AgentConfig(                           # → flat kwargs
                name="TechDataAgent",
                model_name=settings.SUB_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT,
                tools=TECH_DATA_FUNCTIONS + FUZZY_FUNCTIONS,
                history_limit=80,
            )
        )
```

**Target:**
```python
from ai_tools.agent import Agent
from tools.tech_data_tools import TOOL_FUNCTIONS as TECH_DATA_FUNCTIONS
from tools.fuzzy_search import TOOL_FUNCTIONS as FUZZY_FUNCTIONS
from utils.config import settings
from utils.logger import setup_logger

SYSTEM_PROMPT = """..."""  # Keep existing prompt text unchanged


class TechDataAgent(Agent):
    TOOL_NAME = "run_tech_data_agent"
    TOOL_DESCRIPTION = "..."  # Keep existing description text unchanged

    def __init__(self):
        super().__init__(
            name="TechDataAgent",
            model=settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT,
            tools=TECH_DATA_FUNCTIONS + FUZZY_FUNCTIONS,
            history_limit=80,
            logger=setup_logger("TechDataAgent"),
        )
```

---

#### 0.9.6 — Rewrite `agents/web_search_agent.py`

**Current** (211 lines — 132 lines of tool definitions + 79 lines of class):
```python
from ai_tools.agent import AgentConfig                    # DELETE
from ai_tools.tool_definition import tool                 # KEEP
from agents.base_agent import BaseAgent                   # DELETE
# ... tool imports and @tool definitions UNCHANGED ...

class WebSearchAgent(BaseAgent):                          # → Agent
    TOOL_NAME = "run_web_search_agent"
    TOOL_DESCRIPTION = "..."

    def __init__(self, model_name=None):
        super().__init__(
            config=AgentConfig(                           # → flat kwargs
                name="WebSearchAgent",
                model_name=model_name or settings.SUB_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT_WEB_SEARCH_AGENT,
                tools=[bulbapedia_search, bulbapedia_page_links, ...],
                history_limit=120,
            )
        )
```

**Target:**
```python
from typing import Optional
from pydantic import BaseModel, Field
from ai_tools.agent import Agent
from ai_tools.tool_definition import tool
from tools.web_search_brave_llm_context import (
    brave_llm_context_search, BraveLLMContextInput,
)
from tools.web_content import (
    extract_page_links, extract_structured_data,
    ExtractLinksInput, ExtractStructuredDataInput,
)
from tools.web_vector_db import (
    ingest_web_page, query_web_content,
    IngestWebPageArgs, QueryWebContentArgs,
)
from utils.config import settings
from utils.logger import setup_logger

# ... ALL @tool-decorated functions stay UNCHANGED ...
# bulbapedia_search, bulbapedia_page_links, bulbapedia_structured_data,
# bulbapedia_ingest_page, bulbapedia_query_content

SYSTEM_PROMPT_WEB_SEARCH_AGENT = """..."""  # Keep existing prompt unchanged


class WebSearchAgent(Agent):
    TOOL_NAME = "run_web_search_agent"
    TOOL_DESCRIPTION = "..."  # Keep existing description text unchanged

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(
            name="WebSearchAgent",
            model=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_WEB_SEARCH_AGENT,
            tools=[
                bulbapedia_search,
                bulbapedia_page_links,
                bulbapedia_structured_data,
                bulbapedia_ingest_page,
                bulbapedia_query_content,
            ],
            history_limit=120,
            logger=setup_logger("WebSearchAgent"),
        )
```

**Key point:** The 132 lines of Pydantic models + `@tool`-decorated functions at the top of the file are **unchanged**. Only the class header and constructor change.

---

#### 0.9.7 — Rewrite `agents/pokemon_agent.py`

This is the most complex agent. Besides the `AgentConfig` → flat kwargs change, it also has **property proxies** that must be deleted.

**Current property proxies to DELETE** (found in pokemon_agent.py):
```python
# These ALL go away — Agent has them directly:
@property
def chat_history(self): return self.llm.chat_history

@property  
def clean_chat_history(self): return self.llm.clean_chat_history

@property
def model(self): return self.llm.model

@property
def reasoning_history(self): return self.llm.reasoning_history

def query(self, message, **kwargs): return self.llm.query(message, **kwargs)
def get_tool_responses(self): return self.llm.get_tool_responses()
```

**Target:**
```python
from ai_tools.agent import Agent
from ai_tools.memory import MemoryHandler, SQLiteBackend
from agents.api_agent import APIAgent
from agents.rag_agent import RAGAgent
from agents.tech_data_agent import TechDataAgent
from agents.web_search_agent import WebSearchAgent
from utils.config import settings, PROJECT_ROOT
from utils.logger import setup_logger
import os

SYSTEM_PROMPT_POKEMON_AGENT = """..."""  # Keep existing prompt text unchanged


class PokemonAgent(Agent):
    """Main orchestrator agent (Professor Oak)."""

    def __init__(self, model_name=None, user_id=None):
        self._tech = TechDataAgent()
        self._rag = RAGAgent()
        self._api = APIAgent()
        self._web = WebSearchAgent()

        memory_dir = os.path.join(PROJECT_ROOT, "data", "memory")
        os.makedirs(memory_dir, exist_ok=True)

        super().__init__(
            name="PokemonAgent",
            model=model_name or settings.DEFAULT_MODEL,
            system_prompt=SYSTEM_PROMPT_POKEMON_AGENT,
            tools=[
                self._tech.as_tool(),
                self._rag.as_tool(),
                self._api.as_tool(),
                self._web.as_tool(),
            ],
            memory=MemoryHandler(
                backend=SQLiteBackend(os.path.join(memory_dir, "agent.db")),
                agent_name="PokemonAgent",
                user_id=user_id,
            ),
            user_id=user_id,
            history_limit=50,
            logger=setup_logger("PokemonAgent"),
        )

    def get_ui_state(self) -> dict:
        """Expose internal state for the UI."""
        return {
            "chat_history": self.chat_history,
            "tool_calls": self.tool_calls,
            "reasoning_history": self.reasoning_history,
            "tokens": self.usage.snapshot,
            "cost": self.usage.total_cost,
        }
```

**What changes for `PokemonAgent`:**
- Imports: `AgentConfig` → removed, `BaseAgent` → `Agent`
- Add: `from utils.logger import setup_logger`
- Class: `BaseAgent` → `Agent`
- Constructor: `AgentConfig` wrapping removed, flat kwargs
- `model_name=` arg → `model=`
- `get_ui_state()`: `self.llm.total_*` → `self.usage.snapshot` / `self.usage.total_cost`
- **DELETE**: All `@property` proxies and method proxies (`chat_history`, `clean_chat_history`, `model`, `reasoning_history`, `query()`, `get_tool_responses()`) — they now live on `Agent` directly

---

#### 0.9.8 — Verification

After updating all agents, run a quick import check:

```bash
uv run python -c "from agents.pokemon_agent import PokemonAgent; print('OK')"
uv run python -c "from agents.rag_agent import RAGAgent; print('OK')"
uv run python -c "from agents.api_agent import APIAgent; print('OK')"
uv run python -c "from agents.tech_data_agent import TechDataAgent; print('OK')"
uv run python -c "from agents.web_search_agent import WebSearchAgent; print('OK')"
```

Then run the full test suite:
```bash
uv run pytest ai_tools/tests/ -v
```

---

### Step 0.10 — Update `utils/ui_utils.py`

**Key changes:**
1. Replace all `client_state.llm.*` accesses with direct `client_state.*` accesses
2. Replace `trace_turn()` with `trace_span()` — or let `Agent.run()` handle tracing internally
3. Replace `client_state.llm.response` with `client_state.response`
4. Replace `client_state.llm.memory` with `client_state.memory`

**Specific replacements:**

| Before | After |
|---|---|
| `client_state.llm.chat_history` | `client_state.chat_history` |
| `client_state.llm.memory` | `client_state.memory` |
| `client_state.llm.memory.root_thread_id` | `client_state.session_id` |
| `client_state.llm.response` | `client_state.response` |
| `client_state.llm.tool_calls` | `client_state.tool_calls` |
| `client_state.llm.memory.list_threads()` | `client_state.memory.list_threads()` |
| `client_state.llm.memory.list_checkpoints()` | `client_state.memory.list_checkpoints()` |
| `client_state.llm.memory.switch_thread(id)` | `client_state.memory.switch_thread(id)` |
| `client_state.llm.memory.rollback(step)` | `client_state.memory.rollback(step)` |
| `client_state.llm.chat_history = ...` | `client_state.chat_history = ...` |
| `client_state.query(message)` + `client_state.get_tool_responses()` | `client_state.run(message)` |

**Tracing simplification** in `respond()`:
The current manual `trace_turn()` wrapper (ui_utils.py:137-191) can be simplified because `Agent.run()` handles its own tracing internally. However, the UI still needs the polling loop for streaming updates.

```python
# Before:
with trace_turn(name=..., user_id=..., session_id=..., ...) as span:
    client_state.query(message)
    # ... poll thread ...
    client_state.get_tool_responses()
    update_span(span, output=client_state.llm.response)

# After:
# Agent handles its own tracing via trace_span. The UI only calls flush_tracing() 
# in the final block.
# We retain the query() + get_tool_responses() polling structure in the UI for streaming!
```

**Decision:** Keep the existing `query()` + tool-response polling structure in the UI since `get_tool_responses()` remains a public method of `Agent`. Remove the manual `trace_turn` wrapping since `Agent.run()` or the internal logic handles it, or use `trace_span` correctly directly wrapping the polling loop.

**Also update:**
- `switch_thread()` — ui_utils.py:218-222: `client_state.memory.switch_thread(thread_id)` + `client_state.chat_history = client_state.memory.load_history()`
- `rollback_thread()` — ui_utils.py:225-229: same pattern

---

### Step 0.11 — Update `utils/config.py`

Check if `utils/config.py` references `LLMQuery` or `LLMAgent` anywhere. If so, update imports.

---

### Step 0.12 — Migrate all test files

> **CRITICAL:** Run tests after EACH file migration to catch breakage early.
> `uv run pytest ai_tools/tests/<file> -v`

#### 0.12.1 — `test_agent.py` (84 lines)

**Full rewrite required.** Currently tests `LLMAgent` + `AgentConfig` + `LLMQuery` delegation.

**Import changes:**
```python
# Before:
from ai_tools.agent import LLMAgent, AgentConfig
from ai_tools.tools import LLMQuery

# After:
from ai_tools.agent import Agent
```

**Test class changes:**
```python
# Before:
class DummyAgent(LLMAgent):
    TOOL_NAME = "dummy_agent"
    TOOL_DESCRIPTION = "A dummy agent for testing."

# After:
class DummyAgent(Agent):
    TOOL_NAME = "dummy_agent"
    TOOL_DESCRIPTION = "A dummy agent for testing."
```

**Test-by-test migration:**

| Test | Change |
|---|---|
| `test_llm_agent_initialization` | Replace `AgentConfig(name=..., model_name=...)` → `DummyAgent(name=..., model=...)`. Assert `agent.history_limit == 10` directly (not `agent.llm.history_limit`). Remove `isinstance(agent.llm, LLMQuery)` assertion. |
| `test_llm_agent_run_without_tools` | Replace `@patch.object(LLMQuery, ...)` → `@patch.object(Agent, ...)`. Remove `agent.llm.tool_calls = []` → `agent.tool_calls = []`. Replace `agent.llm.total_prompt_tokens` → `agent.usage.total_prompt_tokens`. |
| `test_llm_agent_run_with_tools` | Same pattern: patch `Agent.query` and `Agent.get_tool_responses` directly. Replace `agent.llm.tool_calls` → `agent.tool_calls`. |
| `test_llm_agent_as_tool` | Replace `AgentConfig(...)` → Agent constructor args. Keep schema assertions unchanged. |
| `test_llm_agent_as_tool_raises_value_error_if_no_name` | Replace `class InvalidAgent(LLMAgent)` → `class InvalidAgent(Agent)`. Replace `AgentConfig(...)` → Agent constructor args. |

---

#### 0.12.2 — `test_tools.py` (145 lines)

**Partial rewrite.** Pipeline tests deleted; initialization and history tests adapted.

**Import changes:**
```python
# Before:
from ai_tools.tools import LLMQuery
from ai_tools.pipeline import _Pipeline, _PipeableString

# After:
from ai_tools.agent import Agent
```

**Section-by-section:**

| Section | Action |
|---|---|
| `TestLLMQueryInitialization` → `TestAgentInitialization` | Replace `LLMQuery()` → `Agent()`. All attribute assertions stay the same (`.system_prompt`, `.model`, `.stream`, `.json_format`, `.chat_history`, `.tools`, `.functions`, `.history_limit`). |
| `TestPipelineSyntax` (3 tests) | **DELETE ENTIRELY** — pipeline syntax removed. |
| `TestHistoryManagement` (5 tests) | Replace `LLMQuery()` → `Agent()`. Method names stay the same (`_update_history`, `_prepare_messages`). No other changes needed. |

---

#### 0.12.3 — `test_concurrency.py` (123 lines)

**Full rewrite.** Tests thread safety of `as_tool()` for both old classes.

**Import changes:**
```python
# Before:
from ai_tools.tools import LLMQuery
from ai_tools.agent import LLMAgent, AgentConfig

# After:
from ai_tools.agent import Agent
```

**Test `test_llm_query_as_tool_concurrency`** → **DELETE** (LLMQuery.as_tool() removed).

**Test `test_llm_agent_as_tool_concurrency`** → **REWRITE** as `test_agent_as_tool_concurrency`:
- Replace `DummyAgent(config=AgentConfig(...))` → `DummyAgent(name="TestAgent", model="openai/gpt-4o-mini")`
- Replace `patch.object(LLMQuery, "_get_client_for_model", ...)` → `patch("ai_tools.client.get_client", ...)`
- Replace `patch.object(LLMQuery, "_create_chat_completion", ...)` → `patch.object(Agent, "_create_chat_completion", ...)`
- Replace `patch("ai_tools.agent.trace_agent_run", ...)` → `patch("ai_tools.tracing.trace_span", ...)`
- Replace `agent.llm.total_prompt_tokens` → `agent.usage.total_prompt_tokens` in assertions
- Replace `agent.llm.total_cost` → `agent.usage.total_cost`

---

#### 0.12.4 — `test_tracing.py` (304 lines)

**Significant changes.** Remove `trace_agent_run` tests; adapt remaining tests.

**Import changes:**
```python
# Before:
from ai_tools.tracing import trace_agent_run, ...
from ai_tools.tools import LLMQuery

# After:
from ai_tools.tracing import trace_span, ...
from ai_tools.agent import Agent
```

**Test-by-test:**

| Test | Action |
|---|---|
| `test_tracing_disabled_no_env_vars` | Keep unchanged |
| `test_tracing_disabled_no_package` | Keep unchanged |
| `test_tracing_enabled_with_env_vars` | Keep unchanged |
| `test_trace_agent_run_creates_span` | **REWRITE** → `test_trace_span_creates_span`. Use `trace_span()` instead of `trace_agent_run()`. |
| `test_trace_agent_run_nested` | **REWRITE** → `test_trace_span_nested`. Use `trace_span()`. |
| `test_trace_tool_execution_records_error` | Keep unchanged |
| `test_memory_handler_user_id_property` | Keep unchanged |
| `test_memory_handler_root_thread_id` | Keep unchanged |
| `test_scoped_handler_inherits_user_id` | Keep unchanged |
| `test_flush_tracing_calls_client_flush` | Keep unchanged |
| `test_get_current_trace_context_*` (3 tests) | Keep unchanged |
| `test_build_openrouter_trace_dict_*` (2 tests) | Keep unchanged |
| `test_trace_dict_injected_for_openrouter` | Replace `LLMQuery(model=...)` → `Agent(model=...)`. Replace `patch.object(q, "_create_chat_completion", ...)` → same but on Agent. |
| `test_trace_dict_not_injected_for_openai` | Same as above — `LLMQuery` → `Agent` |
| `test_checkpoint_stores_trace_id` | Replace `LLMQuery(model=..., memory=mem)` → `Agent(model=..., memory=mem)` |
| `test_sqlite_migration_idempotent` | Keep unchanged |

---

#### 0.12.5 — `test_tracing_safety.py` (75 lines)

**Import changes:**
```python
# Before:
from ai_tools.tools import LLMQuery

# After:
from ai_tools.agent import Agent
```

**Changes:**
- Replace `LLMQuery(model=..., memory=mock_memory)` → `Agent(model=..., memory=mock_memory)`
- Replace `patch.object(LLMQuery, ...)` → `patch.object(Agent, ...)`
- Replace `patch("ai_tools.tools.get_openai_class")` → `patch("ai_tools.client.get_openai_class")` (or `patch("ai_tools.tracing.get_openai_class")` depending on where it's called from)
- Replace `llm.user_id` → `agent.user_id` (same attr name, no functional change)

---

#### 0.12.6 — `test_dynamic_naming.py` (130 lines)

**Import changes:**
```python
# Before:
from ai_tools.tools import LLMQuery

# After:
from ai_tools.agent import Agent
```

**Changes:**
- Replace all `LLMQuery(model=..., agent_name=...)` → `Agent(model=..., name=...)`
- Replace `patch("ai_tools.tools.get_openai_class")` → `patch("ai_tools.tracing.get_openai_class")` (the function lives in tracing.py)
- The `agent_name` constructor parameter is now called `name` — update accordingly
- The test `test_naming_without_agent_name` should check that the generation name falls back to `self.name` which defaults to `Agent.__name__` → generation name should be `"generation:Agent"` (not `"generation:LLMQuery"`)

---

#### 0.12.7 — `test_history_consistency.py` (63 lines)

**Import changes:**
```python
# Before:
from ai_tools.tools import LLMQuery

# After:
from ai_tools.agent import Agent
```

**Changes:** Minimal — replace `LLMQuery(system_prompt=...)` → `Agent(system_prompt=...)`. All method calls (`_get_consistent_history`) stay the same.

---

#### 0.12.8 — `test_tool_definition.py` (522 lines)

**Mostly unchanged.** Most tests target `tool_definition.py` and `utils.py` which are not changing.

**Import changes:**
```python
# Before:
from ai_tools.tools import LLMQuery

# After:
from ai_tools.agent import Agent
```

**Section-by-section:**

| Section | Action |
|---|---|
| `TestFunctionToToolSchema` (8 tests) | Keep unchanged — tests `tool_definition.py` directly |
| `TestPydanticToToolSchema` (2 tests) | Keep unchanged |
| `TestToolDecorator` (6 tests) | Keep unchanged |
| `TestLLMQueryResolveTools` (8 tests) → `TestAgentResolveTools` | Replace `LLMQuery._resolve_tools(...)` → `Agent._resolve_tools(...)`. Same static method, same behavior. |
| `TestHandleToolCallPydantic` (4 tests) | Keep unchanged |
| `TestHandleToolCallAsyncPydantic` (2 tests) | Keep unchanged |
| `TestLLMQueryAsTool` (2 tests) | **DELETE** — `LLMQuery.as_tool()` no longer exists. Agent's `as_tool()` is tested in `test_agent.py`. |

---

#### 0.12.9 — `test_handle_tool_call.py` (no changes needed)

This file tests `handle_tool_call()` and `handle_tool_call_async()` from `utils.py` directly. These functions remain unchanged. **No modifications required.**

---

#### 0.12.10 — `test_memory.py` (no changes needed)

Tests the memory subsystem directly. **No modifications required.**

---

#### 0.12.11 — New: `ai_tools/tests/test_usage.py`

**Create** new test file for the extracted `UsageTracker`:

```python
"""Unit tests for ai_tools.usage.UsageTracker."""

import threading
from unittest.mock import MagicMock
from ai_tools.usage import UsageTracker


def test_initial_state():
    tracker = UsageTracker()
    assert tracker.total_tokens == 0
    assert tracker.total_cost == 0.0
    assert tracker.snapshot == {
        "prompt_tokens": 0, "completion_tokens": 0,
        "total_tokens": 0, "reasoning_tokens": 0, "cost": 0.0,
    }


def test_update_from_api_usage():
    tracker = UsageTracker()
    usage = MagicMock(
        prompt_tokens=10, completion_tokens=20, total_tokens=30,
        model_extra={"cost": 0.001}, completion_tokens_details=None,
    )
    tracker.update(usage)
    assert tracker.total_prompt_tokens == 10
    assert tracker.total_completion_tokens == 20
    assert tracker.total_tokens == 30
    assert tracker.total_cost == 0.001


def test_update_none_is_noop():
    tracker = UsageTracker()
    tracker.update(None)
    assert tracker.total_tokens == 0


def test_aggregate_from():
    parent = UsageTracker()
    child = UsageTracker()
    child.total_cost = 0.05
    child.total_tokens = 100
    child.total_prompt_tokens = 40
    child.total_completion_tokens = 60

    parent.aggregate_from(child)
    assert parent.total_cost == 0.05
    assert parent.total_tokens == 100


def test_reset():
    tracker = UsageTracker()
    tracker.total_cost = 1.0
    tracker.total_tokens = 500
    tracker.reset()
    assert tracker.total_cost == 0.0
    assert tracker.total_tokens == 0


def test_thread_safety():
    tracker = UsageTracker()
    usage = MagicMock(
        prompt_tokens=1, completion_tokens=1, total_tokens=2,
        model_extra={"cost": 0.0001}, completion_tokens_details=None,
    )

    def update_n_times(n):
        for _ in range(n):
            tracker.update(usage)

    threads = [threading.Thread(target=update_n_times, args=(100,)) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert tracker.total_tokens == 2000  # 10 threads * 100 updates * 2 tokens
```

---

#### 0.12.12 — New: `ai_tools/tests/test_parsing.py`

**Create** new test file for the extracted parsing module:

```python
"""Unit tests for ai_tools.parsing — XML/token tool-call parsers."""

from ai_tools.parsing import (
    parse_xml_tool_calls,
    sanitize_tool_id,
    extract_and_sanitize_tool_calls,
    extract_reasoning,
)


class TestParseXMLToolCalls:
    def test_standard_invoke(self):
        content = '<invoke name="get_weather">{"city": "Berlin"}</invoke>'
        calls = parse_xml_tool_calls(content, [])
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"

    def test_deepseek_functioninvoke(self):
        content = '<functioninvoke name="search"><parameter name="query">test</parameter></functioninvoke>'
        calls = parse_xml_tool_calls(content, [])
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "search"

    def test_token_based_format(self):
        content = 'to=functions.get_weather json<|message|>{"city": "Berlin"}'
        calls = parse_xml_tool_calls(content, [])
        assert len(calls) == 1

    def test_call_prefix_tags(self):
        content = '<call:get_weather>{"city": "Berlin"}</call:get_weather>'
        calls = parse_xml_tool_calls(content, [])
        assert len(calls) == 1

    def test_named_tags_with_known_functions(self):
        content = '<get_weather>{"city": "Berlin"}</get_weather>'
        calls = parse_xml_tool_calls(content, ["get_weather"])
        assert len(calls) == 1

    def test_empty_content(self):
        assert parse_xml_tool_calls("", []) == []

    def test_no_tool_calls_in_text(self):
        assert parse_xml_tool_calls("Hello, this is a normal response.", []) == []


class TestSanitizeToolId:
    def test_valid_id_unchanged(self):
        assert sanitize_tool_id("call_abc123") == "call_abc123"

    def test_invalid_chars_replaced(self):
        assert sanitize_tool_id("call.abc:123") == "call_abc_123"

    def test_none_generates_new_id(self):
        result = sanitize_tool_id(None)
        assert result.startswith("call_")

    def test_empty_generates_new_id(self):
        result = sanitize_tool_id("")
        assert result.startswith("call_")
```

---

**Verification checkpoint after all test migrations:**
```bash
uv run pytest ai_tools/tests/ -v
uv run pytest tests/ -v
```

---

## Phase 1: Tracing as the Skeleton

### Step 1.1 — Simplify `ai_tools/tracing.py`

**Delete these functions** (redundant wrappers):
- `trace_turn()` — tracing.py:195-227 — replaced by `trace_span` usage in Agent.run()
- `trace_agent_run()` — tracing.py:229-253 — same thing with different name

**Simplify `trace_span()`** — tracing.py:255-330:
The `is_nested` / `not is_nested` branches are nearly identical code. Collapse into a single branch:

```python
@contextmanager
def trace_span(name, ...):
    """Open a tracing span. Auto-detects nested vs. root context."""
    if not is_tracing_enabled():
        yield None
        return

    langfuse = _get_langfuse()
    parent = _active_span.get()
    
    if parent:
        span = parent.span(name=name, input=input_data, metadata=metadata)
    else:
        trace = langfuse.trace(
            name=name, user_id=user_id, session_id=session_id,
            tags=tags, metadata=metadata, input=input_data,
        )
        span = trace.span(name=name, input=input_data, metadata=metadata) if as_span else trace
    
    token = _active_span.set(span)
    try:
        yield span
    except Exception as e:
        update_span(span, level="ERROR", status_message=str(e))
        raise
    finally:
        if output_data:
            update_span(span, output=output_data)
        span.end()
        _active_span.reset(token)
```

**Keep these functions unchanged:**
- `is_tracing_enabled()`
- `flush_tracing()`
- `get_openai_class()`
- `get_langfuse_params()`
- `get_current_trace_context()`
- `build_openrouter_trace_dict()`
- `propagate_langfuse_attributes()`
- `update_span()`
- `trace_tool_execution()`
- `get_thread_session_id()`, `get_thread_user_id()`

### Step 1.2 — Update Agent tracing integration

Ensure `Agent.run()` wraps execution in `trace_span()`:

```python
def run(self, message, ...):
    with trace_span(
        name=f"agent:run:{self.name}",
        input_data=message,
        user_id=self.user_id,
        session_id=self.session_id,
        tags=[self.name, self._provider],
        metadata={"model": self.model},
    ) as span:
        response = self.query(message, ...)
        if self.tool_calls:
            response = self.get_tool_responses()
        update_span(span, output=response)
    return response
```

### Step 1.3 — Update `ui_utils.py` tracing

Remove the manual `trace_turn` usage. Instead, since `Agent.run()` handles its own tracing, the UI layer only needs `flush_tracing()` in its `finally` block.

If the UI still needs to wrap the entire interaction (including the polling loop) in a trace, use `trace_span` directly:

```python
from ai_tools.tracing import trace_span, flush_tracing, update_span
# Remove: from ai_tools import trace_turn
```

**Verification checkpoint:**
```bash
uv run pytest ai_tools/tests/ -v
```

---

## Phase 2: Internal Module Decomposition

### Step 2.1 — Update `ai_tools/multimodal.py`

Replace all inline prefix-stripping blocks with `strip_provider_prefix()`:

```python
from .config import strip_provider_prefix

# Before (4 occurrences):
api_model = model
for prefix in ["openai/", ...]:
    if model.startswith(prefix):
        api_model = model[len(prefix):]

# After:
_, api_model = strip_provider_prefix(model)
```

### Step 2.2 — Update `ai_tools/utils.py`

**Remove** the `from IPython.display import ...` import at the top of the file (if present).

**Remove** `pretty_print_json()` function entirely (IPython dependency removed).

**Keep** and update:
- `clean_json()` — still needed
- `handle_tool_call()` — still used internally by Agent
- `handle_tool_call_async()` — still used internally by Agent
- `generate_short_id()` — used by parsing.py
- `sanitize_tool_name()` — used by parsing.py

---

## Phase 3: DRY Tool Dispatch

### Step 3.1 — Unify `handle_tool_call` and `handle_tool_call_async`

**In `ai_tools/utils.py`**, extract shared preparation logic:

```python
@dataclass
class PreparedToolCall:
    tool_id: str
    function_name: str
    arguments: dict
    function_to_call: Callable
    pydantic_model: Optional[type]
    parse_error: Optional[str]

def _prepare_tool_dispatch(tool_call: dict, function_map: dict) -> PreparedToolCall:
    """Parse, validate, and resolve a tool call. Shared by sync/async paths."""
    # Extract from current handle_tool_call: argument parsing, function lookup,
    # pydantic model detection, error handling
    ...
```

Then `handle_tool_call()` and `handle_tool_call_async()` become thin execution wrappers.

**Verification:**
```bash
uv run pytest ai_tools/tests/test_handle_tool_call.py -v
```

---

## Phase 4: Documentation

### Step 4.1 — Rewrite `ai_tools/README.md`

- Replace all `LLMQuery` references with `Agent`
- Remove duplicated sections (Concurrent Tool Calls: lines 355-370, Override Resolution: lines 372-382, Side Effects: lines 384-394)
- Remove pipeline syntax documentation
- Remove IPython display documentation
- Add "Architecture" section with the layer diagram
- Update "Quick Start" examples
- Update "Tool Registration" examples
- Document `Agent.run()` vs `Agent.query()` distinction
- Document tracing lifecycle (automatic in `run()`, manual via `trace_span`)
- Document memory-tracing integration (session_id from memory)

### Step 4.2 — Update `ai_tools/memory/README.md`

Replace `LLMQuery` references with `Agent`.

### Step 4.3 — Update module docstrings

Update docstrings in all new/modified files:
- `agent.py` — module docstring for unified Agent
- `client.py` — module docstring
- `parsing.py` — module docstring
- `usage.py` — module docstring

---

## Final Verification

### Automated
```bash
# Unit tests
uv run pytest ai_tools/tests/ -v
uv run pytest tests/ -v

# Type checking (if configured)
uv run mypy ai_tools/ --ignore-missing-imports
```

### Manual
1. Start the Streamlit app and run a multi-turn query with tool calls
2. Check Langfuse dashboard: verify trace hierarchy (PokemonAgent → SubAgent → Tool → Generation)
3. Test memory: restart app, verify thread resumption works
4. Test thread switching and rollback from the UI

### Cleanup
```bash
# Ensure deleted files are gone
git status
# Verify no remaining references to LLMQuery, LLMAgent, AgentConfig, BaseAgent
grep -r "LLMQuery\|LLMAgent\|AgentConfig\|BaseAgent" ai_tools/ agents/ utils/ --include="*.py" -l
```

---

## File Impact Summary

| Action | File | Lines Before | Lines After (est.) |
|---|---|---|---|
| **NEW** | `ai_tools/usage.py` | — | ~95 |
| **NEW** | `ai_tools/client.py` | — | ~50 |
| **NEW** | `ai_tools/parsing.py` | — | ~200 |
| **REWRITE** | `ai_tools/agent.py` | 230 | ~900 |
| **DELETE** | `ai_tools/tools.py` | 1534 | 0 |
| **DELETE** | `ai_tools/pipeline.py` | 153 | 0 |
| **DELETE** | `agents/base_agent.py` | 25 | 0 |
| **MODIFY** | `ai_tools/config.py` | 123 | ~140 |
| **MODIFY** | `ai_tools/utils.py` | 383 | ~300 |
| **MODIFY** | `ai_tools/multimodal.py` | 335 | ~320 |
| **SIMPLIFY** | `ai_tools/tracing.py` | 474 | ~350 |
| **MODIFY** | `ai_tools/__init__.py` | 30 | ~30 |
| **REWRITE** | `agents/pokemon_agent.py` | 198 | ~70 |
| **REWRITE** | `agents/rag_agent.py` | 46 | ~25 |
| **REWRITE** | `agents/api_agent.py` | 70 | ~30 |
| **REWRITE** | `agents/tech_data_agent.py` | 146 | ~30 |
| **REWRITE** | `agents/web_search_agent.py` | 211 | ~145 |
| **MODIFY** | `utils/ui_utils.py` | 230 | ~200 |
| **MODIFY** | `ai_tools/README.md` | 540 | ~350 |
| **UPDATE** | All test files | ~500 | ~450 |
| | **Total** | **~5,228** | **~3,685** |

**Net reduction: ~1,500 lines** (~30% smaller codebase).
