from datetime import datetime, timezone
from sqlalchemy import (
    Column, DateTime, Integer, String, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ThreadModel(Base):
    """SQLAlchemy ORM model representing a conversation thread.
    
    A thread groups a series of agent interaction checkpoints. It tracks metadata
    like the agent's name, parent tracing (for subagent scoping), message counts,
    and timestamps.
    """
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
    """SQLAlchemy ORM model for a conversation state checkpoint.
    
    A checkpoint represents a complete immutable snapshot of a conversation
    at a specific step. It stores the raw JSON of messages, raw tool call outputs,
    and token usage snapshots.
    """
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
