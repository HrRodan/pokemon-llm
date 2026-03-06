"""
tool_definition.py — Ergonomic tool registration for LLMQuery.

Provides three complementary ways to define an OpenAI-compatible tool:

1. **Pure-function inference** — annotate a function with ``@tool`` and the
   schema is derived entirely from type hints and the docstring.  No extra
   classes required::

       @tool(description="Returns the current weather for a city.")
       def get_weather(city: str, units: str = "metric") -> str: ...

2. **Pydantic-backed validation** — pass a ``BaseModel`` subclass to get full
   field-level validation at dispatch time.  The function receives a *single*
   validated model instance instead of raw ``**kwargs``::

       class WeatherArgs(BaseModel):
           city: str = Field(description="City name.")
           units: str = Field(default="metric")

       @tool(schema=WeatherArgs)
       def get_weather(args: WeatherArgs) -> str:
           return fetch(args.city, args.units)

2. **Manual generation** — ``function_to_tool_schema(fn)`` and ``pydantic_to_tool_schema(name, model)``

Public API
----------
- ``tool`` — decorator factory
- ``get_tool_schema`` — safely extract schema from a decorated fn

Attributes attached to decorated functions
------------------------------------------
- ``.__tool_schema__`` — OpenAI-compatible tool definition dict
- ``.__pydantic_model__`` — the ``BaseModel`` subclass, or ``None``
"""

from __future__ import annotations

import inspect
import re
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    get_args,
    get_origin,
)

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Internal type helpers
# ---------------------------------------------------------------------------

_PY_TO_JSON: Dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    bytes: "string",
}


def _py_type_to_json(annotation: Any) -> Tuple[str, bool]:
    """
    Map a Python type annotation to a JSON Schema type string.

    Returns:
        Tuple of (json_type, is_required).  ``is_required`` is ``False``
        when the annotation is ``Optional[X]`` (i.e. ``Union[X, None]``).
    """
    if annotation is inspect.Parameter.empty:
        return "string", True

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[X] == Union[X, None] — detect None in args
    if origin is not None and hasattr(origin, "__name__") is False:
        # Generic alias (Union, List, Dict, …)
        import types as _types

        is_union = origin is _types.UnionType if hasattr(_types, "UnionType") else False

        # Also handle typing.Union (before Python 3.10)
        try:
            import typing as _typing

            if origin is _typing.Union:
                is_union = True
        except Exception:
            pass

        if is_union and type(None) in args:
            # Optional — recurse on the non-None arg
            inner = next((a for a in args if a is not type(None)), str)
            json_type, _ = _py_type_to_json(inner)
            return json_type, False

        # List[X] → array
        if origin is list:
            return "array", True

        # Dict[K, V] → object
        if origin is dict:
            return "object", True

    # Plain type
    return _PY_TO_JSON.get(annotation, "string"), True


def _parse_param_descriptions(docstring: Optional[str]) -> Dict[str, str]:
    """
    Extract per-parameter descriptions from a Google-style docstring.

    Looks for an ``Args:`` section and parses lines of the form::

        param_name: Description text.
            Continuation lines are included.

    Returns a mapping of ``{param_name: description}``.
    """
    if not docstring:
        return {}

    descriptions: Dict[str, str] = {}
    in_args = False
    current_param: Optional[str] = None
    current_lines: List[str] = []

    for raw_line in docstring.splitlines():
        line = raw_line.strip()

        if re.match(r"^Args\s*:", line):
            in_args = True
            current_param = None
            current_lines = []
            continue

        if in_args:
            # A new top-level section ends the Args block
            if re.match(r"^[A-Z][a-z]+\s*:", line) and not re.match(r"^\w+\s*:", line):
                break
            # Detect a new parameter definition: "name: description"
            param_match = re.match(r"^(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)", line)
            if param_match and not line.startswith(" "):
                if current_param:
                    descriptions[current_param] = " ".join(current_lines).strip()
                current_param = param_match.group(1)
                current_lines = [param_match.group(2)]
            elif current_param and line:
                current_lines.append(line)
            elif current_param and not line:
                # Blank line — flush and reset
                descriptions[current_param] = " ".join(current_lines).strip()
                current_param = None
                current_lines = []

    if current_param:
        descriptions[current_param] = " ".join(current_lines).strip()

    return descriptions


def _extract_summary(docstring: Optional[str]) -> str:
    """Return the first non-blank line of a docstring as the summary."""
    if not docstring:
        return ""
    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


