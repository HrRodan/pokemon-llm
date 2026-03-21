# AI Tools (`ai_tools`)

Core utilities and classes for interacting with LLMs via an OpenAI-compatible
API (OpenAI, Gemini, OpenRouter, Ollama) and performing multi-modal AI tasks
(image generation, TTS, audio transcription, embeddings).

---

## Module Structure

| Module | Responsibility |
|---|---|
| [`config.py`](config.py) | API keys (lazy Colab → env → prompt fallback), model `Literal` types, `MODEL_DICT`, provider base URLs |
| [`utils.py`](utils.py) | `pretty_print_json`, `clean_json`, `handle_tool_call`, `handle_tool_call_async`, `generate_short_id` |
| [`pipeline.py`](pipeline.py) | Pipe operator classes enabling `"text" \| query1 \| query2` syntax |
| [`multimodal.py`](multimodal.py) | `MultiModalMixin` — image generation, TTS, audio transcription, embeddings |
| [`tools.py`](tools.py) | `LLMQuery` (primary core client) |
| [`agent.py`](agent.py) | `LLMAgent` — A higher-level wrapper for `LLMQuery` providing an automated execution loop, dynamic usage tracking, and tool exporting. |
| [`logger.py`](logger.py) | Optional colored console logging functions via `setup_agent_logger()`. |
| [`tool_definition.py`](tool_definition.py) | `@tool` decorator, `collect_tools`, schema inference from type hints |
| [`__init__.py`](__init__.py) | Package-level convenience imports |

---

## Quick Start

```python
from ai_tools.tools import LLMQuery

# Basic query
llm = LLMQuery(model="gemini/gemini-flash-latest", system_prompt="You are helpful.")
reply = llm.query("Explain quantum computing in one sentence.")

# With chat history (default: on)
llm.query("Follow up question here...")  # history automatically included

# Single-call model override
reply = llm.query("Translate this.", model="openai/gpt-4o-mini")
```

---

## Key Concepts

### Tool Registration — Three Styles

`LLMQuery` accepts the type `ToolInput = Union[Dict[str, Any], Callable]` in
its `tools` list. How the schema and implementation are resolved depends on
what you pass:

---

#### Style 1 — `@tool`-decorated callable (recommended)

Decorate a function with `@tool` and pass it directly. The schema is inferred
from type hints and docstrings automatically. **No `functions` argument
needed.**

```python
from ai_tools import LLMQuery, tool

@tool(description="Returns the current temperature for a city.")
def get_weather(city: str, units: str = "metric") -> str:
    return f"22°C in {city}"

llm = LLMQuery(model="openai/gpt-4o-mini", tools=[get_weather])
llm.query("What's the weather in Berlin?")
reply = llm.get_tool_responses()
```

For **Pydantic-backed validation** (the LLM's arguments are validated
before the function receives them as a typed model instance):

```python
from pydantic import BaseModel, Field

class WeatherArgs(BaseModel):
    city: str = Field(description="City name.")
    units: str = Field(default="metric")

@tool(schema=WeatherArgs)
def get_weather(args: WeatherArgs) -> str:
    return f"{args.city}: 22°C ({args.units})"

llm = LLMQuery(model="openai/gpt-4o-mini", tools=[get_weather])
```

---

#### Style 2 — Raw schema dict + explicit `functions`

For hand-crafted schemas or third-party definitions. Pass the schema in
`tools` and the matching callable in `functions`. The callable is looked up
by `.__name__` at dispatch time.

```python
def get_weather(city: str) -> str:
    return f"22°C in {city}"

schema = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}

llm = LLMQuery(model="openai/gpt-4o-mini", tools=[schema], functions=[get_weather])
```

---

#### Style 3 — Mixed list (advanced)

`tools` may contain any combination of `@tool` callables and raw dicts.
Explicit `functions` entries take precedence over same-name callables
auto-extracted from `tools`.

```python
llm = LLMQuery(
    tools=[decorated_fn, raw_schema_dict],
    functions=[manual_override_fn],
)
```

---

### `@tool` decorator — details

| Usage | When to use |
|---|---|
| `@tool` | Bare decorator — schema inferred from type hints & docstring |
| `@tool(description="…")` | Override the description |
| `@tool(name="…")` | Override the function name exposed to the LLM |
| `@tool(schema=MyModel)` | Pydantic-backed — full validation at dispatch, receives typed instance |

Attributes added to the decorated function:

- `.__tool_schema__` — OpenAI-compatible JSON dict
- `.__pydantic_model__` — the Pydantic class, or `None`

---

### `collect_tools(*fns)` — when you need the split lists

`collect_tools` returns the raw `(schemas, functions)` tuple — useful if you
need to inspect schemas separately or pass them to another system.  **You do
not need it when using Style 1.**

