"""
Usage Tracker Module.

Provides a thread-safe, singleton registry of per-agent token usage and cost
statistics. Sub-agents are never reset during a session, so their LLMQuery
counters are already fully cumulative. This tracker simply stores the latest
snapshot from each agent; get_totals() sums them to produce session totals.
"""

import threading
from dataclasses import dataclass
from typing import Dict


@dataclass
class AgentUsage:
    """Holds cumulative usage metrics for a single agent."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    call_count: int = 0


class UsageTracker:
    """
    Global, thread-safe, singleton registry of per-agent usage statistics.

    Each agent reports its full cumulative totals via ``update()``; the tracker
    overwrites the previous snapshot.  ``get_totals()`` sums the latest
    snapshot from every agent to produce session-wide statistics.

    Usage::

        tracker = UsageTracker.get()
        tracker.update("RAGAgent", AgentUsage(prompt_tokens=120, ...))
        totals  = tracker.get_totals()
    """

    _instance: "UsageTracker | None" = None
    _lock_cls = threading.Lock()  # class-level lock for singleton creation

    def __init__(self) -> None:
        self._agents: Dict[str, AgentUsage] = {}
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "UsageTracker":
        """
        Return the singleton UsageTracker instance (created on first call).

        Returns:
            The global UsageTracker.
        """
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def update(self, agent_name: str, usage: AgentUsage) -> None:
        """
        Overwrite the stored usage snapshot for the given agent.

        Because sub-agents live for the entire session, ``usage`` should be
        the agent's **full cumulative totals**, not a per-call delta.

        Args:
            agent_name: Identifier of the agent (e.g. ``"RAGAgent"``).
            usage: The current cumulative usage to store.
        """
        with self._lock:
            self._agents[agent_name] = AgentUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                total_tokens=usage.total_tokens,
                cost=usage.cost,
                call_count=usage.call_count,
            )

    def get_agent_usage(self, agent_name: str) -> AgentUsage:
        """
        Return the latest usage snapshot for a specific agent.

        Args:
            agent_name: Identifier of the agent.

        Returns:
            A copy of the agent's usage, or a zeroed AgentUsage if unknown.
        """
        with self._lock:
            usage = self._agents.get(agent_name)
            return AgentUsage() if usage is None else AgentUsage(**usage.__dict__)

    def get_all(self) -> Dict[str, AgentUsage]:
        """
        Return a snapshot of usage for every agent that has reported.

        Returns:
            Dict mapping agent names to copies of their AgentUsage.
        """
        with self._lock:
            return {name: AgentUsage(**u.__dict__) for name, u in self._agents.items()}

    def get_totals(self) -> AgentUsage:
        """
        Return the sum of the latest usage snapshots across all agents.

        Returns:
            An AgentUsage whose fields are the sum of every registered agent.
        """
        with self._lock:
            totals = AgentUsage(
                prompt_tokens=sum(u.prompt_tokens for u in self._agents.values()),
                completion_tokens=sum(
                    u.completion_tokens for u in self._agents.values()
                ),
                reasoning_tokens=sum(u.reasoning_tokens for u in self._agents.values()),
                total_tokens=sum(u.total_tokens for u in self._agents.values()),
                cost=sum(u.cost for u in self._agents.values()),
                call_count=sum(u.call_count for u in self._agents.values()),
            )
        return totals

    def reset(self) -> None:
        """Clear all recorded usage data."""
        with self._lock:
            self._agents.clear()
