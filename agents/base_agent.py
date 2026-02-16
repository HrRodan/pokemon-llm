from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from ai_tools.tools import LLMQuery
from utils.logger import setup_logger
from utils.config import settings


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    Provides common functionality for logging, LLM client initialization, and configuration.
    """

    def __init__(self, name: str, model_name: Optional[str] = None):
        """
        Initialize the agent.

        Args:
            name: The name of the agent (used for logging).
            model_name: The LLM model to use. Defaults to settings.DEFAULT_MODEL.
        """
        self.name = name
        self.logger = setup_logger(name)
        self.model_name = model_name or settings.DEFAULT_MODEL

        # Initialize LLM Client
        # We use LLMQuery as the interface to the LLM
        self.llm = LLMQuery(model=self.model_name)

        self.logger.info(
            f"Agent '{self.name}' initialized with model '{self.model_name}'"
        )

    @abstractmethod
    def response(self, message: str, history: List[Dict[str, str]]) -> str:
        """
        Generate a response to the user's message.

        Args:
            message: The user's input message.
            history: The chat history.

        Returns:
            str: The response text.
        """
        pass

    def log_usage(self):
        """
        Logs the current token usage of the LLM client.
        """
        # Assuming LLMQuery has usage tracking (based on answer.py extract_usage_info)
        # If LLMQuery doesn't expose it directly globally, we might need to rely on the shared client state
        # For now, we just log a placeholder or access attributes if available
        pass

    def log_query(self, query: str):
        """
        Logs the incoming user query with standard formatting.
        """
        self.logger.info(f"QUERY: {query}")

    def log_tool_use(self, tool_name: str, args: Any):
        """
        Logs a tool call with standard formatting.
        """
        self.logger.info(f"🛠️  TOOL USE: {tool_name} | Args: {args}")

    def log_tool_output(self, output: Any):
        """
        Logs a tool output with standard formatting.
        """
        # Truncate long outputs for readability
        str_output = str(output)
        if len(str_output) > 500:
            str_output = str_output[:500] + "... [truncated]"
        self.logger.info(f"✅ TOOL OUTPUT: {str_output}")

    def log_response(self, response: str):
        """
        Logs the final agent response with standard formatting.
        """
        self.logger.info(f"🧠 RESPONSE: {response}")
