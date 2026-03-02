from typing import Optional, List, Dict, Any, Callable, cast
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

    def __init__(
        self,
        name: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        functions: Optional[List[Callable]] = None,
        history_limit: Optional[int] = None,
        concurrent_tool_calls: bool = True,
    ) -> None:
        """
        Initialize the agent.

        Args:
            name: The name of the agent (used for logging and usage tracking).
            model_name: The LLM model to use. Defaults to ``settings.DEFAULT_MODEL``.
            system_prompt: System prompt to configure the LLM's behaviour.
            tools: List of tool definitions (OpenAI-style function dicts) to supply to the LLM.
            functions: List of callable functions that implement the tools.
            history_limit: Maximum chat-history turns the LLM will consider.
            concurrent_tool_calls: If ``True``, run tool calls concurrently
                via ``asyncio.to_thread``.  Ideal for I/O-bound tools.
        """
        self.name = name
        self.logger = setup_logger(name)
        self.model_name = model_name or settings.DEFAULT_MODEL

        # Initialize LLM Client
        # We use LLMQuery as the interface to the LLM
        # Pass the agent's logger so LLMQuery can log queries, responses, tool calls, etc.
        self.llm = LLMQuery(model=cast(ModelName, self.model_name), logger=self.logger)

        # Apply optional LLM configuration supplied by the subclass
        if system_prompt is not None:
            self.llm.system_prompt = system_prompt
        if tools is not None:
            self.llm.tools = tools
        if functions is not None:
            self.llm.functions = functions
        if history_limit is not None:
            self.llm.history_limit = history_limit
        if concurrent_tool_calls:
            self.llm.concurrent_tool_calls = concurrent_tool_calls

        self._call_count: int = 0

        self.logger.info(
            f"Agent '{self.name}' initialized with model '{self.model_name}'"
        )

    # ------------------------------------------------------------------
    # Usage tracking helpers
    # ------------------------------------------------------------------

    def _collect_usage(self) -> None:
        """
        Push the LLM client's cumulative totals to the global
        :class:`UsageTracker`.

        Sub-agents are never reset during a session, so the ``LLMQuery``
        counters already reflect the full lifetime totals of this agent.
        We simply overwrite the tracker's snapshot on every call.

        Call this at the **end** of every ``response()`` implementation.
        """
        self._call_count += 1
        UsageTracker.get().update(
            self.name,
            AgentUsage(
                prompt_tokens=self.llm.total_prompt_tokens,
                completion_tokens=self.llm.total_completion_tokens,
                reasoning_tokens=self.llm.total_reasoning_tokens,
                total_tokens=self.llm.total_tokens,
                cost=self.llm.total_cost,
                call_count=self._call_count,
            ),
        )

    # ------------------------------------------------------------------
    # Common execution helper
    # ------------------------------------------------------------------

    def _run(self, message: str, use_history: bool = False) -> str:
        """
        Execute the standard query → tool-loop → collect-usage cycle.

        This is the shared implementation that all sub-agents delegate to
        from their ``response()`` method.  Sub-agents that need custom
        behaviour before or after the LLM call should override
        ``response()`` directly instead of calling this helper.

        Args:
            message: The user's input text.
            use_history: Whether to include chat history in the LLM call.

        Returns:
            Final response text after any tool calls have been resolved.
        """
        self.log_query(message)
        response = self.llm.query(user_prompt=message, use_history=use_history)

        if self.llm.tool_calls:
            response = self.llm.get_tool_responses()

        self.log_response(response)
        self._collect_usage()
        return response

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
