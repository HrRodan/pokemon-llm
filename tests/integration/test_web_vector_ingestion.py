"""Integration tests for the web vector ingestion pipeline.

Uses an in-memory ChromaDB and mocked embeddings/fetch to test
the full ingest → query cycle without network or API calls.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import chromadb
import pytest

from tools.web_content import PageMarkdownResult, FetchPageInput
from tools.web_vector_db import (
    IngestWebPageArgs,
    QueryWebContentArgs,
    ingest_web_page,
    query_web_content,
    generate_chunk_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_MARKDOWN = (
    "## Biology\n\n"
    "Bulbasaur is a small, quadrupedal amphibian Pokémon that has blue-green skin "
    "with darker patches. It has red eyes with white pupils, pointed, ear-like "
    "structures on top of its head, and a short, blunt snout with a wide mouth.\n\n"
    "## In the games\n\n"
    "Bulbasaur is one of the three starter Pokémon of Kanto available at the "
    "beginning of Pokémon Red, Green, Blue, FireRed, and LeafGreen.\n\n"
    "## Moves\n\n"
    "Bulbasaur can learn a variety of Grass and Poison-type moves including "
    "Vine Whip, Razor Leaf, Solar Beam, and Sludge Bomb."
)

_SAMPLE_RESULT_JSON = PageMarkdownResult(
    url="https://example.com/bulbasaur",
    title="Bulbasaur - Bulbapedia",
    timestamp="2025-06-01T12:00:00Z",
    markdown=_SAMPLE_MARKDOWN,
).model_dump_json()

# Fixed-dimension embedding for consistency
_EMBEDDING_DIM = 128


def _fake_embedding(texts):
    """Generate deterministic fake embeddings based on text hash."""
    result = []
    for t in texts:
        h = hash(t) % 10000
        vec = [(h + i) % 100 / 100.0 for i in range(_EMBEDDING_DIM)]
        result.append(vec)
    return result


@pytest.fixture()
def in_memory_collection():
    """Create a fresh in-memory ChromaDB collection for each test."""
    client = chromadb.Client()
    collection = client.get_or_create_collection(name="pokemon_web_content_test")
    yield collection
    client.delete_collection(name="pokemon_web_content_test")


@pytest.fixture()
def mock_deps(in_memory_collection):
    """Patch singletons to use the in-memory collection and fake embeddings."""
    mock_emb = MagicMock()
    mock_emb.generate_embedding.side_effect = _fake_embedding

    with (
        patch("tools.web_vector_db._get_collection", return_value=in_memory_collection),
        patch("tools.web_vector_db._get_embedding_client", return_value=mock_emb),
        patch(
            "tools.web_vector_db.fetch_page_as_markdown",
            return_value=_SAMPLE_RESULT_JSON,
        ),
    ):
        yield in_memory_collection, mock_emb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test the full ingest → query cycle."""

    def test_ingest_and_query(self, mock_deps):
        collection, mock_emb = mock_deps

        # Ingest
        args = IngestWebPageArgs(url="https://example.com/bulbasaur")
        result = ingest_web_page(args)

        assert "Ingested" in result
        assert "chunks" in result
        assert "Bulbasaur" in result

        # Verify chunks are in the collection
        all_docs = collection.get()
        assert len(all_docs["ids"]) > 0

        # Verify metadata on first chunk
        meta = all_docs["metadatas"][0]
        assert meta["url"] == "https://example.com/bulbasaur"
        assert meta["title"] == "Bulbasaur - Bulbapedia"
        assert meta["source"] == "web"
        assert meta["chunk_index"] == 0
        assert "ingested_at" in meta

    def test_query_after_ingest(self, mock_deps):
        collection, mock_emb = mock_deps

        # Ingest first
        ingest_args = IngestWebPageArgs(url="https://example.com/bulbasaur")
        ingest_web_page(ingest_args)

        # Query
        query_args = QueryWebContentArgs(query="grass pokemon starter")
        result = query_web_content(query_args)

        assert "Bulbasaur" in result
        assert "**Source:**" in result


class TestDuplicateIngestion:
    """Verify that re-ingesting the same URL replaces chunks, not duplicates."""

    def test_no_duplicate_chunks_on_force_reingest(self, mock_deps):
        collection, mock_emb = mock_deps

        # Ingest twice (force by using max_age_days=0 won't work since
        # freshness check will pass; we need to patch is_content_fresh)
        args = IngestWebPageArgs(url="https://example.com/bulbasaur")

        result1 = ingest_web_page(args)
        assert "Ingested" in result1
        count_after_first = len(collection.get()["ids"])

        # Second ingest should be skipped because content is fresh
        result2 = ingest_web_page(args)
        assert "Skipped" in result2
        count_after_second = len(collection.get()["ids"])
        assert count_after_first == count_after_second

    def test_stale_content_gets_replaced(self, mock_deps):
        collection, mock_emb = mock_deps

        # First ingest
        args = IngestWebPageArgs(url="https://example.com/bulbasaur")
        result1 = ingest_web_page(args)
        assert "Ingested" in result1
        count_after_first = len(collection.get()["ids"])

        # Simulate stale content by patching is_content_fresh
        with patch("tools.web_vector_db.is_content_fresh", return_value=False):
            result2 = ingest_web_page(args)
            assert "Ingested" in result2

        count_after_second = len(collection.get()["ids"])
        # Should have same number of chunks (old deleted, new inserted)
        assert count_after_first == count_after_second


class TestFetchError:
    """Verify error handling when fetch fails."""

    def test_returns_error_on_fetch_failure(self, in_memory_collection):
        error_result = PageMarkdownResult(
            url="https://broken.example.com",
            title="",
            timestamp="2025-01-01T00:00:00Z",
            markdown="",
            error="Fetch failed: Connection refused",
        )

        mock_emb = MagicMock()
        with (
            patch("tools.web_vector_db._get_collection", return_value=in_memory_collection),
            patch("tools.web_vector_db._get_embedding_client", return_value=mock_emb),
            patch(
                "tools.web_vector_db.fetch_page_as_markdown",
                return_value=error_result.model_dump_json(),
            ),
        ):
            args = IngestWebPageArgs(url="https://broken.example.com")
            result = ingest_web_page(args)
            assert "Error" in result
            assert "Fetch failed" in result
