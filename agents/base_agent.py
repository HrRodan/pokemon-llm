from typing import Optional, List, Dict, cast
from abc import ABC, abstractmethod
from ai_tools.tools import LLMQuery, ModelName
from utils.logger import setup_logger
from utils.config import settings
from utils.usage_tracker import UsageTracker, AgentUsage


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Provides common functionality for logging, LLM client initialization,
    configuration, and **usage tracking**.  Any subclass that calls
    ``self._collect_usage()`` at the end of its ``response()`` method
    will automatically have its token / cost metrics recorded in the
    global :class:`UsageTracker`.
    """

    def __init__(self, name: str, model_name: Optional[str] = None) -> None:
        """
        Initialize the agent.

        Args:
            name: The name of the agent (used for logging and usage tracking).
            model_name: The LLM model to use. Defaults to ``settings.DEFAULT_MODEL``.
        """
        self.name = name
        self.logger = setup_logger(name)
        self.model_name = model_name or settings.DEFAULT_MODEL

        # Initialize LLM Client
        # We use LLMQuery as the interface to the LLM
        # Pass the agent's logger so LLMQuery can log queries, responses, tool calls, etc.
        self.llm = LLMQuery(model=cast(ModelName, self.model_name), logger=self.logger)

        # Snapshot the LLM counters so we can compute deltas later
        self._usage_snapshot = self._snapshot_usage()

        self.logger.info(
            f"Agent '{self.name}' initialized with model '{self.model_name}'"
        )

    # ------------------------------------------------------------------
    # Usage tracking helpers
    # ------------------------------------------------------------------

    def _snapshot_usage(self) -> AgentUsage:
        """
        Take a point-in-time snapshot of the LLM client's cumulative counters.

        Returns:
            An :class:`AgentUsage` reflecting the current counter values.
        """
        return AgentUsage(
            prompt_tokens=self.llm.total_prompt_tokens,
            completion_tokens=self.llm.total_completion_tokens,
            reasoning_tokens=self.llm.total_reasoning_tokens,
            total_tokens=self.llm.total_tokens,
            cost=self.llm.total_cost,
            call_count=0,
        )

    def _collect_usage(self) -> None:
        """
        Compute the delta between the current LLM counters and the last
        snapshot, then record it in the global :class:`UsageTracker`.

        Call this at the **end** of every ``response()`` implementation.
        """
        current = self._snapshot_usage()
        delta = AgentUsage(
            prompt_tokens=current.prompt_tokens - self._usage_snapshot.prompt_tokens,
            completion_tokens=current.completion_tokens
            - self._usage_snapshot.completion_tokens,
            reasoning_tokens=current.reasoning_tokens
            - self._usage_snapshot.reasoning_tokens,
            total_tokens=current.total_tokens - self._usage_snapshot.total_tokens,
            cost=current.cost - self._usage_snapshot.cost,
            call_count=1,
        )
        UsageTracker.get().record(self.name, delta)
        # Advance the snapshot so the next call computes a fresh delta
        self._usage_snapshot = current

    # ------------------------------------------------------------------
    # Abstract & logging helpers
    # ------------------------------------------------------------------

    @abstractmethod
    def response(
        self, message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate a response to the user's message.

        Args:
            message: The user's input message.
            history: The chat history.

        Returns:
            The response text.
        """
        pass

    def log_query(self, query: str) -> None:
        """
        Log the incoming user query with standard formatting.

        Args:
            query: The raw user query string.
        """
        self.logger.info(f"QUERY: {query}")

    def log_response(self, response: str) -> None:
        """
        Log the final agent response with standard formatting.

        Args:
            response: The agent's response text.
        """
        self.logger.info(f"🧠 RESPONSE: {response}")
