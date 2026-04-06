# Phase 1 — Conversational Memory: Implementation Plan

> **Parent:** [task_memory.md](task_memory.md)  
> **Status:** Draft — awaiting approval  
> **Last Updated:** 2026-03-31  
> **Scope:** Requirements R-TH-*, R-PB-01/02, R-CP-*, R-RR-01/02/04, R-HL-*, R-SA-01/02/03/04, R-NF-*

---

## 1. Summary

Implement a pluggable conversational memory subsystem for the `ai_tools` package.
After this phase, users can:

- **Persist** conversations to SQLite (or keep the zero-config in-memory default).
- **Resume** any conversation via a `thread_id`.
- **Rollback** to any prior checkpoint within a thread.
- **List** threads and checkpoints for a given agent.
- Use **subagent memory modes** (ephemeral, scoped) without code changes to existing consumers.

---

## 2. System Impact

### New Files

| File | Purpose |
|---|---|
| `ai_tools/memory/__init__.py` | Sub-package init; re-exports public API. |
| `ai_tools/memory/types.py` | Data classes: `Checkpoint`, `ThreadInfo`, `CheckpointInfo`, `ConversationState`. |
| `ai_tools/memory/base.py` | `MemoryBackend` — abstract base class (protocol) for all storage backends. |
| `ai_tools/memory/in_memory.py` | `InMemoryBackend` — RAM-only, dict-keyed-by-thread. |
| `ai_tools/memory/sqlite.py` | `SQLiteBackend` — SQLAlchemy + SQLite with WAL mode. |
| `ai_tools/memory/handler.py` | `MemoryHandler` — the user-facing coordinator injected into `LLMQuery` / `LLMAgent`. |
| `ai_tools/memory/models.py` | SQLAlchemy ORM models (`ThreadModel`, `CheckpointModel`). |
| `tests/test_memory_backend.py` | Unit tests for `InMemoryBackend` and `SQLiteBackend`. |
| `tests/test_memory_handler.py` | Unit tests for `MemoryHandler` coordination logic. |
| `tests/test_memory_integration.py` | Integration tests: `MemoryHandler` ↔ `LLMQuery` ↔ `LLMAgent`. |

### Modified Files

| File | Change Summary |
|---|---|
| `ai_tools/tools.py` | Add optional `memory` param to `__init__`, hook into `query()` / `_prepare_messages()` / `clear_history()` / `as_tool()`. |
| `ai_tools/agent.py` | Add `memory` to `AgentConfig`, pass through to `LLMQuery`, wire subagent modes in `as_tool()`. |
| `ai_tools/__init__.py` | Re-export `MemoryHandler`, `InMemoryBackend`, `SQLiteBackend`, `SubagentMemoryMode`. |
| `ai_tools/README.md` | Add Memory section documenting usage. |

### Dependencies

**No new dependencies.** SQLAlchemy (`>=2.0.45`) is already in `pyproject.toml`.

---

## 3. Detailed Design

### 3.1 Data Types — `ai_tools/memory/types.py`

All data classes use `dataclasses.dataclass` with full type hints. No Pydantic here — these are internal transport objects, not API schemas.

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    """Complete state snapshot at a single checkpoint."""
    messages: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None


@dataclass
class Checkpoint:
    """A persisted conversation state at a specific step."""
    thread_id: str
    step_id: int
    state: ConversationState
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThreadInfo:
    """Metadata about a conversation thread."""
    thread_id: str
    agent_name: str
    parent_thread_id: Optional[str] = None
    parent_step_id: Optional[int] = None
    message_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CheckpointInfo:
    """Lightweight summary of a checkpoint (without the full message list)."""
    thread_id: str
    step_id: int
    message_count: int
    created_at: datetime


class SubagentMemoryMode:
    """Enum-like constants for subagent checkpointer modes."""
    EPHEMERAL = "ephemeral"
    SCOPED = "scoped"
```

---

### 3.2 Abstract Backend — `ai_tools/memory/base.py`

Defines the contract every storage backend must implement. Uses Python's `abc.ABC` for enforceability.

```python
from abc import ABC, abstractmethod
from typing import List, Optional

from .types import Checkpoint, CheckpointInfo, ConversationState, ThreadInfo


