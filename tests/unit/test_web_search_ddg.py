"""Unit tests for tools.web_search_ddg — schema validation & result parsing."""

import json
from unittest.mock import patch

import pytest

from tools.web_search_ddg import (
    DuckDuckGoSearchInput,
    DuckDuckGoSearchResult,
    SearchResultItem,
    _build_ddg_url,
    _parse_results,
    duckduckgo_search,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestDuckDuckGoSearchInputValidation:
    """Verify the Pydantic input schema accepts/rejects expected values."""

    def test_minimal_input(self):
        inp = DuckDuckGoSearchInput(query="Pikachu")
        assert inp.query == "Pikachu"
        assert inp.site_restrict is None
        assert inp.max_results == 10

    def test_full_input(self):
        inp = DuckDuckGoSearchInput(
            query="Pikachu", site_restrict="bulbapedia.bulbagarden.net", max_results=5
        )
        assert inp.site_restrict == "bulbapedia.bulbagarden.net"
        assert inp.max_results == 5

    def test_max_results_lower_bound(self):
        with pytest.raises(Exception):
            DuckDuckGoSearchInput(query="test", max_results=0)

    def test_max_results_upper_bound(self):
        with pytest.raises(Exception):
            DuckDuckGoSearchInput(query="test", max_results=51)


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


class TestDuckDuckGoSearchResult:
    """Verify the output schema."""

    def test_empty_results(self):
        result = DuckDuckGoSearchResult(
            query="test", results=[], total_returned=0
        )
        assert result.error is None
        assert result.total_returned == 0

    def test_with_error(self):
        result = DuckDuckGoSearchResult(
            query="test",
            results=[],
            total_returned=0,
            error="Fetch failed: timeout",
        )
        assert result.error == "Fetch failed: timeout"


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------


class TestBuildDDGUrl:
    """Verify URL construction."""

    def test_simple_query(self):
        url = _build_ddg_url("Pikachu")
        assert "q=Pikachu" in url
        assert "t=h_" in url

    def test_query_with_spaces(self):
        url = _build_ddg_url("fire type pokemon")
        assert "q=fire+type+pokemon" in url

    def test_site_operator_in_query(self):
        url = _build_ddg_url("site:bulbapedia.bulbagarden.net Bulbasaur")
        assert "site" in url
        assert "Bulbasaur" in url


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

_MOCK_RESULTS_HTML = """
<html><body>
<div class="results">
    <article>
        <h2><a data-testid="result-title-a" href="https://example.com/page1"><span>Page One Title</span></a></h2>
        <div data-result="snippet">This is the first snippet with enough text to be detected.</div>
    </article>
    <article>
        <h2><a href="https://example.com/page2">Page Two Title</a></h2>
        <div class="yD50T_hI">This is the second snippet with enough text to be detected.</div>
    </article>
    <div data-testid="result">
        <h2><a href="https://example.com/page3"><span>Page Three Title</span></a></h2>
        <div><div>Third snippet here with enough text to pass the length check and not be skipped.</div></div>
    </div>
</div>
</body></html>
"""


class TestParseResults:
    """Verify CSS-based result extraction from mock HTML."""

    @pytest.fixture()
    def mock_page(self):
        from scrapling.parser import Selector

        return Selector(_MOCK_RESULTS_HTML)

    def test_parse_all_results(self, mock_page):
        items = _parse_results(mock_page, max_results=10)
        assert len(items) == 3
        assert items[0].title == "Page One Title"
        assert items[0].url == "https://example.com/page1"
        assert "first snippet" in items[0].snippet

    def test_max_results_limits_output(self, mock_page):
        items = _parse_results(mock_page, max_results=1)
        assert len(items) == 1
        assert items[0].title == "Page One Title"

    def test_parse_empty_page(self):
        from scrapling.parser import Selector

        page = Selector("<html><body></body></html>")
        items = _parse_results(page, max_results=10)
        assert items == []


# ---------------------------------------------------------------------------
# Tool function (mocked network)
# ---------------------------------------------------------------------------


class TestDuckDuckGoSearchTool:
    """Verify the duckduckgo_search tool function with mocked fetcher."""

    @patch("tools.web_search_ddg.StealthyFetcher")
    def test_successful_search(self, mock_fetcher_cls):
        from scrapling.parser import Selector

        mock_page = Selector(_MOCK_RESULTS_HTML)
        mock_fetcher_cls.fetch.return_value = mock_page

        args = DuckDuckGoSearchInput(query="Pikachu", max_results=2)
        raw = duckduckgo_search(args)
        result = DuckDuckGoSearchResult.model_validate_json(raw)

        assert result.error is None
        assert result.query == "Pikachu"
        assert result.total_returned == 2
        assert len(result.results) == 2

    @patch("tools.web_search_ddg.StealthyFetcher")
    def test_site_restrict_prepends_operator(self, mock_fetcher_cls):
        from scrapling.parser import Selector

        mock_page = Selector("<html><body></body></html>")
        mock_fetcher_cls.fetch.return_value = mock_page

        args = DuckDuckGoSearchInput(
            query="Bulbasaur", site_restrict="bulbapedia.bulbagarden.net"
        )
        raw = duckduckgo_search(args)
        result = DuckDuckGoSearchResult.model_validate_json(raw)

        assert result.query == "site:bulbapedia.bulbagarden.net Bulbasaur"

    @patch("tools.web_search_ddg.StealthyFetcher")
    def test_fetch_failure_returns_error(self, mock_fetcher_cls):
        mock_fetcher_cls.fetch.side_effect = RuntimeError("Connection refused")

        args = DuckDuckGoSearchInput(query="test")
        raw = duckduckgo_search(args)
        result = DuckDuckGoSearchResult.model_validate_json(raw)

        assert result.error is not None
        assert "Fetch failed" in result.error
        assert result.total_returned == 0
