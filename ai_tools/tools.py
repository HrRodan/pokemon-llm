import json
import os
import base64
import io
import mimetypes
import getpass
import re
import uuid
from PIL import Image
from typing import (
    Dict,
    List,
    Literal,
    get_args,
    Union,
    Generator,
    Optional,
    Any,
    Callable,
    Type,
)

from dotenv import load_dotenv
from IPython.display import Markdown, display
from openai import OpenAI
from pydantic import BaseModel

load_dotenv(override=True)

OLLAMA_BASE_URL = "http://localhost:11434/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# API Key Retrieval
# Priority 1: Google Colab Userdata (for native Colab environment)
try:
    from google.colab import userdata  # pyrefly: ignore

    GOOGLE_API_KEY = userdata.get("GOOGLE_API_KEY")
    OPENAI_API_KEY = userdata.get("OPENAI_API_KEY")
    OPENROUTER_API_KEY = userdata.get("OPENROUTER_API_KEY")
except (ImportError, AttributeError, Exception):
    GOOGLE_API_KEY = None
    OPENAI_API_KEY = None
    OPENROUTER_API_KEY = None

# Priority 2: Environment Variables (local development, .env files)
if not GOOGLE_API_KEY:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENROUTER_API_KEY:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Priority 3: Interactive Prompt (VS Code Colab extension, fallback)
if not GOOGLE_API_KEY:
    try:
        GOOGLE_API_KEY = getpass.getpass("GOOGLE_API_KEY: ")
    except Exception:
        print("Warning: GOOGLE_API_KEY not found and interactive prompt failed.")
if not OPENAI_API_KEY:
    try:
        OPENAI_API_KEY = getpass.getpass("OPENAI_API_KEY: ")
    except Exception:
        print("Warning: OPENAI_API_KEY not found and interactive prompt failed.")
if not OPENROUTER_API_KEY:
    try:
        OPENROUTER_API_KEY = getpass.getpass("OPENROUTER_API_KEY: ")
    except Exception:
        print("Warning: OPENROUTER_API_KEY not found and interactive prompt failed.")

GPTModels = Literal[
    "gpt-4o-mini",
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5.1",
    "gpt-5.2",
    "gpt-4.1-mini",
    "gpt-5.2-pro",
    "gpt-image-1.5",
    "gpt-4o-mini-tts",
    "tts-1",
]

OllamaModels = Literal["llama3.2", "deepseek-r1:1.5b"]

GeminiModels = Literal[
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "models/imagen-4.0-generate-001",
    "gemini-2.5-pro-preview-tts",
    "gemini-3-flash-preview",
]

OpenRouterModels = Literal[
    #"anthropic/claude-sonnet-4.5",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "deepseek/deepseek-v3.2",  # top price / intelligence
    #"x-ai/grok-4",
    #"anthropic/claude-opus-4.5",
    "x-ai/grok-4.1-fast",  # top price / intelligence
    "z-ai/glm-4.7",
    "moonshotai/kimi-k2-thinking",
    "qwen/qwen3-embedding-8b",  # Embedding model
]

ModelName = Union[GPTModels, OllamaModels, GeminiModels, OpenRouterModels]

MODEL_DICT = {
    "gpt": set(get_args(GPTModels)),
    "ollama": set(get_args(OllamaModels)),
    "gemini": set(get_args(GeminiModels)),
    "openrouter": set(get_args(OpenRouterModels)),
}


def pretty_print_json(data):
    """
    Prints JSON data in a readable, indented format with syntax highlighting.
    Accepts a dictionary, list, or a JSON string.
    """
    try:
        # If input is a string, try to parse it as JSON first
        if isinstance(data, str):
            data = json.loads(data)

        # Convert back to string with indentation
        pretty_json = json.dumps(data, indent=2, ensure_ascii=False)

        # Display using Markdown for syntax highlighting in the notebook
        display(Markdown(f"```json\n{pretty_json}\n```"))

    except json.JSONDecodeError:
        print("Invalid JSON string provided.")

    except Exception as e:
        print(f"Error prettifying JSON: {e}")


def clean_json(text: str) -> str:
    """
    Cleans a JSON string by removing Markdown code blocks and leading/trailing whitespace.

    Args:
        text (str): The input string containing JSON, potentially wrapped in Markdown.

    Returns:
        str: The cleaned JSON string.
    """
    cleaned_text = text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json") :]
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[len("```") :]

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[: -len("```")]

    return cleaned_text.strip()