class MemoryBackend(ABC):
    """Abstract interface for conversation memory storage."""

    @abstractmethod
    def save_checkpoint(
        self,
        thread_id: str,
        step_id: int,
        state: ConversationState,
        agent_name: str = "",
    ) -> None:
        """Persist a checkpoint. Creates the thread record if it doesn't exist."""

    @abstractmethod
    def load_checkpoint(
        self, thread_id: str, step_id: Optional[int] = None
    ) -> Optional[Checkpoint]:
        """Load a specific checkpoint, or the latest if step_id is None."""

    @abstractmethod
    def get_history(
        self, thread_id: str, limit: Optional[int] = None
    ) -> List[dict]:
        """Return the message list from the latest checkpoint of the thread."""

    @abstractmethod
    def list_threads(self, agent_name: Optional[str] = None) -> List[ThreadInfo]:
        """List all threads, optionally filtered by agent name."""

    @abstractmethod
    def list_checkpoints(self, thread_id: str) -> List[CheckpointInfo]:
        """List all checkpoints in a thread (step_id ascending)."""

    @abstractmethod
    def rollback(self, thread_id: str, step_id: int) -> None:
        """Delete all checkpoints AFTER the given step_id."""

    @abstractmethod
    def delete_thread(self, thread_id: str) -> None:
        """Remove a thread and all its checkpoints."""

    @abstractmethod
    def thread_exists(self, thread_id: str) -> bool:
        """Check whether a thread exists."""
```

> **Design Decision:** `branch()` is deferred to Phase 2 to keep Phase 1 scope minimal. The interface is ready for it (thread records already have `parent_thread_id` / `parent_step_id`), but the implementation and tests are Phase 2.

---

### 3.3 InMemoryBackend — `ai_tools/memory/in_memory.py`

A dict-of-lists implementation. Thread isolation is guaranteed by keying on `thread_id`.

**Key invariants:**
- `self._threads: Dict[str, ThreadInfo]`
- `self._checkpoints: Dict[str, List[Checkpoint]]` — list kept sorted by `step_id`.
- All operations are O(n) at worst (n = checkpoints per thread); acceptable for RAM-only usage.

```python
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .base import MemoryBackend
from .types import Checkpoint, CheckpointInfo, ConversationState, ThreadInfo


class InMemoryBackend(MemoryBackend):
    """RAM-only storage. Data lost on process exit."""

    def __init__(self) -> None:
        self._threads: Dict[str, ThreadInfo] = {}
        self._checkpoints: Dict[str, List[Checkpoint]] = {}

    def save_checkpoint(
        self,
        thread_id: str,
        step_id: int,
        state: ConversationState,
        agent_name: str = "",
    ) -> None:
        now = datetime.now(timezone.utc)
        if thread_id not in self._threads:
            self._threads[thread_id] = ThreadInfo(
                thread_id=thread_id,
                agent_name=agent_name,
                created_at=now,
                updated_at=now,
            )
            self._checkpoints[thread_id] = []

        cp = Checkpoint(
            thread_id=thread_id, step_id=step_id, state=state, created_at=now
        )
        self._checkpoints[thread_id].append(cp)

        info = self._threads[thread_id]
        info.updated_at = now
        info.message_count = len(state.messages)

    def load_checkpoint(
        self, thread_id: str, step_id: Optional[int] = None
    ) -> Optional[Checkpoint]:
        cps = self._checkpoints.get(thread_id)
        if not cps:
            return None
        if step_id is None:
            return cps[-1]
        for cp in cps:
            if cp.step_id == step_id:
                return cp
        return None

    def get_history(
        self, thread_id: str, limit: Optional[int] = None
    ) -> List[dict]:
        cp = self.load_checkpoint(thread_id)
        if cp is None:
            return []
        messages = cp.state.messages
        if limit is not None and limit > 0:
            return messages[-limit:]
        return list(messages)

    def list_threads(self, agent_name: Optional[str] = None) -> List[ThreadInfo]:
        threads = list(self._threads.values())
        if agent_name:
            threads = [t for t in threads if t.agent_name == agent_name]
        return sorted(threads, key=lambda t: t.updated_at, reverse=True)

    def list_checkpoints(self, thread_id: str) -> List[CheckpointInfo]:
        cps = self._checkpoints.get(thread_id, [])
        return [
            CheckpointInfo(
                thread_id=cp.thread_id,
                step_id=cp.step_id,
                message_count=len(cp.state.messages),
                created_at=cp.created_at,
            )
            for cp in cps
        ]

    def rollback(self, thread_id: str, step_id: int) -> None:
        cps = self._checkpoints.get(thread_id)
        if not cps:
            return
        self._checkpoints[thread_id] = [cp for cp in cps if cp.step_id <= step_id]
        remaining = self._checkpoints[thread_id]
        info = self._threads[thread_id]
        if remaining:
            info.updated_at = remaining[-1].created_at
            info.message_count = len(remaining[-1].state.messages)
        else:
            info.message_count = 0

    def delete_thread(self, thread_id: str) -> None:
        self._threads.pop(thread_id, None)
        self._checkpoints.pop(thread_id, None)

    def thread_exists(self, thread_id: str) -> bool:
        return thread_id in self._threads
