"""
agent.py — Base LLMAgent class simplifying the LLMQuery orchestration loop.

Provides an LLMAgent that integrates usage tracking, a generalized execution loop,
history management, and an easy `as_tool()` method to expose an agent as a callable `@tool`.
"""

from typing import Optional, List, Callable, Any, cast, Union, Type, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory import MemoryHandler
import logging
from dataclasses import dataclass

from .tools import LLMQuery
from .config import ModelName
from .tracing import trace_agent_run, trace_subagent_call, update_span


@dataclass(kw_only=True)
class AgentConfig:
    """Configuration class for LLMAgent, encompassing LLMQuery configuration."""

    name: str
    model_name: str
    system_prompt: str = ""
    tools: Optional[List[Any]] = None
    history_limit: Optional[int] = None
    concurrent_tool_calls: bool = True
    logger: Optional[logging.Logger] = None
    user_id: Optional[str] = None

    # LLMQuery specific settings
    stream: bool = False
    json_format: bool = False
    tool_choice: Optional[Union[str, Dict]] = None
    functions: Optional[List[Callable]] = None
    image_model: str = "gemini/models/imagen-4.0-generate-001"
    tts_model: str = "openai/gpt-4o-mini-tts"
    transcription_model: str = "gemini/gemini-2.5-flash"
    embedding_model: str = "openrouter/qwen/qwen3-embedding-8b"
    reasoning_effort: Optional[str] = None
    use_history: bool = True
    response_format: Union[Dict[str, Any], Type[Any], None] = None
    memory: Optional["MemoryHandler"] = None


@dataclass
class AgentUsage:
    """Holds cumulative usage metrics for an agent."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    call_count: int = 0


class LLMAgent:
    """
    A unified base agent that orchestrates LLMQuery.

    Features:
    - Automatically handles tool resolution loops in `run()`.
    - Tracks cumulative token usage across multiple runs.
    - Exposes an `as_tool()` adapter to be natively fed into other `LLMQuery` instances.
    """

    TOOL_NAME: str = ""
    TOOL_DESCRIPTION: str = ""

    def __init__(self, config: AgentConfig) -> None:
        """
        Initialize the LLMAgent.

        Args:
            config: An AgentConfig containing all LLMAgent and LLMQuery configurations.
        """
        self.config = config
        self.name = config.name
        self.logger = config.logger or logging.getLogger(config.name)
        self.model_name = config.model_name

        self.llm = LLMQuery(
            model=cast(ModelName, self.model_name),
            logger=self.logger,
            system_prompt=config.system_prompt,
            tools=config.tools,
            stream=config.stream,
            json_format=config.json_format,
            tool_choice=config.tool_choice,
            functions=config.functions,
            image_model=config.image_model,
            tts_model=config.tts_model,
            transcription_model=config.transcription_model,
            embedding_model=config.embedding_model,
            reasoning_effort=config.reasoning_effort,
            history_limit=config.history_limit,
            use_history=config.use_history,
            response_format=config.response_format,
            concurrent_tool_calls=config.concurrent_tool_calls,
            memory=config.memory,
            user_id=config.user_id,
        )

        self._call_count: int = 0
        self.usage = AgentUsage()

        self.logger.info(
            f"Agent '{self.name}' initialized with model '{self.model_name}'"
        )

    def _update_usage(self) -> None:
        """Updates internal usage tracking from the underlying LLMQuery instance."""
        self._call_count += 1
        self.usage = AgentUsage(
            prompt_tokens=self.llm.total_prompt_tokens,
            completion_tokens=self.llm.total_completion_tokens,
            reasoning_tokens=self.llm.total_reasoning_tokens,
            total_tokens=self.llm.total_tokens,
            cost=self.llm.total_cost,
            call_count=self._call_count,
        )

    def run(self, message: str, use_history: bool = True) -> str:
        """
        Execute the standard query -> tool-loop cycle.

        Args:
            message: The user's input text.
            use_history: Whether to include chat history in the LLM call. Default is True.

        Returns:
            The final text response from the LLM.
        """
        self.logger.info(f"QUERY: {message}")

        # Derive session_id from memory root thread if available
        session_id = None
        if self.llm.memory and hasattr(self.llm.memory, "root_thread_id"):
            session_id = self.llm.memory.root_thread_id

        with trace_agent_run(
            agent_name=self.name,
            input_message=message,
            user_id=self.config.user_id,
            session_id=session_id,
            tags=[self.name, self.model_name.split("/")[0]],
            metadata={"model": self.model_name},
        ) as span:
            response = self.llm.query(user_prompt=message, use_history=use_history)

            if self.llm.tool_calls:
                response = self.llm.get_tool_responses()

            self.logger.info(f"🧠 RESPONSE: {response}")
            self._update_usage()

            update_span(span, output=response[:1000] if response else "")

        return response

    def as_tool(self) -> Callable:
        """
        Exposes this agent as a `@tool`-compatible callable.

        Returns a wrapper callable whose `.__tool_schema__` attribute holds
        the OpenAI-compatible schema derived from the class `TOOL_NAME` and
        `TOOL_DESCRIPTION`.

        The wrapper PERSISTS history across tool calls, allowing the agent
        to maintain context from previous turns in the same session. Use
        `history_limit` in the `AgentConfig` to manage context window size.

        Returns:
            Callable: The tool wrapper.

        Raises:
            ValueError: If TOOL_NAME or TOOL_DESCRIPTION aren't defined.
        """
        if not self.TOOL_NAME:
            raise ValueError(
                f"{self.__class__.__name__}.TOOL_NAME must be defined to use as_tool()."
            )
        if not self.TOOL_DESCRIPTION:
            raise ValueError(
                f"{self.__class__.__name__}.TOOL_DESCRIPTION must be defined to use as_tool()."
            )

        tool_schema = {
            "type": "function",
            "function": {
                "name": self.TOOL_NAME,
                "description": self.TOOL_DESCRIPTION,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": self.TOOL_DESCRIPTION,
                        }
                    },
                    "required": ["query"],
                },
            },
        }

        # capture reference to avoid circular binding
        agent_ref = self

        def _wrapper(**kwargs) -> str:
            query = kwargs.get("query", "")
            with trace_subagent_call(self.TOOL_NAME, query) as span:
                original_memory = getattr(agent_ref.llm, "memory", None)
                if original_memory:
                    # Scoped: each invocation gets its own isolated thread
                    scoped = original_memory.create_scoped_handler(self.TOOL_NAME)
                    agent_ref.llm.memory = scoped
                    agent_ref.llm.chat_history = []
                else:
                    agent_ref.llm.clear_history()
                result = agent_ref.run(query)
                if original_memory:
                    agent_ref.llm.memory = original_memory  # restore parent handler
                
                update_span(span, output=result[:1000] if result else "")
                return result

        _wrapper.__name__ = self.TOOL_NAME
        _wrapper.__tool_schema__ = tool_schema
        _wrapper.__pydantic_model__ = None

        return _wrapper
