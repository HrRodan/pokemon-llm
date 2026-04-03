"""
Abstract base classes and protocols for the conversational memory storage backends.

This file defines the `MemoryBackend` interface, which dictates the strict protocol
any storage integration must follow to be used by a `MemoryHandler`. It covers
checkpoint saving, thread resumption, retrieving conversation histories,
checkpoint listing, and rollback features.
"""

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
        user_id: Optional[str] = None,
    ) -> None:
        """Persist a checkpoint. Creates the thread record if it doesn't exist."""

    @abstractmethod
    def load_checkpoint(
        self, thread_id: str, step_id: Optional[int] = None
    ) -> Optional[Checkpoint]:
        """Load a specific checkpoint, or the latest if step_id is None."""

    @abstractmethod
    def get_history(self, thread_id: str, limit: Optional[int] = None) -> List[dict]:
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
    def fork_thread(self, thread_id: str, step_id: int, new_thread_id: str) -> None:
        """Fork a thread at a specific step_id into a new thread."""

    @abstractmethod
    def delete_thread(self, thread_id: str) -> None:
        """Remove a thread and all its checkpoints."""

    @abstractmethod
    def thread_exists(self, thread_id: str) -> bool:
        """Check whether a thread exists."""