```

---

### 3.4 SQLAlchemy ORM Models — `ai_tools/memory/models.py`

Uses SQLAlchemy 2.x declarative-mapped style. A `JSON` column stores messages as serialised dicts.

```python
from datetime import datetime, timezone
from sqlalchemy import (
    Column, DateTime, Integer, String, Text, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ThreadModel(Base):
    __tablename__ = "threads"

    thread_id = Column(String, primary_key=True)
    agent_name = Column(String, nullable=False, default="")
    parent_thread_id = Column(String, nullable=True)
    parent_step_id = Column(Integer, nullable=True)
    message_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    metadata_ = Column("metadata", JSON, nullable=True)

    checkpoints = relationship(
        "CheckpointModel",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="CheckpointModel.step_id",
    )


class CheckpointModel(Base):
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(
        String, ForeignKey("threads.thread_id", ondelete="CASCADE"), nullable=False
    )
    step_id = Column(Integer, nullable=False)
    messages = Column(JSON, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    usage = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    thread = relationship("ThreadModel", back_populates="checkpoints")

    __table_args__ = (
        UniqueConstraint("thread_id", "step_id", name="uq_thread_step"),
    )
```

---

### 3.5 SQLiteBackend — `ai_tools/memory/sqlite.py`

Implements `MemoryBackend` with SQLAlchemy sessions. Auto-creates tables on first use.

**Key design decisions:**
- Uses `StaticPool` + `check_same_thread=False` for thread-safe SQLite access.
- Enables WAL mode via `PRAGMA journal_mode=WAL` on connect (R-NF-03).
- Each public method uses a session-per-call pattern with `with Session(self._engine) as session`.

```python
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import create_engine, event, select, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from .base import MemoryBackend
from .models import Base, ThreadModel, CheckpointModel
from .types import Checkpoint, CheckpointInfo, ConversationState, ThreadInfo


class SQLiteBackend(MemoryBackend):
    """SQLite-backed persistent memory via SQLAlchemy."""

    def __init__(
        self,
        db_path: str = "memory.db",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger = logger
        url = f"sqlite:///{db_path}"
        self._engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self._engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self._engine)
        if self._logger:
            self._logger.info(f"SQLiteBackend initialized: {url}")

    def save_checkpoint(
        self,
        thread_id: str,
        step_id: int,
        state: ConversationState,
        agent_name: str = "",
    ) -> None:
        now = datetime.now(timezone.utc)
        with Session(self._engine) as session:
            thread = session.get(ThreadModel, thread_id)
            if thread is None:
                thread = ThreadModel(
                    thread_id=thread_id,
                    agent_name=agent_name,
                    created_at=now,
                    updated_at=now,
                    message_count=len(state.messages),
                )
                session.add(thread)
            else:
                thread.updated_at = now
                thread.message_count = len(state.messages)

            cp = CheckpointModel(
                thread_id=thread_id,
                step_id=step_id,
                messages=state.messages,
                tool_calls=state.tool_calls or None,
                usage=state.usage,
                created_at=now,
            )
            session.add(cp)
            session.commit()

    def load_checkpoint(
        self, thread_id: str, step_id: Optional[int] = None
    ) -> Optional[Checkpoint]:
        with Session(self._engine) as session:
            stmt = select(CheckpointModel).where(
                CheckpointModel.thread_id == thread_id
            )
            if step_id is not None:
                stmt = stmt.where(CheckpointModel.step_id == step_id)
            else:
                stmt = stmt.order_by(CheckpointModel.step_id.desc())

            row = session.execute(stmt).scalars().first()
            if row is None:
                return None

            return Checkpoint(
                thread_id=row.thread_id,
                step_id=row.step_id,
                state=ConversationState(
                    messages=row.messages,
                    tool_calls=row.tool_calls or [],
                    usage=row.usage,
                ),
                created_at=row.created_at,
            )

    def get_history(
        self, thread_id: str, limit: Optional[int] = None
    ) -> List[dict]:
        cp = self.load_checkpoint(thread_id)
        if cp is None:
            return []
        messages = cp.state.messages
        if limit is not None and limit > 0:
            return messages[-limit:]
        return list(messages)

    def list_threads(self, agent_name: Optional[str] = None) -> List[ThreadInfo]:
        with Session(self._engine) as session:
            stmt = select(ThreadModel)
            if agent_name:
                stmt = stmt.where(ThreadModel.agent_name == agent_name)
            stmt = stmt.order_by(ThreadModel.updated_at.desc())

            rows = session.execute(stmt).scalars().all()
            return [
                ThreadInfo(
                    thread_id=r.thread_id,
                    agent_name=r.agent_name,
                    parent_thread_id=r.parent_thread_id,
                    parent_step_id=r.parent_step_id,
                    message_count=r.message_count,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    metadata=r.metadata_,
                )
                for r in rows
            ]

    def list_checkpoints(self, thread_id: str) -> List[CheckpointInfo]:
        with Session(self._engine) as session:
            stmt = (
                select(CheckpointModel)
                .where(CheckpointModel.thread_id == thread_id)
                .order_by(CheckpointModel.step_id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [
                CheckpointInfo(
                    thread_id=r.thread_id,
                    step_id=r.step_id,
                    message_count=len(r.messages) if r.messages else 0,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def rollback(self, thread_id: str, step_id: int) -> None:
        with Session(self._engine) as session:
            stmt = delete(CheckpointModel).where(
                CheckpointModel.thread_id == thread_id,
                CheckpointModel.step_id > step_id,
            )
            session.execute(stmt)

            # Update thread metadata from the now-latest checkpoint
            latest = (
                session.execute(
                    select(CheckpointModel)
                    .where(CheckpointModel.thread_id == thread_id)
                    .order_by(CheckpointModel.step_id.desc())
                )
                .scalars()
                .first()
            )
            thread = session.get(ThreadModel, thread_id)
            if thread and latest:
                thread.updated_at = latest.created_at
                thread.message_count = (
                    len(latest.messages) if latest.messages else 0
                )
            session.commit()

    def delete_thread(self, thread_id: str) -> None:
        with Session(self._engine) as session:
            thread = session.get(ThreadModel, thread_id)
            if thread:
                session.delete(thread)  # cascades to checkpoints
                session.commit()

    def thread_exists(self, thread_id: str) -> bool:
        with Session(self._engine) as session:
            return session.get(ThreadModel, thread_id) is not None
```

---

### 3.6 MemoryHandler — `ai_tools/memory/handler.py`

The **user-facing coordinator** that `LLMQuery` and `LLMAgent` reference. It wraps a `MemoryBackend` and manages thread state.

**Responsibilities:**
1. Tracks the active `thread_id` and `step_id` counter.
2. Provides a `save()` / `load()` / `switch_thread()` API that the `LLMQuery` hooks call.
3. Generates `thread_id` automatically (UUID4) if none provided.
4. Logs all state transitions.

```python
import logging
import uuid
from typing import Dict, List, Optional, Any

from .base import MemoryBackend
from .in_memory import InMemoryBackend
from .types import (
    CheckpointInfo,
    ConversationState,
    SubagentMemoryMode,
    ThreadInfo,
)


class MemoryHandler:
    """User-facing coordinator for conversation memory.

    Wraps a ``MemoryBackend`` and manages active thread state.
    Injected into ``LLMQuery`` / ``LLMAgent`` via the ``memory`` parameter.

    Example::

        from ai_tools.memory import MemoryHandler, SQLiteBackend

        memory = MemoryHandler(backend=SQLiteBackend("agent.db"))
        llm = LLMQuery(model="gemini/gemini-flash-latest", memory=memory)

        # First conversation — thread auto-generated
        llm.query("Hello")
        thread_id = memory.thread_id  # save this for later

        # Resume later
        memory.switch_thread(thread_id)
        llm.query("What did I say before?")  # has full context
    """

    def __init__(
        self,
        backend: Optional[MemoryBackend] = None,
        thread_id: Optional[str] = None,
        agent_name: str = "",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._backend = backend or InMemoryBackend()
        self._agent_name = agent_name
        self._logger = logger
        self._thread_id: Optional[str] = None
        self._step_id: int = 0

        if thread_id:
            self.switch_thread(thread_id)
        else:
            self._new_thread()

    # -- Properties -----------------------------------------------------------

    @property
    def thread_id(self) -> str:
        """The active thread ID."""
        assert self._thread_id is not None
        return self._thread_id

    @property
    def step_id(self) -> int:
        """Current step counter (monotonically increasing within a thread)."""
        return self._step_id

    @property
    def backend(self) -> MemoryBackend:
        """The underlying storage backend."""
        return self._backend

    # -- Thread lifecycle -----------------------------------------------------

    def _new_thread(self) -> str:
        """Create a new thread with an auto-generated UUID."""
        self._thread_id = str(uuid.uuid4())
        self._step_id = 0
        if self._logger:
            self._logger.debug(f"💾 New memory thread: {self._thread_id}")
        return self._thread_id

    def switch_thread(self, thread_id: str) -> None:
        """Switch to an existing thread, loading its latest step_id.

        If the thread doesn't exist yet, it will be created on the first
        ``save_checkpoint()`` call.
        """
        self._thread_id = thread_id

        # Determine current step_id from the backend
        cp = self._backend.load_checkpoint(thread_id)
        self._step_id = cp.step_id if cp else 0

        if self._logger:
            self._logger.debug(
                f"💾 Switched to thread {thread_id} (step={self._step_id})"
            )

    def new_thread(self, thread_id: Optional[str] = None) -> str:
        """Start a fresh thread. Returns the new thread_id.

        Args:
            thread_id: Optional custom ID. If None, a UUID4 is generated.
        """
        if thread_id:
            self._thread_id = thread_id
            self._step_id = 0
        else:
            self._new_thread()
        return self.thread_id

    # -- Checkpoint operations ------------------------------------------------

    def save_checkpoint(
        self,
        messages: List[Dict[str, Any]],
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        usage: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Persist a checkpoint of the current conversation state.

        Increments ``step_id`` and writes to the backend.

        Returns:
            The step_id of the newly created checkpoint.
        """
        self._step_id += 1
        state = ConversationState(
            messages=list(messages),
            tool_calls=tool_calls or [],
            usage=usage,
        )
        self._backend.save_checkpoint(
            thread_id=self.thread_id,
            step_id=self._step_id,
            state=state,
            agent_name=self._agent_name,
        )
        if self._logger:
            self._logger.debug(
                f"💾 Checkpoint saved: thread={self.thread_id} "
                f"step={self._step_id} msgs={len(messages)}"
            )
        return self._step_id

    def load_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load the message history from the latest checkpoint.

        Args:
            limit: If set, return only the last N messages.

        Returns:
            List of message dicts (empty if thread has no checkpoints).
        """
        return self._backend.get_history(self.thread_id, limit=limit)

    # -- Query operations -----------------------------------------------------

    def list_threads(self) -> List[ThreadInfo]:
        """List all threads, filtered by this handler's agent_name if set."""
        name = self._agent_name if self._agent_name else None
        return self._backend.list_threads(agent_name=name)

    def list_checkpoints(self) -> List[CheckpointInfo]:
        """List all checkpoints in the active thread."""
        return self._backend.list_checkpoints(self.thread_id)

    # -- Rollback -------------------------------------------------------------

    def rollback(self, step_id: int) -> None:
        """Rollback the active thread to the given step_id.

        Deletes all checkpoints after ``step_id`` and resets the internal
        counter so the next save starts from ``step_id + 1``.
        """
        self._backend.rollback(self.thread_id, step_id)
        self._step_id = step_id
        if self._logger:
            self._logger.info(
                f"💾 Rolled back thread {self.thread_id} to step {step_id}"
            )

    # -- Deletion -------------------------------------------------------------

    def delete_thread(self, thread_id: Optional[str] = None) -> None:
        """Delete a thread and all its checkpoints.

        Args:
            thread_id: Thread to delete. Defaults to the active thread.
                If the active thread is deleted, a new thread is started.
        """
        target = thread_id or self.thread_id
        self._backend.delete_thread(target)
        if target == self._thread_id:
            self._new_thread()
        if self._logger:
            self._logger.info(f"💾 Deleted thread {target}")

    # -- Subagent helpers -----------------------------------------------------

    def create_scoped_handler(
        self, subagent_name: str
    ) -> "MemoryHandler":
        """Create a child MemoryHandler scoped for a subagent invocation.

        Generates a unique isolated thread ID for each invocation.
        (Note: Parent thread traceability is deferred to Phase 2).

        Returns:
            A new MemoryHandler with a unique scoped thread_id,
            sharing the same backend.
        """
        scoped_id = f"{subagent_name}::{uuid.uuid4().hex[:8]}"
        child = MemoryHandler(
            backend=self._backend,
            thread_id=None,
            agent_name=subagent_name,
            logger=self._logger,
        )
        child._thread_id = scoped_id
        child._step_id = 0
        return child
```

---

### 3.7 Sub-package Init — `ai_tools/memory/__init__.py`

```python
from .base import MemoryBackend
from .handler import MemoryHandler
from .in_memory import InMemoryBackend
from .sqlite import SQLiteBackend
from .types import (
    Checkpoint,
    CheckpointInfo,
    ConversationState,
    SubagentMemoryMode,
    ThreadInfo,
)

__all__ = [
    "MemoryBackend",
    "MemoryHandler",
    "InMemoryBackend",
    "SQLiteBackend",
    "Checkpoint",
    "CheckpointInfo",
    "ConversationState",
    "SubagentMemoryMode",
    "ThreadInfo",
]
```

---

## 4. Integration Changes

### 4.1 `LLMQuery.__init__()` — add `memory` parameter

[tools.py](tools.py) line 83–191.

Add an optional `memory: Optional[MemoryHandler] = None` parameter immediately after `logger`. Store as `self.memory`.

On init, if `memory` is set, load existing history into `self.chat_history`:

```python
self.memory = memory
if self.memory:
    self.chat_history = self.memory.load_history()
```

→ **Verify:** Existing code that does NOT pass `memory` behaves identically (R-NF-01).

---

### 4.2 `LLMQuery.query()` — save checkpoint after response

[tools.py](tools.py) line 876–1037.

After `_update_history()` completes (line ~1014), add:

```python
if self.memory:
    usage_snapshot = {
        "prompt_tokens": self.total_prompt_tokens,
        "completion_tokens": self.total_completion_tokens,
        "total_tokens": self.total_tokens,
        "cost": self.total_cost,
    }
    self.memory.save_checkpoint(
        messages=self.chat_history,
        tool_calls=self.tool_calls if self.tool_calls else None,
        usage=usage_snapshot,
    )
```

This executes **after** the successful API response (R-CP-04).

> **Checkpoint granularity decision:** Checkpoints are saved after each `query()` call, including intermediate tool-loop calls inside `get_tool_responses()`. This gives maximum rollback granularity. Each `query()` invocation increments `step_id` by 1.

---

### 4.3 `LLMQuery._prepare_messages()` — no change needed

The history is already in `self.chat_history` because:
- On init, `self.chat_history = self.memory.load_history()` seeds it.
- On each `query()` call, `_update_history()` appends to `self.chat_history` in-memory.
- Then `save_checkpoint()` persists the full list.

This avoids a fragile DB-read-per-query pattern and keeps `_prepare_messages()` / `_get_consistent_history()` completely unchanged — the existing windowing logic keeps working as-is (R-HL-01, R-HL-03).

---

### 4.4 `LLMQuery.clear_history()` — thread-aware reset

[tools.py](tools.py) line 193–205.

Modify to start a new thread when memory is present, instead of discarding data:

```python
def clear_history(self) -> None:
    if self.memory:
        self.memory.new_thread()
    self.chat_history = []
    self.tool_calls = []
    self.response = ""
    self.reasoning_history = []
```

---

### 4.5 `LLMQuery.as_tool()` — respect subagent memory mode

[tools.py](tools.py) line 1264–1327.

The `as_tool()` wrapper currently calls `clear_history()` on each invocation. With memory:

- **Ephemeral mode** (default): Same as current — `clear_history()` creates a new throwaway thread. No persistent checkpoints needed because the InMemoryBackend data is lost when clear_history resets the thread.
- **Scoped mode**: Create a scoped child handler per invocation so each call writes to its own isolated thread in the backend. This requires the `_wrapper` to call `self.memory.create_scoped_handler(name)` and temporarily swap the handler.

```python
def _wrapper(**kwargs) -> str:
    prompt = kwargs.get(input_arg, "")
    original_memory = llm_ref.memory
    
    if original_memory:
        # Scoped: each invocation gets its own thread for audit trail
        scoped = original_memory.create_scoped_handler(name)
        llm_ref.memory = scoped  # temporarily swap
        llm_ref.chat_history = []
    else:
        llm_ref.clear_history()
        
    llm_ref.query(prompt)
    result = llm_ref.get_tool_responses()
    
    if original_memory:
        llm_ref.memory = original_memory  # restore parent handler
        
    return result
```

> **Note:** `original_memory` is captured before the closure, not inside it.

---

### 4.6 `AgentConfig` + `LLMAgent` — pass-through

**`agent.py` changes:**

1. Add field to `AgentConfig`:
   ```python
   from ai_tools.memory import MemoryHandler
   memory: Optional[MemoryHandler] = None
   ```

2. Pass through in `LLMAgent.__init__()`:
   ```python
   self.llm = LLMQuery(
       ...,
       memory=config.memory,
   )
   ```

3. Update `LLMAgent.as_tool()` — the `_wrapper` closure now delegates to `LLMQuery.as_tool()` logic (which already handles memory modes). No additional agent-level changes needed because `self.llm` already owns the `memory` reference. The clear-history call on line 190 will invoke the memory-aware `LLMQuery.clear_history()`.

---

### 4.7 `__init__.py` — re-exports

Add to `ai_tools/__init__.py`:

```python
from .memory import MemoryHandler, InMemoryBackend, SQLiteBackend, SubagentMemoryMode
```

Add to `__all__`:

```python
"MemoryHandler",
"InMemoryBackend",
"SQLiteBackend",
"SubagentMemoryMode",
```

---

## 5. Test Plan

All tests in the `tests/` directory. Run with `uv run pytest tests/`.

### 5.1 `tests/test_memory_backend.py` — Backend Unit Tests

Both `InMemoryBackend` and `SQLiteBackend` share the same test suite via **parameterised fixtures**:

```python
@pytest.fixture(params=["in_memory", "sqlite"])
def backend(request, tmp_path):
    if request.param == "in_memory":
        return InMemoryBackend()
    else:
        return SQLiteBackend(db_path=str(tmp_path / "test.db"))
```

| Test Case | Covers |
|---|---|
| `test_save_and_load_checkpoint` | R-CP-01, R-CP-02, R-CP-03 |
| `test_load_latest_checkpoint` | Loads latest when `step_id=None` |
| `test_load_specific_checkpoint` | Loads checkpoint by exact `step_id` |
| `test_load_nonexistent_thread_returns_none` | Edge case |
| `test_get_history_returns_messages` | R-HL-01: returns message list |
| `test_get_history_with_limit` | R-HL-01: respects `limit` param |
| `test_get_history_empty_thread` | Edge case: returns `[]` |
| `test_list_threads` | R-TH-04: listing with metadata |
| `test_list_threads_filter_by_agent` | Filters by `agent_name` |
| `test_list_checkpoints` | R-RR-04: ordered by `step_id` |
| `test_rollback` | R-RR-02: deletes checkpoints after step |
| `test_rollback_preserves_target` | Target step_id checkpoint remains |
| `test_delete_thread` | Removes thread + all checkpoints |
| `test_thread_exists` | Boolean existence check |
| `test_thread_isolation` | R-TH-03: two threads don't interfere |
| `test_auto_create_schema` | R-PB-05: SQLite tables created on init |

### 5.2 `tests/test_memory_handler.py` — Handler Unit Tests

Uses `InMemoryBackend` (fast, no I/O).

| Test Case | Covers |
|---|---|
| `test_handler_auto_generates_thread_id` | R-TH-02 |
| `test_handler_custom_thread_id` | R-TH-02 |
| `test_handler_save_and_load` | Round-trip |
| `test_handler_step_id_increments` | R-CP-02 |
| `test_handler_switch_thread` | R-TH-03, R-RR-01 |
| `test_handler_switch_to_nonexistent_thread` | Creates on first save |
| `test_handler_rollback` | R-RR-02 |
| `test_handler_delete_active_thread` | Starts new thread after delete |
| `test_handler_list_threads` | R-TH-04 |
| `test_handler_list_checkpoints` | R-RR-04 |
| `test_handler_create_scoped_handler` | R-SA-03: scoped subagent thread |

### 5.3 `tests/test_memory_integration.py` — Integration Tests

Tests `MemoryHandler` wired into `LLMQuery` and `LLMAgent` with mocked LLM calls.

| Test Case | Covers |
|---|---|
| `test_llmquery_with_memory_saves_checkpoints` | R-CP-01, R-CP-04 |
| `test_llmquery_without_memory_unchanged` | R-NF-01 |
| `test_llmquery_memory_resumes_history` | R-RR-01 |
| `test_llmquery_clear_history_starts_new_thread` | `clear_history()` creates new thread |
| `test_llmagent_with_memory_passthrough` | Agent forwards `memory` to LLMQuery |
| `test_llmagent_as_tool_ephemeral` | R-SA-02: default clears history |
| `test_llmagent_as_tool_scoped` | R-SA-03: scoped thread per invocation |

---

## 6. Step-by-Step Execution Order

Each step has a **verification checkpoint**.

| # | Action | Verify |
|---|---|---|
| 1 | Create `ai_tools/memory/` package with `__init__.py` | Directory exists, importable |
| 2 | Implement `types.py` | `from ai_tools.memory.types import Checkpoint` works |
| 3 | Implement `base.py` (ABC) | `MemoryBackend` is abstract, cannot be instantiated |
| 4 | Implement `in_memory.py` | Unit tests pass: `uv run pytest tests/test_memory_backend.py -k in_memory` |
| 5 | Implement `models.py` (SQLAlchemy ORM) | Import succeeds, `Base.metadata` has 2 tables |
| 6 | Implement `sqlite.py` | Unit tests pass: `uv run pytest tests/test_memory_backend.py -k sqlite` |
| 7 | Implement `handler.py` | Unit tests pass: `uv run pytest tests/test_memory_handler.py` |
| 8 | Modify `tools.py` — add `memory` param + checkpoint hook | Existing tests still pass: `uv run pytest ai_tools/tests/` |
| 9 | Modify `agent.py` — add `memory` to config + pass-through | Existing agent tests pass |
| 10 | Write integration tests | `uv run pytest tests/test_memory_integration.py` |
| 11 | Update `__init__.py` re-exports | `from ai_tools import MemoryHandler` works |
| 12 | Update `README.md` — Memory section | Review for correctness |
| 13 | Full regression | `uv run pytest` — all tests green |

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Checkpoint on every `query()` inside tool loops creates many steps | Storage growth, slower rollback listing | Accept: fine-grained checkpoints are more useful than coarse. Can add `checkpoint_on_tool_loop=False` opt-out later if needed. |
| SQLite WAL mode + StaticPool may block under high-concurrency | Unlikely for single-agent dev usage | StaticPool serialises access. For true concurrency, users should use PostgresBackend (Phase 3). |
| Swapping `self.memory` in `as_tool()` is now thread-safe | Resolved by cloning the LLMQuery instance per invocation. | Thread-safe by design. |
| JSON serialisation of `messages` may lose non-serialisable data | Tool results containing PIL images / bytes | Already handled: `append_tool_result()` converts non-string outputs to `[Image created]` etc. |

---

## 8. Out of Scope (deferred to Phase 2+)

- `branch()` (conversation forking)
- LLM-powered condensation
- Fact extraction, semantic memory, vector embeddings
- PostgresBackend
- Stateful subagent mode
- User ID / authentication
- Chat interface UI integration
- Memory import/export