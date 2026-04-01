"""
Persistent SQLite-backed conversational memory storage using SQLAlchemy.

The `SQLiteBackend` implementation maps the abstract `MemoryBackend` protocol onto
a raw SQLite database instance. It uses SQLAlchemy's declarative mappers to push
records to disk robustly, automatically initializing tables and utilizing `WAL`
mode for high-concurrency throughput (suitable for both synchronous scripts and
async HTTP agent servers).
"""

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
    """SQLite-backed persistent memory via SQLAlchemy.

    Stores conversations, threads, and complete usage/tool-call payloads
    long-term in a robust local SQLite file configured with WAL mode to
    withstand concurrent synchronous/async environment writes.

    Attributes:
        db_path (str): The local filesystem path to the sqlite `.db` file.
        logger (Optional[logging.Logger]): Logger instance for emitting SQL/connection debugs.
    """

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
            stmt = select(CheckpointModel).where(CheckpointModel.thread_id == thread_id)
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

    def get_history(self, thread_id: str, limit: Optional[int] = None) -> List[dict]:
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
            if thread:
                if latest:
                    thread.updated_at = latest.created_at
                    thread.message_count = (
                        len(latest.messages) if latest.messages else 0
                    )
                else:
                    thread.message_count = 0
            session.commit()

    def fork_thread(self, thread_id: str, step_id: int, new_thread_id: str) -> None:
        """Fork a given thread up to a step_id into a fully isolated persistent new thread.
        
        This retains all checkpoint history of the source thread and duplicates
        up to `step_id` to establish the new `new_thread_id` sequence.
        """
        now = datetime.now(timezone.utc)
        with Session(self._engine) as session:
            source_thread = session.get(ThreadModel, thread_id)
            if not source_thread:
                return

            stmt = (
                select(CheckpointModel)
                .where(
                    CheckpointModel.thread_id == thread_id,
                    CheckpointModel.step_id <= step_id,
                )
                .order_by(CheckpointModel.step_id.asc())
            )
            checkpoints = session.execute(stmt).scalars().all()
            message_count = len(checkpoints[-1].messages) if checkpoints else 0

            new_thread = ThreadModel(
                thread_id=new_thread_id,
                agent_name=source_thread.agent_name,
                parent_thread_id=thread_id,
                parent_step_id=step_id,
                created_at=now,
                updated_at=now,
                message_count=message_count,
            )
            session.add(new_thread)

            for cp in checkpoints:
                new_cp = CheckpointModel(
                    thread_id=new_thread_id,
                    step_id=cp.step_id,
                    messages=cp.messages,
                    tool_calls=cp.tool_calls,
                    usage=cp.usage,
                    created_at=cp.created_at,
                )
                session.add(new_cp)

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
