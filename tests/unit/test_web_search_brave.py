"""Unit tests for tools.web_search_brave — schema validation & result parsing."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from tools.web_search_brave import (
    BraveSearchInput,
    BraveSearchResult,
    SearchResultItem,
    _perform_brave_search,
    brave_search,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestBraveSearchInputValidation:
    """Verify the Pydantic input schema accepts/rejects expected values."""

    def test_minimal_input(self):
        inp = BraveSearchInput(query="Pikachu")
        assert inp.query == "Pikachu"
        assert inp.site_restrict is None
        assert inp.max_results == 10

    def test_full_input(self):
        inp = BraveSearchInput(
            query="Pikachu", site_restrict="bulbapedia.bulbagarden.net", max_results=5
        )
        assert inp.site_restrict == "bulbapedia.bulbagarden.net"
        assert inp.max_results == 5

    def test_max_results_lower_bound(self):
        with pytest.raises(Exception):
            BraveSearchInput(query="test", max_results=0)

    def test_max_results_upper_bound(self):
        with pytest.raises(Exception):
            BraveSearchInput(query="test", max_results=51)


class TestSearchResultItem:
    """Verify the result item schema."""

    def test_valid_item(self):
        item = SearchResultItem(
            title="Test Title",
            url="https://example.com",
            snippet="A test snippet.",
        )
        assert item.title == "Test Title"
        assert item.url == "https://example.com"

    def test_serialization_roundtrip(self):
        item = SearchResultItem(
            title="Title", url="https://example.com", snippet="Snippet"
        )
        data = json.loads(item.model_dump_json())
        reconstructed = SearchResultItem(**data)
        assert reconstructed == item


class TestBraveSearchResult:
    """Verify the output schema."""

    def test_empty_results(self):
        result = BraveSearchResult(
            query="test", results=[], total_returned=0
        )
        assert result.error is None
        assert result.total_returned == 0

    def test_with_error(self):
        result = BraveSearchResult(
            query="test",
            results=[],
            total_returned=0,
            error="Fetch failed: timeout",
        )
        assert result.error == "Fetch failed: timeout"


# ---------------------------------------------------------------------------
# Tool function (mocked network)
# ---------------------------------------------------------------------------

_MOCK_BRAVE_RESPONSE = {
    "web": {
        "results": [
            {
                "title": "Page One Title",
                "url": "https://example.com/page1",
                "description": "First snippet here."
            },
            {
                "title": "Page Two Title",
                "url": "https://example.com/page2",
                "description": ""
            },
            {
                "title": "Page Three Title",
                "url": "https://example.com/page3",
                "extra_snippets": [
                    "Extra snippet part 1.",
                    "Extra snippet part 2."
                ]
            }
        ]
    }
}


class TestBraveSearchTool:
    """Verify the brave_search tool function with mocked API."""

    @patch("tools.web_search_brave.requests.get")
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_key"})
    def test_successful_search(self, mock_get):
        # Mock requests.get response
        mock_response = MagicMock()
        mock_response.json.return_value = _MOCK_BRAVE_RESPONSE
        mock_get.return_value = mock_response

        args = BraveSearchInput(query="Pikachu", max_results=3)
        raw = brave_search(args)
        result = BraveSearchResult.model_validate_json(raw)

        assert result.error is None
        assert result.query == "Pikachu"
        assert result.total_returned == 3
        assert len(result.results) == 3

        # Check parsing
        assert result.results[0].snippet == "First snippet here."
        # Blank description without extra_snippets becomes empty or stripped
        assert result.results[1].snippet == ""
        # Check extraction from extra_snippets
        assert result.results[2].snippet == "Extra snippet part 1. Extra snippet part 2."

    @patch("tools.web_search_brave.requests.get")
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_key"})
    def test_site_restrict_prepends_operator(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_get.return_value = mock_response

        args = BraveSearchInput(
            query="Bulbasaur", site_restrict="bulbapedia.bulbagarden.net"
        )
        raw = brave_search(args)
        result = BraveSearchResult.model_validate_json(raw)

        assert result.query == "site:bulbapedia.bulbagarden.net Bulbasaur"
        mock_get.assert_called_once()
        # Verify if query with operator was sent
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["q"] == "site:bulbapedia.bulbagarden.net Bulbasaur"

    @patch("tools.web_search_brave.requests.get")
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_key"})
    def test_fetch_failure_returns_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        args = BraveSearchInput(query="test")
        raw = brave_search(args)
        result = BraveSearchResult.model_validate_json(raw)

        assert result.error is not None
        assert "Search failed" in result.error
        assert result.total_returned == 0

    @patch.dict(os.environ, clear=True)
    def test_missing_api_key_returns_error(self):
        # We ensure BRAVE_SEARCH_API_KEY is not in environ
        args = BraveSearchInput(query="test")
        raw = brave_search(args)
        result = BraveSearchResult.model_validate_json(raw)

        assert result.error is not None
        assert "BRAVE_SEARCH_API_KEY environment variable is not set" in result.error
        assert result.total_returned == 0

