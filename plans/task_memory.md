# Memory Management — Requirements Specification

> **Status:** Draft v2 — Requirements only (implementation design in separate document)  
> **Last Updated:** 2026-03-31  
> **Scope:** `ai_tools` package (`LLMQuery`, `LLMAgent`, and new `Memory*` modules)

---

## 1. Goal

Provide a **pluggable, layered memory system** for the `ai_tools` library that:

1. Works transparently with both `LLMQuery` and `LLMAgent`.
2. Ships an **in-memory default** that requires zero configuration.
3. Allows opt-in to **persistent storage** (SQLite → PostgreSQL) per agent.
4. Supports **flexible composition** — e.g. a main agent persists to SQLite while its subagents use ephemeral in-memory storage.
5. Is designed with **future extensibility** in mind (semantic memory, knowledge graphs, RAG pipelines) without requiring breaking changes.

---

## 2. Memory Taxonomy

The system distinguishes **four conceptual memory types**, inspired by cognitive science and production agentic frameworks (CrewAI, LangGraph, Letta):

| Memory Type | Scope | Persistence | Purpose |
|---|---|---|---|
| **Short-Term (Working)** | Single conversation turn / tool-loop | In-memory (RAM) | Active context window — the messages currently fed to the LLM. Already exists via `chat_history`. |
| **Conversational (Episodic)** | Thread (multi-turn session) | Configurable (RAM / SQLite / PostgreSQL) | Full conversation history tied to a `thread_id`. Enables resume, rollback, branching. |
| **Long-Term (Semantic)** | Cross-thread, per-user or global | Database + vector store | Distilled facts, preferences, learned knowledge. Survives across threads. |
| **Procedural** | Global | Code / config | Encoded in system prompts, tool definitions, and agent logic. Not managed by the memory subsystem. |

### Phase 1 scope: Short-Term + Conversational  
### Phase 2 scope: Long-Term (Semantic)

---

## 3. Architectural Principles

### 3.1 Separation of Concerns

Memory management logic must live in **its own module(s)**, not inside `LLMQuery` or `LLMAgent`. These classes receive a memory handler via dependency injection.

### 3.2 Strategy Pattern

The memory backend must implement a common **abstract interface** (protocol / ABC). Concrete backends (in-memory, SQLite, PostgreSQL) are interchangeable behind this interface.

### 3.3 Non-Invasive Integration

- `LLMQuery` and `LLMAgent` continue to work **without any memory configuration** — they default to the existing in-memory `chat_history` behaviour.
- Memory is activated via an optional parameter (e.g. `memory=MemoryHandler(...)`) at construction time.

### 3.4 Composition over Inheritance

A main agent can use a persistent backend while its subagents (created via `as_tool()`) use ephemeral memory — or vice versa. The memory handler is per-instance, not global.

### 3.5 Thread Isolation