```python
from ai_tools import collect_tools

TOOLS, FUNCTIONS = collect_tools(get_weather, search_web)
llm = LLMQuery(model="openai/gpt-4o-mini", tools=TOOLS, functions=FUNCTIONS)
```

---

### `LLMAgent.as_tool()` — Sub-agents as Tools

Any `LLMAgent` subclass that defines `TOOL_NAME` and `TOOL_DESCRIPTION` can
expose itself natively as a `@tool`-compatible callable via `as_tool()`. The returned
callable carries `.__tool_schema__` and can be passed directly into another agent's tools list.

```python
from ai_tools.agent import LLMAgent

class RAGAgent(LLMAgent):
    TOOL_NAME = "run_rag_agent"
    TOOL_DESCRIPTION = "Semantic search over Pokémon lore."
    ...

rag = RAGAgent(name="RAG", model_name="openai/gpt-4o-mini")

# Pass directly to an Orchestrator — no separate schema or functions needed:
orchestrator = LLMQuery(model="openai/gpt-4o-mini", tools=[rag.as_tool()])
orchestrator.query("What does the RAG agent think about Mewtwo?")
```

---

### Concurrent Tool Calls

When the LLM returns multiple tool calls in one response they are dispatched
**concurrently** by default via `asyncio.to_thread` — ideal for I/O-bound
tools (HTTP, sub-agent LLMs).

```python
# Default: concurrent
llm = LLMQuery(model="openai/gpt-4o-mini", tools=[fn_a, fn_b])

# Sequential (e.g. tools share mutable state)
llm = LLMQuery(model="openai/gpt-4o-mini", tools=[fn_a, fn_b], concurrent_tool_calls=False)
```

---

### Override Resolution

All `query()` parameters follow:

```
per-call argument  >  instance attribute  >  hardcoded default
```

### Side Effects of `query()`

| Attribute | Content |
|---|---|
| `self.response` | Raw text of the last response |
| `self.tool_calls` | List of tool-call dicts (empty if model returned only text) |
| `self.reasoning_history` | One entry per call with CoT reasoning (or `None`) |
| `self.chat_history` | Full conversation history (user + assistant turns) |
| `self.total_*` | Cumulative token counts and cost |

---

## Pipeline Syntax

Chain queries with Python's `|` operator:

```python
q1 = LLMQuery(model="openai/gpt-4o-mini", system_prompt="Translate to German")
q2 = LLMQuery(model="openai/gpt-4o-mini", system_prompt="Make it UPPERCASE")

result = "Hello, how are you?" | q1 | q2
# result: "HALLO, WIE GEHT ES DIR?"
```

---

## Multi-Modal

```python
llm = LLMQuery(model="openai/gpt-4o-mini")

img   = llm.generate_image("A futuristic city at night")
audio = llm.generate_tts("Hello, world!", voice="onyx")
text  = llm.transcribe_audio("recording.wav")
vecs  = llm.generate_embedding(["Hello", "World"])
```

---

## Structured Output (Pydantic)

```python
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    key_points: list[str]

llm = LLMQuery(model="openai/gpt-4o-mini", response_format=Summary)
reply = llm.query("Summarise the French Revolution in 3 points.")
```

---

## Adding a New Model or Provider

1. Add model names to the appropriate `Literal` in `config.py`.
2. Add them to `MODEL_DICT` (or create a new provider entry).
3. Handle the new provider in `LLMQuery._get_client_for_model()`.

```python
def get_weather(city: str) -> str:
    return f"22°C in {city}"

tools_schema = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"]
        }
    }
}]

llm = LLMQuery(model="openai/gpt-4o-mini", tools=tools_schema, functions=[get_weather])
llm.query("What's the weather in Berlin?")
final_response = llm.get_tool_responses()  # executes tool, gets final reply
```

### Concurrent Tool Calls

By default, when the LLM returns multiple tool calls in a single response,
they are dispatched **concurrently** using `asyncio.to_thread`. This is ideal
for I/O-bound tools (API calls, sub-agent LLM queries) where parallel execution
cuts wall-clock time significantly.

```python
# Default: concurrent dispatch (all tool calls run in parallel threads)
llm = LLMQuery(model="openai/gpt-4o-mini", tools=tools_schema, functions=[fn_a, fn_b])

# Opt out if needed (e.g. tools that share mutable state)
llm = LLMQuery(model="openai/gpt-4o-mini", concurrent_tool_calls=False, ...)
```

Works seamlessly in both regular Python scripts and Jupyter notebooks.

### Override Resolution

All `query()` parameters follow this priority:

```
per-call argument  >  instance attribute  >  hardcoded default
```

Passing `None` (or omitting the argument) falls back to the instance value.
For example, passing `model="openai/gpt-4o-mini"` to `query()` overrides `self.model`
for that call only.

