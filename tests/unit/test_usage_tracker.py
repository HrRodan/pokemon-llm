"""
Unit tests for utils.usage_tracker.
Moved from tests/ root into tests/unit/ for consistent layout.
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

    def test_custom_values(self) -> None:
        """Fields should store the values given at construction."""
        u = AgentUsage(
            prompt_tokens=10,
            completion_tokens=5,
            reasoning_tokens=2,
            total_tokens=15,
            cost=0.01,
            call_count=1,
        )
        assert u.prompt_tokens == 10
        assert u.completion_tokens == 5
        assert u.reasoning_tokens == 2
        assert u.total_tokens == 15
        assert u.cost == 0.01
        assert u.call_count == 1


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

    def test_update_and_get(self) -> None:
        """Updating usage for two agents should be retrievable individually and as totals."""
        tracker = self._fresh_tracker()
        tracker.update(
            "AgentA",
            AgentUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost=0.01,
                call_count=1,
            ),
        )
        tracker.update(
            "AgentB",
            AgentUsage(
                prompt_tokens=200,
                completion_tokens=80,
                total_tokens=280,
                cost=0.03,
                call_count=1,
            ),
        )

        a_usage = tracker.get_agent_usage("AgentA")
        assert a_usage.prompt_tokens == 100
        assert a_usage.total_tokens == 150
        assert a_usage.call_count == 1

        b_usage = tracker.get_agent_usage("AgentB")
        assert b_usage.prompt_tokens == 200
        assert b_usage.call_count == 1

        totals = tracker.get_totals()
        assert totals.prompt_tokens == 300
        assert totals.total_tokens == 430
        assert totals.call_count == 2

    def test_update_overwrites_previous_snapshot(self) -> None:
        """A second update() for the same agent should overwrite, not accumulate."""
        tracker = self._fresh_tracker()
        tracker.update(
            "AgentA",
            AgentUsage(prompt_tokens=100, total_tokens=100, call_count=1),
        )
        # Overwrite with new cumulative snapshot
        tracker.update(
            "AgentA",
            AgentUsage(prompt_tokens=150, total_tokens=220, call_count=2),
        )

        a_usage = tracker.get_agent_usage("AgentA")
        assert a_usage.prompt_tokens == 150  # overwritten, not 250
        assert a_usage.total_tokens == 220
        assert a_usage.call_count == 2

    def test_get_unknown_agent(self) -> None:
        """Requesting an unknown agent should return zeroed AgentUsage."""
        tracker = self._fresh_tracker()
        u = tracker.get_agent_usage("NonExistent")
        assert u.prompt_tokens == 0
        assert u.call_count == 0

    def test_reset(self) -> None:
        """reset() should clear all recorded data."""
        tracker = self._fresh_tracker()
        tracker.update("X", AgentUsage(prompt_tokens=1, total_tokens=1, call_count=1))
        tracker.reset()
        assert tracker.get_totals().total_tokens == 0
        assert tracker.get_all() == {}

    def test_get_all_returns_copies(self) -> None:
        """Modifying returned dicts should not affect internal state."""
        tracker = self._fresh_tracker()
        tracker.update(
            "Agent", AgentUsage(prompt_tokens=10, total_tokens=10, call_count=1)
        )
        snapshot = tracker.get_all()
        snapshot["Agent"].prompt_tokens = 9999
        assert tracker.get_agent_usage("Agent").prompt_tokens == 10

    def test_thread_safety(self) -> None:
        """Concurrent writes from multiple threads should not raise or corrupt state."""
        tracker = self._fresh_tracker()
        iterations = 1000

        def writer(agent_name: str) -> None:
            for i in range(iterations):
                # update() overwrites — each call sets the cumulative total
                tracker.update(
                    agent_name,
                    AgentUsage(
                        prompt_tokens=i + 1, total_tokens=i + 1, call_count=i + 1
                    ),
                )

        threads = [threading.Thread(target=writer, args=(f"T{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each agent should have its final snapshot (iterations)
        for i in range(5):
            usage = tracker.get_agent_usage(f"T{i}")
            assert usage.prompt_tokens == iterations
            assert usage.total_tokens == iterations
            assert usage.call_count == iterations

        totals = tracker.get_totals()
        assert totals.prompt_tokens == 5 * iterations
        assert totals.total_tokens == 5 * iterations
        assert totals.call_count == 5 * iterations
