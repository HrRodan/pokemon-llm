# AI Tools (`ai_tools`)

Core utilities and classes for interacting with LLMs via an OpenAI-compatible
API (OpenAI, Gemini, OpenRouter, Ollama) and performing multi-modal AI tasks
(image generation, TTS, audio transcription, embeddings).

The package is built around a unified, lifecycle-driven `Agent` class that
decomposes complex orchestration logic into modular, thread-safe components.

---

## Module Structure

| Module | Responsibility |
|---|---|
| [`agent.py`](agent.py) | **Agent (Primary Core)** — Unified class replacing `LLMQuery` and `LLMAgent`. Handles state, history, and the agentic loop. |
| [`client.py`](client.py) | Stateless provider client factory (OpenAI, Gemini, OpenRouter, Ollama). |
| [`parsing.py`](parsing.py) | Pure logic for extracting tool calls, reasoning, and thought signatures from API responses. |
| [`usage.py`](usage.py) | Thread-safe token and cost tracker for concurrent execution environments. |
| [`tracing.py`](tracing.py) | Langfuse observability implementation (fully optional). |
| [`memory/`](memory/) | Pluggable conversational memory system (SQLite / In-Memory), threads, and rollbacks. |
| [`multimodal.py`](multimodal.py) | `MultiModalMixin` — unified image generation, TTS, transcription, and embeddings. |
| [`config.py`](config.py) | API keys (lazy Colab → env → prompt fallback), model definitions, and provider URLs. |
| [`tool_definition.py`](tool_definition.py) | `@tool` decorator, `collect_tools`, schema inference from type hints and Pydantic models. |
| [`utils.py`](utils.py) | Low-level JSON cleaning, short ID generation, and tool dispatch helpers. |

---

## Quick Start

```python
from ai_tools import Agent

# Basic query
agent = Agent(model="gemini/gemini-flash-latest", system_prompt="You are helpful.")
reply = agent.query("Explain quantum computing in one sentence.")

# With automated tool execution (Agentic Loop)
# Agent.run() handles the query -> tools -> re-query iteration automatically.
result = agent.run("What's the weather in Berlin?")
```

### With Persistent Memory (SQLite)

```python
from ai_tools import Agent
from ai_tools.memory import MemoryHandler, SQLiteBackend

# Wrap an SQLite storage engine into the MemoryHandler
memory = MemoryHandler(backend=SQLiteBackend("agent_state.db"))

agent = Agent(model="gemini/gemini-flash-latest", memory=memory)
agent.query("Remember my name is Ash.")

# Switch threads at any time
memory.new_thread()
agent.query("Who am I?") # "I don't know."
```

---

## Core Features

### 1. Unified Agent Architecture
The `Agent` class provides a single, consistent API for both simple one-off queries (`.query()`) and complex tool-using workflows (`.run()`). It maintains its own conversational state, usage tracking, and tracing context.

### 2. Ergonomic Tooling
Register tools using the `@tool` decorator. The schema is automatically inferred from docstrings and type hints.

```python
from ai_tools import Agent, tool

@tool
def get_weather(city: str) -> str:
    """Returns the current weather for a city."""
    return f"22°C in {city}"

agent = Agent(model="openai/gpt-4o-mini", tools=[get_weather])
agent.run("Is it raining in London?")
```

### 3. Distributed Tracing (Langfuse)
Built-in observability that captures the full hierarchy of every turn. Sub-agents are automatically nested within parent traces.

```bash
# Tracking activates automatically if these env vars are present
LANGFUSE_PUBLIC_KEY="..."
LANGFUSE_SECRET_KEY="..."
LANGFUSE_BASE_URL="https://cloud.langfuse.com"
```

### 4. Concurrent Tool Dispatch
When an LLM returns multiple tool calls, the `Agent` executes them in parallel by default, significantly reducing latency for I/O-bound tasks.

### 5. Multi-Modal Mixin
Image generation, TTS, and transcription are available on any Agent:

```python
img = agent.generate_image("A cute Pikachu")
audio = agent.generate_tts("Pika Pika!")
text = agent.transcribe_audio("battle_cry.wav")
```

---

## Technical Performance

- **Thread-Safety**: `UsageTracker` uses mutex locks to safely aggregate tokens and cost during parallel tool execution.
- **Lazy Initialization**: API client factory instantiation and API key resolution are deferred until the first actual call.
- **Smart Retries**: Uses `tenacity` for exponential backoff and jitter on API failures.
- **Memory Efficiency**: Checkpoints are stored as delta-capable states in pluggable backends.
