"""
Unit tests for handle_tool_call and handle_tool_call_async.

All tool functions are simple stubs — no live API keys required.
Tests cover:
  - Sync handle_tool_call still works unchanged
  - Async handle_tool_call_async runs concurrently
  - Error isolation: one failing tool doesn't block others
  - Result ordering matches input order
  - Graceful handling of bad JSON args, unknown functions, and execution errors
"""

import asyncio
import json
import time
import threading
from ai_tools.utils import handle_tool_call, handle_tool_call_async


# ---------------------------------------------------------------------------
# Stub tool functions
# ---------------------------------------------------------------------------


def add(a: int, b: int) -> int:
    """Simple arithmetic tool."""
    return a + b


def greet(name: str) -> str:
    """Simple greeting tool."""
    return f"Hello, {name}!"


def slow_tool(delay: float = 0.3) -> str:
    """Simulates an I/O-bound tool that takes some time."""
    time.sleep(delay)
    return f"done after {delay}s"


def failing_tool() -> str:
    """Always raises."""
    raise RuntimeError("Something went wrong inside the tool")


FUNCTIONS = [add, greet, slow_tool, failing_tool]


def _make_tool_call(name: str, arguments: dict, call_id: str = "call_1"):
    """Helper to build a tool-call dict."""
    return {
        "id": call_id,
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }


# ---------------------------------------------------------------------------
# Synchronous handle_tool_call tests
# ---------------------------------------------------------------------------


class TestHandleToolCallSync:
    """Verify existing synchronous dispatch still works correctly."""

    def test_single_tool_call(self):
        calls = [_make_tool_call("add", {"a": 2, "b": 3})]
        results = handle_tool_call(calls, FUNCTIONS)
        assert len(results) == 1
        assert results[0]["output"] == 5
        assert results[0]["name"] == "add"

    def test_multiple_tool_calls(self):
        calls = [
            _make_tool_call("add", {"a": 1, "b": 2}, "c1"),
            _make_tool_call("greet", {"name": "Ash"}, "c2"),
        ]
        results = handle_tool_call(calls, FUNCTIONS)
        assert len(results) == 2
        assert results[0]["output"] == 3
        assert results[1]["output"] == "Hello, Ash!"

    def test_unknown_function_returns_error(self):
        calls = [_make_tool_call("nonexistent", {}, "c1")]
        results = handle_tool_call(calls, FUNCTIONS)
        assert "Error" in results[0]["output"]
        assert "nonexistent" in results[0]["output"]

    def test_bad_json_returns_error(self):
        calls = [{"id": "c1", "function": {"name": "add", "arguments": "{bad json"}}]
        results = handle_tool_call(calls, FUNCTIONS)
        assert "Error" in results[0]["output"]

    def test_execution_error_returns_error(self):
        calls = [_make_tool_call("failing_tool", {}, "c1")]
        results = handle_tool_call(calls, FUNCTIONS)
        assert "Error" in results[0]["output"]
        assert "Something went wrong" in results[0]["output"]


# ---------------------------------------------------------------------------
# Async handle_tool_call_async tests
# ---------------------------------------------------------------------------


class TestHandleToolCallAsync:
    """Test the concurrent async dispatch."""

    def test_single_tool_call_async(self):
        calls = [_make_tool_call("add", {"a": 10, "b": 20})]
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        assert len(results) == 1
        assert results[0]["output"] == 30

    def test_result_order_preserved(self):
        """Results come back in the same order as the input tool calls."""
        calls = [
            _make_tool_call("greet", {"name": "A"}, "c1"),
            _make_tool_call("add", {"a": 1, "b": 2}, "c2"),
            _make_tool_call("greet", {"name": "B"}, "c3"),
        ]
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        assert results[0]["output"] == "Hello, A!"
        assert results[1]["output"] == 3
        assert results[2]["output"] == "Hello, B!"
        assert [r["tool_call_id"] for r in results] == ["c1", "c2", "c3"]

    def test_concurrent_execution_is_faster(self):
        """Three 0.3s calls should complete in ~0.3s total, not ~0.9s."""
        calls = [
            _make_tool_call("slow_tool", {"delay": 0.3}, f"c{i}") for i in range(3)
        ]
        start = time.monotonic()
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        elapsed = time.monotonic() - start

        assert len(results) == 3
        # If sequential, would take ~0.9s. With concurrency, should be ~0.3s.
        # Use 0.7s as a safe upper bound to avoid flakiness.
        assert elapsed < 0.7, f"Expected concurrent execution, but took {elapsed:.2f}s"

    def test_error_isolation(self):
        """One failing tool doesn't prevent others from completing."""
        calls = [
            _make_tool_call("add", {"a": 1, "b": 2}, "c1"),
            _make_tool_call("failing_tool", {}, "c2"),
            _make_tool_call("greet", {"name": "Oak"}, "c3"),
        ]
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        assert results[0]["output"] == 3
        assert "Error" in results[1]["output"]
        assert results[2]["output"] == "Hello, Oak!"

    def test_unknown_function_async(self):
        calls = [_make_tool_call("does_not_exist", {}, "c1")]
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        assert "Error" in results[0]["output"]
        assert "does_not_exist" in results[0]["output"]

    def test_bad_json_async(self):
        calls = [{"id": "c1", "function": {"name": "add", "arguments": "not json"}}]
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        assert "Error" in results[0]["output"]

    def test_dict_arguments_work(self):
        """When arguments are already a dict (e.g. from XML fallback), it still works."""
        calls = [
            {
                "id": "c1",
                "function": {"name": "greet", "arguments": {"name": "Misty"}},
            }
        ]
        results = asyncio.run(handle_tool_call_async(calls, FUNCTIONS))
        assert results[0]["output"] == "Hello, Misty!"

    def test_runs_in_threads(self):
        """Verify tool functions actually run in separate threads."""
        thread_ids = []

        def record_thread(**kwargs):
            thread_ids.append(threading.current_thread().ident)
            return "ok"

        record_thread.__name__ = "record_thread"

        calls = [
            _make_tool_call("record_thread", {}, "c1"),
            _make_tool_call("record_thread", {}, "c2"),
        ]
        asyncio.run(handle_tool_call_async(calls, [record_thread]))

        # Both calls ran in threads different from the main thread
        main_thread = threading.current_thread().ident
        assert all(tid != main_thread for tid in thread_ids)
