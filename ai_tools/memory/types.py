"""
Dataclass schemas and type definitions across the memory subsystem.

Includes common abstractions for mapping agent states into discrete objects
that backends serialize and deserialize. Key constructs include `ConversationState`
(the payload generated at the end of an LLM turn), `Checkpoint` (an immutable step
snapshot), and enumeration flags like `SubagentMemoryMode`.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    """Complete state snapshot at a single checkpoint.

    This dataclass encapsulates the data that needs to be persisted at the end
    of each successful model interaction step.

    Attributes:
        messages: Full list of raw OpenAI-compatible message dictionaries.
        tool_calls: (Optional) List of any tool calls executed in this step.
        usage: (Optional) Snapshot of token usage (`prompt_tokens`, `completion_tokens`).
    """

    messages: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None


@dataclass
class Checkpoint:
    """A persisted conversation state at a specific step in time.

    Attributes:
        thread_id: The UUID mapping to the parent conversation thread.
        step_id: The sequence number for this checkpoint.
        state: The encapsulated actual content of the snapshot.
        created_at: Read-only timestamp of when this checkpoint was generated.
    """

    thread_id: str
    step_id: int
    state: ConversationState
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThreadInfo:
    """Metadata container describing a conversation thread.

    Attributes:
        thread_id: The unique identifier (usually UUID4).
        agent_name: Name of the agent running the thread.
        user_id: (Optional) The user ID associated with this thread.
        parent_thread_id: (Optional) The thread that invoked this thread, used for tracing.
        parent_step_id: (Optional) The exact step in the parent thread when invoked.
        message_count: Current number of messages inside the most recent checkpoint.
        created_at: Original creation timestamp.
        updated_at: Timestamp of the latest checkpoint push or change.
        metadata: User-defined arbitrary dictionary for extra context storage.
    """

    thread_id: str
    agent_name: str
    user_id: Optional[str] = None
    parent_thread_id: Optional[str] = None
    parent_step_id: Optional[int] = None
    message_count: int = 0
    initial_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CheckpointInfo:
    """Lightweight summary of a checkpoint (without the full message payload).

    Useful for populating UIs showing history steps or calculating rollback
    targets without loading massive payloads into memory.

    Attributes:
        thread_id: Thread ID.
        step_id: Sequence number.
        message_count: Total messages at this step snapshot.
        created_at: Timestamp when created.
    """

    thread_id: str
    step_id: int
    message_count: int
    created_at: datetime


class SubagentMemoryMode:
    """Enum-like constants for subagent checkpointer modes.

    Attributes:
        EPHEMERAL: Each invocation begins a new thread but relies on basic in-memory operation (dropped at exit).
        SCOPED: Each invocation spawns a persistent isolated child thread stored on the handler's backend.
    """

    EPHEMERAL = "ephemeral"
    SCOPED = "scoped"
