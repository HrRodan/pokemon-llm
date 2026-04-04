"""
tools.py — LLMQuery: the primary class for LLM interactions.

This module is the public face of the ``ai_tools`` package.  It:

- Defines ``LLMQuery``, which inherits ``MultiModalMixin`` to provide both
  text-chat and multi-modal capabilities in a single object.
- Re-exports all public symbols from the sub-modules so existing code that
  imports from ``ai_tools.tools`` continues to work without changes.
- Provides lazy API-key accessor functions (``GOOGLE_API_KEY()``, etc.) that
  resolve at call time rather than import time, preventing blocking in
  non-interactive environments.

Typical usage::

    from ai_tools.tools import LLMQuery

    llm = LLMQuery(model="gemini/gemini-flash-latest", system_prompt="You are helpful.")
    reply = llm.query("What is the capital of France?")

See README.md for full examples including tool use and pipeline syntax.
"""

import json
import re
import logging
from typing import (
    Dict,
    List,
    Union,
    Optional,
    Any,
    Callable,
    Type,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .memory import MemoryHandler
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel
from openai import OpenAI
from IPython.display import Markdown, display
import ai_tools.config as _cfg
from .config import ModelName
from .utils import (
    pretty_print_json,
    clean_json,
    handle_tool_call,
    handle_tool_call_async,
    generate_short_id,
    sanitize_tool_name,
)
from .pipeline import _Pipeline, _PipeableString, _PipeableQuery
from .multimodal import MultiModalMixin
from .tracing import (
    trace_llm_generation,
    update_generation,
    update_span,
    trace_span,
)

# ---------------------------------------------------------------------------
# Public type alias
# ---------------------------------------------------------------------------

#: An item accepted by the ``tools`` constructor argument of :class:`LLMQuery`.
#:
#: Can be one of:
#:
#: * **``@tool``-decorated callable** (preferred) — a function decorated with
#:   :func:`ai_tools.tool`.  The schema is extracted automatically and the
#:   callable is registered as the implementation.  No separate ``functions``
#:   entry needed.
#: * **Plain ``dict``** — a fully-specified OpenAI function-tool schema.  When
#:   using this form you must also pass the matching callable via ``functions``.
ToolInput = Union[Dict[str, Any], Callable]


class LLMQuery(MultiModalMixin):
    """
    Core class for standard LLM chat, tool usage, and pipelines.
    Inherits from MultiModalMixin to provide image, TTS, audio transcription,
    and embeddings.

    Pipeline Usage:
        query1 = LLMQuery(system_prompt="Translate to German")
        query2 = LLMQuery(system_prompt="Make it formal")
        pipeline = query1 | query2
        result = "Hello, how are you?" | pipeline
    """

    def __init__(
        self,
        system_prompt: str = "",
        model: ModelName = "gemini/gemini-flash-latest",
        stream: bool = False,
        json_format: bool = False,
        tools: Optional[List[ToolInput]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        functions: Optional[List[Callable]] = None,
        image_model: str = "gemini/models/imagen-4.0-generate-001",
        tts_model: str = "openai/gpt-4o-mini-tts",
        transcription_model: str = "gemini/gemini-2.5-flash",
        embedding_model: str = "openrouter/qwen/qwen3-embedding-8b",
        reasoning_effort: Optional[str] = None,
        history_limit: Optional[int] = None,
        use_history: bool = True,
        response_format: Union[Dict[str, Any], Type[BaseModel], None] = None,
        concurrent_tool_calls: bool = True,
        logger: Optional[logging.Logger] = None,
        memory: Optional["MemoryHandler"] = None,
        user_id: Optional[str] = None,
    ):
        """
        Initialize the LLMQuery instance.

        **Tool registration — three supported styles:**

        **Style 1 — ``@tool``-decorated callables (recommended):**

        Pass the decorated function directly in ``tools``.  The schema is
        extracted automatically and the function is registered without any
        entry in ``functions``::

            @tool
            def get_weather(city: str) -> str: ...

            llm = LLMQuery(tools=[get_weather])

        **Style 2 — Raw schema dicts + explicit function list:**

        Pass a hand-crafted OpenAI schema in ``tools`` and the matching
        callable in ``functions``.  The callable is looked up by name at
        dispatch time::

            schema = {"type": "function", "function": {"name": "get_weather", ...}}
            llm = LLMQuery(tools=[schema], functions=[get_weather])

        **Style 3 — Mixed (advanced):**

        ``tools`` may contain a mix of ``@tool`` callables and raw dicts.
        Explicit ``functions`` entries always take precedence on name
        collisions::

            llm = LLMQuery(tools=[decorated_fn, raw_schema], functions=[manual_fn])

        Args:
            system_prompt: System prompt sent before every user message.
            model: The text chat model to use.
            stream: Whether to stream the response by default.
            json_format: Whether to request JSON format by default.
            tools: List of tool definitions.  Each entry is either a
                ``@tool``-decorated callable or an OpenAI tool schema dict.
                See the three styles above.
            tool_choice: Tool choice strategy (``"auto"``, ``"none"``, or a
                specific function dict).  ``None`` lets the API decide.
            functions: Explicit list of callables used when ``tools`` contains
                raw schema dicts.  Each callable's ``__name__`` must match the
                ``function.name`` in the corresponding schema.  Not needed when
                all entries in ``tools`` are ``@tool``-decorated.
            image_model: Default image generation model.
            tts_model: Default Text-To-Speech model.
            transcription_model: Default audio transcription model.
            embedding_model: Default embedding model.
            reasoning_effort: Effort level for reasoning models.
            history_limit: Max number of history entries to include.
            use_history: Whether to use chat history by default.
            response_format: Format (dict or Pydantic model) for structured
                outputs.
            concurrent_tool_calls: If ``True`` (default), tool calls in a
                single LLM response are dispatched concurrently via
                ``asyncio.to_thread``.  Ideal for I/O-bound tools.  Set to
                ``False`` to force sequential dispatch.
            logger: Logger instance for traces.
            memory: Optional memory handler for conversation persistence.
                When provided, history is loaded on init and checkpointed after
                every successful ``query()`` call.
            user_id: Optional user identifier for tracing.
        """
        self.logger = logger
        self.user_id = user_id
        self.model = model
        self.image_model = image_model
        self.tts_model = tts_model
        self.transcription_model = transcription_model
        self.embedding_model = embedding_model
        self.reasoning_effort = reasoning_effort
        self.history_limit = history_limit
        self.use_history = use_history
        self.stream = stream
        self.json_format = json_format
        self.response_format = response_format
        self.concurrent_tool_calls = concurrent_tool_calls
        self.tool_choice = tool_choice
        self.system_prompt = system_prompt
        self.memory = memory
        resolved_schemas, resolved_fns = LLMQuery._resolve_tools(tools, functions)
        self.tools = resolved_schemas
        self.functions = resolved_fns
        self.chat_history: List[Dict[str, Any]] = []
        if self.memory:
            self.chat_history = self.memory.load_history()
            if self.user_id:
                self.memory.user_id = self.user_id
        self.tool_calls: List[Dict] = []
        self.response = ""
        self.reasoning_history: List[Optional[str]] = []
        self.total_cost: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_reasoning_tokens: int = 0
        self.total_tokens: int = 0

    def clear_history(self) -> None:
        """
        Reset per-conversation state for a fresh context.

        Clears ``chat_history``, ``tool_calls``, ``response``, and
        ``reasoning_history``.  Cumulative usage counters
        (``total_tokens``, ``total_cost``, etc.) are left intact so the
        owning agent can still report lifetime cost across multiple sessions.
        """
        if self.memory:
            self.memory.new_thread()
        self.chat_history = []
        self.tool_calls = []
        self.response = ""
        self.reasoning_history = []

    @staticmethod
    def _resolve_tools(
        tools: Optional[List[ToolInput]] = None,
        functions: Optional[List[Callable]] = None,
    ) -> "tuple[list, list]":
        """
        Normalise a mixed ``tools`` list into separate schemas and callables.

        Supports three item types in the ``tools`` list:

        - **``@tool``-decorated callable** — carries ``.__tool_schema__``.
          The schema is extracted and the callable is auto-added to functions.
        - **Plain dict** — treated as an already-resolved OpenAI schema.
        - **Anything else** — passed through unchanged (forward-compat guard).

        Explicit entries in ``functions`` are merged in *after* the callables
        inferred from ``tools``, so they take precedence for name collisions.

        Args:
            tools: Raw tools list (dicts, decorated callables, or mixed).
            functions: Explicit callable list (optional).

        Returns:
            Tuple of ``(schema_list, function_list)``.
        """
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

    @retry(
        stop=stop_after_attempt(5),
        # Exponential back-off: 1s, 2s, 4s, 8s, 10s (capped)
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _create_chat_completion(self, client: OpenAI, **kwargs) -> Any:
        """
        Execute ``client.chat.completions.create()`` with automatic retries.

        Validates the response structure before returning.  If the response is
        empty, malformed, or contains neither content nor tool calls, it raises
        ``ValueError`` which triggers tenacity to retry.

        The retry decorator (5 attempts, exponential back-off) handles transient
        network errors and rate-limit responses transparently.

        Args:
            client: Configured ``OpenAI`` client to use for the request.
            **kwargs: Forwarded verbatim to ``chat.completions.create()``.

        Returns:
            The raw API response object.

        Raises:
            ValueError: If the response structure is invalid after all retries.
        """
        response = client.chat.completions.create(**kwargs)

        # Guard: API can return a response with an empty choices list
        if not response or not response.choices:
            if self.logger:
                self.logger.error(
                    f"Invalid response structure: response={response}, retrying"
                )
            raise ValueError(f"Invalid response structure: response={response}")

        message = response.choices[0].message
        # Guard: message should never be None, but some edge-case models do this
        if message is None:
            if self.logger:
                self.logger.error(f"Message is None response={response}, retrying")
            raise ValueError(f"Message is None response={response}")

        # A valid response must have either text content, tool calls, or reasoning.
        # We check for reasoning here to avoid retrying when the model is just "thinking"
        # but hasn't emitted a final response yet.
        reasoning, _ = self._extract_reasoning(message)
        
        if not message.content and not message.tool_calls and not reasoning:
            if self.logger:
                self.logger.error(
                    f"Response empty and no tool calls or reasoning found response={response}, retrying"
                )
            raise ValueError(
                f"Response empty and no tool calls or reasoning found response={response}"
            )

        return response

    def _parse_xml_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse XML-formatted and token-based tool calls embedded in message content.

        Handles several distinct formats emitted by different models:

        **Format 1 — Standard ``<invoke>``:**
        Can be inside ``<function_calls>`` or standalone.
        ``<invoke name="get_weather">{"city": "Berlin"}</invoke>``

        **Format 2 — DeepSeek 3.2 ``<functioninvoke>``:**
        Uses ``<parameter>`` tags for arguments.

        **Format 3 — Token-based (Qwen/OpenRouter fallback):**
        ``to=functions.get_weather json<|message|>{"city": "Berlin"}``

        **Format 4 — Call-prefix tags:**
        ``<call:get_weather>{"city": "Berlin"}</call:get_weather>``

        **Format 5 — Named tags (for known functions):**
        ``<get_weather>{"city": "Berlin"}</get_weather>``

        Regex-based parsing is used to salvage malformed or partial XML.

        Args:
            content: The raw text content of the assistant message.

        Returns:
            List of tool-call dicts.
        """
        tool_calls = []
        seen_segments = set()  # prevent double-parsing the same content

        def add_call(name: str, args: str, segment: str):
            if segment in seen_segments:
                return
            seen_segments.add(segment)
            tool_calls.append(
                {
                    "id": f"call_via_content_{generate_short_id()}",
                    "type": "function",
                    "function": {"name": sanitize_tool_name(name), "arguments": args},
                }
            )

        # ----------------------------------------------------------------
        # Path 1: <invoke> tags (standard and standalone)
        # ----------------------------------------------------------------
        invoke_matches = re.finditer(
            r"<invoke([^>]*)>(.*?)</invoke>",
            content,
            re.DOTALL,
        )
        for match in invoke_matches:
            attrs = match.group(1).strip()
            args_str = match.group(2).strip()
            name_match = re.search(r'name=["\']([^"\']+)["\']', attrs)
            fn_name = name_match.group(1) if name_match else "error_missing_function_name"
            
            if args_str.startswith("<![CDATA[") and args_str.endswith("]]>"):
                args_str = args_str[9:-3].strip()
            
            add_call(fn_name, args_str, match.group(0))

        # ----------------------------------------------------------------
        # Path 2: DeepSeek 3.2 <functioninvoke> format
        # ----------------------------------------------------------------
        function_invoke_matches = re.finditer(
            r"<functioninvoke([^>]*)>(.*?)</(?:parameterinvoke|functioninvoke|invoke)>",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        for match in function_invoke_matches:
            attrs = match.group(1).strip()
            inner = match.group(2).strip()
            name_match = re.search(r'name=["\']([^"\']+)["\']', attrs)
            fn_name = name_match.group(1) if name_match else "error_missing_function_name"

            args: Dict[str, Any] = {}
            param_matches = re.finditer(
                r'<parameter\s+name=["\']([^"\']+)["\'][^>]*>(.*?)(?:</parameter>|$)',
                inner,
                re.DOTALL | re.IGNORECASE,
            )
            for p_match in param_matches:
                args[p_match.group(1)] = p_match.group(2).strip()

            args_str = json.dumps(args) if args else inner
            add_call(fn_name, args_str, match.group(0))

        # ----------------------------------------------------------------
        # Path 3: Token-based (to=functions.NAME json<|message|>ARGS)
        # ----------------------------------------------------------------
        token_matches = re.finditer(
            r"to=functions\.([a-zA-Z0-9_<|>-]+).*?<\|message\|>(.*?)(?=<\||\n\s*\n|$)",
            content,
            re.DOTALL
        )
        for match in token_matches:
            add_call(match.group(1), match.group(2).strip(), match.group(0))

        # ----------------------------------------------------------------
        # Path 4: Call-prefix tags (<call:NAME>ARGS</call:NAME>)
        # ----------------------------------------------------------------
        call_prefix_matches = re.finditer(
            r"<call:([a-zA-Z0-9_-]+)>(.*?)</call:\1>",
            content,
            re.DOTALL
        )
        for match in call_prefix_matches:
            add_call(match.group(1), match.group(2).strip(), match.group(0))

        # ----------------------------------------------------------------
        # Path 5: Named tags (<FUNCTION_NAME>ARGS</FUNCTION_NAME>)
        # ----------------------------------------------------------------
        if hasattr(self, "functions") and self.functions:
            for fn in self.functions:
                name = fn.__name__
                # We use a non-greedy match for the content
                tag_matches = re.finditer(
                    f"<{name}([^>]*)>(.*?)</{name}>",
                    content,
                    re.DOTALL
                )
                for match in tag_matches:
                    add_call(name, match.group(2).strip(), match.group(0))

        return tool_calls

    def _sanitize_tool_id(self, tool_id: Optional[str]) -> str:
        """
        Return a sanitised version of a tool call ID.

        The OpenAI API requires tool call IDs to match ``^[a-zA-Z0-9_-]+$``.
        Some providers (especially XML-based fallback paths) generate IDs with
        dots, colons, or other characters that would cause a validation error.
        We replace any invalid character with ``_``.

        Args:
            tool_id: Raw ID from the API or XML parser.  ``None`` or empty
                string causes a fresh ID to be generated.

        Returns:
            str: A sanitised, non-empty ID string.
        """
        if not tool_id:
            return f"call_{generate_short_id()}"
        # Replace any character outside [a-zA-Z0-9_-] with underscore
        return re.sub(r"[^a-zA-Z0-9_-]", "_", tool_id)

    def _get_client_for_model(self, model: str) -> OpenAI:
        """
        Return an OpenAI-compatible client for the given model name.

        Raises:
            ValueError: If the model is not listed with a supported prefix.
        """
        if model.startswith("openai/"):
            return OpenAI(api_key=_cfg.get_api_key("OPENAI_API_KEY"))
        elif model.startswith("ollama/"):
            return OpenAI(base_url=_cfg.OLLAMA_BASE_URL, api_key="ollama")
        elif model.startswith("gemini/"):
            return OpenAI(
                base_url=_cfg.GEMINI_BASE_URL,
                api_key=_cfg.get_api_key("GOOGLE_API_KEY"),
            )
        elif model.startswith("openrouter/"):
            return OpenAI(
                base_url=_cfg.OPENROUTER_BASE_URL,
                api_key=_cfg.get_api_key("OPENROUTER_API_KEY"),
            )
        raise ValueError(
            f"Model '{model}' lacks a recognized provider prefix (openai/, ollama/, gemini/, openrouter/)."
        )

    @property
    def client(self) -> OpenAI:
        """
        Convenience property returning the configured OpenAI client for the
        instance's default model.  Useful for one-off API calls outside the
        normal ``query()`` flow (e.g. custom endpoints).
        """
        return self._get_client_for_model(self.model)

    def _get_consistent_history(self, limit: int) -> List[Dict[str, Any]]:
        """
        Slice history while ensuring consistency for tool-use sequences.

        Strict providers (Mistral, Claude, etc.) require that history starts
        with a 'user' message and that 'tool' messages are preceded by the
        matching 'assistant' call. This method backtracks from the suggested
        limit until it finds a safe 'user' starting point.

        Args:
            limit: Suggested number of history entries to include.

        Returns:
            List[Dict]: A consistent slice starting with a 'user' message.
        """
        if limit <= 0:
            return []

        history_len = len(self.chat_history)
        start_idx = max(0, history_len - limit)

        # Backtrack: if we start with 'tool' or 'assistant', we must go back
        # to the preceding 'user' turn to maintain turn-based consistency.
        while start_idx > 0 and self.chat_history[start_idx].get("role") != "user":
            start_idx -= 1

        # If we are at index 0 and it's still not a 'user' message, skip forward
        # to find the first 'user' turn. Starting with 'tool' or 'assistant'
        # causes 400 errors on strict providers like Mistral.
        if (
            start_idx == 0
            and self.chat_history
            and self.chat_history[0].get("role") != "user"
        ):
            while start_idx < history_len and self.chat_history[start_idx].get("role") != "user":
                start_idx += 1

        return self.chat_history[start_idx:]

    def _prepare_messages(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None],
        use_history: bool,
        history_limit: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Build the full message list for the API call.

        Prepends the system prompt, optionally appends history (with optional
        tail limit), and finally appends the user prompt. A blank user message
        is injected when no other user content exists, to satisfy APIs like
        Gemini that require at least one user turn.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if use_history:
            if history_limit:
                messages.extend(self._get_consistent_history(history_limit))
            else:
                messages.extend(self.chat_history)

        if user_prompt is not None:
            if isinstance(user_prompt, list):
                messages.extend(user_prompt)
            else:
                messages.append({"role": "user", "content": user_prompt})

        if len(messages) == 1:
            messages.append({"role": "user", "content": ""})

        return messages

    def _prepare_request_kwargs(
        self,
        messages: List[Dict[str, str]],
        stream: bool,
        json_format: bool,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        **kwargs,
    ) -> Dict:
        """
        Build the keyword-argument dict for ``client.chat.completions.create()``.

        Handles three distinct response_format strategies:

        1. ``json_format=True`` → ``{"type": "json_object"}`` — asks the model
           to return any JSON object.
        2. ``self.response_format`` is a Pydantic ``BaseModel`` subclass →
           ``{"type": "json_schema", ...}`` with a strict schema derived from
           the model — guaranteed structured output.
        3. ``self.response_format`` is a plain dict → forwarded as-is for
           provider-specific format specs.

        OpenRouter-specific extras (``require_parameters``, ``data_collection",
        ``usage``) are injected automatically when the model is in the
        ``openrouter`` provider group.

        Args:
            messages: The full message list (system + history + user turn).
            stream: Whether to request a streaming response.
            json_format: Whether to force JSON output mode.
            model: Target model name (already resolved from overrides).
            reasoning_effort: Reasoning depth for compatible models.
            tools: Tool definitions to include in the request.
            tool_choice: Tool selection strategy.
            **kwargs: Any extra args forwarded to the API verbatim.

        Returns:
            Dict: Ready-to-unpack kwargs for ``create()``.
        """
        target_model = model if model is not None else self.model
        
        # Strip provider prefix for the API request
        api_model = target_model
        if target_model.startswith("openai/"):
            api_model = target_model[len("openai/"):]
        elif target_model.startswith("ollama/"):
            api_model = target_model[len("ollama/"):]
        elif target_model.startswith("gemini/"):
            api_model = target_model[len("gemini/"):]
        elif target_model.startswith("openrouter/"):
            api_model = target_model[len("openrouter/"):]

        request_kwargs: Dict[str, Any] = {"model": api_model, "messages": messages}

        if tools:
            request_kwargs["tools"] = tools
        if tool_choice:
            request_kwargs["tool_choice"] = tool_choice

        # Apply response format — three mutually exclusive branches
        if json_format:
            # Generic JSON mode: model returns any valid JSON object
            request_kwargs["response_format"] = {"type": "json_object"}
        elif self.response_format:
            if isinstance(self.response_format, type) and issubclass(
                self.response_format, BaseModel
            ):
                # Structured output: derive a strict JSON schema from the Pydantic model
                request_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": self.response_format.__name__,
                        "schema": self.response_format.model_json_schema(),
                        "strict": True,
                    },
                }
            else:
                # Raw dict: forward provider-specific format specs unchanged
                request_kwargs["response_format"] = self.response_format

        if stream:
            request_kwargs["stream"] = True
        if reasoning_effort:
            request_kwargs["reasoning_effort"] = reasoning_effort

        # Apply any additional caller-supplied kwargs last so they can override
        # anything set above (e.g. custom temperature or max_tokens)
        request_kwargs.update(kwargs)

        # OpenRouter requires extra provider hints for correct routing and to
        # receive cost/usage data back in the response.
        if target_model.startswith("openrouter/"):
            extra_body = request_kwargs.setdefault("extra_body", {})
            provider = extra_body.setdefault("provider", {})
            provider.setdefault("require_parameters", True)  # reject unsupported params
            provider.setdefault("data_collection", "deny")  # opt out of training data
            extra_body["usage"] = {"include": True}  # include cost in response

        return request_kwargs

    def _resolve_overrides(self, **kwargs) -> Dict[str, Any]:
        """
        Merge per-call overrides with instance defaults.

        Priority: explicit argument > instance attribute.
        A passed value of ``None`` is treated as "not provided" and falls
        back to the instance default, allowing callers to omit any key.
        """

        def _pick(key: str, default):
            val = kwargs.get(key)
            return val if val is not None else default

        return {
            "model": _pick("model", self.model),
            "json_format": _pick("json_format", self.json_format),
            "reasoning_effort": _pick("reasoning_effort", self.reasoning_effort),
            "tools": _pick("tools", self.tools),
            "tool_choice": _pick("tool_choice", self.tool_choice),
            "use_history": _pick("use_history", self.use_history),
            "history_limit": _pick("history_limit", self.history_limit),
        }

    def _update_usage(self, usage) -> None:
        """
        Accumulate token counts and cost from an API usage object.

        Handles two cost data locations:
        - ``usage.model_extra["cost"]`` — OpenRouter injects cost here.
        - ``usage["cost"]`` — fallback for dict-shaped usage objects.

        Handles two reasoning-token locations:
        - ``usage.completion_tokens_details`` as a dict or object attribute.

        Args:
            usage: The usage object from the API response, or ``None``.
        """
        if not usage:
            return

        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens

        # Extract cost — OpenRouter puts it in model_extra; some providers use a dict
        model_extra = getattr(usage, "model_extra", None)
        if model_extra:
            self.total_cost += model_extra.get("cost", 0.0)
        elif isinstance(usage, dict):
            self.total_cost += usage.get("cost", 0.0)

        # Extract reasoning tokens — shape varies by provider
        details = getattr(usage, "completion_tokens_details", None)
        if details:
            if isinstance(details, dict):
                self.total_reasoning_tokens += details.get("reasoning_tokens", 0)
            elif hasattr(details, "reasoning_tokens"):
                self.total_reasoning_tokens += details.reasoning_tokens

    def _extract_reasoning(self, message) -> tuple[Optional[str], Optional[str]]:
        """
        Extract chain-of-thought reasoning and Google thought_signature.

        Three providers store reasoning in different locations:

        - **OpenRouter / DeepSeek**: ``message.reasoning`` (top-level attribute)
        - **OpenRouter extra_body**:  ``message.model_extra["reasoning"]``
        - **Gemini via Google**:      ``message.model_extra["extra_content"]``
                                      ``["google"]["thought_signature"]``

        The thought_signature is opaque bytes used by Gemini's multi-turn
        reasoning API to preserve reasoning state across turns.

        Args:
            message: The assistant message object from the API response.

        Returns:
            Tuple of (reasoning_text, thought_signature).  Either or both may
            be ``None`` if not present in this response.
        """
        current_reasoning = getattr(message, "reasoning", None)
        thought_signature = None

        # model_extra is the pydantic-v2 field for unknown response keys;
        # extra_content is an older alias used by some SDK versions.
        extra_fields = getattr(message, "model_extra", None) or getattr(
            message, "extra_content", None
        )
        if extra_fields:
            extra_content = (
                extra_fields.get("extra_content", extra_fields)
                if isinstance(extra_fields, dict)
                else extra_fields
            )

            # OpenRouter may put reasoning inside model_extra directly
            if not current_reasoning and isinstance(extra_fields, dict):
                current_reasoning = extra_fields.get("reasoning")

            # Gemini's thought_signature lives at extra_content.google.thought_signature
            if isinstance(extra_content, dict):
                google_info = extra_content.get("google")
                if isinstance(google_info, dict):
                    thought_signature = google_info.get("thought_signature")

        return current_reasoning, thought_signature

    def _extract_and_sanitize_tool_calls(
        self, message_tool_calls, content: Optional[str]
    ) -> List[Dict]:
        """Collect native & XML tool calls, sanitize IDs, and ensure names."""
        calls = []
        if message_tool_calls:
            calls = [tc.model_dump() for tc in message_tool_calls]

        if content:
            calls.extend(self._parse_xml_tool_calls(content))

        for tc in calls:
            tc["id"] = self._sanitize_tool_id(tc.get("id"))
            if not tc.get("function"):
                tc["function"] = {"name": "unknown_function", "arguments": "{}"}
            
            # Sanitize the function name to remove LLM-specific tokens
            tc["function"]["name"] = sanitize_tool_name(tc["function"].get("name"))

        return calls

    def _log_response(
        self,
        content: Optional[str],
        reasoning: Optional[str],
        tool_calls: List[Dict],
        usage,
    ) -> None:
        """
        Log LLM response details at appropriate levels.

        Args:
            content: The text response from the LLM.
            reasoning: Any chain-of-thought / reasoning extracted from the message.
            tool_calls: The sanitized list of tool calls from this response.
            usage: The API usage object (or None if unavailable).
        """
        if not self.logger:
            return

        def trunc(s: str) -> str:
            return s[:500] + "... [truncated]" if len(s) > 500 else s

        if content:
            self.logger.debug(f"🧠 LLM RESPONSE: {trunc(content)}")
        
        if reasoning:
            if not content and not tool_calls:
                # Reasoning-only turn: log at INFO for easier debugging
                self.logger.info(f"💭 REASONING (ONLY): {trunc(str(reasoning))}")
            else:
                self.logger.debug(f"💭 REASONING: {trunc(str(reasoning))}")

        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "?")
            args = tc.get("function", {}).get("arguments", "{}")
            self.logger.info(f"🛠️  TOOL REQUESTED: {name} | Args: {args}")

        if usage:
            self.logger.debug(
                f"📊 TOKENS: prompt={usage.prompt_tokens}, "
                f"completion={usage.completion_tokens}, "
                f"total={usage.total_tokens}"
            )

    def _update_history(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None],
        response_content: Optional[str],
        tool_calls: Optional[List[Dict]] = None,
        thought_signature: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> None:
        """
        Append the user prompt and assistant response to ``self.chat_history``.

        Args:
            user_prompt: The user's input for this turn.
            response_content: The assistant's text response.
            tool_calls: Any tool calls made by the assistant.
            thought_signature: Gemini-specific thought signature for multi-turn reasoning.
            reasoning: Chain-of-thought reasoning text.
        """
        if user_prompt is not None:
            if isinstance(user_prompt, list):
                self.chat_history.extend(user_prompt)
            else:
                self.chat_history.append({"role": "user", "content": user_prompt})

        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": response_content,
        }
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        if thought_signature:
            assistant_msg["thought_signature"] = thought_signature
        
        # Only include reasoning in history if it's the ONLY thing provided.
        # This allows continuation without bloating history with redundant CoT.
        if reasoning and not response_content and not tool_calls:
            assistant_msg["reasoning"] = reasoning

        self.chat_history.append(assistant_msg)

    def query(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None] = None,
        model: Optional[ModelName] = None,
        use_history: Optional[bool] = None,
        display_output: bool = False,
        json_format: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        history_limit: Optional[int] = None,
        _recursion_depth: int = 0,
        **kwargs,
    ) -> str:
        """
        Send a non-streaming query to the LLM and return the response text.

        **Override resolution:** All optional parameters follow the pattern
        ``per-call argument > instance attribute > hardcoded default``.
        Passing ``None`` (or omitting the argument) falls back to the value
        set on the instance at construction time.

        **Side effects:** After each call the following instance attributes
        are updated:

        - ``self.response`` — the raw text response from the model.
        - ``self.tool_calls`` — list of tool-call dicts requested by the model
          (empty if the model returned only text).
        - ``self.reasoning_history`` — one entry appended per call with the
          chain-of-thought reasoning string (or ``None`` if not provided by
          the model).
        - ``self.chat_history`` — user and assistant messages appended so
          subsequent calls carry context automatically.
        - ``self.total_*`` counters updated with token usage from this call.

        To execute tool calls after this method, call
        ``get_tool_responses()`` which loops until no further tool calls are
        requested.

        Args:
            user_prompt: The user message to send.  Can be a plain string, a
                list of OpenAI-style message dicts (for multimodal or
                pre-formatted payloads), or ``None`` to continue from the
                existing history without a new user turn.
            model: Override the instance's default model for this call only.
            use_history: Include ``self.chat_history`` in the request.
                Overrides the instance's ``use_history`` flag.
            display_output: If ``True``, render the response in the notebook
                immediately via ``display_response()``.
            json_format: Ask the model to return a raw JSON object and
                automatically strip any Markdown code fences from the result.
                Overrides the instance's ``json_format`` flag.
            reasoning_effort: Effort level string for reasoning-capable models
                (e.g. ``"high"``). Overrides the instance attribute.
            tools: JSON-schema tool-definition list to pass to the API.
                Overrides ``self.tools`` for this call only.
            tool_choice: Tool-selection strategy (e.g. ``"auto"``, ``"none"``,
                or a specific-function dict). Overrides ``self.tool_choice``.
            history_limit: Limit the number of history entries included (uses
                the *last N* entries). ``None`` means include all history.
            _recursion_depth: Internal counter for re-querying on reasoning-only turns.
            **kwargs: Any extra keyword arguments are forwarded verbatim to the
                underlying ``client.chat.completions.create()`` call.

        Returns:
            str: The assistant's text response, or an empty string if the
            model returned only tool calls with no accompanying text.

        Example::

            q = LLMQuery(model="openai/gpt-4o-mini", system_prompt="You are helpful.")
            reply = q.query("What is the capital of France?")
            # reply == "Paris."

            # Use tools
            q = LLMQuery(model="openai/gpt-4o-mini", tools=[...], functions=[my_fn])
            q.query("Call the tool please.")
            final = q.get_tool_responses()
        """
        cfg = self._resolve_overrides(
            model=model,
            json_format=json_format,
            reasoning_effort=reasoning_effort,
            tools=tools,
            tool_choice=tool_choice,
            use_history=use_history,
            history_limit=history_limit,
        )

        if self.logger:
            prompt_str = str(user_prompt) if user_prompt else "[None/continuation]"
            self.logger.debug(f"📝 QUERY INPUT ({cfg['model']}): {prompt_str[:500]}")

        client = self._get_client_for_model(cfg["model"])
        messages = self._prepare_messages(
            user_prompt, cfg["use_history"], history_limit=cfg["history_limit"]
        )

        request_kwargs = self._prepare_request_kwargs(
            messages,
            stream=False,
            json_format=cfg["json_format"],
            model=cfg["model"],
            reasoning_effort=cfg["reasoning_effort"],
            tools=cfg["tools"],
            tool_choice=cfg["tool_choice"],
            **kwargs,
        )

        session_id = None
        if self.memory and hasattr(self.memory, "root_thread_id"):
            session_id = self.memory.root_thread_id

        metadata = {"provider": cfg["model"].split("/")[0] if "/" in cfg["model"] else "unknown"}
        if cfg["tool_choice"]:
            metadata["tool_choice"] = cfg["tool_choice"]
            
        model_params = {k: v for k, v in request_kwargs.items() if k not in ("messages", "model", "tools", "tool_choice", "extra_body")}

        with trace_llm_generation(
            name="llm-query",
            model=cfg["model"],
            input_messages=messages,
            model_parameters=model_params,
            tool_definitions=cfg["tools"] if cfg["tools"] else None,
            metadata=metadata,
            user_id=self.user_id,
            session_id=session_id,
        ) as generation:
            response = self._create_chat_completion(client, **request_kwargs)

            # Extract usage for Langfuse
            usage_data = None
            if hasattr(response, "usage") and response.usage:
                self._update_usage(response.usage)
                usage_data = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }

                cost = getattr(response.usage, "cost", None)
                if cost is None:
                    model_extra = getattr(response.usage, "model_extra", None)
                    if model_extra:
                        cost = model_extra.get("cost")
                if cost is None and isinstance(response.usage, dict):
                    cost = response.usage.get("cost")
                    
                if cost is not None:
                    usage_data["total_cost"] = float(cost)

            message = response.choices[0].message
            content = message.content

            self.tool_calls = self._extract_and_sanitize_tool_calls(
                message.tool_calls, content
            )

            tool_call_names = [tc["function"]["name"] for tc in self.tool_calls] if self.tool_calls else None
            update_generation(
                generation,
                output=content or "[tool_calls_only]",
                usage=usage_data,
                model=cfg["model"],
                tool_calls=self.tool_calls if self.tool_calls else None,
                tool_call_names=tool_call_names,
            )

        if cfg["json_format"] and content:
            content = clean_json(content)

        reasoning, thought_signature = self._extract_reasoning(message)
        self.reasoning_history.append(reasoning)

        self._log_response(
            content, reasoning, self.tool_calls, getattr(response, "usage", None)
        )

        self.response = content if content is not None else ""
        self._update_history(
            user_prompt,
            content,
            self.tool_calls if self.tool_calls else None,
            thought_signature=thought_signature,
            reasoning=reasoning,
        )

        if self.memory and not self.tool_calls:
            usage_snapshot = {
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_tokens,
                "cost": self.total_cost,
            }
            self.memory.save_checkpoint(
                messages=self.chat_history,
                tool_calls=None,
                usage=usage_snapshot,
            )

        # Handle reasoning-only response by re-querying (max 3 attempts)
        if not content and not self.tool_calls and reasoning and _recursion_depth < 3:
            if self.logger:
                self.logger.info("Reasoning-only response received; re-querying for content...")
            return self.query(
                user_prompt="Answer the original user question",
                model=cfg["model"],
                use_history=True,
                display_output=display_output,
                json_format=cfg["json_format"],
                reasoning_effort=cfg["reasoning_effort"],
                tools=cfg["tools"],
                tool_choice=cfg["tool_choice"],
                history_limit=cfg["history_limit"],
                _recursion_depth=_recursion_depth + 1,
                **kwargs,
            )

        if display_output:
            self.display_response()

        return self.response

    def invoke(
        self,
        input: Union[str, Dict[str, Any], List[Dict[str, str]]],
        config: Optional[Any] = None,
        **kwargs,
    ) -> str:
        """
        LangChain-compatible invoke method.

        Accepts a plain string, a list of message dicts, or a dict with an
        ``'input'``, ``'query'``, or ``'content'`` key and delegates to ``query()``.

        Args:
            input: The user prompt in one of several supported forms.
            config: Unused; accepted for interface compatibility.
            **kwargs: Forwarded to ``query()``.

        Returns:
            str: The response text.
        """
        user_prompt: Union[str, List[Dict[str, str]], None] = None

        if isinstance(input, (str, list)):
            user_prompt = input
        elif isinstance(input, dict):
            raw = input.get("input") or input.get("query") or input.get("content")
            if isinstance(raw, (str, list)):
                user_prompt = raw
            elif isinstance(raw, dict) and "role" in raw and "content" in raw:
                user_prompt = [raw]
            else:
                user_prompt = str(raw) if raw is not None else None

        return self.query(user_prompt=user_prompt, **kwargs)

    def append_tool_result(self, tool_outputs: List[Dict[str, Any]]) -> None:
        """
        Append tool execution results to the chat history.

        Converts non-string outputs (PIL images, bytes, arbitrary objects)
        to serialisable strings before storing.

        Args:
            tool_outputs: List of dicts with ``'tool_call_id'`` and ``'output'`` keys,
                as returned by ``handle_tool_call``.
        """
        for tool_output in tool_outputs:
            out = tool_output["output"]
            if hasattr(out, "mode") and hasattr(
                out, "size"
            ):  # basic duck-type check for PIL Image
                out = "[Image created]"
            elif isinstance(out, bytes):
                out = "[Audio created]"
            elif not isinstance(out, str):
                try:
                    out = json.dumps(out)
                except Exception:
                    out = f"[{type(out).__name__} object created]"

            self.chat_history.append(
                {
                    "role": "tool",
                    "content": out,
                    "tool_call_id": self._sanitize_tool_id(tool_output["tool_call_id"]),
                }
            )

    def inject_system_message(self, content: str) -> None:
        """
        Append a system-role message to the chat history.

        Unlike ``system_prompt`` (always prepended), injected messages live
        inside ``chat_history`` and are subject to ``use_history`` /
        ``history_limit`` — so judge feedback naturally ages out with old turns.

        Use-cases: LLM-as-Judge corrections, mid-conversation rule changes,
        dynamic guardrails.

        Args:
            content: The system directive to inject.

        Example::

            llm.query("Draft a reply.")
            llm.inject_system_message("Too verbose — be concise from now on.")
            llm.query("Revise the reply.")
        """
        self.chat_history.append({"role": "system", "content": content})

    def display_response(self) -> None:
        """Display the last response in the notebook using Markdown or JSON formatting."""
        if self.json_format:
            pretty_print_json(self.response)
        else:
            display(Markdown(self.response))

    def get_chat_history_as_string(self) -> str:
        """
        Return the chat history formatted as a human-readable Markdown string.

        Each turn is labelled with ``**User**``, ``**Assistant**``, or ``**Tool Output**``.
        Tool calls made by the assistant are also included.
        """
        history: List[str] = []
        for msg in self.chat_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            if role in ("User", "Tool"):
                history.append(f"**{role}**: {content}")
            elif role == "System":
                # Injected system messages (distinct from the immutable system_prompt)
                history.append(f"**System (injected)**: {content}")
            elif role == "Assistant":
                if content is not None:
                    history.append(f"**Assistant**: {content}")
                if "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]
                        history.append(
                            f"**Assistant Tool Call**: {fn['name']}({fn['arguments']})"
                        )
        return "\n\n".join(history)

    @property
    def clean_chat_history(self) -> List[Dict[str, str]]:
        """
        Chat history filtered to only user/assistant turns with non-empty content.

        Strips out tool messages and assistant stub entries, returning only
        ``{'role': ..., 'content': ...}`` dicts — useful for feeding into
        another ``LLMQuery`` or for display purposes.
        """
        return [
            {"role": h["role"], "content": h["content"]}
            for h in self.chat_history
            if h["role"] in ("assistant", "user") and h["content"]
        ]

    def display_chat_history(self) -> None:
        """Display the full chat history in the notebook as formatted Markdown."""
        display(Markdown(self.get_chat_history_as_string()))

    @staticmethod
    def _run_async(coro):
        """
        Run an async coroutine from synchronous code.

        Handles the common case where an event loop is already running
        (e.g. Jupyter notebooks) by applying ``nest_asyncio`` to allow
        re-entrant use of the loop.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running — safe to use asyncio.run()
            return asyncio.run(coro)

        # An event loop is already running (Jupyter / IPython / uvicorn etc.).
        # Patch it so we can call run_until_complete() re-entrantly.
        import nest_asyncio

        nest_asyncio.apply(loop)
        return loop.run_until_complete(coro)

    def get_tool_responses(self, max_iterations: int = 50) -> str:  # noqa: C901
        """
        Run tool calls until no more are returned, up to max_iterations.

        This method drives the tool-use loop:

        1. Checks ``self.tool_calls`` for pending calls.
        2. If present, calls ``handle_tool_call`` (synchronous) or
           ``handle_tool_call_async`` (concurrent) to execute them.
        3. Appends the tool result to the chat history via ``append_tool_result``.
        4. Repeats until no more tool calls are returned or ``max_iterations``
           is reached.

        Args:
            max_iterations: Maximum number of tool-use rounds to allow.

        Returns:
            The final assistant response text after all tool calls have been
            processed.
        """
        response = self.response
        iterations = 0

        while self.tool_calls and iterations < max_iterations:
            if self.concurrent_tool_calls:
                tool_response = self._run_async(
                    handle_tool_call_async(
                        self.tool_calls,
                        functions=self.functions,
                        logger=self.logger,
                    )
                )
            else:
                tool_response = handle_tool_call(
                    self.tool_calls, functions=self.functions, logger=self.logger
                )
            self.append_tool_result(tool_response)

            query_response = self.query(tools=self.tools)

            if not query_response and not self.tool_calls:
                if (
                    self.chat_history
                    and self.chat_history[-1]["role"] == "assistant"
                    and not self.chat_history[-1]["content"]
                ):
                    self.chat_history.pop()
                query_response = self.query(tools=self.tools)

            if query_response:
                response = (
                    f"{response}\n\n{query_response}" if response else query_response
                )

            iterations += 1

        return response

    def as_tool(
        self,
        name: str,
        description: str,
        input_arg: str = "query",
    ) -> "tuple[dict, Callable]":
        """
        Wrap this ``LLMQuery`` instance as an LLM-callable tool.

        Returns a ``(tool_schema_dict, wrapper_fn)`` pair.  The wrapper runs
        the full ``query() → get_tool_responses()`` agentic loop and returns
        the final text string.

        Unlike many sub-agent wrappers, this one clears history on each tool
        call so that every invocation starts with a fresh context, preventing
        context bleed-through between consecutive calls from the parent agent.
        Use the ``query()`` / ``get_tool_responses()`` loop directly if you
        need persistent multi-turn history within a single tool invocation.

        Typical usage::

            rag = LLMQuery(system_prompt="You are a RAG agent…")
            schema, fn = rag.as_tool(
                name="run_rag_agent",
                description="Delegates to the RAG Specialist Agent.",
            )
            orchestrator = LLMQuery(tools=[schema], functions=[fn])

        Args:
            name: The function name exposed to the LLM.
            description: Human-readable description of what the tool does.
            input_arg: Name of the single string parameter the LLM must provide.
                Defaults to ``"query"``.

        Returns:
            Tuple of ``(tool_schema_dict, wrapper_callable)``.
        """
        tool_schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        input_arg: {"type": "string", "description": description}
                    },
                    "required": [input_arg],
                },
            },
        }

        llm_ref = self

        def _wrapper(**kwargs) -> str:
            prompt = kwargs.get(input_arg, "")
            original_memory = getattr(llm_ref, "memory", None)
            
            if original_memory:
                # Scoped: each invocation gets its own thread for audit trail
                scoped = original_memory.create_scoped_handler(name)
                llm_ref.memory = scoped  # temporarily swap
                llm_ref.chat_history = []
            else:
                llm_ref.clear_history()
                
            llm_ref.query(prompt)
            result = llm_ref.get_tool_responses()
            
            if original_memory:
                llm_ref.memory = original_memory  # restore parent handler
            
            return result

        _wrapper.__name__ = name
        _wrapper.__pydantic_model__ = None  # use raw **kwargs path in dispatcher

        return tool_schema, _wrapper

    def __call__(self, **kwargs) -> _PipeableQuery:
        """
        Return a ``_PipeableQuery`` that defers execution and captures optional
        per-call kwargs.

        Example::

            result = "Explain AI" | llm(model="openai/gpt-4o-mini")
        """
        return _PipeableQuery(self, kwargs)

    def __ror__(self, other: Any) -> Any:
        """
        Enable right-hand pipe: ``"text" | llm_query``.

        Returns a ``_PipeableString`` so the result can be piped further.
        """
        if isinstance(other, (str, list, dict)):
            result = self.invoke(other)
            return _PipeableString(result) if isinstance(result, str) else result
        return NotImplemented

    def __or__(self, other: Any) -> _Pipeline:
        """
        Enable left-hand pipe to compose a reusable pipeline::

            pipeline = query1 | query2
            result = "Hello" | pipeline
        """
        return _Pipeline(self, other)
