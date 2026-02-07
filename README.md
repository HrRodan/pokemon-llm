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
# pokemon-llm
Playground for a LLM Pokemon Chatbot - Langchain, tool assistance, RAG

## Features
- **Agent-Based Architecture**: Powered by `PokemonAgent` orchestrating specialized tools.
- **RAG (Retrieval Augmented Generation)**: Uses ChromaDB for qualitative data.
- **SQL Database**: Uses SQLite for technical data queries and aggregations.
- **PokéAPI Integration**: Real-time data from PokéAPI.

## Setup
```bash
uv sync
uv run scripts/create_tech_db.py
uv run scripts/ingest.py
```

## Run
```bash
uv run app.py
```