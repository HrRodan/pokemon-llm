# Refactoring Status & Architecture

**Last Updated:** 2026-02-07
**Status:** Phase 1 Complete (Core Architecture & Main Agents)

## 1. Project Overview

The project has been refactored to a **Multi-Agent Architecture**. The goal is to create a modular, maintainable codebase where `PokemonAgent` acts as the orchestrator, delegating tasks to specialized sub-agents or tools.

### Current State
*   **Agent-First Approach**: Adopted.
*   **Structure**: Modularized into `agents/`, `tools/`, `utils/`, `data/`.
*   **Base Abstraction**: `BaseAgent` implemented.
*   **Orchestrator**: `PokemonAgent` implemented (replaces `chatbot.py`).

## 2. Architecture Guidelines

*   **Location**: All Agents are in `agents/`.
*   **Inheritance**: All Agents inherit from `agents.base_agent.BaseAgent`.
*   **Interface**: Each agent implements `response(message, history) -> str`.
*   **Logging**: Use `utils.logger` for standardized logging.
*   **Configuration**: Use `utils.config.settings` for environment variables.

## 3. Agents Status

### ✅ Pokemon Agent (Orchestrator)
*   **File**: `agents/pokemon_agent.py`
*   **Role**: Main interface (Professor Oak). Orchestrates other agents/tools.
*   **Status**: **Implemented**.
*   **Notes**: Currently calls `TechDataAgent` as a sub-agent. Calls API and RAG functions directly as tools (pending refactor to full sub-agents).

### ✅ Tech Data Agent
*   **File**: `agents/tech_data_agent.py`
*   **Role**: Specialized SQL querying for stats, moves, items.
*   **Status**: **Implemented**.
*   **Notes**: Fully refactored to use `BaseAgent` and proper tool execution loop.

### ⏳ API Agent (Pending)
*   **Target File**: `agents/api_agent.py`
*   **Role**: Specialized agent for raw PokéAPI data.
*   **Current State**: Logic resides in `tools/api_client.py`. currently exposed as a list of tools to `PokemonAgent`.
*   **Next Step**: Wrap `tools.api_client` into a dedicated `APIAgent` class to decouple it from the main agent.

### ⏳ RAG Agent (Pending)
*   **Target File**: `agents/rag_agent.py`
*   **Role**: Specialized agent for qualitative data (Vector DB).
*   **Current State**: Logic resides in `tools/vector_db.py`. Currently exposed as a tool (`query_database`) to `PokemonAgent`.
*   **Next Step**: Wrap `tools.vector_db` into a dedicated `RAGAgent` class.

## 4. Project Structure (Current)

```text
project_root/
├── agents/                 # Agent implementations
│   ├── base_agent.py       # [Implemented] Base class
│   ├── pokemon_agent.py    # [Implemented] Orchestrator
│   └── tech_data_agent.py  # [Implemented] SQL Specialist
├── tools/                  # Tool logic & Clients
│   ├── api_client.py       # PokéAPI Client
│   ├── vector_db.py        # ChromaDB / RAG Logic
│   └── tech_data_tools.py  # SQL Logic
├── ai_tools/               # LLM Interface
│   └── tools.py            # LLMQuery Class
├── utils/                  # Shared Utilities
│   ├── config.py           # Settings management
│   ├── logger.py           # Logging setup
│   └── ui_utils.py         # UI helpers
├── data/
│   ├── models.py           # SQLAlchemy Models
│   ├── raw/                # JSON Data
│   ├── vector_db/          # ChromaDB persistence
│   └── tech_db/            # SQLite DB
├── scripts/                # Maintenance Scripts
│   ├── ingest.py           # RAG Ingestion
│   └── create_tech_db.py   # SQL DB Creation
├── tests/                  # Test Suite
│   └── integration/
├── app.py                  # Gradio Entry Point
└── requirements.txt
```

## 5. Next Steps / Todo

1.  **Implement APIAgent**: Create `agents/api_agent.py`. Move tool definitions from `pokemon_agent.py` to this new agent.
2.  **Implement RAGAgent**: Create `agents/rag_agent.py`. Move `query_database` tool usage to this agent.
3.  **Update Orchestrator**: Update `PokemonAgent` to call `ST_API_AGENT` and `ST_RAG_AGENT` (Agent-as-a-Tool) instead of raw functions.
