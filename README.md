---
title: Pokemon LLM Chatbot
emoji: 🦕
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: 6.3.0
app_file: app.py
python_version: 3.12
---
# ⚡ Pokémon AI Agent

An intelligent, multi-agent Pokémon chatbot powered by LLMs, vector search, SQL analytics, and live API data — all wrapped in a Gradio UI.

## Features

- **Multi-Agent Orchestration** — A main agent (Professor Oak) delegates to specialised sub-agents.
- **RAG (Retrieval-Augmented Generation)** — ChromaDB vector store for lore, descriptions, and semantic search.
- **SQL Analytics** — SQLite database for stats, aggregations, and filtered queries.
- **PokéAPI Integration** — Real-time data lookups (stats, moves, items, evolutions, locations).
- **Per-Agent Usage Tracking** — Token, cost, and call-count statistics tracked per agent and displayed in the UI.
- **Centralised Logging** — Color-coded console + in-app log viewer with per-agent colours.
- **Gradio UI** — Chat interface with tool activity, reasoning history, live logs, model selection, and usage statistics.

---

## Architecture

```
┌──────────────────────────────────┐
│         Gradio UI (app.py)       │
│  Chat │ Tools │ Reasoning │ Logs │
│       │       │ Settings  │ Usage│
└────────────┬─────────────────────┘
             │
     ┌───────▼────────┐
     │  PokemonAgent  │  ← Orchestrator (Professor Oak)
     │  (BaseAgent)   │
     └──┬─────┬────┬──┘
        │     │    │
   ┌────▼┐ ┌──▼──┐ ┌▼────────────┐
   │ RAG │ │ API │ │  TechData   │
   │Agent│ │Agent│ │   Agent     │
   └──┬──┘ └──┬──┘ └──┬──────────┘
      │       │       │
  ChromaDB  PokéAPI  SQLite
```

### Agents

All agents extend `BaseAgent` (`agents/base_agent.py`), which provides logging, LLM access, and **automatic usage tracking**.

| Agent | Role | Data Source |
| :--- | :--- | :--- |
| **PokemonAgent** | Orchestrator — analyses queries and delegates to the right sub-agent | — |
| **RAGAgent** | Lore, descriptions, biology, semantic search | ChromaDB vector DB |
| **TechDataAgent** | Stats, aggregations, rankings, filtered SQL queries | SQLite (`data/tech_db/tech.db`) |
| **APIAgent** | Precise lookups — base stats, moves, items, evolutions, locations | PokéAPI (REST) |

Sub-agents are instantiated on-demand for each tool call and destroyed afterwards. Their usage is preserved via the global `UsageTracker`.

---

## Logging

Logging is centralised in `utils/logger.py`. Each agent receives its own named logger via `setup_logger(name)`.

**Three output channels:**

| Channel | Formatter | Purpose |
| :--- | :--- | :--- |
| **Console** (stdout) | `ColoredFormatter` — ANSI colours per agent | Developer terminal |
| **File** | Standard timestamp + level | Persistent debug log |
| **UI Buffer** | `HtmlFormatter` — CSS-coloured HTML spans | In-app "Agent Logs" tab |

Agent colour map:

| Agent | Console | UI (CSS) |
| :--- | :--- | :--- |
| PokemonAgent | Cyan | `#06b6d4` |
| APIAgent | Magenta | `#d946ef` |
| RAGAgent | Green | `#22c55e` |
| TechDataAgent | Yellow | `#eab308` |

All LLM queries, responses, tool calls, tool outputs, and reasoning are logged at appropriate levels (INFO / DEBUG) **by the `LLMQuery` class**, so agents only need to pass their logger instance.

---

## Usage Tracking

Token consumption and cost are tracked per-agent via a singleton `UsageTracker` (`utils/usage_tracker.py`).

**How it works:**

1. `BaseAgent.__init__` snapshots the LLM client's zero counters.
2. At the end of each `response()`, `_collect_usage()` computes the delta and records it in the global tracker.
3. Sub-agents are created and destroyed each call — but since they record *before* destruction, usage is preserved.

The tracker is **thread-safe** (uses `threading.Lock`) and provides:

- `get_agent_usage(name)` — per-agent stats
- `get_totals()` — sum across all agents
- `get_all()` — snapshot of every agent's stats
- `reset()` — clears all data (called on new session)

---

## Gradio UI

The app (`app.py`) provides a tabbed interface:

| Tab | Content |
| :--- | :--- |
| **💬 Chat** | Main conversation with Professor Oak, includes example prompts |
| **🛠️ Tool Activity** | Real-time display of tool calls and their results |
| **🧠 Reasoning History** | Model reasoning traces (when supported, e.g. DeepSeek-R2) |
| **📜 Agent Logs** | Scrollable, colour-coded HTML log viewer |
| **⚙️ Settings** | Model selector dropdown |
| **📊 Usage Statistics** | Accumulated totals table + per-agent breakdown (tokens, cost, call count) |

The UI uses a threaded polling loop for tool execution, yielding intermediate updates so the user sees progress in real time.

---

## Setup

```bash
# Install dependencies
uv sync

# Build the SQLite tech database
uv run scripts/create_tech_db.py

# Ingest data into ChromaDB vector store
uv run scripts/ingest.py
```

### Environment Variables

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your_key_here
# Optional:
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
HUGGINGFACE_TOKEN=...
```

## Run

```bash
uv run app.py
```

## Tests

```bash
uv run python -m pytest tests/ -v
```

---

## Adding a New Agent

1. Create a new file in `agents/` extending `BaseAgent`.
2. Implement `response()` and call `self._collect_usage()` at the end.
3. Define a `run_<name>_agent()` tool function and a `TOOL_DEFINITION` dict.
4. Register the tool in `PokemonAgent.__init__`.
5. Add the agent name and colour to `AGENT_COLORS` / `AGENT_CSS_COLORS` in `utils/logger.py`.

The usage tracker and UI will automatically discover the new agent — no further wiring needed.