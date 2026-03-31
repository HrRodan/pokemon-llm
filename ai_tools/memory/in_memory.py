"""
Ephemeral, RAM-only execution backend for conversational memory.

`InMemoryBackend` stores all `ThreadInfo` and `Checkpoint` states explicitly in
Python dictionaries. It requires zero configuration, enforces no disk I/O, and
operates purely during the runtime of the executing process. When the Python
process terminates, all stored conversation histories are discarded.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone

from .base import MemoryBackend
from .types import Checkpoint, CheckpointInfo, ConversationState, ThreadInfo


class InMemoryBackend(MemoryBackend):
    """RAM-only ephemeral storage backend.
    
    Automatically used by default if no persistence is required. All threads,
    checkpoints, and token snapshots are tracked in standard Python dictionaries.
    Data is lost upon process termination.
    """

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
