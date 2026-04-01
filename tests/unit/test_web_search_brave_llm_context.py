"""Unit tests for tools.web_search_brave_llm_context — schema validation & result parsing."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from tools.web_search_brave_llm_context import (
    BraveLLMContextInput,
    BraveLLMContextSearchResult,
    SearchResultItem,
    _perform_brave_llm_context_search,
    brave_llm_context_search,
)

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestBraveLLMContextInputValidation:
    """Verify the Pydantic input schema accepts/rejects expected values."""

    def test_minimal_input(self):
        inp = BraveLLMContextInput(query="Pikachu")
        assert inp.query == "Pikachu"
        assert inp.site_restrict is None
        assert inp.max_results == 5
        assert inp.maximum_number_of_tokens == 2048
        assert inp.context_threshold_mode == "balanced"

    def test_full_input(self):
        inp = BraveLLMContextInput(
            query="Pikachu", 
            site_restrict="bulbapedia.bulbagarden.net", 
            max_results=3,
            maximum_number_of_tokens=4096,
            context_threshold_mode="strict",
            freshness="pw"
        )
        assert inp.site_restrict == "bulbapedia.bulbagarden.net"
        assert inp.max_results == 3
        assert inp.maximum_number_of_tokens == 4096
        assert inp.context_threshold_mode == "strict"
        assert inp.freshness == "pw"

    def test_max_results_lower_bound(self):
        with pytest.raises(Exception):
            BraveLLMContextInput(query="test", max_results=0)

    def test_max_tokens_lower_bound(self):
        with pytest.raises(Exception):
            BraveLLMContextInput(query="test", maximum_number_of_tokens=256)


class TestBraveLLMContextSearchResult:
    """Verify the output schema."""

    def test_empty_results(self):
        result = BraveLLMContextSearchResult(
            query="test", results=[], total_returned=0
        )
        assert result.error is None
        assert result.total_returned == 0

    def test_with_error(self):
        result = BraveLLMContextSearchResult(
            query="test",
            results=[],
            total_returned=0,
            error="Fetch failed: timeout",
        )
        assert result.error == "Fetch failed: timeout"


# ---------------------------------------------------------------------------
# Tool function (mocked network)
# ---------------------------------------------------------------------------

_MOCK_BRAVE_LLM_RESPONSE = {
    "grounding": {
        "generic": [
            {
                "title": "Page One Title",
                "url": "https://example.com/page1",
                "snippets": [
                    "Snippet chunk 1.",
                    "Snippet chunk 2."
                ]
            },
            {
                "title": "Page Two Title",
                "url": "https://example.com/page2",
                "snippets": []
            },
            {
                "title": "Page Three Title",
                "url": "https://example.com/page3",
                "snippets": [
                    "Only one chunk here."
                ]
            }
        ]
    }
}


class TestBraveLLMContextSearchTool:
    """Verify the brave_llm_context_search tool function with mocked API."""

    @patch("tools.web_search_brave_llm_context.requests.get")
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_key"})
    def test_successful_search(self, mock_get):
        # Mock requests.get response
        mock_response = MagicMock()
        mock_response.json.return_value = _MOCK_BRAVE_LLM_RESPONSE
        mock_get.return_value = mock_response

        args = BraveLLMContextInput(query="Pikachu", max_results=3)
        raw = brave_llm_context_search(args)
        result = BraveLLMContextSearchResult.model_validate_json(raw)

        assert result.error is None
        assert result.query == "Pikachu"
        # Page Two was dropped because it had no concatenated snippets
        assert result.total_returned == 2
        assert len(result.results) == 2

        # Check parsing & concatenation
        assert result.results[0].snippet == "Snippet chunk 1.\\n\\nSnippet chunk 2."
        assert result.results[1].snippet == "Only one chunk here."
        
    @patch("tools.web_search_brave_llm_context.requests.get")
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_key"})
    def test_site_restrict_prepends_operator(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"grounding": {"generic": []}}
        mock_get.return_value = mock_response

        args = BraveLLMContextInput(
            query="Bulbasaur", site_restrict="bulbapedia.bulbagarden.net"
        )
        raw = brave_llm_context_search(args)
        result = BraveLLMContextSearchResult.model_validate_json(raw)

        assert result.query == "site:bulbapedia.bulbagarden.net Bulbasaur"
        mock_get.assert_called_once()
        # Verify if query with operator was sent
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["q"] == "site:bulbapedia.bulbagarden.net Bulbasaur"

    @patch("tools.web_search_brave_llm_context.requests.get")
    @patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "test_key"})
    def test_fetch_failure_returns_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")

        args = BraveLLMContextInput(query="test")
        raw = brave_llm_context_search(args)
        result = BraveLLMContextSearchResult.model_validate_json(raw)

        assert result.error is not None
        assert "Search failed" in result.error
        assert result.total_returned == 0

    @patch.dict(os.environ, clear=True)
    def test_missing_api_key_returns_error(self):
        # Ensure BRAVE_SEARCH_API_KEY is not in environ
        args = BraveLLMContextInput(query="test")
        raw = brave_llm_context_search(args)
        result = BraveLLMContextSearchResult.model_validate_json(raw)

        assert result.error is not None
        assert "BRAVE_SEARCH_API_KEY environment variable is not set" in result.error
        assert result.total_returned == 0
