"""
agent.py — Unified Agent abstraction for LLM interactions.

Decomposes the monolithic LLMQuery and LLMAgent into a single lifecycle-driven
Agent class, leveraging specialized modules for client management, parsing,
and usage tracking.
"""

import copy
import json
import logging
import re
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    TYPE_CHECKING,
    cast,
)

from pydantic import BaseModel
from openai import OpenAI

from . import config as _cfg
from .config import ModelName, strip_provider_prefix
from .usage import UsageTracker
from .client import get_client
from .parsing import (
    extract_and_sanitize_tool_calls,
    extract_reasoning,
)
from .utils import (
    clean_json,
    generate_short_id,
    sanitize_tool_name,
    handle_tool_call,
    handle_tool_call_async,
)
from .multimodal import MultiModalMixin
from . import tracing

if TYPE_CHECKING:
    from .memory import MemoryHandler

# Re-export ToolInput for backward compatibility in imports
ToolInput = Union[Dict[str, Any], Callable]


class Agent(MultiModalMixin):
    """
    The primary abstraction for LLM interactions.

    Incorporates identity (name), behavior (system_prompt, tools),
    memory (persistence), and observability (tracing).
    """

    TOOL_NAME: str = ""
    TOOL_DESCRIPTION: str = ""

    def __init__(
        self,
        model: Optional[ModelName] = None,
        system_prompt: str = "",
        *,
        name: str = "",
        tools: Optional[List[ToolInput]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        functions: Optional[List[Callable]] = None,
        memory: Optional["MemoryHandler"] = None,
        user_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        # query behavior
        stream: bool = False,
        json_format: bool = False,
        reasoning_effort: Optional[str] = None,
        history_limit: Optional[int] = None,
        use_history: bool = True,
        response_format: Union[Dict[str, Any], Type[BaseModel], None] = None,
        concurrent_tool_calls: bool = True,
        # multimodal models
        image_model: Optional[str] = None,
        tts_model: Optional[str] = None,
        transcription_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize the Agent.

        Args:
            model: Full model name with provider prefix (e.g. "gemini/gemini-flash-latest").
            system_prompt: System prompt sent before every user message.
            name: Human-friendly name for tracing/logging. Defaults to class name.
            tools: List of tool definitions (@tool callables or OpenAI schemas).
            tool_choice: "auto", "none", or a specific function dict.
            functions: Explicit callables for raw schema dicts in `tools`.
            memory: Optional persistence handler.
            user_id: Optional identifier for tracing and multi-tenant memory.
            logger: Custom logger instance.
            stream: Whether to stream response text (default False).
            json_format: Whether to force generic JSON output (default False).
            reasoning_effort: Effort level for reasoning models ("low", "medium", "high").
            history_limit: Max messages to include from history.
            use_history: Whether to include history by default (default True).
            response_format: Pydantic model or schema for structured output.
            concurrent_tool_calls: Whether to dispatch multiple tools in parallel.
            image_model: Default model for image generation.
            tts_model: Default model for Text-To-Speech.
            transcription_model: Default model for audio transcription.
            embedding_model: Default model for text embeddings.
        """
        self.name = name or self.__class__.__name__
        self.logger = logger or logging.getLogger(self.name)
        self.model = model or "gemini/gemini-flash-latest"
        self.system_prompt = system_prompt
        self.user_id = user_id
        
        # Query behavior
        self.stream = stream
        self.json_format = json_format
        self.reasoning_effort = reasoning_effort
        self.history_limit = history_limit
        self.use_history = use_history
        self.response_format = response_format
        self.concurrent_tool_calls = concurrent_tool_calls
        self.tool_choice = tool_choice
        
        # Multimodal
        self.image_model = image_model or "gemini/models/imagen-4.0-generate-001"
        self.tts_model = tts_model or "openai/gpt-4o-mini-tts"
        self.transcription_model = transcription_model or "gemini/gemini-2.5-flash"
        self.embedding_model = embedding_model or "openrouter/qwen/qwen3-embedding-8b"
        
        # Internal State
        self.usage = UsageTracker()
        self.memory = memory
        self._session_id: Optional[str] = None
        
        # Resolve Tools
        resolved_schemas, resolved_fns = self._resolve_tools(tools, functions)
        self.tools = resolved_schemas
        self.functions = resolved_fns
        
        # Dynamic State
        self.chat_history: List[Dict[str, Any]] = []
        if self.memory:
            self.chat_history = self.memory.load_history()
            self._session_id = self.memory.root_thread_id
            if self.user_id:
                self.memory.user_id = self.user_id
                
        self.tool_calls: List[Dict] = []
        self.response = ""
        self.reasoning_history: List[Optional[str]] = []

        self.logger.info(f"Agent '{self.name}' initialized with model '{self.model}'")

    @property
    def session_id(self) -> Optional[str]:
        """Single source of truth for session identity."""
        if self.memory and hasattr(self.memory, "root_thread_id") and self.memory.root_thread_id:
            return self.memory.root_thread_id
        return self._session_id

    @session_id.setter
    def session_id(self, value: Optional[str]) -> None:
        self._session_id = value

    @property
    def clean_chat_history(self) -> List[Dict[str, Any]]:
        """Return history without internal reasoning fragments (used for UI)."""
        return [
            {k: v for k, v in m.items() if k != "reasoning"} for m in self.chat_history
        ]

    def clear_history(self) -> None:
        """Reset per-conversation state for a fresh context."""
        if self.memory:
            self.memory.new_thread()
        self.chat_history = []
        self.tool_calls = []
        self.response = ""
        self.reasoning_history = []
        # usage is intentionally NOT cleared (persists for lifetime of Agent)

    def clone(self) -> "Agent":
        """Create a fresh run-state copy for isolated sub-agent execution."""
        new_agent = copy.copy(self)
        new_agent.chat_history = []
        new_agent.tool_calls = []
        new_agent.response = ""
        new_agent.reasoning_history = []
        new_agent.usage = UsageTracker()
        return new_agent

    def invoke(self, input_dict: Union[str, Dict]) -> str:
        """LangChain-compatible entry point."""
        prompt = input_dict if isinstance(input_dict, str) else input_dict.get("input", "")
        return self.run(prompt)

    def query(
        self,
        user_prompt: Optional[Union[str, List[Dict]]] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Single LLM call. Updates history. No tool loop."""
        overrides = self._resolve_overrides(**kwargs)
        target_model = model or overrides["model"]
        
        # 0. Update history with user prompt
        if user_prompt is not None:
            if isinstance(user_prompt, list):
                self.chat_history.extend(user_prompt)
            else:
                self.chat_history.append({"role": "user", "content": user_prompt})

        messages = self._prepare_messages(
            user_prompt,
            use_history=overrides["use_history"],
            history_limit=overrides["history_limit"],
        )
        
        client = get_client(target_model)
        # Construction request parameters
        all_kwargs = {**overrides, **kwargs}
        all_kwargs.pop("model", None)  # Ensure we don't pass model twice

        request_kwargs = self._prepare_request_kwargs(
            messages=messages,
            model=target_model,
            **all_kwargs,
        )

        with tracing.propagate_langfuse_attributes(
            session_id=self.session_id,
            user_id=self.user_id,
            tags=[self.name, target_model.split("/")[0]],
        ):
            response_obj = self._create_chat_completion(client, request_kwargs)

        message = response_obj.choices[0].message
        content = message.content or ""
        reasoning, thought_signature = extract_reasoning(message)
        
        # Handle reasoning
        if reasoning:
            self.reasoning_history.append(reasoning)
        
        # Build Tool Calls
        known_names = [f.__name__ for f in self.functions]
        self.tool_calls = extract_and_sanitize_tool_calls(
            message.tool_calls, content, known_names
        )
        
        # Update usage
        self.usage.update(response_obj.usage)
        
        # Final Response Text
        self.response = content
        
        # Update history
        self._update_history(message, reasoning, thought_signature)
        
        # Memory Checkpoint
        # Memory Checkpoint
        if self.memory and not self.tool_calls:
            ctx = tracing.get_current_trace_context()
            self.memory.save_checkpoint(
                messages=self.chat_history,
                usage=self.usage.last_usage,
                trace_id=ctx.trace_id if ctx else None
            )
            
        return content

    def run(self, message: str, use_history: bool = True, **kwargs) -> str:
        """Full agentic loop: query -> tool calls -> re-query -> done."""
        self.logger.info(f"RUN starts: '{message[:50]}...'")
        
        with tracing.trace_span(
            name=f"Agent Run: {self.name}",
            input={"message": message},
            user_id=self.user_id,
            session_id=self.session_id,
            metadata={"model": self.model},
            tags=[self.name],
            _is_agent_run=True,
            as_type="agent",
        ) as span:
            self.query(user_prompt=message, use_history=use_history, **kwargs)
            
            if self.tool_calls:
                self.get_tool_responses()
                
            final_response = self.response
            if span:
                from .tracing import update_span, flush_tracing
                update_span(span, output=final_response)
                flush_tracing()
                
            self.logger.info(f"RUN ends. Result length: {len(final_response)}")
            return final_response

    def get_tool_responses(self, max_iterations: int = 20) -> str:
        """Iterative tool execution loop."""
        iteration = 0
        while self.tool_calls and iteration < max_iterations:
            iteration += 1
            self.logger.info(f"Iteration {iteration}: Processing {len(self.tool_calls)} tools")
            
            tool_results = self._dispatch_tools(self.tool_calls)
            
            # Step 1: Append all tool *results* to history
            for tc, result in zip(self.tool_calls, tool_results):
                self.append_tool_result(tc["id"], result)
                
            # Step 2: Next LLM turn (pass None as user_prompt to just continue with history)
            self.query(user_prompt=None)
            
            # Memory checkpoint after each turn
            if self.memory:
                from .tracing import get_current_trace_context
                ctx = get_current_trace_context()
                self.memory.save_checkpoint(
                    messages=self.chat_history,
                    usage=self.usage.last_usage,
                    trace_id=ctx.trace_id if ctx else None
                )
                
        return self.response

    def as_tool(self) -> Callable:
        """Expose this agent as a @tool-compatible callable."""
        if not self.TOOL_NAME or not self.TOOL_DESCRIPTION:
            raise ValueError(f"{self.__class__.__name__} missing TOOL_NAME/DESCRIPTION")
            
        tool_schema = {
            "type": "function",
            "function": {
                "name": self.TOOL_NAME,
                "description": self.TOOL_DESCRIPTION,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The prompt to the agent."}
                    },
                    "required": ["query"],
                },
            },
        }

        # capture ref
        outer_self = self

        def _wrapper(query: str) -> str:
            # 1. Clone + state isolation
            local_agent = outer_self.clone()
            
            # 2. Scoped memory
            if outer_self.memory:
                scoped = outer_self.memory.create_scoped_handler(outer_self.TOOL_NAME)
                local_agent.memory = scoped
                local_agent.session_id = scoped.root_thread_id
            else:
                # Inherit session from tracing context if no memory
                local_agent.session_id = tracing.get_thread_session_id() or outer_self.session_id
            
            # 3. Propagate context
            local_agent.user_id = tracing.get_thread_user_id() or outer_self.user_id
            
            # 4. Execute
            result = local_agent.run(query)
            
            # 5. Aggregate usage
            outer_self.usage.aggregate_from(local_agent.usage)
            
            return result

        _wrapper.__name__ = self.TOOL_NAME
        _wrapper.__tool_schema__ = tool_schema
        _wrapper.__pydantic_model__ = None  # Needed for handle_tool_call consistency
        return _wrapper

    # --- Internal Helpers (Extracted/Refactored from LLMQuery) ---

    @staticmethod
    def _resolve_tools(tools: Optional[List[ToolInput]], functions: Optional[List[Callable]]) -> tuple:
        schemas: list = []
        fns: list = list(functions or [])
        fn_names = {f.__name__ for f in fns}

        for item in tools or []:
            if callable(item) and hasattr(item, "__tool_schema__"):
                schemas.append(item.__tool_schema__)
                if item.__name__ not in fn_names:
                    fns.append(item)
                    fn_names.add(item.__name__)
            else:
                schemas.append(item)
        return schemas, fns

    def _resolve_overrides(self, **kwargs) -> Dict:
        def _get(k, default):
            v = kwargs.get(k)
            return v if v is not None else default
            
        return {
            "model": _get("model", self.model),
            "json_format": _get("json_format", self.json_format),
            "reasoning_effort": _get("reasoning_effort", self.reasoning_effort),
            "use_history": _get("use_history", self.use_history),
            "history_limit": _get("history_limit", self.history_limit),
            "tool_choice": _get("tool_choice", self.tool_choice),
        }

    def _prepare_messages(self, user_prompt, use_history: bool, history_limit: Optional[int]) -> List[Dict]:
        """Generate the list of messages for the API. PURE function (no side effects)."""
        msgs = [{"role": "system", "content": self.system_prompt}]
        if use_history:
            limit = history_limit or 100
            history_slice = self._get_consistent_history(limit)
            msgs.extend(history_slice)
            
        # We assume the user_prompt has ALREADY been added to self.chat_history if it was a new turn,
        # but for specific sub-calls we might want to include it without duplicating it in history.
        # Actually, if we just called query(), history_slice ALREADY contains it.
        # So we only add user_prompt if it's NOT already at the end of the history slice.
        
        last_msg = history_slice[-1] if use_history and history_slice else None
        
        if user_prompt is not None:
            if isinstance(user_prompt, list):
                # Only add if not already present in history_slice
                if not use_history or user_prompt != history_slice[-len(user_prompt):]:
                    msgs.extend(user_prompt)
            else:
                prompt_msg = {"role": "user", "content": user_prompt}
                if not use_history or prompt_msg != last_msg:
                    msgs.append(prompt_msg)
                
        if len(msgs) == 1:
            msgs.append({"role": "user", "content": ""})
        return msgs

    def _get_consistent_history(self, limit: int) -> List[Dict]:
        if not self.chat_history:
            return []
        if limit <= 0:
            return []
            
        start = max(0, len(self.chat_history) - limit)
        
        # Ensure we start with a user message for strict providers
        # 1. Backtrack to nearest preceding user message
        while start > 0 and self.chat_history[start].get("role") != "user":
            start -= 1
            
        # 2. If we are still not at a user message (e.g. at idx 0 or orphan tool calls),
        # skip forward to binary-safe first user message.
        if self.chat_history[start].get("role") != "user":
            while start < len(self.chat_history) - 1 and self.chat_history[start].get("role") != "user":
                start += 1
                
        # 3. Final safety: If we skipped all the way to the end and NO user message exists,
        # return empty to avoid API rejection.
        if self.chat_history[start].get("role") != "user":
            return []
            
        return self.chat_history[start:]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _create_chat_completion(self, client, request_kwargs):
        """Wrapper for API call with retry logic and basic validation."""
        response = client.chat.completions.create(**request_kwargs)
        if not response.choices:
            raise ValueError("Empty response from API")
        return response

    def _prepare_request_kwargs(self, messages, model, **kwargs) -> Dict:
        from .tracing import get_langfuse_params, get_current_trace_context, build_openrouter_trace_dict
        
        provider, api_model = strip_provider_prefix(model)
        
        rkwargs = {
            "model": api_model,
            "messages": messages,
            "stream": kwargs.get("stream", self.stream),
        }

        if self.tools:
            rkwargs["tools"] = self.tools
        if kwargs.get("tool_choice"):
            rkwargs["tool_choice"] = kwargs["tool_choice"]
            
        # Response Format
        if kwargs.get("json_format"):
            rkwargs["response_format"] = {"type": "json_object"}
        elif self.response_format:
            if isinstance(self.response_format, type) and issubclass(self.response_format, BaseModel):
                rkwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": self.response_format.__name__,
                        "schema": self.response_format.model_json_schema(),
                        "strict": True,
                    }
                }
            else:
                rkwargs["response_format"] = self.response_format
                
        if kwargs.get("reasoning_effort"):
            rkwargs["reasoning_effort"] = kwargs["reasoning_effort"]
            
        # Langfuse Tracing Parameters (Generation Naming)
        lparams = get_langfuse_params(
            model=model,
            agent_name=self.name,
            user_id=self.user_id,
            session_id=self.session_id,
            metadata=kwargs.get("metadata"),
        )
        rkwargs.update(lparams)

        # Provider-specific extras
        if provider == "openrouter":
            eb = rkwargs.setdefault("extra_body", {})
            pcfg = eb.setdefault("provider", {})
            pcfg["require_parameters"] = True
            pcfg["data_collection"] = "deny"
            eb["usage"] = {"include": True}
            
            # Trace Propagation for OpenRouter
            ctx = get_current_trace_context(
                session_id=self.session_id,
                user_id=self.user_id,
                trace_name=self.name
            )
            otrace = build_openrouter_trace_dict(
                ctx, 
                generation_name=lparams.get("name"),
                span_name=f"agent:run:{self.name}"
            )
            if otrace:
                eb["trace"] = otrace

            if self.session_id:
                eb["session_id"] = self.session_id
                
        if self.user_id:
            rkwargs["user"] = self.user_id
            
        return rkwargs

    def _update_history(self, message, reasoning=None, thought_signature=None) -> None:
        # Append assistant message with reasoning if present
        msg_dict = message.model_dump()
        if reasoning:
            msg_dict["reasoning"] = reasoning
        if thought_signature:
            if "model_extra" not in msg_dict:
                msg_dict["model_extra"] = {}
            msg_dict["model_extra"]["thought_signature"] = thought_signature
            
        self.chat_history.append(msg_dict)

    def append_tool_result(self, tool_call_id: str, content: Any) -> None:
        """Append a tool's output to the conversation history."""
        self.chat_history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(content) if content is not None else "",
        })

    def _dispatch_tools(self, tool_calls: List[Dict]) -> List[str]:
        """Dispatch tool calls using the refactored utility helpers."""
        if self.concurrent_tool_calls and len(tool_calls) > 1:
            # handle_tool_call_async is already optimized for thread-safe context propagation
            results = asyncio.run(handle_tool_call_async(
                tool_calls, self.functions, logger=self.logger
            ))
        else:
            results = handle_tool_call(
                tool_calls, self.functions, logger=self.logger
            )
            
        return [r["output"] for r in results]

    def inject_system_message(self, content: str) -> None:
        """Append a system message to history mid-conversation."""
        self.chat_history.append({"role": "system", "content": content})

    def get_chat_history_as_string(self) -> str:
        """Return history as a formatted string."""
        lines = []
        for m in self.chat_history:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)
# For backward compatibility with tests that might try to patch these
from .tracing import get_langfuse_params
