# Conversational Memory System

The `ai_tools.memory` package provides a robust, pluggable layer for tracking agent conversations, persisting threads, and resuming state seamlessly. It replaces the naive in-memory array tracking with a checkpoint-driven architecture that naturally supports subagents, rollbacks, and long-term storage.

---

## Core Concepts

1. **Threads:** Every conversation is isolated under a unique `thread_id` (usually a UUID4).
2. **Checkpoints:** Following every successful model inference, a snapshot (checkpoint) of the conversation state (including tool calls and tokens) is saved under an incrementing sequence number (`step_id`). 
3. **Subagent Scoping:** Natively integrated with `LLMQuery.as_tool`, meaning child agents are automatically granted a fresh, isolated `thread_id` that shares the same storage backend but does not pollute the parent agent's history.

---

## Quick Start

The system revolves around the `MemoryHandler`, which coordinates thread IDs, active steps, and the underlying storage protocol (`MemoryBackend`).

### 1. Persistent Setup (SQLite)

```python
from ai_tools.tools import LLMQuery
from ai_tools.memory import MemoryHandler, SQLiteBackend

# Create a MemoryHandler wrapping the SQLite backend
handler = MemoryHandler(
    backend=SQLiteBackend(db_path="conversations.db"),
    agent_name="MainAssistant"
)

# Inject into the LLMQuery or LLMAgent config
llm = LLMQuery(model="openai/gpt-4o-mini", memory=handler)

# Interact as normal
llm.query("Hello! I am Martin.")

# Retrieve the auto-generated thread ID for resumption later
active_thread = handler.thread_id
print(f"Saved to: {active_thread}")
```

### 2. Resuming a Thread

```python
# Create a handler and explicitly switch to a known thread
handler = MemoryHandler(backend=SQLiteBackend("conversations.db"))
handler.switch_thread(active_thread)

llm = LLMQuery(model="openai/gpt-4o-mini", memory=handler)

# The handler natively restores context via `handler.load_history()`
llm.query("What is my name?") 
# > "Your name is Martin."
```

---

## Storage Backends

| Backend | Description | Use Case |
|---|---|---|
| `InMemoryBackend` | Stores checkpoints purely in Python RAM (as dictionaries). Automatically discarded when the process exits. | Tests, ephemeral runs, or simple CLI utilities. (Default if backend omitted). |
| `SQLiteBackend` | Stores checkpoints as serialized JSON in a local SQLite file using SQLAlchemy. Configured with WAL mode and `check_same_thread=False` for concurrent environments. | CLI agents, chat UIs, or local daemons demanding durability. |

---

## Handler APIs

If you are building an orchestrator, you can directly interact with the handler rather than merely passing it to `LLMQuery`.

```python
# List all generated threads for a given user or system
all_threads = handler.list_threads()

# List every specific interaction step in a thread
checkpoints = handler.list_checkpoints()

# Revert memory context (e.g., if a tool crashes or hallucinations occur)
handler.rollback(step_id=2)  # Discard all checkpoints > 2

# Erase the memory entirely
handler.delete_thread("user_123_thread")
```

---

## Architecture details

All operations adhere to the `MemoryBackend` Protocol ABC. You can drop in any custom storage (e.g., PostgreSQL, Redis, or Mongo) by simply implementing the abstract methods defined in `base.py`. Under the hood, the backend receives a `ConversationState` dataclass containing the entire JSON-serializable snapshot. 
