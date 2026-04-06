from abc import ABC
from ai_tools.agent import LLMAgent, AgentConfig
from utils.logger import setup_logger
from utils.config import settings


class BaseAgent(LLMAgent, ABC):
    """
    Abstract base class for all pokemon-llm-specific agents in the system.

    Provides common functionality for logging and color logging.

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