### Side Effects of `query()`

After every call, the following instance attributes are updated:

| Attribute | Content |
|---|---|
| `self.response` | Raw text of the last response |
| `self.tool_calls` | List of tool-call dicts (empty if model returned only text) |
| `self.reasoning_history` | One entry per call with CoT reasoning (or `None`) |
| `self.chat_history` | Full conversation history (user + assistant turns) |
| `self.total_*` | Cumulative token counts and cost |

### Lazy API Key Loading

Keys are **never resolved at import time** — they are fetched on first use via
a three-tier chain: **Colab userdata → environment variable → interactive
prompt**. This makes the module safe to import in scripts and CI without
blocking.

```python
# Keys resolved lazily when the first query fires — no blocking on import
from ai_tools.tools import LLMQuery
llm = LLMQuery(model="gemini/gemini-flash-latest")
```

---

## Pipeline Syntax

Chain queries together with Python's `|` operator:

```python
q1 = LLMQuery(model="openai/gpt-4o-mini", system_prompt="Translate to German")
q2 = LLMQuery(model="openai/gpt-4o-mini", system_prompt="Make it UPPERCASE")

# Build a reusable pipeline
pipeline = q1 | q2

# Execute with any string
result = "Hello, how are you?" | pipeline
# result: "HALLO, WIE GEHT ES DIR?"

# Override kwargs inline
result = "Hello" | q1(model="gemini/gemini-flash-latest")
```

---

## Multi-Modal

`LLMQuery` inherits `MultiModalMixin` — all multi-modal methods are available
directly on the same object:

```python
llm = LLMQuery(model="openai/gpt-4o-mini")

# Image generation (returns PIL Image)
img = llm.generate_image("A futuristic city at night", size="1024x1024")
img.save("city.png")

# Text-to-speech (returns raw audio bytes)
audio = llm.generate_tts("Hello, world!", voice="onyx")

# Audio transcription (accepts path, bytes, or file object)
text = llm.transcribe_audio("recording.wav")

# Embeddings (one vector per input string)
vectors = llm.generate_embedding(["Hello", "World"])
```

---

## Structured Output (Pydantic)

```python
from pydantic import BaseModel

class Summary(BaseModel):
    title: str
    key_points: list[str]

llm = LLMQuery(model="openai/gpt-4o-mini", response_format=Summary)
reply = llm.query("Summarise the French Revolution in 3 points.")
# reply is a valid JSON string matching the Summary schema
```

---

## Tool Definition

`tool_definition.py` provides ergonomic helpers to define and register LLM tools.

### `@tool` decorator

Infers the OpenAI-compatible schema from type hints and docstrings.  Attaches
`.__tool_schema__` and `.__pydantic_model__` to the decorated function:

```python
from ai_tools import tool, collect_tools
from pydantic import BaseModel, Field

# Pure-function inference — schema derived from type hints + docstring
@tool(description="Returns the current weather for a city.")
def get_weather(city: str, units: str = "metric") -> str:
    """Fetch weather data."""
    return f"22°C, {units}"

# Pydantic-backed — full validation at dispatch time
class WeatherArgs(BaseModel):
    city: str = Field(description="City name.")
    units: str = Field(default="metric")

@tool(schema=WeatherArgs)
def get_weather_validated(args: WeatherArgs) -> str:
    return f"{args.city}: 22°C"
```

### `collect_tools(*fns)`

Builds the `(tool_schemas, functions)` pair expected by `LLMQuery`:

```python
TOOLS, FUNCTIONS = collect_tools(get_weather, get_weather_validated)
llm = LLMQuery(model="openai/gpt-4o-mini", tools=TOOLS, functions=FUNCTIONS)
```

### Automatic Pydantic validation

When `handle_tool_call` dispatches a `@tool(schema=Model)` function, it
automatically validates the LLM's arguments and passes a **typed model instance**
to the function instead of raw `**kwargs`.

Validation errors are returned to the LLM as a descriptive string — no crash,
no exception propagation.

### `LLMAgent.as_tool()`

Wrap an `LLMAgent` instance as a callable tool for an orchestrating agent. This dynamically delegates requests directly into the subclass's native `.run()` method string processing.

```python
from ai_tools.agent import LLMAgent

my_agent = LLMAgent(name="MyAgent", model_name="openai/gpt-4o-mini")
my_agent.TOOL_NAME = "run_custom_agent"
my_agent.TOOL_DESCRIPTION = "Semantic search customizer."

orchestrator = LLMQuery(model="openai/gpt-4o-mini", tools=[my_agent.as_tool()])
```

---

## Adding a New Model or Provider

1. Add model names to the appropriate `Literal` in `config.py`.
2. Add them to `MODEL_DICT` (or create a new provider entry).
3. Handle the new provider in `LLMQuery._get_client_for_model()`.
