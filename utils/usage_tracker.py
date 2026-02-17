"""
Usage Tracker Module.

Provides a thread-safe, singleton registry that accumulates per-agent
token usage and cost statistics. Designed to survive sub-agent
creation/destruction cycles so the Gradio UI can always display
accurate cumulative statistics.
"""

import threading
from dataclasses import dataclass
from typing import Dict


@dataclass
class AgentUsage:
    """Holds accumulated usage metrics for a single agent."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    call_count: int = 0

    def add(self, other: "AgentUsage") -> None:
        """
        Add another AgentUsage's values to this one (in-place).

        Args:
            other: The AgentUsage delta to merge in.
        """
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.total_tokens += other.total_tokens
        self.cost += other.cost
        self.call_count += other.call_count


class UsageTracker:
    """
    Global, thread-safe, singleton registry of per-agent usage statistics.

    Usage::

        tracker = UsageTracker.get()
        tracker.record("RAGAgent", AgentUsage(prompt_tokens=120, ...))
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

    def record(self, agent_name: str, delta: AgentUsage) -> None:
        """
        Record a usage delta for the given agent.

        Args:
            agent_name: Identifier of the agent (e.g. ``"RAGAgent"``).
            delta: The incremental usage to add.
        """
        with self._lock:
            if agent_name not in self._agents:
                self._agents[agent_name] = AgentUsage()
            self._agents[agent_name].add(delta)

    def get_agent_usage(self, agent_name: str) -> AgentUsage:
        """
        Return accumulated usage for a specific agent.

        Args:
            agent_name: Identifier of the agent.

        Returns:
            A copy of the agent's usage, or a zeroed AgentUsage if unknown.
        """
        with self._lock:
            usage = self._agents.get(agent_name)
            if usage is None:
                return AgentUsage()
            # Return a copy so callers can't mutate internal state
            return AgentUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                total_tokens=usage.total_tokens,
                cost=usage.cost,
                call_count=usage.call_count,
            )

    def get_all(self) -> Dict[str, AgentUsage]:
        """
        Return a snapshot of usage for every agent that has reported.

        Returns:
            Dict mapping agent names to copies of their AgentUsage.
        """
        with self._lock:
            return {
                name: AgentUsage(
                    prompt_tokens=u.prompt_tokens,
                    completion_tokens=u.completion_tokens,
                    reasoning_tokens=u.reasoning_tokens,
                    total_tokens=u.total_tokens,
                    cost=u.cost,
                    call_count=u.call_count,
                )
                for name, u in self._agents.items()
            }

    def get_totals(self) -> AgentUsage:
        """
        Return the sum of usage across all agents.

        Returns:
            An AgentUsage whose fields are the sum of all registered agents.
        """
        totals = AgentUsage()
        with self._lock:
            for u in self._agents.values():
                totals.add(u)
        return totals

    def reset(self) -> None:
        """Clear all recorded usage data."""
        with self._lock:
            self._agents.clear()
