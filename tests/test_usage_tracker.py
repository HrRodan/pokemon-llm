"""
Unit tests for the UsageTracker and AgentUsage classes.
"""

import threading
from utils.usage_tracker import UsageTracker, AgentUsage


class TestAgentUsage:
    """Tests for the AgentUsage dataclass."""

    def test_defaults(self) -> None:
        """All fields should default to zero."""
        u = AgentUsage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.reasoning_tokens == 0
        assert u.total_tokens == 0
        assert u.cost == 0.0
        assert u.call_count == 0

    def test_add(self) -> None:
        """add() should merge another AgentUsage in-place."""
        a = AgentUsage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.01,
            call_count=1,
        )
        b = AgentUsage(
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            cost=0.02,
            call_count=2,
        )
        a.add(b)
        assert a.prompt_tokens == 30
        assert a.completion_tokens == 15
        assert a.total_tokens == 45
        assert a.cost == 0.03
        assert a.call_count == 3


class TestUsageTracker:
    """Tests for the singleton UsageTracker."""

    def _fresh_tracker(self) -> UsageTracker:
        """Return the singleton after a reset, so tests are independent."""
        tracker = UsageTracker.get()
        tracker.reset()
        return tracker

    def test_singleton(self) -> None:
        """get() should always return the same instance."""
        a = UsageTracker.get()
        b = UsageTracker.get()
        assert a is b

    def test_record_and_get(self) -> None:
        """Recording usage for two agents should be retrievable individually and as totals."""
        tracker = self._fresh_tracker()
        tracker.record(
            "AgentA",
            AgentUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost=0.01,
                call_count=1,
            ),
        )
        tracker.record(
            "AgentB",
            AgentUsage(
                prompt_tokens=200,
                completion_tokens=80,
                total_tokens=280,
                cost=0.03,
                call_count=1,
            ),
        )
        # Second call for AgentA
        tracker.record(
            "AgentA",
            AgentUsage(
                prompt_tokens=50,
                completion_tokens=20,
                total_tokens=70,
                cost=0.005,
                call_count=1,
            ),
        )

        a_usage = tracker.get_agent_usage("AgentA")
        assert a_usage.prompt_tokens == 150
        assert a_usage.total_tokens == 220
        assert a_usage.call_count == 2

        b_usage = tracker.get_agent_usage("AgentB")
        assert b_usage.prompt_tokens == 200
        assert b_usage.call_count == 1

        totals = tracker.get_totals()
        assert totals.prompt_tokens == 350
        assert totals.total_tokens == 500
        assert totals.call_count == 3

    def test_get_unknown_agent(self) -> None:
        """Requesting an unknown agent should return zeroed AgentUsage."""
        tracker = self._fresh_tracker()
        u = tracker.get_agent_usage("NonExistent")
        assert u.prompt_tokens == 0
        assert u.call_count == 0

    def test_reset(self) -> None:
        """reset() should clear all recorded data."""
        tracker = self._fresh_tracker()
        tracker.record("X", AgentUsage(prompt_tokens=1, total_tokens=1, call_count=1))
        tracker.reset()
        assert tracker.get_totals().total_tokens == 0
        assert tracker.get_all() == {}

    def test_get_all_returns_copies(self) -> None:
        """Modifying returned dicts should not affect internal state."""
        tracker = self._fresh_tracker()
        tracker.record(
            "Agent", AgentUsage(prompt_tokens=10, total_tokens=10, call_count=1)
        )
        snapshot = tracker.get_all()
        snapshot["Agent"].prompt_tokens = 9999
        assert tracker.get_agent_usage("Agent").prompt_tokens == 10

    def test_thread_safety(self) -> None:
        """Concurrent writes from multiple threads should produce consistent totals."""
        tracker = self._fresh_tracker()
        iterations = 1000

        def writer(agent_name: str) -> None:
            for _ in range(iterations):
                tracker.record(
                    agent_name,
                    AgentUsage(prompt_tokens=1, total_tokens=1, call_count=1),
                )

        threads = [threading.Thread(target=writer, args=(f"T{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        totals = tracker.get_totals()
        assert totals.prompt_tokens == 5 * iterations
        assert totals.total_tokens == 5 * iterations
        assert totals.call_count == 5 * iterations
