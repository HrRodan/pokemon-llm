# GOAL #

Refactor the Pokemon LLM application to use a multi-agent architecture. The goal is to create a more modular and maintainable codebase that can be easily extended with new agents and tools.

The project should have a Agent first approach. 

# AGENT RULES #

- Each Agent must have its own file located in the "agents" folder.
- All Agents should inherit from a common `BaseAgent` class (to be created in `agents/base_agent.py`) to standardize logging and model initialization.
- The Agent must have have a python class that encapsulates the agent.
- The file contains everything necessary to run the agent.
- Each agent has a central "respond" method, as central anchor point.
- A Agent must provide a tool definition for its respond method explaining its capabilities.
- Sub-Agent use the "openai/gpt-oss-20b" model.
- The project must use a project wide logging (e.g. `utils/logger.py`), each agent must log its actions to this log with distinct messages.

# IMPLEMENTATION RULES #

- Add docstrings and type hints.
- Use Pydantic models for structured data.
- Add comments on complex logic.
- Write comprehensive README.md for the project, making it easy for future developers to understand the project structure.

# AGENTS #

## Pokemon Agent ##

- The Pokemon Agent is responsible for answering questions about Pokemon.
- It is the main agent and is used via its respond method by the gradio UI.
- It is currently located in the `chatbot.py` file and must be moved to `agents/pokemon_agent.py`.
- This Agent is the main entry point for the application.
- The Pokemon Agent can delegate tasks to other agents.
- The Pokemon Agent should use the Tech Data Agent for complex queries.
- The Pokemon Agent should use the RAG Agent for qualitative queries.
- The Pokemon Agent should use the API Agent for precise queries.
- It summarizes the results of the other agents and provides a final answer to the user.

## Tech Data Agent ##

- The Tech data agent is already implemented and located in the `agents/tech_data_agent.py` file.
- It must be refactored to inherit from `BaseAgent` and follow the new logging standards.

## API Agent ##

- The API Agent calls the Pokemon API via `pokemon_tools/pokemon_client.py`.
- **Status via Refactor**: Does NOT currently exist in `agents/`. Must be created as `agents/api_agent.py`.
- It wraps `PokemonAPIClient` and exposes its methods (`get_pokemon_details` etc.) as tools.
- It has detailed knowledge via its tools of the Pokemon API.
- Reuse relevant parts of the current System prompt in `chatbot.py`.

## RAG Agent ##

- The RAG Agent is responsible for answering questions about Pokemon using the RAG database in db folder.
- **Status via Refactor**: Does NOT currently exist in `agents/`. Logic is in `rag_data_tool.py`. Must be created as `agents/rag_agent.py`.
- It must be created in accordance with the new agent structure.
- The RAG Agent will query the RAG database and return the results, filtered and reordered, depending on the question. 
- It has detailed knowledge via its tools of the vector database.
- The function to query the RAG database is located in `rag_data_tool.py`.
- Reuse relevant parts of the current System prompt in `chatbot.py`.


# PROJECT STRUCTURE #

The current project structure is flat and mixes concerns. Refactor into the following principal structure:


```text
project_root/
├── agents/                 # All agent implementations
│   ├── __init__.py
│   ├── base_agent.py       # [NEW] Base class for all agents
│   ├── pokemon_agent.py    # [NEW] Main agent (was chatbot.py)
│   ├── tech_data_agent.py  # Existing, refactored
│   ├── api_agent.py        # [NEW] Wraps PokemonAPIClient
│   └── rag_agent.py        # [NEW] Wraps Vector DB logic
├── tools/                  # Lower-level tools and clients
│   ├── __init__.py
│   ├── api_client.py       # [MOVED] from pokemon_tools/pokemon_client.py
│   ├── vector_db.py        # [MOVED] from db_tools/rag_data_tool.py
│   └── tech_data_tools.py  # [MOVED] from db_tech/tech_data_tool.py & models.py
├── ai_tools/               # [KEEP] LLM Interface / Core AI Logic
│   └── tools.py            # Existing LLMQuery interface
├── data/
│   ├── raw/                # JSON/MD files
│   ├── vector_db/          # [MOVED] ChromaDB persistence (was ./db). **Tracked by Git LFS**
│   └── tech_db/            # [MOVED] SQLite DB (was ./db_tech/tech.db). **Tracked by Git LFS**
├── utils/                  # Shared utilities
│   ├── __init__.py
│   ├── logger.py           # [NEW] Structured logging
│   ├── config.py           # [NEW] Configuration management
│   └── ui_utils.py         # [MOVED] from answer.py (chat history extraction)
├── scripts/                # Utility scripts
│   ├── ingest.py           # [MOVED] from db_tools/ingest.py
│   ├── upload_to_hf.py
│   └── create_tech_db.py   # [MOVED] from db_tech/create_db.py
├── tests/                  # Test suite
│   ├── unit/
│   └── integration/
├── notebooks/              # Jupyter notebooks
│   └── test_chatbot.ipynb
├── app.py                  # Entry point (Gradio UI)
├── requirements.txt
├── pyproject.toml
└── .gitattributes          # [UPDATE] Update LFS paths for new data location
```


# OPTIMIZATION SUGGESTIONS #

1.  **Base Agent Abstraction**: Create a `BaseAgent` class to handle common logic like:
    -   Model initialization (defaulting to "openai/gpt-oss-20b").
    -   Logging setup.
    -   Tool registration helper methods.
2.  **Configuration Management**: Move hardcoded model names and API keys to a `config.py` or use environment variables/`pydantic-settings` to make the application more portable.
3.  **Structured Logging**: Implement a `utils/logger.py` module that provides a standard logger instance. This ensures all agents log in a consistent format (Timestamp - AgentName - Message).
4.  **Async Support**: Consider making the `respond` method `async` to allow the Pokemon Agent to call sub-agents (like API and RAG) in parallel effectively.
5.  **Strict Interfaces**: Define a `Protocol` or `ABC` for Agents to ensure they all implement `respond(query: str) -> str`.