def handle_tool_call(
    tool_calls: List[Dict[str, Any]], functions: List[Callable]
) -> List[Dict[str, Any]]:
    """
    Handle LLM tool calls by executing the corresponding functions.

    Iterates over a list of tool calls, looks up the function in the provided list,
    executes it with the provided arguments, and collects the results.
    Captures errors during parsing or execution and returns them as tool outputs.

    Args:
        tool_calls (List[Dict]): A list of tool call dictionaries from the LLM response.
            Each dictionary should contain 'function' with 'name' and 'arguments', and an 'id'.
        functions (List[Callable]): A list of functions that can be called.

    Returns:
        List[Dict]: A list of tool response dictionaries containing 'tool_call_id', 'output', 'arguments', and 'name'.
    """
    tool_response = []
    function_map = {f.__name__: f for f in functions}

    for tool_call in tool_calls:
        tool_id = tool_call.get("id", "unknown_id")
        function_name = tool_call.get("function", {}).get("name", "unknown_function")
        arguments_str = tool_call.get("function", {}).get("arguments", "")
        arguments = {}

        try:
            # Parse arguments
            if arguments_str:
                if isinstance(arguments_str, dict):
                    arguments = arguments_str
                else:
                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Failed to parse arguments JSON: {e}")

            # Check if function exists
            if function_name not in function_map:
                raise ValueError(
                    f"Function '{function_name}' not found. Available functions: {list(function_map.keys())}"
                )

            # Execute function
            function_to_call = function_map[function_name]
            try:
                result = function_to_call(**arguments)
            except Exception as e:
                # Catch execution errors and return them as tool output so the LLM knows it failed
                raise RuntimeError(f"Error while executing '{function_name}': {e}")

        except Exception as e:
            result = f"Error: {str(e)}"

        tool_response.append(
            {
                "tool_call_id": tool_id,
                "output": result,
                "arguments": arguments,
                "name": function_name,
            }
        )

    return tool_response


