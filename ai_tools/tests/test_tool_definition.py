"""
Unit tests for ai_tools.tool_definition and the three tool registration styles.

Covers:
  - Schema inference from Python type hints (function_to_tool_schema)
  - Optional / default param handling (excluded from 'required')
  - Pydantic-backed schema generation (pydantic_to_tool_schema)
  - @tool decorator — bare, with args, Pydantic, name override
  - handle_tool_call — Pydantic dispatch (receives model instance)
  - handle_tool_call — validation error returns safe error string
  - handle_tool_call_async — same Pydantic path, async
  - LLMQuery._resolve_tools — all three tool registration styles:
      Style 1: @tool-decorated callable → schema extracted, fn auto-registered
      Style 2: raw dict + explicit functions list
      Style 3: mixed list, explicit functions take precedence
  - LLMQuery.as_tool() — schema + callable returned correctly
"""

import asyncio
import json
from typing import Optional
from pydantic import BaseModel, Field

from ai_tools.tool_definition import (
    tool,
    function_to_tool_schema,
    pydantic_to_tool_schema,
)
from ai_tools.utils import handle_tool_call, handle_tool_call_async
from ai_tools.tools import LLMQuery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_call(name: str, arguments: dict, call_id: str = "c1") -> dict:
    return {
        "id": call_id,
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


# ---------------------------------------------------------------------------
# function_to_tool_schema — schema inferred from type hints
# ---------------------------------------------------------------------------


class TestFunctionToToolSchema:
    def test_basic_type_hints(self):
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            ...

        schema = function_to_tool_schema(add)
        fn = schema["function"]
        assert schema["type"] == "function"
        assert fn["name"] == "add"
        assert fn["description"] == "Add two numbers."
        props = fn["parameters"]["properties"]
        assert props["a"]["type"] == "integer"
        assert props["b"]["type"] == "integer"
        assert fn["parameters"]["required"] == ["a", "b"]

    def test_str_and_float_hints(self):
        def measure(label: str, value: float) -> str:
            """Measure something."""
            ...

        schema = function_to_tool_schema(measure)
        props = schema["function"]["parameters"]["properties"]
        assert props["label"]["type"] == "string"
        assert props["value"]["type"] == "number"

    def test_bool_hint(self):
        def toggle(enabled: bool) -> None: ...

        schema = function_to_tool_schema(toggle)
        assert (
            schema["function"]["parameters"]["properties"]["enabled"]["type"]
            == "boolean"
        )

    def test_optional_param_not_required(self):
        def greet(name: str, greeting: Optional[str] = None) -> str:
            """Greet someone."""
            ...

        schema = function_to_tool_schema(greet)
        required = schema["function"]["parameters"]["required"]
        assert "name" in required
        assert "greeting" not in required

    def test_default_param_not_required(self):
        def search(query: str, limit: int = 10) -> str:
            """Search."""
            ...

        schema = function_to_tool_schema(search)
        required = schema["function"]["parameters"]["required"]
        assert "query" in required
        assert "limit" not in required

    def test_description_override(self):
        def fn(x: int) -> int:
            """Original docstring."""
            ...

        schema = function_to_tool_schema(fn, description="Custom description.")
        assert schema["function"]["description"] == "Custom description."

    def test_no_annotations_defaults_to_string(self):
        def raw_fn(x, y):
            """Raw fn."""
            ...

        schema = function_to_tool_schema(raw_fn)
        props = schema["function"]["parameters"]["properties"]
        assert props["x"]["type"] == "string"
        assert props["y"]["type"] == "string"

    def test_docstring_param_descriptions_included(self):
        def fn(city: str) -> str:
            """Get weather.

            Args:
                city: Name of the city to look up.
            """
            ...

        schema = function_to_tool_schema(fn)
        prop = schema["function"]["parameters"]["properties"]["city"]
        assert "description" in prop
        assert (
            "city" in prop["description"].lower()
            or "name" in prop["description"].lower()
        )


# ---------------------------------------------------------------------------
# pydantic_to_tool_schema
# ---------------------------------------------------------------------------


class TestPydanticToToolSchema:
    def test_schema_matches_model_json_schema(self):
        class WeatherArgs(BaseModel):
            """Get the current weather."""

            city: str = Field(description="The city name.")
            units: str = Field(default="metric")

        schema = pydantic_to_tool_schema("get_weather", WeatherArgs)
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "get_weather"
        assert schema["function"]["description"] == "Get the current weather."
        assert schema["function"]["parameters"] == WeatherArgs.model_json_schema()

    def test_description_override(self):
        class Args(BaseModel):
            """Original."""

            x: int

        schema = pydantic_to_tool_schema("fn", Args, description="Override.")
        assert schema["function"]["description"] == "Override."


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------


class TestToolDecorator:
    def test_attaches_schema_pure_function(self):
        @tool(description="Returns the sum.")
        def my_add(a: int, b: int) -> int: ...

        assert hasattr(my_add, "__tool_schema__")
        assert hasattr(my_add, "__pydantic_model__")
        assert my_add.__pydantic_model__ is None
        assert my_add.__tool_schema__["function"]["name"] == "my_add"
        assert my_add.__tool_schema__["function"]["description"] == "Returns the sum."

    def test_infers_schema_from_type_hints_without_description(self):
        """The @tool decorator derives schema entirely from type hints if no description given."""

        @tool
        def compute(value: float, scale: int) -> float:
            """Compute scaled value."""
            ...

        _schema = my_schema = compute.__tool_schema__["function"]
        assert my_schema["parameters"]["properties"]["value"]["type"] == "number"
        assert my_schema["parameters"]["properties"]["scale"]["type"] == "integer"
        assert my_schema["description"] == "Compute scaled value."

    def test_attaches_schema_pydantic(self):
        class AddArgs(BaseModel):
            """Adds two numbers."""

            a: int
            b: int

        @tool(schema=AddArgs)
        def pydantic_add(args: AddArgs) -> int: ...

        assert pydantic_add.__pydantic_model__ is AddArgs
        assert (
            pydantic_add.__tool_schema__["function"]["parameters"]
            == AddArgs.model_json_schema()
        )

    def test_decorator_without_parens(self):
        @tool
        def bare(x: str) -> str:
            """Bare decorated fn."""
            ...

        assert hasattr(bare, "__tool_schema__")
        assert bare.__pydantic_model__ is None

    def test_name_override(self):
        @tool(name="custom_name", description="Custom.")
        def original_name(x: str) -> str: ...

        assert original_name.__tool_schema__["function"]["name"] == "custom_name"

    def test_function_still_callable(self):
        @tool
        def double(x: int) -> int:
            """Doubles x."""
            return x * 2

        assert double(5) == 10


# ---------------------------------------------------------------------------
# LLMQuery._resolve_tools — three registration styles
# ---------------------------------------------------------------------------


class TestLLMQueryResolveTools:
    """
    Tests for LLMQuery._resolve_tools(), which powers the three tool styles.
    Uses the static method directly to avoid needing a real LLM client.
    """

    def test_style1_decorated_callable_extracts_schema(self):
        """Style 1: @tool fn passed in tools → schema extracted, fn auto-registered."""

        @tool(description="Returns the sum.")
        def add(a: int, b: int) -> int:
            return a + b

        schemas, fns = LLMQuery._resolve_tools(tools=[add])

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "add"
        assert (
            schemas[0]["function"]["parameters"]["properties"]["a"]["type"] == "integer"
        )
        assert len(fns) == 1
        assert fns[0] is add

    def test_style1_no_functions_arg_needed(self):
        """Style 1: functions arg is None — fns come entirely from @tool callables."""

        @tool
        def greet(name: str) -> str:
            """Greets a person."""
            return f"Hello {name}"

        schemas, fns = LLMQuery._resolve_tools(tools=[greet], functions=None)

        assert len(schemas) == 1
        assert len(fns) == 1
        assert fns[0].__name__ == "greet"

    def test_style1_schema_properties_match_type_hints(self):
        """Style 1 schema inference correctly maps Python types to JSON Schema types."""

        @tool
        def measure(label: str, value: float, count: int, enabled: bool) -> str:
            """Measures something."""
            ...

        schemas, _ = LLMQuery._resolve_tools(tools=[measure])
        props = schemas[0]["function"]["parameters"]["properties"]
        assert props["label"]["type"] == "string"
        assert props["value"]["type"] == "number"
        assert props["count"]["type"] == "integer"
        assert props["enabled"]["type"] == "boolean"

    def test_style2_raw_dict_requires_functions(self):
        """Style 2: raw schema dict + explicit functions list."""

        def get_weather(city: str) -> str:
            return f"22°C in {city}"

        schema = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }

        schemas, fns = LLMQuery._resolve_tools(tools=[schema], functions=[get_weather])

        assert len(schemas) == 1
        assert schemas[0] is schema
        assert len(fns) == 1
        assert fns[0] is get_weather

    def test_style2_dict_passed_through_unchanged(self):
        """Raw schema dicts are stored verbatim — no mutation."""

        raw = {"type": "function", "function": {"name": "x", "parameters": {}}}
        schemas, _ = LLMQuery._resolve_tools(tools=[raw])
        assert schemas[0] is raw

    def test_style3_mixed_list_decorated_and_raw(self):
        """Style 3: mix of @tool callable and raw dict in one tools list."""

        @tool(description="Tool A.")
        def tool_a(x: str) -> str: ...

        def tool_b_impl(y: int) -> int:
            return y * 2

        raw_schema = {
            "type": "function",
            "function": {
                "name": "tool_b_impl",
                "description": "Tool B.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }

        schemas, fns = LLMQuery._resolve_tools(
            tools=[tool_a, raw_schema],
            functions=[tool_b_impl],
        )

        assert len(schemas) == 2
        assert schemas[0]["function"]["name"] == "tool_a"
        assert schemas[1] is raw_schema
        fn_names = [f.__name__ for f in fns]
        assert "tool_a" in fn_names
        assert "tool_b_impl" in fn_names

    def test_style3_explicit_functions_take_precedence(self):
        """Explicit functions override same-name callables inferred from @tool."""

        @tool(description="Original implementation.")
        def my_fn(x: str) -> str:
            return "original"

        def my_fn_override(x: str) -> str:
            return "override"

        my_fn_override.__name__ = "my_fn"

        _, fns = LLMQuery._resolve_tools(
            tools=[my_fn],
            functions=[my_fn_override],
        )

        # my_fn_override is in explicit functions, so it is kept; my_fn is deduplicated
        fn_by_name = {f.__name__: f for f in fns}
        assert fn_by_name["my_fn"] is my_fn_override

    def test_empty_tools_returns_empty_lists(self):
        schemas, fns = LLMQuery._resolve_tools()
        assert schemas == []
        assert fns == []

    def test_llmquery_init_uses_resolve_tools(self):
        """LLMQuery.__init__ calls _resolve_tools: passing @tool fn registers it correctly."""

        @tool(description="Doubles a number.")
        def double(x: int) -> int:
            return x * 2

        llm = LLMQuery.__new__(LLMQuery)
        # Simulate just the tool-resolution part of __init__
        schemas, fns = LLMQuery._resolve_tools(tools=[double])
        llm.tools = schemas
        llm.functions = fns

        assert len(llm.tools) == 1
        assert llm.tools[0]["function"]["name"] == "double"
        assert len(llm.functions) == 1
        assert llm.functions[0] is double


# ---------------------------------------------------------------------------
# handle_tool_call — Pydantic dispatch
# ---------------------------------------------------------------------------


class TestHandleToolCallPydantic:
    def _make_pydantic_fn(self):
        class SumArgs(BaseModel):
            a: int
            b: int

        @tool(schema=SumArgs)
        def pydantic_sum(args: SumArgs) -> int:
            return args.a + args.b

        return pydantic_sum, SumArgs

    def test_pydantic_fn_receives_model_instance(self):
        received = []

        class MyArgs(BaseModel):
            value: str

        @tool(schema=MyArgs)
        def capture(args: MyArgs) -> str:
            received.append(type(args).__name__)
            return args.value

        calls = [_make_call("capture", {"value": "hello"})]
        results = handle_tool_call(calls, [capture])
        assert results[0]["output"] == "hello"
        assert received == ["MyArgs"]

    def test_pydantic_validation_pass(self):
        fn, _ = self._make_pydantic_fn()
        calls = [_make_call("pydantic_sum", {"a": 3, "b": 4})]
        results = handle_tool_call(calls, [fn])
        assert results[0]["output"] == 7

    def test_pydantic_validation_fail_returns_error(self):
        fn, _ = self._make_pydantic_fn()
        calls = [_make_call("pydantic_sum", {"a": "not-an-int", "b": "also-not"})]
        results = handle_tool_call(calls, [fn])
        assert "Error" in results[0]["output"]

    def test_undecorated_fn_receives_kwargs(self):
        received = {}

        def plain_fn(x: str, y: int) -> str:
            received["x"] = x
            received["y"] = y
            return f"{x}{y}"

        calls = [_make_call("plain_fn", {"x": "hello", "y": 42})]
        results = handle_tool_call(calls, [plain_fn])
        assert results[0]["output"] == "hello42"
        assert received == {"x": "hello", "y": 42}


# ---------------------------------------------------------------------------
# handle_tool_call_async — Pydantic dispatch
# ---------------------------------------------------------------------------


class TestHandleToolCallAsyncPydantic:
    def test_pydantic_async_dispatch(self):
        class MulArgs(BaseModel):
            x: int
            y: int

        @tool(schema=MulArgs)
        def multiply(args: MulArgs) -> int:
            return args.x * args.y

        calls = [_make_call("multiply", {"x": 6, "y": 7})]
        results = asyncio.run(handle_tool_call_async(calls, [multiply]))
        assert results[0]["output"] == 42

    def test_pydantic_async_validation_fail(self):
        class StrArgs(BaseModel):
            name: str

        @tool(schema=StrArgs)
        def greet(args: StrArgs) -> str:
            return f"Hello {args.name}"

        calls = [_make_call("greet", {})]  # missing required 'name'
        results = asyncio.run(handle_tool_call_async(calls, [greet]))
        assert "Error" in results[0]["output"]


# ---------------------------------------------------------------------------
# LLMQuery.as_tool
# ---------------------------------------------------------------------------


class TestLLMQueryAsTool:
    def test_returns_schema_and_callable(self):
        llm = LLMQuery.__new__(LLMQuery)
        llm.model = "openai/gpt-4o-mini"
        llm.system_prompt = "test"

        schema, fn = llm.as_tool(
            name="my_tool", description="Does something.", input_arg="query"
        )

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "my_tool"
        assert schema["function"]["parameters"]["required"] == ["query"]
        assert callable(fn)
        assert fn.__name__ == "my_tool"
        assert fn.__pydantic_model__ is None

    def test_schema_uses_custom_input_arg(self):
        llm = LLMQuery.__new__(LLMQuery)
        schema, _ = llm.as_tool(name="tool", description="desc.", input_arg="message")
        assert "message" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["message"]