# ---------------------------------------------------------------------------
# Schema builders
# ---------------------------------------------------------------------------


def function_to_tool_schema(
    fn: Callable, description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Derive an OpenAI-compatible tool definition dict from a Python function.

    Type hints are required for parameter schema inference.  Parameters
    without annotations are treated as ``string``.  ``Optional[X]`` params
    are omitted from the ``required`` list.

    Args:
        fn: The Python callable to introspect.
        description: Override the function description.  Falls back to the
            first line of the docstring.

    Returns:
        A dict conforming to the OpenAI function-tool schema.
    """
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn)
    hints = fn.__annotations__

    effective_description = description or _extract_summary(doc) or fn.__name__
    param_descriptions = _parse_param_descriptions(doc)

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "args", "kwargs"):
            continue

        annotation = hints.get(param_name, inspect.Parameter.empty)
        json_type, is_required = _py_type_to_json(annotation)

        prop: Dict[str, Any] = {"type": json_type}

        # Attach per-parameter description from docstring
        if param_name in param_descriptions:
            prop["description"] = param_descriptions[param_name]

        properties[param_name] = prop

        # Only required if no default AND not Optional
        has_default = param.default is not inspect.Parameter.empty
        if is_required and not has_default:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": effective_description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def pydantic_to_tool_schema(
    name: str,
    model: Type[BaseModel],
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derive an OpenAI-compatible tool definition from a Pydantic BaseModel.

    The model's ``model_json_schema()`` is used verbatim for the parameters
    block.  The description falls back to the model's class docstring.

    Args:
        name: The tool / function name exposed to the LLM.
        model: The Pydantic ``BaseModel`` subclass that defines the arguments.
        description: Override the tool description.  Falls back to the
            model's docstring.

    Returns:
        A dict conforming to the OpenAI function-tool schema.
    """
    effective_description = (
        description or _extract_summary(inspect.getdoc(model)) or name
    )
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": effective_description,
            "parameters": model.model_json_schema(),
        },
    }


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------


def tool(
    fn: Optional[Callable] = None,
    *,
    description: Optional[str] = None,
    schema: Optional[Type[BaseModel]] = None,
    name: Optional[str] = None,
) -> Any:
    """
    Decorator that registers a function as an LLM tool.

    Attaches ``.__tool_schema__`` (OpenAI-compatible dict) and
    ``.__pydantic_model__`` (Pydantic class or ``None``) to the function.

    The decorator can be used with or without arguments::

        # Pure-function inference
        @tool
        def get_weather(city: str) -> str: ...

        # With explicit description
        @tool(description="Fetch the current weather.")
        def get_weather(city: str) -> str: ...

        # Pydantic-backed with automatic validation at dispatch time
        @tool(schema=WeatherArgs)
        def get_weather(args: WeatherArgs) -> str: ...

        # Override both name and description
        @tool(name="weather_tool", description="Fetch weather.", schema=WeatherArgs)
        def get_weather(args: WeatherArgs) -> str: ...

    Args:
        fn: The function to decorate (when used without parentheses).
        description: Override the tool description.
        schema: Optional Pydantic ``BaseModel`` subclass for argument validation.
        name: Override the function name exposed to the LLM.

    Returns:
        The original function, unmodified except for the two new attributes.
    """

    def _decorate(func: Callable) -> Callable:
        effective_name = name or func.__name__

        if schema is not None:
            func.__tool_schema__ = pydantic_to_tool_schema(
                effective_name, schema, description
            )
            func.__pydantic_model__ = schema
        else:
            func.__tool_schema__ = function_to_tool_schema(func, description)
            if effective_name != func.__name__:
                func.__tool_schema__["function"]["name"] = effective_name
            func.__pydantic_model__ = None

        return func

    # Support both @tool and @tool(...) usage
    if fn is not None:
        # Called as @tool without arguments
        return _decorate(fn)
    # Called as @tool(...) — return the decorator
    return _decorate


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------


def get_tool_schema(fn: Callable) -> Dict[str, Any]:
    """
    Retrieve the tool schema attached to a ``@tool``-decorated function.

    Args:
        fn: A function previously decorated with ``@tool``.

    Returns:
        The OpenAI-compatible tool definition dict.

    Raises:
        ValueError: If the function was not decorated with ``@tool``.
    """
    schema = getattr(fn, "__tool_schema__", None)
    if schema is None:
        raise ValueError(
            f"Function '{fn.__name__}' has no __tool_schema__. "
            "Did you forget to decorate it with @tool?"
        )
    return schema
