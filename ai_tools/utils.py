"""
utils.py — Shared utility functions for the ai_tools package.

Contains stateless helpers used across the package and exported for external
callers:

- ``generate_short_id()`` — compact unique ID for tool call tagging
- ``clean_json()`` — strips Markdown code fences so JSON strings can be parsed
- ``pretty_print_json()`` — renders JSON with syntax highlighting in notebooks
- ``handle_tool_call()`` — dispatches LLM tool-call requests to Python callables
- ``handle_tool_call_async()`` — concurrent version using ``asyncio.to_thread``
"""

import asyncio
import contextvars
import json
import logging
import uuid
from typing import Dict, List, Any, Callable, Optional

async def run_in_thread_with_context(func: Callable, *args, **kwargs) -> Any:
    """Run a blocking function in a separate thread while preserving contextvars."""
    ctx = contextvars.copy_context()
    def wrapper():
        return ctx.run(func, *args, **kwargs)
    return await asyncio.to_thread(wrapper)


from pydantic import ValidationError
from IPython.display import Markdown, display
from .tracing import trace_tool_execution, update_span


def generate_short_id() -> str:
    """
    Generate a short, URL-safe 8-character unique identifier.

    Uses the first 8 hex characters of a random UUID4.  Collision probability
    is negligible for the tool-call-tagging use case (one per LLM response).

    Returns:
        str: An 8-character lowercase hex string, e.g. ``"3f9a1b2c"``.
    """
    return uuid.uuid4().hex[:8]


def pretty_print_json(data) -> None:
    """
    Render JSON in a notebook cell with syntax highlighting.

    If ``data`` is a raw JSON string it is parsed first, then re-serialised
    with indentation.  The result is displayed as a fenced Markdown code block
    so Jupyter renders it with colour.

    Silently logs a warning instead of raising if the input is invalid JSON.

    Args:
        data: A Python ``dict`` / ``list``, or a JSON-encoded ``str``.
    """
    try:
        # If input is a raw string, parse it into a Python object first so we
        # can re-serialise it with consistent indentation.
        if isinstance(data, str):
            data = json.loads(data)

        pretty_json = json.dumps(data, indent=2, ensure_ascii=False)
        display(Markdown(f"```json\n{pretty_json}\n```"))

    except json.JSONDecodeError:
        logging.warning("Invalid JSON string provided to pretty_print_json.")
    except Exception as e:
        logging.error(f"Error prettifying JSON: {e}")


def clean_json(text: str) -> str:
    """
    Strip Markdown code fences from an LLM-returned JSON string.

    Some models wrap JSON output in a Markdown code block even when asked not
    to.  This strips those fences so the result can be passed directly to
    ``json.loads()``.

    Handles both::

        ```json
        { ... }
        ```

    and::

        ```
        { ... }
        ```

    Args:
        text (str): The raw LLM output, potentially wrapped in Markdown.

    Returns:
        str: The cleaned JSON string with leading/trailing whitespace removed.
    """
    cleaned_text = text.strip()

    # Remove opening fence — prefer the more specific "```json" over plain "```"
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json") :]
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[len("```") :]

    # Remove closing fence
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[: -len("```")]

    return cleaned_text.strip()


def sanitize_tool_name(name: Optional[str]) -> str:
    """
    Return a sanitised version of a tool call name.

    Some providers (especially with OpenRouter and specific model formats)
    may accidentally include special tokens, suffixes, or 'functions.'
    prefix in the tool call name. This strips them.

    Args:
        name: Raw tool name from the API or XML parser.

    Returns:
        str: A clean string containing only the core tool name.
    """
    if not name:
        return "unknown_function"

    # 1. Strip everything from '<' onwards — removes "<|channel|>commentary" etc.
    name = name.split("<")[0]

    # 2. Strip everything from '|' onwards — fallback for incomplete tokens
    name = name.split("|")[0]

    # 3. Strip everything from '(' onwards — removes model hallucinated calls like "fn(arg)"
    name = name.split("(")[0]

    # 4. Remove common prefixes like "functions." or "function."
    if name.startswith("functions."):
        name = name[len("functions.") :]
    elif name.startswith("function."):
        name = name[len("function.") :]

    # 5. Remove common model-specific suffixes — e.g. "func_namecommentary"
    # We only do this if the name is long and ends exactly with these words.
    for suffix in ["commentary", "analysis", "thought", "call"]:
        if name.endswith(suffix) and name != suffix:
            name = name[: -len(suffix)]

    # Finally, clean any remaining whitespace
    return name.strip()


