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
| [`tools.py`](tools.py) | `LLMQuery` (primary class) + backward-compatible re-exports of all symbols |
| [`__init__.py`](__init__.py) | Package-level convenience imports |

---

## Quick Start

```python
from ai_tools.tools import LLMQuery

# Basic query
llm = LLMQuery(model="gemini-flash-latest", system_prompt="You are helpful.")
reply = llm.query("Explain quantum computing in one sentence.")

# With chat history (default: on)
llm.query("Follow up question here...")  # history automatically included

# Single-call model override
reply = llm.query("Translate this.", model="gpt-4o-mini")
```

---

## Key Concepts

### `tools` vs `functions`

These are two separate constructor arguments with distinct roles:

- **`tools`** (`List[Dict]`): JSON Schema descriptions sent to the LLM so it
  knows *what* tools are available and their parameter shapes.
- **`functions`** (`List[Callable]`): The **actual Python callables** executed
  when the LLM requests a tool call. Keys are matched by `function.__name__`.

Both are needed for end-to-end tool use:

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

llm = LLMQuery(model="gpt-4o-mini", tools=tools_schema, functions=[get_weather])
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
llm = LLMQuery(model="gpt-4o-mini", tools=tools_schema, functions=[fn_a, fn_b])

# Opt out if needed (e.g. tools that share mutable state)
llm = LLMQuery(model="gpt-4o-mini", concurrent_tool_calls=False, ...)
```

Works seamlessly in both regular Python scripts and Jupyter notebooks.

### Override Resolution

All `query()` parameters follow this priority:

```
per-call argument  >  instance attribute  >  hardcoded default
```

Passing `None` (or omitting the argument) falls back to the instance value.
For example, passing `model="gpt-4o-mini"` to `query()` overrides `self.model`
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
llm = LLMQuery(model="gemini-flash-latest")
```

---

## Pipeline Syntax

Chain queries together with Python's `|` operator:

```python
q1 = LLMQuery(model="gpt-4o-mini", system_prompt="Translate to German")
q2 = LLMQuery(model="gpt-4o-mini", system_prompt="Make it UPPERCASE")

# Build a reusable pipeline
pipeline = q1 | q2

# Execute with any string
result = "Hello, how are you?" | pipeline
# result: "HALLO, WIE GEHT ES DIR?"

# Override kwargs inline
result = "Hello" | q1(model="gemini-flash-latest")
```

---

## Multi-Modal

`LLMQuery` inherits `MultiModalMixin` — all multi-modal methods are available
directly on the same object:

```python
llm = LLMQuery(model="gpt-4o-mini")

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

llm = LLMQuery(model="gpt-4o-mini", response_format=Summary)
reply = llm.query("Summarise the French Revolution in 3 points.")
# reply is a valid JSON string matching the Summary schema
```

---

## Backward Compatibility

All existing imports continue to work unchanged:

```python
from ai_tools.tools import LLMQuery, handle_tool_call, clean_json, ModelName
```

Fine-grained imports from sub-modules are also available:

```python
from ai_tools.config import ModelName, MODEL_DICT
from ai_tools.utils import clean_json, pretty_print_json, handle_tool_call_async
from ai_tools import LLMQuery, handle_tool_call
```

---

## Adding a New Model or Provider

1. Add model names to the appropriate `Literal` in `config.py`.
2. Add them to `MODEL_DICT` (or create a new provider entry).
3. Handle the new provider in `LLMQuery._get_client_for_model()`.
