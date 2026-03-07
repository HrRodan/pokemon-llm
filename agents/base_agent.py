from abc import ABC
from ai_tools.agent import LLMAgent, AgentConfig
from utils.logger import setup_logger
from utils.config import settings
from utils.usage_tracker import UsageTracker, AgentUsage as TrackerAgentUsage


class BaseAgent(LLMAgent, ABC):
    """
    Abstract base class for all pokemon-llm-specific agents in the system.

    Provides common functionality for logging configuring the specific
    project `UsageTracker` and color logging.

    Subclasses that need to be used as tools (e.g. sub-agents wired into an
    orchestrator via :meth:`as_tool`) should define the class-level constants:

    - ``TOOL_NAME``: the function name exposed to the LLM (snake_case).
    - ``TOOL_DESCRIPTION``: a concise description for the LLM.
    """

    def __init__(self, config: AgentConfig) -> None:
        """Initialize the agent."""
        config.logger = config.logger or setup_logger(config.name)
        config.model_name = config.model_name or settings.DEFAULT_MODEL
        super().__init__(config=config)

    def _collect_usage(self) -> None:
        """
        Push the LLM client's cumulative totals to the global UsageTracker.
        This gets called at the end of the `run` method automatically via overriding.
        """
        UsageTracker.get().update(
            self.name,
            TrackerAgentUsage(
                prompt_tokens=self.usage.prompt_tokens,
                completion_tokens=self.usage.completion_tokens,
                reasoning_tokens=self.usage.reasoning_tokens,
                total_tokens=self.usage.total_tokens,
                cost=self.usage.cost,
                call_count=self.usage.call_count,
            ),
        )

    def run(self, message: str, use_history: bool = True) -> str:
        """
        Override run to inject standard pokemon-llm _collect_usage into the execution loop.
        """
        response = super().run(message, use_history=use_history)
        self._collect_usage()
        return response