Conversations are identified by a `thread_id`. Different thread IDs maintain **fully isolated** state (analogous to LangGraph's thread model). Within a thread, history is sequential and ordered.

---

## 4. Conversational Memory — Detailed Requirements

### 4.1 Thread Management

| Requirement | Description |
|---|---|
| **R-TH-01** | Every conversation is identified by a unique `thread_id` (string). |
| **R-TH-02** | `thread_id` may be user-supplied or auto-generated (UUID). |
| **R-TH-03** | Switching `thread_id` on the same agent instance loads the corresponding history — **no** cross-thread bleed. |
| **R-TH-04** | A listing API must return all known `thread_id`s for a given agent, with metadata (creation time, last activity, message count). |

### 4.2 Persistence Backends

| Requirement | Description |
|---|---|
| **R-PB-01** | **InMemoryBackend** — default. Stores history in a Python list. Lost on process exit. |
| **R-PB-02** | **SQLiteBackend** — single-file, zero-config persistent storage via SQLAlchemy. |
| **R-PB-03** | **PostgresBackend** — production-grade, connection-pooled. Requires connection string. |
| **R-PB-04** | All backends implement the same abstract interface so new stores can be added without touching consumer code. |
| **R-PB-05** | Database schema must be auto-created on first use (migrations handled via SQLAlchemy). |

### 4.3 Checkpointing & State

| Requirement | Description |
|---|---|
| **R-CP-01** | Every `query()` / `run()` call produces a **checkpoint** — a snapshot of the full conversation state after that turn. |
| **R-CP-02** | Each checkpoint has a monotonically increasing `step_id` within its thread. |
| **R-CP-03** | Checkpoints store: messages (user, assistant, tool, system), tool call metadata, token usage, cost, timestamps. |
| **R-CP-04** | Checkpoints are persisted **after** a successful API response, not before. |

### 4.4 Resume & Rollback

| Requirement | Description |
|---|---|
| **R-RR-01** | An agent can **resume** a conversation by loading the latest checkpoint for a given `thread_id`. |
| **R-RR-02** | An agent can **rollback** to any previous `step_id` within a thread, discarding all subsequent checkpoints. |
| **R-RR-03** | An agent can **branch** from any checkpoint — creating a new `thread_id` that forks from a specific `step_id` of an existing thread (conversation branching). |
| **R-RR-04** | A **history browse** API allows listing all checkpoints for a thread with summary metadata. |

### 4.5 History Limits & Windowing

| Requirement | Description |
|---|---|
| **R-HL-01** | The existing `history_limit` parameter on `LLMQuery` / `AgentConfig` continues to work — it controls how many messages are sent to the LLM, not how many are persisted. |
| **R-HL-02** | Persisted history is unbounded unless the user configures a maximum checkpoint count per thread. |
| **R-HL-03** | When `history_limit` is active, the windowing logic (`_get_consistent_history`) must still start on a `user` message boundary and respect tool-call pairing rules. |

---

## 5. Subagent Memory Handling

### 5.1 Subagents Created via `as_tool()`

| Requirement | Description |
|---|---|
| **R-SA-01** | Subagent memory configuration is **independent** of the parent agent. |
| **R-SA-02** | By default, subagents created via `as_tool()` use ephemeral in-memory storage (history cleared per invocation, as currently implemented). |
| **R-SA-03** | If a subagent is configured with a persistent backend, it operates in 'Scoped' mode. Each tool invocation gets a fresh, isolated thread to prevent context bleed. (Note: True parent traceability linking to `parent_thread_id` requires context-aware tool routing and is deferred to Phase 2). |
| **R-SA-04** | A traceability record linking parent checkpoint → subagent thread must be stored so that a parent's conversation can be inspected alongside its delegated subagent work. *(Deferred to Phase 2)* |

### 5.2 Subagent Checkpointer Modes (inspired by LangGraph)

| Mode | Behaviour |
|---|---|
| **Ephemeral** (default) | History cleared per tool call. No persistence. Equivalent to current `clear_history()` in `as_tool()`. |
| **Scoped** | Each tool invocation gets a fresh, isolated thread within the persistent backend. Useful for auditing. |
| **Stateful** | Subagent maintains history across invocations within the parent's thread. Use with caution — can cause context bleed if not managed. |

---

## 6. Memory Handler Interface

The memory handler is the object injected into `LLMQuery` / `LLMAgent`. It must expose **at minimum** the following operations:

| Operation | Signature (conceptual) | Description |
|---|---|---|
| `save_checkpoint` | `(thread_id, step_id, state) → None` | Persist a conversation checkpoint. |
| `load_checkpoint` | `(thread_id, step_id=None) → State` | Load latest or specific checkpoint. Returns `None` if thread doesn't exist. |
| `list_threads` | `(filter?) → List[ThreadInfo]` | List all known threads with metadata. |
| `list_checkpoints` | `(thread_id) → List[CheckpointInfo]` | List all checkpoints in a thread. |
| `rollback` | `(thread_id, step_id) → None` | Delete all checkpoints after `step_id`. |
| `branch` | `(source_thread_id, step_id, new_thread_id) → None` | Fork a new thread from a checkpoint. |
| `delete_thread` | `(thread_id) → None` | Remove a thread and all its checkpoints. |
| `get_history` | `(thread_id, limit?) → List[Message]` | Return the message list for the LLM context. |

---

## 7. LLM-Enhanced Memory Management

An optional `LLMQuery` instance can be attached to the memory handler to provide intelligent memory operations. This LLM is **not** the primary agent — it is a fast, cheap model used strictly for memory housekeeping.

### 7.1 Conversation Condensation

| Requirement | Description |
|---|---|
| **R-LC-01** | When a thread's message count exceeds a configurable `condensation_threshold`, the memory LLM summarises older messages into a single condensed message. |
| **R-LC-02** | Condensation preserves: key decisions, facts, user preferences, and tool results. Drops: verbose reasoning, redundant greetings, failed tool attempts. |
| **R-LC-03** | The condensed summary replaces the original messages in the context window, but the full history remains in persistent storage (no data loss). |
| **R-LC-04** | Condensation runs **asynchronously** and does not block the primary agent's response. |

### 7.2 Fact Extraction (Future — Phase 2)

| Requirement | Description |
|---|---|
| **R-FE-01** | After each conversation turn, the memory LLM extracts discrete, atomic facts (inspired by CrewAI's `extract_memories`). |
| **R-FE-02** | Extracted facts are stored in the long-term semantic memory with metadata: source thread, timestamp, importance score, categories. |
| **R-FE-03** | Duplicate / contradicting facts are detected and consolidated (keep / update / delete — similar to CrewAI's consolidation model). |

---

## 8. Data Model — Conceptual Schema

### 8.1 Threads Table

| Column | Type | Description |
|---|---|---|
| `thread_id` | `TEXT PK` | Unique thread identifier. |
| `agent_name` | `TEXT` | Name of the owning agent. |
| `parent_thread_id` | `TEXT NULL` | If branched, the source thread. |
| `parent_step_id` | `INT NULL` | If branched, the fork point. |
| `user_id` | `TEXT NULL` | Optional user binding (future). |
| `created_at` | `DATETIME` | Thread creation timestamp. |
| `updated_at` | `DATETIME` | Last activity timestamp. |
| `metadata` | `JSON NULL` | Arbitrary key-value metadata. |

### 8.2 Checkpoints Table

| Column | Type | Description |
|---|---|---|
| `id` | `INT PK AUTOINCREMENT` | Internal row ID. |
| `thread_id` | `TEXT FK` | Owning thread. |
| `step_id` | `INT` | Monotonic step within thread (unique per thread). |
| `messages` | `JSON` | Full message list at this checkpoint. |
| `tool_calls` | `JSON NULL` | Tool call metadata for this step. |
| `usage` | `JSON NULL` | Token counts and cost snapshot. |
| `created_at` | `DATETIME` | Checkpoint timestamp. |

### 8.3 Facts Table (Phase 2)

| Column | Type | Description |
|---|---|---|
| `id` | `INT PK AUTOINCREMENT` | Internal row ID. |
| `content` | `TEXT` | The atomic fact. |
| `embedding` | `BLOB` | Vector embedding for semantic search. |
| `source_thread_id` | `TEXT` | Thread that produced this fact. |
| `importance` | `FLOAT` | 0.0–1.0 importance score. |
| `categories` | `JSON` | Categorical tags. |
| `scope` | `TEXT` | Hierarchical scope path (e.g. `/agent/researcher`). |
| `created_at` | `DATETIME` | Extraction timestamp. |
| `updated_at` | `DATETIME` | Last consolidation timestamp. |

---

## 9. Integration Points

### 9.1 With `LLMQuery`

- `LLMQuery.__init__()` accepts an optional `memory` parameter.
- If `memory` is provided:
  - `query()` calls `memory.save_checkpoint()` after each successful response.
  - `_prepare_messages()` calls `memory.get_history()` instead of reading `self.chat_history` directly.
  - `clear_history()` will optionally start a new thread (rather than destroying data).

### 9.2 With `LLMAgent`

- `AgentConfig` gains an optional `memory` field.
- `LLMAgent.__init__()` passes it through to the underlying `LLMQuery`.
- `as_tool()` respects the subagent memory mode (ephemeral / scoped / stateful).

### 9.3 With Chat Interface (Streamlit / Gradio)

- The chat interface must be able to:
  - List available threads and let the user select one to resume.
  - Display a thread's checkpoint history for rollback/branching.
  - Optionally associate threads with a user session / login (future).

---

## 10. Non-Functional Requirements

| Requirement | Description |
|---|---|
| **R-NF-01** | **Zero breaking changes** — existing code that does not use the memory parameter must behave identically. |
| **R-NF-02** | **Performance** — in-memory backend adds negligible overhead. SQLite backend must handle ≤50ms per checkpoint write. |
| **R-NF-03** | **Thread safety** — SQLite operations must use proper locking for concurrent access (e.g. WAL mode). |
| **R-NF-04** | **Testability** — all backends must be testable in isolation with unit tests. Integration tests only for database backends. |
| **R-NF-05** | **Observability** — memory operations emit structured log events via the existing `logger` system. |

---

## 11. Phased Roadmap

### Phase 1 — Conversational Memory (MVP)

- [ ] Abstract memory handler interface (protocol/ABC)
- [ ] InMemoryBackend implementation
- [ ] SQLiteBackend implementation (SQLAlchemy)
- [ ] Thread management (create, list, switch, delete)
- [ ] Checkpoint save/load
- [ ] Resume conversations via `thread_id`
- [ ] Rollback to previous checkpoint
- [ ] Integration with `LLMQuery` and `LLMAgent`
- [ ] Subagent memory modes (ephemeral, scoped)
- [ ] Unit tests for all backends

### Phase 2 — Intelligent Memory

- [ ] LLM-powered conversation condensation
- [ ] Conversation branching (fork from checkpoint)
- [ ] Fact extraction from conversations
- [ ] Semantic fact storage with embeddings
- [ ] Composite scoring for fact retrieval (semantic + recency + importance — inspired by CrewAI)
- [ ] Fact consolidation (deduplication, contradiction resolution)
- [ ] Scoped memory views (global / per-agent / per-user)
- [ ] Chat interface integration (thread picker, rollback UI)

### Phase 3 — Advanced & Production

- [ ] PostgresBackend with connection pooling
- [ ] Stateful subagent mode
- [ ] User ID / authentication binding
- [ ] Knowledge graph storage and retrieval
- [ ] RAG pipeline integration with long-term memory
- [ ] Memory import/export (JSON serialisation)
- [ ] Cross-agent memory sharing (shared facts between agents in a pipeline)
- [ ] Memory policies (auto-expiry, pinned facts, privacy flags)

---

## 12. Suggestions for Further Improvement

The following ideas emerged from analysing CrewAI, LangGraph, Letta, and Mem0 — they are **not committed requirements** but worth evaluating during design:

### 12.1 Scoped Memory Hierarchies (CrewAI pattern)
CrewAI organises memory into a **hierarchical scope tree** (e.g. `/agent/researcher/findings`, `/project/alpha/decisions`). This enables:
- Private agent memory that other agents cannot see.
- Shared team/project memory that multiple agents can read.
- Read-only slices for agents that should consume but not modify shared knowledge.

**Recommendation:** Design the `scope` field in the Facts table to support this from the start, even if the tree-navigation API comes later.

### 12.2 Composite Scoring for Retrieval (CrewAI pattern)
When recalling facts, rank results by a weighted formula:
```
score = semantic_weight × similarity + recency_weight × decay + importance_weight × importance
```
This prevents the retrieval from being dominated by any single signal and allows tuning per use-case (e.g. sprint retrospectives favour recency; architecture docs favour importance).

**Recommendation:** Make weights configurable on the memory handler.

### 12.3 Cross-Thread Store (LangGraph pattern)
LangGraph's `Store` provides a key-value namespace that is **shared across threads** — ideal for user preferences, learned facts, and persistent configuration. This is complementary to the per-thread checkpoint model.

**Recommendation:** Consider a lightweight key-value store alongside the fact table for simple preference/config storage that doesn't need vector search.

### 12.4 Source Tracking and Privacy (CrewAI pattern)
Tag memories with their origin (`source="user:alice"`, `source="agent:researcher"`) and support `private=True` flag so sensitive memories are only visible to the originating source.

**Recommendation:** Add `source` and `is_private` columns to the Facts table.

### 12.5 Non-Blocking Writes
CrewAI's `remember_many()` operates asynchronously — writes happen in a background thread, and `recall()` automatically waits for pending writes (read barrier). This prevents memory operations from blocking the agent's primary reasoning loop.

**Recommendation:** Implement async write with read-barrier semantics for the persistent backends.

### 12.6 Self-Managing Memory
Advanced systems (Letta, Mem0) give the agent **tools to manage its own memory** — explicit `save_fact`, `recall_facts`, `forget` tool calls rather than automatic extraction. This puts the agent in control of what it considers worth remembering.

**Recommendation:** Provide both modes — automatic extraction (via memory LLM) and explicit tool-based management — and let the user choose.

### 12.7 Memory-Aware System Prompts
Automatically inject relevant recalled facts into the system prompt before each query, so the agent has persistent knowledge without manual wiring.

**Recommendation:** The memory handler could expose a `get_context_injection(query) → str` method that returns relevant facts formatted for system prompt inclusion.

---

## 13. Open Questions

1. **Thread ID generation** — should the library auto-generate UUIDs, or require user-supplied IDs? (Recommendation: auto-generate by default, allow override.)
2. **Checkpoint granularity** — should tool-call intermediate steps also be checkpointed, or only final turn completions? (Recommendation: checkpoint after each complete turn including tool resolution.)
3. **Migration strategy** — how to handle schema evolution across library versions? (Recommendation: Alembic for SQLAlchemy-backed stores.)
4. **Memory LLM cost** — condensation and fact extraction cost money. Should there be a budget/rate-limit config? (Recommendation: yes, with sensible defaults.)
5. **Serialisation format** — should checkpoints store raw OpenAI message dicts, or a normalised internal format? (Recommendation: normalised internal format with conversion utilities, to decouple from provider-specific quirks.)