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
from typing import Dict, List, Any, Callable, Optional, Tuple
from pydantic import ValidationError
from .tracing import trace_tool_execution, update_span

async def run_in_thread_with_context(func: Callable, *args, **kwargs) -> Any:
    """Run a blocking function in a separate thread while preserving contextvars."""
    ctx = contextvars.copy_context()
    def wrapper():
        return ctx.run(func, *args, **kwargs)
    return await asyncio.to_thread(wrapper)


def generate_short_id() -> str:
    """
    Generate a short, URL-safe 8-character unique identifier.
    """
    return uuid.uuid4().hex[:8]


def clean_json(text: str) -> str:
    """
    Strip Markdown code fences from an LLM-returned JSON string.
    """
    cleaned_text = text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json") :]
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[len("```") :]

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[: -len("```")]

    return cleaned_text.strip()


def sanitize_tool_name(name: Optional[str]) -> str:
    """
    Return a sanitised version of a tool call name.
    """
    if not name:
        return "unknown_function"

    name = name.split("<")[0]
    name = name.split("|")[0]
    name = name.split("(")[0]

    if name.startswith("functions."):
        name = name[len("functions.") :]
    elif name.startswith("function."):
        name = name[len("function.") :]

    for suffix in ["commentary", "analysis", "thought", "call"]:
        if name.endswith(suffix) and name != suffix:
            name = name[: -len(suffix)]

    return name.strip()


def _prepare_tool_dispatch(
    tool_call: Dict[str, Any],
    function_map: Dict[str, Callable],
) -> Tuple[str, str, Dict[str, Any], Optional[Callable], Optional[type], Optional[str]]:
    """
    Common preparation logic for sync/async tool dispatch.
    
    Returns:
        (tool_id, function_name, arguments, function_to_call, pydantic_model, error_msg)
    """
    tool_id = tool_call.get("id", "unknown_id")
    raw_name = tool_call.get("function", {}).get("name", "unknown_function")
    function_name = sanitize_tool_name(raw_name)
    arguments_str = tool_call.get("function", {}).get("arguments", "")
    
    arguments = {}
    error_msg = None
    function_to_call = None
    pydantic_model = None

    # 1. Parse arguments
    try:
        if arguments_str:
            if isinstance(arguments_str, dict):
                arguments = arguments_str
            else:
                arguments = json.loads(arguments_str)
    except Exception as e:
        error_msg = f"Failed to parse arguments JSON: {e}"
        arguments = {"error": error_msg, "raw": arguments_str}

    # 2. Resolve function
    if not error_msg:
        function_to_call = function_map.get(function_name)
        if not function_to_call:
            error_msg = f"Function '{function_name}' not found. Available: {list(function_map.keys())}"
        else:
            pydantic_model = getattr(function_to_call, "__pydantic_model__", None)

    return tool_id, function_name, arguments, function_to_call, pydantic_model, error_msg


def handle_tool_call(
    tool_calls: List[Dict[str, Any]],
    functions: List[Callable],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """
    Dispatch LLM tool-call requests to their Python implementations (Synchronously).
    """
    tool_response = []
    function_map = {f.__name__: f for f in functions}

    for tool_call in tool_calls:
        tool_id, function_name, arguments, function_to_call, pydantic_model, error_msg = \
            _prepare_tool_dispatch(tool_call, function_map)

        with trace_tool_execution(function_name, arguments) as span:
            result = None
            try:
                if error_msg:
                    raise ValueError(error_msg)

                if logger:
                    logger.info(f"TOOL CALL: {function_name} | Args: {arguments}")

                # Execute
                if pydantic_model is not None:
                    try:
                        validated = pydantic_model(**arguments)
                    except ValidationError as e:
                        raise ValueError(f"Argument validation failed: {e}")
                    result = function_to_call(validated)
                else:
                    result = function_to_call(**arguments)

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

        tool_response.append({
            "tool_call_id": tool_id,
            "output": result,
            "arguments": arguments,
            "name": function_name,
        })

    return tool_response


async def handle_tool_call_async(
    tool_calls: List[Dict[str, Any]],
    functions: List[Callable],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """
    Concurrent version of handle_tool_call.
    """
    function_map = {f.__name__: f for f in functions}

    async def _dispatch_one(tool_call: Dict[str, Any]) -> Dict[str, Any]:
        tool_id, function_name, arguments, function_to_call, pydantic_model, error_msg = \
            _prepare_tool_dispatch(tool_call, function_map)

        with trace_tool_execution(function_name, arguments) as span:
            result = None
            try:
                if error_msg:
                    raise ValueError(error_msg)

                if logger:
                    logger.info(f"TOOL CALL (async): {function_name} | Args: {arguments}")

                # Execute in thread
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

    return list(await asyncio.gather(*[_dispatch_one(tc) for tc in tool_calls]))