def handle_tool_call(
    tool_calls: List[Dict[str, Any]],
    functions: List[Callable],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """
    Dispatch LLM tool-call requests to their Python implementations.

    Iterates over the tool calls requested by the model, looks up the
    matching Python function by name, parses arguments from JSON, executes
    the function, and collects results.  Any error at any stage is caught and
    returned as a string result so the model can be informed of the failure
    and potentially retry with corrected arguments.

    Args:
        tool_calls: List of tool-call dicts as produced by
            ``LLMQuery._extract_and_sanitize_tool_calls()``.  Each dict must
            have the shape::

                {
                    "id": "call_abc123",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "Berlin"}'  # JSON string or dict
                    }
                }

        functions: Python callables available to the model.  The function's
            ``__name__`` must match the ``function.name`` in the tool call.
        logger: Optional logger for tracing call/result/error events.

    Returns:
        List of result dicts, one per tool call, each with the shape::

            {
                "tool_call_id": "call_abc123",
                "output": "The weather in Berlin is 22°C",
                "arguments": {"city": "Berlin"},
                "name": "get_weather"
            }

        On error, ``output`` is the string ``"Error: <message>"`` so the LLM
        receives the failure context and can decide how to proceed.
    """
    tool_response = []

    # Build a name → callable map for O(1) lookup instead of linear search.
    function_map = {f.__name__: f for f in functions}

    for tool_call in tool_calls:
        tool_id = tool_call.get("id", "unknown_id")
        raw_name = tool_call.get("function", {}).get("name", "unknown_function")
        function_name = sanitize_tool_name(raw_name)
        arguments_str = tool_call.get("function", {}).get("arguments", "")
        arguments = {}

        # ------------------------------------------------------------
        # Step 1: Parse the arguments before tracing so they are captured
        # ------------------------------------------------------------
        try:
            if arguments_str:
                if isinstance(arguments_str, dict):
                    arguments = arguments_str
                else:
                    arguments = json.loads(arguments_str)
        except Exception as e:
            arguments = {"error": f"Failed to parse arguments JSON: {e}", "raw": arguments_str}

        with trace_tool_execution(function_name, arguments) as span:
            try:
                # ------------------------------------------------------------
                # Step 2: Validate the function name.
                # ------------------------------------------------------------
                if function_name not in function_map:
                    raise ValueError(
                        f"Function '{function_name}' not found. "
                        f"Available: {list(function_map.keys())}"
                    )
                
                if "error" in arguments and "raw" in arguments:
                    raise ValueError(arguments["error"])

                # ------------------------------------------------------------
                # Step 3: Execute the function.
                # ------------------------------------------------------------
                function_to_call = function_map[function_name]
                pydantic_model = getattr(function_to_call, "__pydantic_model__", None)
                if logger:
                    logger.info(f"TOOL CALL: {function_name} | Args: {arguments}")
                try:
                    if pydantic_model is not None:
                        try:
                            validated = pydantic_model(**arguments)
                        except ValidationError as e:
                            raise ValueError(f"Argument validation failed: {e}")
                        result = function_to_call(validated)
                    else:
                        result = function_to_call(**arguments)
                except Exception as e:
                    raise RuntimeError(f"Error while executing '{function_name}': {e}")

                # Log a truncated preview of potentially large outputs.
                if logger:
                    str_result = str(result)
                    if len(str_result) > 500:
                        str_result = str_result[:500] + "... [truncated]"
                    logger.info(f"TOOL OUTPUT ({function_name}): {str_result}")
                
                update_span(span, output=str(result) if result else "")

            except Exception as e:
                # Return the error as a string result so the LLM can read it.
                result = f"Error: {str(e)}"
                if logger:
                    logger.warning(f"TOOL ERROR ({function_name}): {e}")
                
                update_span(span, output=result, level="ERROR", status_message=str(e))

        tool_response.append(
            {
                "tool_call_id": tool_id,
                "output": result,
                "arguments": arguments,
                "name": function_name,
            }
        )

    return tool_response


async def handle_tool_call_async(
    tool_calls: List[Dict[str, Any]],
    functions: List[Callable],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """
    Concurrent version of :func:`handle_tool_call`.

    Dispatches **all** tool calls in parallel using ``asyncio.to_thread``,
    which offloads each synchronous function to a separate thread.  This is
    ideal for I/O-bound tool functions (e.g. LLM API calls, HTTP requests)
    where wall-clock time is dominated by network latency.

    Error handling mirrors the synchronous version: each tool call is
    individually wrapped so one failure does not cancel the others.

    Args:
        tool_calls: List of tool-call dicts (same format as :func:`handle_tool_call`).
        functions: Python callables available to the model.
        logger: Optional logger for tracing call/result/error events.

    Returns:
        List of result dicts in the **same order** as *tool_calls*.
        On error, ``output`` is ``"Error: <message>"``.
    """
    # Build a name → callable map for O(1) lookup.
    function_map = {f.__name__: f for f in functions}

    async def _dispatch_one(tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Parse, validate, and execute a single tool call in a thread."""
        tool_id = tool_call.get("id", "unknown_id")
        function_name = tool_call.get("function", {}).get("name", "unknown_function")
        arguments_str = tool_call.get("function", {}).get("arguments", "")
        arguments = {}

        # --- Parse arguments before tracing ---
        try:
            if arguments_str:
                if isinstance(arguments_str, dict):
                    arguments = arguments_str
                else:
                    arguments = json.loads(arguments_str)
        except Exception as e:
            arguments = {"error": f"Failed to parse arguments JSON: {e}", "raw": arguments_str}

        with trace_tool_execution(function_name, arguments) as span:
            try:
                # --- Validate function name ---
                if function_name not in function_map:
                    raise ValueError(
                        f"Function '{function_name}' not found. "
                        f"Available: {list(function_map.keys())}"
                    )
                
                if "error" in arguments and "raw" in arguments:
                    raise ValueError(arguments["error"])

                # --- Execute in a separate thread ---
                # When the function carries .__pydantic_model__, validate first
                # and pass a typed model instance; otherwise use raw **kwargs.
                function_to_call = function_map[function_name]
                pydantic_model = getattr(function_to_call, "__pydantic_model__", None)
                if logger:
                    logger.info(f"TOOL CALL (async): {function_name} | Args: {arguments}")

                if pydantic_model is not None:
                    try:
                        validated = pydantic_model(**arguments)
                    except ValidationError as e:
                        raise ValueError(f"Argument validation failed: {e}")
                    result = await run_in_thread_with_context(function_to_call, validated)
                else:
                    result = await run_in_thread_with_context(function_to_call, **arguments)

                if logger:
                    str_result = str(result)
                    if len(str_result) > 500:
                        str_result = str_result[:500] + "... [truncated]"
                    logger.info(f"TOOL OUTPUT ({function_name}): {str_result}")
                
                update_span(span, output=str(result) if result else "")

            except Exception as e:
                result = f"Error: {str(e)}"
                if logger:
                    logger.warning(f"TOOL ERROR ({function_name}): {e}")
                
                update_span(span, output=result, level="ERROR", status_message=str(e))

        return {
            "tool_call_id": tool_id,
            "output": result,
            "arguments": arguments,
            "name": function_name,
        }

    # Launch all tool calls concurrently and collect results in order.
    return list(await asyncio.gather(*[_dispatch_one(tc) for tc in tool_calls]))
