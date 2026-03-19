## Goal

Ingest web-scraped markdown into a **separate** ChromaDB collection (`pokemon_web_content`) using **Chonkie** (3.9k ⭐) Pipeline API (CHOMP).

Docs: https://docs.chonkie.ai/oss/pipelines

All new code lives in `tools/web_vector_db.py`.

---

## Architecture — Chonkie CHOMP Pipeline

The Chonkie Pipeline API follows the pattern:

```
Fetcher → Chef → Chunker → Refinery → Handshake
```

Since we already have markdown from `fetch_page_as_markdown`, we skip the Fetcher and pass text directly via `run(texts=...)`.

### Core pipeline (entire ingestion in ~10 lines)

```python
from chonkie import Pipeline

pipeline = (
    Pipeline()
    .process_with("markdown")                             # Chef: markdown-aware preprocessing (extracts tables, code blocks as metadata)
    .chunk_with("recursive", chunk_size=512, chunk_overlap=50)  # Chunker: recursive splitting with markdown rules
    .refine_with("overlap", context_size=100)              # Refinery: add overlap context between chunks
    .refine_with("embedding",                              # Refinery: generate embeddings
                 model="openrouter/qwen/qwen3-embedding-8b")
    .store_in("chroma",                                    # Handshake: write to ChromaDB
              path=settings.VECTOR_DB_DIR,
              collection_name="pokemon_web_content")
)

# Execute
doc = pipeline.run(texts=clean_markdown)
```

### What each stage does

| Stage | Method | Purpose |
|---|---|---|
| **Chef** | `process_with("markdown")` | Parses markdown structure, extracts tables + code blocks as metadata, preserves headings/paragraphs/lists as atomic units |
| **Chunker** | `chunk_with("recursive", chunk_size=512, chunk_overlap=50)` | Recursive splitting using markdown-aware rules. Returns `Chunk` dataclasses with `text`, `token_count`, `start_index`, `end_index` |
| **Overlap Refinery** | `refine_with("overlap", context_size=100)` | Adds `context` field to each chunk with surrounding text for continuity |
| **Embedding Refinery** | `refine_with("embedding", model="openrouter/qwen/qwen3-embedding-8b")` | Generates embeddings via litellm → OpenRouter. Attaches `embedding` to each `Chunk` |
| **ChromaDB Handshake** | `store_in("chroma", ...)` | Writes chunks + embeddings to persistent ChromaDB collection |

### `Chunk` dataclass (returned by pipeline)

```python
@dataclass
class Chunk:
    text: str
    start_index: int
    end_index: int
    token_count: int
    context: str | None = None     # from overlap refinery
    embedding: list[float] | None = None  # from embedding refinery
```

---

## 1 · Pre-processing (custom — ~15 lines)

Before passing to Chonkie pipeline:

1. **Deserialize** `fetch_page_as_markdown` output: `PageMarkdownResult.model_validate_json(result_json)`.
2. **Check `result.error`** → return early if set.
3. **Strip YAML front-matter** (`---…---` block) — metadata, not content.
4. **Prefix** `# {title}\n\n` to the clean markdown so every chunk inherits page context.

---

## 2 · Duplicate / Freshness Check (custom — ~20 lines)

Before running the pipeline, query the `pokemon_web_content` collection for existing documents with matching `url` metadata:

- **If found and younger than `max_age` (default 7 days)** → **skip**, return early.
- **If stale or missing** → **delete all old chunks** for that URL, then run pipeline.

Use deterministic IDs: `f"{sha256(url)[:16]}_{chunk_index}"` for idempotent operations.

---

## 3 · Custom Metadata

The pipeline handles chunk text + embeddings automatically. We still need to attach custom metadata to each chunk before `store_in()`, or pass it at storage time:

```python
{
    "title": str,
    "url": str,
    "chunk_index": int,
    "total_chunks": int,
    "timestamp": str,       # ISO-8601 from fetch
    "ingested_at": str,     # ISO-8601 when written to DB
    "source": "web",
}
```

> **Note:** Check if `store_in("chroma")` accepts custom metadata per chunk. If not, we may need to use `ChromaHandshake` directly instead of `.store_in()` to attach metadata, or fall back to manual `collection.upsert()` after embedding.

---

## 4 · Query Tool (`@tool`, used by agents)

**Custom** — format results as markdown matching the project's `@tool` pattern.

### `QueryWebContentArgs` (Pydantic)

- `query: str`
- `n_results: int = 5` (1–10)
- `filter_url: str | None` — exact match on metadata `url`

### Output format

```markdown
### {title}
**Source:** {url}
**Chunk:** {chunk_index + 1}/{total_chunks}

{chunk text}

---
```

Implementation: generate query embedding via `EmbeddingsRefinery` or `LLMQuery.generate_embedding()`, query `pokemon_web_content` collection, format results.

---

## 5 · Wrapper Tool (`@tool`, used by agents)

`ingest_web_page(url, css_selector?, use_stealth?, max_age_days?)`:

1. Fetch via `fetch_page_as_markdown` → parse JSON with `PageMarkdownResult.model_validate_json()`.
2. Check `result.error` → return early.
3. Pre-process (strip YAML, prefix title).
4. Freshness check → skip if fresh.
5. Run Chonkie pipeline → chunks are embedded and stored.
6. Return: *"Ingested 12 chunks from 'Bulbasaur - Bulbapedia'. Available via `query_web_content`."*

Each step wrapped in try/except.

---

## 6 · Dependencies

```
uv add chonkie litellm
```

- **chonkie** (with `chroma` extra if needed) — chunking, embedding, ChromaDB
- **litellm** — unified embedding API via OpenRouter
- **chromadb** — already installed

---

## 7 · Module Exports

```python
# tools/web_vector_db.py
TOOL_FUNCTIONS = [ingest_web_page, query_web_content]
```

---

## Verification Plan

### Unit Tests (`tests/unit/test_web_vector_db.py`)

Run: `uv run pytest tests/unit/test_web_vector_db.py -v`

- YAML front-matter stripping.
- Title prefix injection.
- Freshness check: mock ChromaDB, verify skip vs. replace.
- Deterministic ID generation.
- Query output formatting.

### Integration Tests (`tests/integration/test_web_vector_ingestion.py`)

Run: `uv run pytest tests/integration/test_web_vector_ingestion.py -v`

- Full pipeline: fetch → chunk → embed → store → query.
- Duplicate ingestion: ingest twice, verify no duplicate chunks.
- Stale replacement: mock old timestamp, verify old chunks deleted.

### Manual Verification

- `ingest_web_page` on a Bulbapedia page → `query_web_content` with a related query → verify relevant chunks with correct metadata.