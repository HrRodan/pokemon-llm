"""
Integration tests for web search and content extraction tools.

These tests hit live websites and may be flaky. Run manually to verify
end-to-end behaviour, not in CI.
"""


import pytest

from tools.web_content import FetchPageInput, PageMarkdownResult, fetch_page_as_markdown
from tools.web_search import GoogleSearchInput, GoogleSearchResult, google_search
from tools.web_search_ddg import DuckDuckGoSearchInput, DuckDuckGoSearchResult, duckduckgo_search
from tools.web_search_brave import BraveSearchInput, BraveSearchResult, brave_search

pytestmark = pytest.mark.integration


class TestGoogleSearchLive:
    """Live integration tests for google_search tool."""

    @pytest.mark.slow
    def test_basic_search(self):
        """Search for a common term and verify we get results."""
        args = GoogleSearchInput(query="Pikachu pokemon", max_results=3)
        raw = google_search(args)
        result = GoogleSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"
        assert result.total_returned > 0, "Expected at least one result"

        for item in result.results:
            assert item.title, "Result should have a title"
            assert item.url.startswith("http"), f"Bad URL: {item.url}"

    @pytest.mark.slow
    def test_site_restricted_search(self):
        """Search restricted to bulbapedia."""
        args = GoogleSearchInput(
            query="Bulbasaur",
            site_restrict="bulbapedia.bulbagarden.net",
            max_results=3,
        )
        raw = google_search(args)
        result = GoogleSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"
        assert "site:bulbapedia.bulbagarden.net" in result.query


class TestDuckDuckGoSearchLive:
    """Live integration tests for duckduckgo_search tool."""

    @pytest.mark.slow
    def test_basic_search(self):
        """Search for a common term and verify we get results."""
        args = DuckDuckGoSearchInput(query="Pikachu pokemon", max_results=3)
        raw = duckduckgo_search(args)
        result = DuckDuckGoSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"
        assert result.total_returned > 0, "Expected at least one result"

        for item in result.results:
            assert item.title, "Result should have a title"
            assert item.url.startswith("http"), f"Bad URL: {item.url}"

    @pytest.mark.slow
    def test_site_restricted_search(self):
        """Search restricted to bulbapedia."""
        args = DuckDuckGoSearchInput(
            query="Bulbasaur",
            site_restrict="bulbapedia.bulbagarden.net",
            max_results=3,
        )
        raw = duckduckgo_search(args)
        result = DuckDuckGoSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"
        assert "site:bulbapedia.bulbagarden.net" in result.query

    @pytest.mark.slow
    def test_no_ads_in_results(self):
        """Use a commercial query likely to surface ads and verify none slip through."""
        _AD_URL_PATTERNS = (
            "duckduckgo.com/y.js",
            "ad.doubleclick.net",
            "googleadservices.com",
            "bing.com/aclick",
        )
        args = DuckDuckGoSearchInput(query="buy pokemon cards online", max_results=10)
        raw = duckduckgo_search(args)
        result = DuckDuckGoSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"

        for item in result.results:
            for pattern in _AD_URL_PATTERNS:
                assert pattern not in item.url, (
                    f"Ad redirect URL slipped through: {item.url}"
                )
            assert item.url.startswith("http"), f"Unexpected URL format: {item.url}"

        print(f"\n[ad-filter live] {result.total_returned} organic results returned:")
        for item in result.results:
            print(f"  {item.title} — {item.url}")


class TestBraveSearchLive:
    """Live integration tests for brave_search tool."""

    @pytest.mark.slow
    def test_basic_search(self):
        """Search for a common term and verify we get results."""
        args = BraveSearchInput(query="Pikachu pokemon", max_results=3)
        raw = brave_search(args)
        result = BraveSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"
        assert result.total_returned > 0, "Expected at least one result"

        for item in result.results:
            assert item.title, "Result should have a title"
            assert item.url.startswith("http"), f"Bad URL: {item.url}"

    @pytest.mark.slow
    def test_site_restricted_search(self):
        """Search restricted to bulbapedia."""
        args = BraveSearchInput(
            query="Bulbasaur",
            site_restrict="bulbapedia.bulbagarden.net",
            max_results=3,
        )
        raw = brave_search(args)
        result = BraveSearchResult.model_validate_json(raw)

        assert result.error is None, f"Search failed: {result.error}"
        # Some URLs might omit www or similar, but the URL must contain bulbapedia
        for item in result.results:
             assert "bulbapedia.bulbagarden.net" in item.url


class TestFetchPageLive:
    """Live integration tests for fetch_page_as_markdown tool."""

    def test_fetch_example_com(self):
        """Fetch example.com — a stable, simple page."""
        args = FetchPageInput(url="https://example.com")
        raw = fetch_page_as_markdown(args)
        result = PageMarkdownResult.model_validate_json(raw)

        assert result.error is None, f"Fetch failed: {result.error}"
        assert "Example Domain" in result.title or "example" in result.title.lower()
        assert len(result.markdown) > 0

    @pytest.mark.slow
    def test_fetch_bulbapedia_page(self):
        """Fetch a Bulbapedia page and check content quality."""
        args = FetchPageInput(
            url="https://bulbapedia.bulbagarden.net/wiki/Pikachu_(Pok%C3%A9mon)",
            css_selector="#mw-content-text",
        )
        raw = fetch_page_as_markdown(args)
        result = PageMarkdownResult.model_validate_json(raw)

        assert result.error is None, f"Fetch failed: {result.error}"
        assert len(result.markdown) > 100, "Expected substantial content"
        assert "pikachu" in result.markdown.lower(), "Expected Pikachu in content"
