"""
Web content vector ingestion and retrieval.

Ingests web-scraped markdown into a ChromaDB collection (``pokemon_web_content``)
using Chonkie CHOMP Pipeline for markdown-aware chunking, and the project's
``LLMQuery`` for embeddings.  Provides two ``@tool`` functions:

- ``ingest_web_page``  — fetch → preprocess → chunk → embed → store
- ``query_web_content`` — semantic search over ingested web content
"""

import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta


import chromadb
from chonkie import RecursiveChunker, OverlapRefinery
from pydantic import BaseModel, Field

from ai_tools.tool_definition import tool
from ai_tools.tools import LLMQuery
from tools.web_content import PageMarkdownResult, fetch_page_as_markdown, FetchPageInput
from utils.config import settings

logger = logging.getLogger(__name__)
logging.getLogger("chonkie").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Lazy singletons — connections created on first use, not at import time.
# ---------------------------------------------------------------------------

_embedding_client: "LLMQuery | None" = None
_collection: "chromadb.Collection | None" = None


def _get_embedding_client() -> "LLMQuery":
    """Return (and lazily create) the shared embedding LLMQuery instance."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = LLMQuery(embedding_model=settings.EMBEDDING_MODEL)
    return _embedding_client


def _get_collection() -> "chromadb.Collection":
    """Return (and lazily create) the shared ChromaDB collection."""
    global _collection
    if _collection is None:
        chroma_client = chromadb.PersistentClient(path=settings.VECTOR_DB_DIR)
        _collection = chroma_client.get_or_create_collection(
            name="pokemon_web_content"
        )
    return _collection


# ---------------------------------------------------------------------------
# Pre-processing helpers
# ---------------------------------------------------------------------------

_YAML_FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def strip_yaml_frontmatter(markdown: str) -> str:
    """Remove YAML front-matter block (``---…---``) from the start of markdown."""
    return _YAML_FRONT_MATTER_RE.sub("", markdown, count=1)


def prepare_markdown(result: PageMarkdownResult) -> str:
    """Strip YAML front-matter and prefix the page title as an H1 heading.

    Returns clean markdown ready for chunking.
    """
    clean = strip_yaml_frontmatter(result.markdown)
    if result.title:
        clean = f"# {result.title}\n\n{clean}"
    return clean.strip()


# ---------------------------------------------------------------------------
# Deterministic IDs & freshness check
# ---------------------------------------------------------------------------


def generate_chunk_id(url: str, chunk_index: int) -> str:
    """Create a deterministic chunk ID from URL hash and index."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"{url_hash}_{chunk_index}"


def is_content_fresh(
    collection: "chromadb.Collection",
    url: str,
    max_age_days: int = 7,
) -> bool:
    """Check whether the collection already has fresh content for *url*.

    Returns ``True`` if chunks exist and the newest ``ingested_at`` timestamp
    is younger than *max_age_days*.
    """
    results = collection.get(where={"url": url}, limit=1, include=["metadatas"])
    if not results["ids"]:
        return False

    ingested_at_str = results["metadatas"][0].get("ingested_at", "")
    if not ingested_at_str:
        return False

    try:
        ingested_at = datetime.fromisoformat(ingested_at_str)
        age = datetime.now(timezone.utc) - ingested_at
        return age < timedelta(days=max_age_days)
    except (ValueError, TypeError):
        return False


def delete_url_chunks(collection: "chromadb.Collection", url: str) -> int:
    """Delete all existing chunks for a URL from the collection.

    Returns the number of chunks deleted.
    """
    existing = collection.get(where={"url": url})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        return len(existing["ids"])
    return 0


# ---------------------------------------------------------------------------
# Chonkie chunker configuration
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class IngestWebPageArgs(BaseModel):
    """Input parameters for ingesting a web page into the vector database."""

    url: str = Field(description="The URL of the page to ingest.")
    css_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to extract specific content.",
    )
    use_stealth: bool = Field(
        default=False,
        description="Use stealth browser mode for sites with anti-bot protection.",
    )
    max_age_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Maximum age in days before re-ingesting. Defaults to 7.",
    )


class QueryWebContentArgs(BaseModel):
    """Queries the web content vector database for relevant information based on a semantic query string. Returns a markdown formatted string with the results."""

    query: str = Field(
        description="The semantic query string to search for."
    )
    n_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of results to return. Defaults to 5.",
    )
    filter_url: str | None = Field(
        default=None,
        description="Optional exact URL to filter results by.",
    )


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


