"""
utils.py — Shared utility functions for the ai_tools package.

Contains stateless helpers used across the package and exported for external
callers:

- ``generate_short_id()`` — compact unique ID for tool call tagging
- ``clean_json()`` — strips Markdown code fences so JSON strings can be parsed
- ``pretty_print_json()`` — renders JSON with syntax highlighting in notebooks
- ``handle_tool_call()`` — dispatches LLM tool-call requests to Python callables
"""

import json
import logging
import uuid
from typing import Dict, List, Any, Callable, Optional
from IPython.display import Markdown, display


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
        function_name = tool_call.get("function", {}).get("name", "unknown_function")
        arguments_str = tool_call.get("function", {}).get("arguments", "")
        arguments = {}

        try:
            # ----------------------------------------------------------------
            # Step 1: Parse the arguments.
            # The OpenAI API returns arguments as a JSON string; some models
            # (or XML-parsed fallback tool calls) may already provide a dict.
            # ----------------------------------------------------------------
            if arguments_str:
                if isinstance(arguments_str, dict):
                    # Already parsed (e.g. from XML fallback path)
                    arguments = arguments_str
                else:
                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Failed to parse arguments JSON: {e}")

            # ----------------------------------------------------------------
            # Step 2: Validate the function name.
            # Returning a descriptive error lets the model self-correct rather
            # than crashing the agent loop entirely.
            # ----------------------------------------------------------------
            if function_name not in function_map:
                raise ValueError(
                    f"Function '{function_name}' not found. "
                    f"Available: {list(function_map.keys())}"
                )

            # ----------------------------------------------------------------
            # Step 3: Execute the function.
            # Wrap in a separate try/except so execution errors are distinct
            # from argument-parsing errors in the logs.
            # ----------------------------------------------------------------
            function_to_call = function_map[function_name]
            if logger:
                logger.info(f"TOOL CALL: {function_name} | Args: {arguments}")
            try:
                result = function_to_call(**arguments)
            except Exception as e:
                raise RuntimeError(f"Error while executing '{function_name}': {e}")

            # Log a truncated preview of potentially large outputs.
            if logger:
                str_result = str(result)
                if len(str_result) > 500:
                    str_result = str_result[:500] + "... [truncated]"
                logger.info(f"TOOL OUTPUT ({function_name}): {str_result}")

        except Exception as e:
            # Return the error as a string result so the LLM can read it.
            result = f"Error: {str(e)}"
            if logger:
                logger.warning(f"TOOL ERROR ({function_name}): {e}")

        tool_response.append(
            {
                "tool_call_id": tool_id,
                "output": result,
                "arguments": arguments,
                "name": function_name,
            }
        )

    return tool_response
