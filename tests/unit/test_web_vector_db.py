"""Unit tests for tools.web_vector_db — pre-processing, ID generation, freshness checks."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


from tools.web_content import PageMarkdownResult
from tools.web_vector_db import (
    prepare_markdown,
    generate_chunk_id,
    is_content_fresh,
    delete_url_chunks,
    QueryWebContentArgs,
    IngestWebPageArgs,
)


# ---------------------------------------------------------------------------
# prepare_markdown
# ---------------------------------------------------------------------------


class TestPrepareMarkdown:
    """Verify title prefix injection and YAML removal."""

    def test_prefixes_title(self):
        result = PageMarkdownResult(
            url="https://example.com",
            title="My Page",
            timestamp="2025-01-01T00:00:00Z",
            markdown='Some content here.',
        )
        clean = prepare_markdown(result)
        assert clean.startswith("# My Page\n\n")
        assert "Some content here." in clean

    def test_no_title(self):
        result = PageMarkdownResult(
            url="https://example.com",
            title="",
            timestamp="2025-01-01T00:00:00Z",
            markdown="Just plain content.",
        )
        clean = prepare_markdown(result)
        assert clean == "Just plain content."

    def test_empty_markdown_with_title(self):
        result = PageMarkdownResult(
            url="https://example.com",
            title="Title Only",
            timestamp="2025-01-01T00:00:00Z",
            markdown="",
        )
        clean = prepare_markdown(result)
        assert clean == "# Title Only"


# ---------------------------------------------------------------------------
# generate_chunk_id
# ---------------------------------------------------------------------------


class TestGenerateChunkId:
    """Verify deterministic ID generation."""

    def test_format(self):
        cid = generate_chunk_id("https://example.com", 0)
        parts = cid.split("_")
        assert len(parts) == 2
        assert len(parts[0]) == 16  # sha256[:16]
        assert parts[1] == "0"

    def test_deterministic(self):
        id1 = generate_chunk_id("https://example.com", 3)
        id2 = generate_chunk_id("https://example.com", 3)
        assert id1 == id2

    def test_different_urls_produce_different_ids(self):
        id1 = generate_chunk_id("https://a.com", 0)
        id2 = generate_chunk_id("https://b.com", 0)
        assert id1 != id2

    def test_different_indices_produce_different_ids(self):
        id1 = generate_chunk_id("https://example.com", 0)
        id2 = generate_chunk_id("https://example.com", 1)
        assert id1 != id2


# ---------------------------------------------------------------------------
# is_content_fresh
# ---------------------------------------------------------------------------


class TestIsContentFresh:
    """Verify freshness check with mocked ChromaDB collection."""

    def _mock_collection(self, ids=None, metadatas=None):
        col = MagicMock()
        col.get.return_value = {
            "ids": ids or [],
            "metadatas": metadatas or [],
        }
        return col

    def test_returns_false_when_no_chunks_exist(self):
        col = self._mock_collection()
        assert is_content_fresh(col, "https://example.com") is False

    def test_returns_true_when_fresh(self):
        recent = datetime.now(timezone.utc).isoformat()
        col = self._mock_collection(
            ids=["abc_0"],
            metadatas=[{"ingested_at": recent}],
        )
        assert is_content_fresh(col, "https://example.com", max_age_days=7) is True

    def test_returns_false_when_stale(self):
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        col = self._mock_collection(
            ids=["abc_0"],
            metadatas=[{"ingested_at": old}],
        )
        assert is_content_fresh(col, "https://example.com", max_age_days=7) is False

    def test_returns_false_when_missing_ingested_at(self):
        col = self._mock_collection(
            ids=["abc_0"],
            metadatas=[{"url": "https://example.com"}],
        )
        assert is_content_fresh(col, "https://example.com") is False

    def test_returns_false_on_invalid_timestamp(self):
        col = self._mock_collection(
            ids=["abc_0"],
            metadatas=[{"ingested_at": "not-a-date"}],
        )
        assert is_content_fresh(col, "https://example.com") is False


# ---------------------------------------------------------------------------
# delete_url_chunks
# ---------------------------------------------------------------------------


class TestDeleteUrlChunks:
    """Verify chunk deletion with mocked ChromaDB collection."""

    def test_deletes_existing_chunks(self):
        col = MagicMock()
        col.get.return_value = {"ids": ["a_0", "a_1", "a_2"]}
        deleted = delete_url_chunks(col, "https://example.com")
        assert deleted == 3
        col.delete.assert_called_once_with(ids=["a_0", "a_1", "a_2"])

    def test_returns_zero_when_nothing_to_delete(self):
        col = MagicMock()
        col.get.return_value = {"ids": []}
        deleted = delete_url_chunks(col, "https://example.com")
        assert deleted == 0
        col.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestIngestWebPageArgs:
    """Verify the ingest tool input schema."""

    def test_minimal(self):
        args = IngestWebPageArgs(url="https://example.com")
        assert args.css_selector is None
        assert args.use_stealth is False
        assert args.max_age_days == 60

    def test_full(self):
        args = IngestWebPageArgs(
            url="https://example.com",
            css_selector="article",
            use_stealth=True,
            max_age_days=14,
        )
        assert args.css_selector == "article"
        assert args.max_age_days == 14


class TestQueryWebContentArgs:
    """Verify the query tool input schema."""

    def test_minimal(self):
        args = QueryWebContentArgs(query="fire type pokemon")
        assert args.n_results == 5
        assert args.filter_url is None

    def test_with_filter(self):
        args = QueryWebContentArgs(
            query="evolution",
            n_results=3,
            filter_url="https://bulbapedia.bulbagarden.net/wiki/Bulbasaur",
        )
        assert args.n_results == 3
        assert args.filter_url is not None


# ---------------------------------------------------------------------------
# query_web_content output formatting
# ---------------------------------------------------------------------------


class TestQueryOutputFormatting:
    """Verify query result formatting."""

    @patch("tools.web_vector_db._get_embedding_client")
    @patch("tools.web_vector_db._get_collection")
    def test_formats_results_as_markdown(self, mock_col_fn, mock_emb_fn):
        from tools.web_vector_db import query_web_content

        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [[0.1] * 128]
        mock_emb_fn.return_value = mock_emb

        mock_col = MagicMock()
        mock_col.query.return_value = {
            "ids": [["id1"]],
            "metadatas": [[{
                "title": "Bulbasaur",
                "url": "https://bulbapedia.example.com/wiki/Bulbasaur",
                "chunk_index": 0,
                "total_chunks": 5,
            }]],
            "documents": [["Bulbasaur is a Grass/Poison-type Pokémon."]],
        }
        mock_col_fn.return_value = mock_col

        args = QueryWebContentArgs(query="grass pokemon")
        result = query_web_content(args)

        assert "### Bulbasaur" in result
        assert "**Source:**" in result
        assert "**Chunk:** 1/5" in result
        assert "Grass/Poison-type" in result

    @patch("tools.web_vector_db._get_embedding_client")
    @patch("tools.web_vector_db._get_collection")
    def test_no_results_message(self, mock_col_fn, mock_emb_fn):
        from tools.web_vector_db import query_web_content

        mock_emb = MagicMock()
        mock_emb.generate_embedding.return_value = [[0.1] * 128]
        mock_emb_fn.return_value = mock_emb

        mock_col = MagicMock()
        mock_col.query.return_value = {"ids": [[]], "metadatas": [[]], "documents": [[]]}
        mock_col_fn.return_value = mock_col

        args = QueryWebContentArgs(query="nonexistent topic")
        result = query_web_content(args)
        assert "No results found" in result
