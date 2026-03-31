"""
Public API exports for the ai_tools conversational memory subsystem.

This module exposes the user-facing interfaces for hooking up persistent conversational
memory into LLMQuery and agents. It exports the primary coordinator `MemoryHandler`,
the storage backend models (`InMemoryBackend`, `SQLiteBackend`), and the corresponding
dataclasses for type safety across the subsystem.
"""

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