class LLMQuery:
    def __init__(
        self,
        system_prompt: str = "",
        model: ModelName = "gemini-flash-latest",
        stream: bool = False,
        json_format: bool = False,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        functions: Optional[List[Callable]] = None,
        image_model: str = "models/imagen-4.0-generate-001",
        tts_model: str = "gpt-4o-mini-tts",
        transcription_model: str = "gemini-2.5-flash",
        embedding_model: str = "qwen/qwen3-embedding-8b",
        reasoning_effort: Optional[str] = None,
        history_limit: Optional[int] = None,
        response_format: Union[Dict[str, Any], Type[BaseModel], None] = None,
    ):
        """
        Initialize the LLMQuery instance.

        Args:
            system_prompt (str, optional): The system prompt to use. Defaults to "".
            model (ModelName, optional): The model to use. Defaults to "gemini-flash-lite-latest".
            stream (bool, optional): Whether to stream the response by default. Defaults to False.
            json_format (bool, optional): Whether to request JSON format by default. Defaults to False.
            tools (List[Dict], optional): List of tools to be available to the model. Defaults to None.
            tool_choice (Union[str, Dict], optional): Tool choice strategy. Defaults to None.
            functions (List[Callable], optional): List of functions to be available to the model. Defaults to None.
            image_model (str, optional): The image generation model to use. Defaults to "models/imagen-4.0-generate-001".
            tts_model (str, optional): The TTS model to use. Defaults to "gpt-4o-mini-tts".
            transcription_model (str, optional): The transcription model to use. Defaults to "gemini-2.5-flash".
            embedding_model (str, optional): The embedding model to use. Defaults to "qwen/qwen3-embedding-8b".
            reasoning_effort (str, optional): The reasoning effort to use. Defaults to None.
            reasoning_effort (str, optional): The reasoning effort to use. Defaults to None.
            reasoning_effort (str, optional): The reasoning effort to use. Defaults to None.
            history_limit (int, optional): The maximum number of history entries to include. Defaults to None (all history).
            response_format (Union[Dict[str, Any], Type[BaseModel], None], optional): The format of the response. Can be a dict or a Pydantic model. Defaults to None.
        """
        self.model = model
        self.image_model = image_model
        self.tts_model = tts_model
        self.transcription_model = transcription_model
        self.embedding_model = embedding_model
        self.reasoning_effort = reasoning_effort
        self.history_limit = history_limit
        self.stream = stream
        self.json_format = json_format
        self.response_format = response_format
        self.tools = tools
        if functions is None:
            self.functions = []
        else:
            self.functions = functions
        self.tool_choice = tool_choice
        self.system_prompt = system_prompt
        self.chat_history: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict] = []
        self.response = ""

    def _parse_xml_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse XML-formatted tool calls from the message content.
        Looks for <function_calls>...</function_calls> blocks and nested <invoke name="...">...</invoke> tags.
        """
        tool_calls = []

        # Regex to find the <function_calls> block
        function_calls_match = re.search(
            r"<function_calls>(.*?)</function_calls>", content, re.DOTALL
        )

        if function_calls_match:
            function_calls_content = function_calls_match.group(1)

            # Regex to find individual <invoke> tags with loose name attribute matching
            # Logic: Match <invoke followed by anything > (content) </invoke>
            invoke_matches = re.finditer(
                r"<invoke(.*?)>(.*?)</invoke>",
                function_calls_content,
                re.DOTALL,
            )

            for match in invoke_matches:
                attrs = match.group(1).strip()
                arguments_str = match.group(2).strip()

                # Extract name from attributes, supporting single or double quotes
                name_match = re.search(r'name=["\']([^"\']+)["\']', attrs)
                if name_match:
                    function_name = name_match.group(1)
                else:
                    # Fallback for missing name to trigger a specific error in handle_tool_call
                    function_name = "error_missing_function_name"

                # Check for CDATA wrapper and remove it if present
                if arguments_str.startswith("<![CDATA[") and arguments_str.endswith(
                    "]]>"
                ):
                    arguments_str = arguments_str[9:-3].strip()

                tool_id = f"call_via_content_{uuid.uuid4().hex[:8]}"

                tool_calls.append(
                    {
                        "id": tool_id,
                        "type": "function",
                        "function": {"name": function_name, "arguments": arguments_str},
                    }
                )

        return tool_calls

    def _get_client_for_model(self, model: str) -> OpenAI:
        """
        Get the OpenAI client for the specified model.

        Args:
            model: The model name to get the client for.

        Returns:
            OpenAI: The OpenAI client instance.

        Raises:
            ValueError: If the model is not supported.
        """
        if model in MODEL_DICT["gpt"]:
            client = OpenAI()
        elif model in MODEL_DICT["ollama"]:
            client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
        elif model in MODEL_DICT["gemini"]:
            client = OpenAI(
                base_url=GEMINI_BASE_URL,
                api_key=GOOGLE_API_KEY,
            )
        elif model in MODEL_DICT["openrouter"]:
            client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=OPENROUTER_API_KEY,
            )
        else:
            raise ValueError(f"Model {model} not supported")
        return client

    @property
    def client(self) -> OpenAI:
        """
        Get the OpenAI client for the configured model.

        Returns:
            OpenAI: The OpenAI client instance.
        """
        return self._get_client_for_model(self.model)

    def _prepare_messages(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None],
        use_history: bool,
        history_limit: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Prepare the list of messages for the API call.

        Args:
            user_prompt: The user's input.
            use_history: Whether to include chat history.
            history_limit (int, optional): The maximum number of history entries to include.

        Returns:
            List of message dictionaries.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if use_history:
            if history_limit:
                messages.extend(self.chat_history[-history_limit:])
            else:
                messages.extend(self.chat_history)

        if user_prompt is not None:
            if isinstance(user_prompt, list):
                messages.extend(user_prompt)
            else:
                messages.append({"role": "user", "content": user_prompt})

        # Ensure at least one message exists besides system prompt to satisfy APIs like Gemini
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
        Prepare the keyword arguments for the API call.
        """
        # Resolve Overrides (Argument > Instance Variable > Default)
        target_model = model if model is not None else self.model
        request_kwargs: Dict[str, Any] = {"model": target_model, "messages": messages}

        # Resolve Tools and Tool Choice
        target_tools = tools if tools is not None else self.tools
        target_tool_choice = (
            tool_choice if tool_choice is not None else self.tool_choice
        )

        if target_tools:
            request_kwargs["tools"] = target_tools
        if target_tool_choice:
            request_kwargs["tool_choice"] = target_tool_choice

        if json_format:
            request_kwargs["response_format"] = {"type": "json_object"}
        elif self.response_format:
            if isinstance(self.response_format, type) and issubclass(
                self.response_format, BaseModel
            ):
                request_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": self.response_format.__name__,
                        "schema": self.response_format.model_json_schema(),
                        "strict": True,
                    },
                }
            else:
                request_kwargs["response_format"] = self.response_format

        if stream:
            request_kwargs["stream"] = True
        if reasoning_effort:
            request_kwargs["reasoning_effort"] = reasoning_effort

        # Include any additional kwargs
        request_kwargs.update(kwargs)

        # OpenRouter specific configuration
        if target_model in MODEL_DICT["openrouter"]:
            extra_body = request_kwargs.get("extra_body", {})
            if "provider" not in extra_body:
                extra_body["provider"] = {}

            # Ensure OpenRouter specific parameters are set
            # require_parameters: True -> ensures 400 error if parameters are missing
            # data_collection: "deny" -> opts out of data collection
            extra_body["provider"].setdefault("require_parameters", True)
            extra_body["provider"].setdefault("data_collection", "deny")

            request_kwargs["extra_body"] = extra_body

        return request_kwargs

    def _update_history(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None],
        response_content: Optional[str],
        tool_calls: Optional[List[Dict]] = None,
        thought_signature: Optional[str] = None,
    ):
        """
        Update the chat history with the user prompt, assistant response and results from tool calls.
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
            # Store appropriately, mimicking the API structure or just as a clear field
            assistant_msg["thought_signature"] = thought_signature

        self.chat_history.append(assistant_msg)

    def query(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None] = None,
        model: Optional[ModelName] = None,
        use_history: bool = True,
        display_output: bool = False,
        json_format: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        history_limit: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Send a non-streaming query to the LLM.

        Args:
            user_prompt: The prompt to send.
            model: Optional model to use, overriding the default instance model.
            use_history: Whether to include chat history.
            display_output: Whether to display the output using IPython display.
            json_format: Whether to request JSON format (overrides instance default).
            reasoning_effort: Effort level for reasoning models.
            tools: Optional list of tools to use.
            tool_choice: Optional tool choice strategy.
            history_limit: Optional override for history limit.
            **kwargs: Additional arguments passed to the API call.

        Returns:
            The response text.
        """
        # Reset tool calls
        self.tool_calls = []

        # Resolve Overrides (Argument > Instance Variable)
        target_json_format = (
            json_format if json_format is not None else self.json_format
        )
        target_model = model if model is not None else self.model
        target_reasoning_effort = (
            reasoning_effort if reasoning_effort is not None else self.reasoning_effort
        )
        target_tools = tools if tools is not None else self.tools
        target_tool_choice = (
            tool_choice if tool_choice is not None else self.tool_choice
        )

        target_history_limit = (
            history_limit if history_limit is not None else self.history_limit
        )

        client = self._get_client_for_model(target_model)

        messages = self._prepare_messages(
            user_prompt, use_history, history_limit=target_history_limit
        )
        request_kwargs = self._prepare_request_kwargs(
            messages,
            stream=False,
            json_format=target_json_format,
            model=target_model,
            reasoning_effort=target_reasoning_effort,
            tools=target_tools,
            tool_choice=target_tool_choice,
            **kwargs,
        )

        response = client.chat.completions.create(**request_kwargs)
        message = response.choices[0].message
        content = message.content

        # Handle tool calls
        if message.tool_calls:
            self.tool_calls = [tc.model_dump() for tc in message.tool_calls]

        # Also check for XML-formatted tool calls in the content
        if content:
            xml_tool_calls = self._parse_xml_tool_calls(content)
            if xml_tool_calls:
                self.tool_calls.extend(xml_tool_calls)

        # Clean JSON if requested
        if target_json_format and content:
            content = clean_json(content)

        # Look for thought_signature in the message object for GEMINI models
        # Based on docs: extra_content.google.thought_signature
        # Also checking model_extra as a fallback/alternative location for extra fields
        thought_signature = None

        # Check standard Pydantic model_extra/extra_fields if available
        # Note: model_extra might contain 'extra_content' dict inside it
        extra_fields = getattr(message, "model_extra", None) or getattr(
            message, "extra_content", None
        )

        if extra_fields:
            # Handle case where extra_content is nested inside model_extra
            if "extra_content" in extra_fields and isinstance(
                extra_fields["extra_content"], dict
            ):
                extra_content = extra_fields["extra_content"]
            else:
                extra_content = extra_fields

            # Navigate key path: google -> thought_signature
            if isinstance(extra_content, dict):
                google_info = extra_content.get("google")
                if isinstance(google_info, dict):
                    thought_signature = google_info.get("thought_signature")

        # Update state
        self.response = content if content is not None else ""
        self._update_history(
            user_prompt,
            content,
            self.tool_calls if self.tool_calls else None,
            thought_signature=thought_signature,
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

        Args:
            input: The input prompt (str), a dictionary containing the prompt/query, or a list of messages.
            config: Optional configuration (unused but required by interface).
            **kwargs: Additional arguments passed to query.

        Returns:
            str: The response text.
        """
        user_prompt = input

        # Handle dict input (e.g. {"input": "..."} or {"query": "..."})
        if isinstance(input, dict):
            if "input" in input:
                user_prompt = input["input"]
            elif "query" in input:
                user_prompt = input["query"]
            elif "content" in input:
                user_prompt = input["content"]

            if isinstance(user_prompt, str):
                pass  # Good
            elif isinstance(user_prompt, list):
                pass  # Good
            elif (
                isinstance(user_prompt, dict)
                and "role" in user_prompt
                and "content" in user_prompt
            ):
                # If the input is a single message dict (e.g., {"role": "user", "content": "..."}),
                # wrap it in a list so it matches the expected input format for self.query.
                user_prompt = [user_prompt]

        return self.query(user_prompt=user_prompt, **kwargs)

    def query_stream(
        self,
        user_prompt: Union[str, List[Dict[str, str]], None] = None,
        model: Optional[ModelName] = None,
        use_history: bool = True,
        display_output: bool = False,
        json_format: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
        return_generator: bool = True,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        history_limit: Optional[int] = None,
        **kwargs,
    ) -> Union[str, Generator[str, None, None]]:
        """
        Send a streaming query to the LLM.

        Args:
            user_prompt: The prompt to send.
            model: Optional model to use, overriding the default instance model.
            use_history: Whether to include chat history.
            display_output: Whether to display the output incrementally using IPython display.
            json_format: Whether to request JSON format (overrides instance default).
            reasoning_effort: Effort level for reasoning models.
            return_generator: If True, returns a generator yielding chunks. If False, returns the full response string.
            tools: Optional list of tools to use.
            tool_choice: Optional tool choice strategy.
            history_limit: Optional override for history limit.
            **kwargs: Additional arguments passed to the API call.

        Yields:
            Accumulated response text as it arrives (if return_generator=True).
        Returns:
            The full response string (if return_generator=False).
        """
        # Reset tool calls
        self.tool_calls = []

        # Resolve Overrides (Argument > Instance Variable)
        target_json_format = (
            json_format if json_format is not None else self.json_format
        )
        target_model = model if model is not None else self.model
        target_reasoning_effort = (
            reasoning_effort if reasoning_effort is not None else self.reasoning_effort
        )
        target_tools = tools if tools is not None else self.tools
        target_tool_choice = (
            tool_choice if tool_choice is not None else self.tool_choice
        )

        target_history_limit = (
            history_limit if history_limit is not None else self.history_limit
        )

        client = self._get_client_for_model(target_model)

        messages = self._prepare_messages(
            user_prompt, use_history, history_limit=target_history_limit
        )
        request_kwargs = self._prepare_request_kwargs(
            messages,
            stream=True,
            json_format=target_json_format,
            model=target_model,
            reasoning_effort=target_reasoning_effort,
            tools=target_tools,
            tool_choice=target_tool_choice,
            **kwargs,
        )

        response_stream = client.chat.completions.create(**request_kwargs)

        def stream_generator():
            output = ""
            display_handle = None
            collected_tool_calls = {}

            if display_output:
                display_handle = display(Markdown(output), display_id=True)

            for chunk in response_stream:
                delta = chunk.choices[0].delta
                content = delta.content

                # Handle content
                if content:
                    output += content
                    if display_handle:
                        display_handle.update(Markdown(output))
                    yield output

                # Handle tool calls
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }

                        if tc_chunk.id:
                            collected_tool_calls[idx]["id"] += tc_chunk.id

                        if tc_chunk.function:
                            if tc_chunk.function.name:
                                collected_tool_calls[idx]["function"]["name"] += (
                                    tc_chunk.function.name
                                )
                            if tc_chunk.function.arguments:
                                collected_tool_calls[idx]["function"]["arguments"] += (
                                    tc_chunk.function.arguments
                                )

            # Update state after stream finishes
            if target_json_format and output:
                output = clean_json(output)
            self.response = output
            if collected_tool_calls:
                self.tool_calls = list(collected_tool_calls.values())

            # Also check for XML-formatted tool calls in the full content
            if output:
                xml_tool_calls = self._parse_xml_tool_calls(output)
                if xml_tool_calls:
                    self.tool_calls.extend(xml_tool_calls)

            self._update_history(
                user_prompt,
                output if output else None,
                self.tool_calls if self.tool_calls else None,
                # Stream extraction of thought_signature is skipped for now as it usually appears at the very end
                # and might require more complex chunk accumulation logic.
            )

        gen = stream_generator()

        if return_generator:
            return gen
        else:
            # Consume generator to ensure side effects run
            for _ in gen:
                pass
            return self.response

    def append_tool_result(self, tool_outputs: List[Dict[str, Any]]):
        """
        Append the results of tool executions to the chat history.

        Args:
            tool_outputs: A list of dictionaries, where each dictionary contains:
                - tool_call_id: The ID of the tool call.
                - output: The output of the tool execution.
        """
        for tool_output in tool_outputs:
            output_content = tool_output["output"]
            if isinstance(output_content, Image.Image):
                output_content = "[Image created]"
            elif isinstance(output_content, bytes):
                output_content = "[Audio created]"
            elif not isinstance(output_content, str):
                try:
                    output_content = json.dumps(output_content)
                except (TypeError, ValueError):
                    output_content = f"[{type(output_content).__name__} object created]"

            self.chat_history.append(
                {
                    "role": "tool",
                    "content": output_content,
                    "tool_call_id": tool_output["tool_call_id"],
                }
            )

    def display_response(self):
        """Display the response in the notebook using Markdown or JSON pretty print."""
        if self.json_format:
            pretty_print_json(self.response)
        else:
            display(Markdown(self.response))

    def get_chat_history_as_string(self) -> str:
        """
        Get the chat history as a formatted string.

        Returns:
            str: The formatted chat history.
        """
        history: List[str] = []
        for msg in self.chat_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            if role == "User":
                history.append(f"**User**: {content}")
            elif role == "Assistant":
                history.append(f"**Assistant**: {content}")
                if "tool_calls" in msg:
                    for tool_call in msg["tool_calls"]:
                        func_name = tool_call["function"]["name"]
                        args = tool_call["function"]["arguments"]
                        history.append(f"**Assistant Tool Call**: {func_name}({args})")
            elif role == "Tool":
                history.append(f"**Tool Output**: {content}")

        return "\n\n".join(history)

    @property
    def clean_chat_history(self) -> List[Dict[str, str]]:
        """
        Get the chat history as a list of dictionaries containing only role and content.

        Only includes messages from 'assistant' or 'user' roles that have non-empty content.

        Returns:
            List[Dict[str, str]]: A list of dictionaries with 'role' and 'content' keys.
        """
        return [
            {"role": h["role"], "content": h["content"]}
            for h in self.chat_history
            if h["role"] in ("assistant", "user") and h["content"]
        ]

    def display_chat_history(self):
        """Display the chat history in the notebook."""
        display(Markdown(self.get_chat_history_as_string()))

    def get_tool_responses(
        self,
        max_iterations: int = 50,
    ) -> str:
        """
        Execute pending tool calls and continue the conversation until no more tool calls are made.

        Args:
            max_iterations: Maximum number of request-response cycles to prevent infinite loops.

        Returns:
            str: The final response from the assistant after all tool executions.
        """
        response = self.response
        iterations = 0

        while self.tool_calls and iterations < max_iterations:
            print(self.tool_calls)
            tool_response = handle_tool_call(self.tool_calls, functions=self.functions)
            self.append_tool_result(tool_response)
            query_response = self.query(tools=self.tools)

            if not query_response and not self.tool_calls:
                # Retry strategy: If LLM returns empty string after tools ran, prompt it again
                if self.chat_history and self.chat_history[-1]["role"] == "assistant":
                    self.chat_history.pop()
                query_response = self.query(tools=self.tools)

            if query_response:
                if response:
                    response += "\n\n" + query_response
                else:
                    response = query_response

            iterations += 1

        return response

    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> Image.Image:
        """
        Generate an image using the specified model.

        Args:
            prompt: The prompt to generate the image for.
            model: Optional model to use, overriding the default instance image_model.
            size: The size of the image to generate. Defaults to "1024x1024".
            quality: The quality of the image to generate. Defaults to "standard".

        Returns:
            Image.Image: The generated image as a PIL Image object.
        """
        # Resolve Overrides (Argument > Instance Variable)
        target_model = model if model is not None else self.image_model
        client = self._get_client_for_model(target_model)
        response = client.images.generate(  # pyrefly: ignore
            model=target_model,
            prompt=prompt,
            size=size,
            quality=quality,
            response_format="b64_json",
        )

        if not response.data or not response.data[0].b64_json:
            raise ValueError("No image data returned from API")

        image_data = base64.b64decode(response.data[0].b64_json)
        return Image.open(io.BytesIO(image_data))

    def generate_tts(
        self,
        text: str,
        model: Optional[str] = None,
        voice: str = "onyx",
        speed: float = 1.0,
    ) -> bytes:
        """
        Generate speech from text using the specified model.

        Args:
            text: The text to generate speech for.
            model: Optional model to use, overriding the default instance tts_model.
            voice: The voice to use for generation. Defaults to "alloy".
            speed: The speed of the speech generation. Defaults to 1.0.

        Returns:
            bytes: The generated audio content.
        """
        # Resolve Overrides (Argument > Instance Variable)
        target_model = model if model is not None else self.tts_model
        client = self._get_client_for_model(target_model)
        response = client.audio.speech.create(
            model=target_model,
            input=text,
            voice=voice,
            speed=speed,
        )
        return response.content

    def transcribe_audio(
        self,
        audio_source: Union[bytes, str, io.IOBase],
        model: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio from a file or bytes.

        Args:
            audio_source: The audio source. Can be a file path (str), audio bytes (bytes), or a file-like object.
            model: Optional model to use, overriding the default instance transcription_model.

        Returns:
            str: The transcribed text.
        """
        # Resolve Overrides (Argument > Instance Variable)
        target_model = model if model is not None else self.transcription_model
        client = self._get_client_for_model(target_model)

        file_obj = None
        should_close = False

        # Determine strict or flexible usage based on model
        is_gemini = "gemini" in target_model

        try:
            if is_gemini:
                # Gemini via OpenAI compat usually requires chat completion with inline data
                # because the audio/transcriptions endpoint might not be supported.
                audio_bytes = None
                mime_type = "audio/wav"  # Default

                if isinstance(audio_source, str):
                    mime_type_guess = mimetypes.guess_type(audio_source)[0]
                    if mime_type_guess:
                        mime_type = mime_type_guess
                    with open(audio_source, "rb") as f:
                        audio_bytes = f.read()
                elif isinstance(audio_source, bytes):
                    audio_bytes = audio_source
                elif isinstance(audio_source, io.IOBase):
                    audio_bytes = audio_source.read()
                    if hasattr(audio_source, "name") and audio_source.name:
                        mime_type_guess = mimetypes.guess_type(audio_source.name)[0]
                        if mime_type_guess:
                            mime_type = mime_type_guess
                else:
                    raise ValueError("Invalid audio_source type.")

                b64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                response = client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Transcribe the following audio.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{b64_audio}"
                                    },
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content or ""

            else:
                # Standard OpenAI transcription endpoint
                if isinstance(audio_source, str):
                    file_obj = open(audio_source, "rb")
                    should_close = True
                elif isinstance(audio_source, bytes):
                    file_obj = io.BytesIO(audio_source)
                    file_obj.name = "audio.wav"
                elif isinstance(audio_source, io.IOBase):
                    file_obj = audio_source
                else:
                    raise ValueError("Invalid audio_source type.")

                response = client.audio.transcriptions.create(  # pyrefly: ignore
                    model=target_model,
                    file=file_obj,
                )
                return response.text

        finally:
            if should_close and file_obj:
                file_obj.close()

    def generate_embedding(
        self,
        text: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using the specified model.

        Args:
            text: A list of strings to generate embeddings for.
            model: Optional model to use, overriding the default instance embedding_model.

        Returns:
            List[List[float]]: A list of embedding vectors.
        """
        target_model = model if model is not None else self.embedding_model
        client = self._get_client_for_model(target_model)

        response = client.embeddings.create(
            model=target_model,
            input=text,
        )
        return [data.embedding for data in response.data]


if __name__ == "__main__":
    llm = LLMQuery(system_prompt="", model="gemini-flash-lite-latest")
    a = llm.query(user_prompt="Hi", display_output=True)
    print(a)
