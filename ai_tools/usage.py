"""Thread-safe token and cost tracker for LLM usage."""

import threading
from typing import Any, Optional


class UsageTracker:
    """Accumulates token counts and cost across multiple LLM calls.

    Thread-safe: uses a lock for all mutations, safe for concurrent tool dispatch.

    Example::
        tracker = UsageTracker()
        tracker.update(api_response.usage)
        print(tracker.total_cost)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_cost: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_reasoning_tokens: int = 0
        self.total_tokens: int = 0
        self.last_usage: Optional[dict] = None

    def update(self, usage: Any) -> None:
        """Accumulate token counts and cost from an API usage object.

        Handles two cost locations:
        - ``usage.model_extra["cost"]`` — OpenRouter injects cost here.
        - ``usage["cost"]`` — fallback for dict-shaped usage objects.

        Handles two reasoning-token locations:
        - ``usage.completion_tokens_details`` as dict or object attribute.
        """
        if not usage:
            return

        with self._lock:
            # Handle both object attributes and dictionary keys safely
            if isinstance(usage, dict):
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                self.total_tokens += usage.get("total_tokens", 0)
                self.total_cost += usage.get("cost", 0.0)
                
                details = usage.get("completion_tokens_details")
                if isinstance(details, dict):
                    self.total_reasoning_tokens += details.get("reasoning_tokens", 0)
            else:
                self.total_prompt_tokens += getattr(usage, "prompt_tokens", 0)
                self.total_completion_tokens += getattr(usage, "completion_tokens", 0)
                self.total_tokens += getattr(usage, "total_tokens", 0)
                
                model_extra = getattr(usage, "model_extra", None)
                if model_extra:
                    self.total_cost += model_extra.get("cost", 0.0)
                elif hasattr(usage, "cost"):
                    self.total_cost += getattr(usage, "cost", 0.0)

                details = getattr(usage, "completion_tokens_details", None)
                if details:
                    if isinstance(details, dict):
                        self.total_reasoning_tokens += details.get("reasoning_tokens", 0)
                    elif hasattr(details, "reasoning_tokens"):
                        self.total_reasoning_tokens += details.reasoning_tokens

            # Store snapshot of this specific update as last_usage
            if isinstance(usage, dict):
                self.last_usage = usage
            else:
                # Basic conversion for object-style usage
                self.last_usage = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage, "completion_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                }

    def aggregate_from(self, other: "UsageTracker") -> None:
        """Merge another tracker's totals into this one. Thread-safe."""
        with self._lock:
            self.total_cost += other.total_cost
            self.total_prompt_tokens += other.total_prompt_tokens
            self.total_completion_tokens += other.total_completion_tokens
            self.total_reasoning_tokens += other.total_reasoning_tokens
            self.total_tokens += other.total_tokens

    def reset(self) -> None:
        """Zero all counters. Does NOT reset the lock."""
        with self._lock:
            self.total_cost = 0.0
            self.total_prompt_tokens = 0
            self.total_completion_tokens = 0
            self.total_reasoning_tokens = 0
            self.total_tokens = 0

    @property
    def snapshot(self) -> dict:
        """Return a dict snapshot of current usage."""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.total_reasoning_tokens,
            "cost": self.total_cost,
        }
