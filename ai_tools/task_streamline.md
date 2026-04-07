# Refactor `ai_tools` Package

## Goal

Unify `LLMQuery` and `LLMAgent` into a single `Agent` class.
Backward compatibility is not necessary.

## Guiding Principles

- Simplicity — one class, one mental model
- DRY — eliminate all duplication
- Tracing as the skeleton — every lifecycle event is observable
- Memory ↔ Tracing unification — session_id, threads, checkpoints all flow from one source
- Sub-agent composition — `as_tool()` is first-class, zero-boilerplate
- Extensibility — MCP servers, skill detection, new providers via dict entries

## Core Architectural Change

Merge LLMQuery (1534-line God Object) + LLMAgent (thin wrapper) → single `Agent` class.

### What This Eliminates
- `AgentConfig` pass-through dataclass (16 fields → direct constructor args)
- 70 lines of property proxying in PokemonAgent (`self.llm.chat_history` etc.)
- Duplicate `as_tool()` implementations
- 4 scattered `session_id` resolution points → 1 property
- 15 leaky `client_state.llm.*` accesses from UI layer
- `BaseAgent` intermediary class

### What This Creates
- `Agent` — the ONE primary abstraction (identity, tools, memory, tracing)
- `_LLMClient` — internal stateless call layer (provider routing, retries, parsing)
- `UsageTracker` — composable cost/token accumulator
- `parsing.py` — pure-function XML/token tool-call parsers
- `client.py` — pluggable provider factory

## Refactoring Phases

### Phase 0: Unify Agent and LLMQuery
- [ ] Merge LLMQuery state/orchestration into Agent
- [ ] Absorb AgentConfig fields as constructor args
- [ ] Simplify all consumer agents (PokemonAgent, RAGAgent, etc.)
- [ ] Delete BaseAgent — Agent IS the base

### Phase 1: Tracing as the Skeleton
- [ ] Build tracing into Agent lifecycle (run/query/tool call auto-traced)
- [ ] Single `session_id` property (memory.root_thread_id → _session_id fallback)
- [ ] Delete redundant `trace_turn`, `trace_agent_run` wrappers
- [ ] Simplify `trace_span` (identical nested/root branches collapsed)
- [ ] Memory checkpoints emit trace metadata

### Phase 2: Internal Module Decomposition
- [ ] Extract `client.py` — provider factory with `PROVIDER_URLS` dict
- [ ] Extract `parsing.py` — XML/token tool-call parsers
- [ ] Extract `usage.py` — `UsageTracker` class
- [ ] Add `strip_provider_prefix()` to config.py
- [ ] Make IPython a lazy import

### Phase 3: DRY Tool Dispatch
- [ ] Unify `handle_tool_call` / `handle_tool_call_async` (~100 lines saved)

### Phase 4: Documentation
- [ ] Remove 3 duplicated README sections
- [ ] Rewrite for unified Agent API
- [ ] Document tracing lifecycle + memory integration

## Critical Features to Preserve

### Memory Management
- Thread-based conversation persistence (SQLite / In-Memory backends)
- Thread switching and rollback (time travel)
- Subagent scoping via `create_scoped_handler()` 
- `root_thread_id` as the single source of `session_id` for tracing
- Memory checkpoint includes `trace_id` for cross-referencing with Langfuse

### Tracing via Langfuse
- Full hierarchy: Orchestrator → Sub-agent → Tool → Generation
- Session grouping via memory thread ID
- User attribution flowing through sub-agent calls
- Error visibility with span-level ERROR status
- Optional — zero overhead when env vars absent

### Sub-Agent Composition
- `Agent.as_tool()` returns `@tool`-compatible callable
- Each sub-agent invocation gets cloned state + scoped memory thread
- Usage aggregation flows back to parent agent
- Tracing context (session_id, user_id) auto-propagated via contextvars
- Thread-safe concurrent tool dispatch for I/O-bound sub-agents

## Future Extensibility

- **Skill Detection** — introspect `TOOL_NAME/TOOL_DESCRIPTION` for dynamic routing
- **MCP Server Access** — add `mcp/` provider prefix + tool injection
- **Streaming** — first-class lifecycle event on Agent