@tool(schema=IngestWebPageArgs)
def ingest_web_page(args: IngestWebPageArgs) -> str:
    """Fetch a web page, chunk and embed its content, and store in the vector database."""
    logger.info("Ingesting web page: %s", args.url)

    # 1. Freshness check (Early exit before fetching)
    collection = _get_collection()
    if is_content_fresh(collection, args.url, args.max_age_days):
        logger.info("Content for %s is still fresh, skipping ingestion.", args.url)
        return (
            f"Skipped: Content for '{args.url}' is still fresh "
            f"(< {args.max_age_days} days old). Available via `query_web_content`."
        )

    # 2. Fetch via fetch_page_as_markdown
    try:
        fetch_input = FetchPageInput(
            url=args.url,
            css_selector=args.css_selector,
            use_stealth=args.use_stealth,
        )
        result_json = fetch_page_as_markdown(fetch_input)
        result = PageMarkdownResult.model_validate_json(result_json)
    except Exception as e:
        logger.error("Fetch failed for %s: %s", args.url, e)
        return f"Error: Fetch failed for {args.url}: {e}"

    # 3. Check for fetch errors
    if result.error:
        return f"Error: {result.error}"

    # 4. Pre-process markdown
    clean_markdown = prepare_markdown(result)
    if not clean_markdown.strip():
        return f"Error: No content extracted from {args.url}"

    # 5. Delete stale chunks
    deleted = delete_url_chunks(collection, args.url)
    if deleted:
        logger.info("Deleted %d stale chunks for %s", deleted, args.url)

    # 6. Run Chonkie chunker
    try:
        chunker = RecursiveChunker.from_recipe("markdown", lang="en", chunk_size=1024)
        chunks = chunker(clean_markdown)
        
        # Add overlap
        refinery = OverlapRefinery(context_size=256)
        chunks = refinery(chunks)
    except Exception as e:
        logger.error("Chunking failed for %s: %s", args.url, e)
        return f"Error: Chunking failed for {args.url}: {e}"

    if not chunks:
        return f"Error: No chunks produced from {args.url}"

    # 7. Generate embeddings via LLMQuery
    try:
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = _get_embedding_client().generate_embedding(chunk_texts)
    except Exception as e:
        logger.error("Embedding generation failed for %s: %s", args.url, e)
        return f"Error: Embedding generation failed for {args.url}: {e}"

    # 8. Upsert to ChromaDB with custom metadata
    ingested_at = datetime.now(timezone.utc).isoformat()
    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        ids.append(generate_chunk_id(args.url, i))
        documents.append(chunk.text)
        metadatas.append(
            {
                "title": result.title,
                "url": args.url,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "timestamp": result.timestamp,
                "ingested_at": ingested_at,
                "source": "web",
            }
        )

    try:
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
    except Exception as e:
        logger.error("ChromaDB upsert failed for %s: %s", args.url, e)
        return f"Error: Database write failed for {args.url}: {e}"

    logger.info(
        "Ingested %d chunks from '%s' (%s)", len(chunks), result.title, args.url
    )
    return (
        f"Ingested {len(chunks)} chunks from '{result.title}'. "
        f"Available via `query_web_content`."
    )


@tool(schema=QueryWebContentArgs)
def query_web_content(args: QueryWebContentArgs) -> str:
    """Query the web content vector database for relevant information using semantic search."""
    collection = _get_collection()

    # Generate query embedding
    try:
        query_embedding = _get_embedding_client().generate_embedding([args.query])[0]
    except Exception as e:
        logger.error("Query embedding failed: %s", e)
        return f"Error: Failed to generate query embedding: {e}"

    # Build optional where filter
    where = {"url": args.filter_url} if args.filter_url else None

    # Query the collection
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=args.n_results,
            where=where,
        )
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return f"Error: Database query failed: {e}"

    if not results or not results.get("ids") or not results["ids"][0]:
        return "No results found for your query. Try ingesting relevant web pages first with `ingest_web_page`."

    # Format results as markdown
    output_parts = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        doc = results["documents"][0][i]

        output_parts.append(
            f"### {meta.get('title', 'Untitled')}\n"
            f"**Source:** {meta.get('url', 'N/A')}\n"
            f"**Chunk:** {meta.get('chunk_index', 0) + 1}/{meta.get('total_chunks', '?')}\n\n"
            f"{doc}\n\n---"
        )

    return "\n\n".join(output_parts)


TOOL_FUNCTIONS = [ingest_web_page, query_web_content]
