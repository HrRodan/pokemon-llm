"""
User-facing MemoryHandler coordinator managing threads, checkpoints, and subagents.

The `MemoryHandler` acts as a stateful coordinator wrapping an underlying `MemoryBackend`.
It abstracts away explicit step tracking, managing the `thread_id` and `step_id`
internally during invocations. It seamlessly swaps context when navigating threads
and generates isolated scoped states for subagent invocations to prevent parent
conversation pollution.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any

from .base import MemoryBackend
from .in_memory import InMemoryBackend
from .types import (
    CheckpointInfo,
    ConversationState,
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
        return MemoryHandler._from_scoped_id(
            backend=self._backend,
            scoped_id=scoped_id,
            agent_name=subagent_name,
            logger=self._logger,
        )

    @classmethod
    def _from_scoped_id(
        cls,
        backend: MemoryBackend,
        scoped_id: str,
        agent_name: str,
        logger: Optional[logging.Logger],
    ) -> "MemoryHandler":
        """Internal factory that creates a scoped child without calling _new_thread()."""
        obj = object.__new__(cls)
        obj._backend = backend
        obj._agent_name = agent_name
        obj._logger = logger
        obj._thread_id = scoped_id
        obj._step_id = 0
        return obj
