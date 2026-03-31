"""Unit tests for tools.web_content — schema validation & content extraction."""

import json
from pathlib import Path
from unittest.mock import patch


from tools.web_content import (
    FetchPageInput,
    PageMarkdownResult,
    _extract_main_html,
    _extract_title,
    fetch_page_as_markdown,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestFetchPageInputValidation:
    """Verify the Pydantic input schema."""

    def test_minimal_input(self):
        inp = FetchPageInput(url="https://example.com")
        assert inp.url == "https://example.com"
        assert inp.css_selector is None
        assert inp.use_stealth is False

    def test_full_input(self):
        inp = FetchPageInput(
            url="https://example.com",
            css_selector="article",
            use_stealth=True,
        )
        assert inp.css_selector == "article"
        assert inp.use_stealth is True


class TestPageMarkdownResult:
    """Verify the output schema."""

    def test_successful_result(self):
        result = PageMarkdownResult(
            url="https://example.com",
            title="Example",
            markdown="# Hello\n\nWorld",
            timestamp="2026-03-22T00:00:00Z",
        )
        assert result.error is None

    def test_error_result(self):
        result = PageMarkdownResult(
            url="https://example.com",
            title="",
            markdown="",
            error="Fetch failed: timeout",
            timestamp="2026-03-22T00:00:00Z",
        )
        assert result.error is not None

    def test_serialization_roundtrip(self):
        result = PageMarkdownResult(
            url="https://example.com", title="T", markdown="# M", timestamp="2026-03-22T00:00:00Z"
        )
        data = json.loads(result.model_dump_json())
        reconstructed = PageMarkdownResult(**data)
        assert reconstructed == result


# ---------------------------------------------------------------------------
# Content extraction helpers
# ---------------------------------------------------------------------------

_FULL_PAGE_HTML = """
<html>
<head><title>Test Page Title</title></head>
<body>
    <nav><a href="/">Home</a></nav>
    <header><h1>Site Header</h1></header>
    <article>
        <h2>Main Article</h2>
        <p>This is the main content.</p>
    </article>
    <aside>Sidebar stuff</aside>
    <footer>Copyright 2025</footer>
</body>
</html>
"""

_WIKI_PAGE_HTML = """
<html>
<head><title>Bulbasaur - Bulbapedia</title></head>
<body>
    <div id="mw-content-text">
        <div class="mw-parser-output">
            <p>Bulbasaur is a Grass/Poison-type Pokémon.</p>
        </div>
    </div>
</body>
</html>
"""

_NO_SEMANTIC_HTML = """
<html>
<head><title>Plain Page</title></head>
<body>
    <nav>Menu</nav>
    <div>Some content here</div>
    <footer>Footer</footer>
</body>
</html>
"""


class TestExtractTitle:
    """Verify title extraction from <title> and <h1>."""

    def test_extracts_from_title_tag(self):
        from scrapling.parser import Selector

        page = Selector(_FULL_PAGE_HTML)
        assert _extract_title(page) == "Test Page Title"

    def test_falls_back_to_h1(self):
        from scrapling.parser import Selector

        html = "<html><body><h1>Heading Title</h1></body></html>"
        page = Selector(html)
        assert _extract_title(page) == "Heading Title"

    def test_returns_empty_for_no_title(self):
        from scrapling.parser import Selector

        page = Selector("<html><body><p>No title here</p></body></html>")
        assert _extract_title(page) == ""


class TestExtractMainHtml:
    """Verify the CSS-selector priority chain for content extraction."""

    def test_explicit_selector(self):
        from scrapling.parser import Selector

        page = Selector(_FULL_PAGE_HTML)
        html = _extract_main_html(page, css_selector="article")
        assert "Main Article" in html
        assert "nav" not in html.lower() or "nav" not in html

    def test_auto_detects_article(self):
        from scrapling.parser import Selector

        page = Selector(_FULL_PAGE_HTML)
        html = _extract_main_html(page)
        assert "Main Article" in html

    def test_auto_detects_wiki_content(self):
        from scrapling.parser import Selector

        page = Selector(_WIKI_PAGE_HTML)
        html = _extract_main_html(page)
        assert "Bulbasaur" in html

    def test_fallback_strips_boilerplate(self):
        from scrapling.parser import Selector

        page = Selector(_NO_SEMANTIC_HTML)
        html = _extract_main_html(page)
        assert "Some content" in html

    def test_explicit_selector_miss_falls_back(self):
        from scrapling.parser import Selector

        page = Selector(_FULL_PAGE_HTML)
        # Selector that doesn't match anything
        html = _extract_main_html(page, css_selector="#nonexistent")
        # Should still return content via auto-detect
        assert "Main Article" in html


# ---------------------------------------------------------------------------
# Tool function (mocked network)
# ---------------------------------------------------------------------------


class TestFetchPageAsMarkdownTool:
    """Verify the fetch_page_as_markdown tool with mocked fetcher."""

    @patch("tools.web_content.Fetcher")
    def test_successful_fetch(self, mock_fetcher_cls):
        from scrapling.parser import Selector

        mock_page = Selector(_FULL_PAGE_HTML)
        mock_fetcher_cls.get.return_value = mock_page

        args = FetchPageInput(url="https://example.com")
        raw = fetch_page_as_markdown(args)
        result = PageMarkdownResult.model_validate_json(raw)

        assert result.error is None
        assert result.url == "https://example.com"
        assert result.title == "Test Page Title"
        assert "Main Article" in result.markdown
        assert "---" not in result.markdown  # YAML header should not be in the result object
        assert len(result.markdown) > 0

        from utils.config import settings
        # Verify the file was saved with the YAML header
        save_dir = Path(settings.WEB_SCRAPER_DIR)
        safe_title = "Test_Page_Title"
        filepath = save_dir / f"{safe_title}.md"
        assert filepath.exists()
        saved_content = filepath.read_text(encoding="utf-8")
        assert saved_content.startswith("---")
        assert 'title: "Test Page Title"' in saved_content
        assert "Main Article" in saved_content

    @patch("tools.web_content.StealthyFetcher")
    def test_stealth_mode_uses_stealthy_fetcher(self, mock_stealthy_cls):
        from scrapling.parser import Selector

        mock_page = Selector(_FULL_PAGE_HTML)
        mock_stealthy_cls.fetch.return_value = mock_page

        args = FetchPageInput(url="https://example.com", use_stealth=True)
        raw = fetch_page_as_markdown(args)
        result = PageMarkdownResult.model_validate_json(raw)

        assert result.error is None
        mock_stealthy_cls.fetch.assert_called_once()

    @patch("tools.web_content.Fetcher")
    def test_fetch_failure_returns_error(self, mock_fetcher_cls):
        mock_fetcher_cls.get.side_effect = ConnectionError("Network unreachable")

        args = FetchPageInput(url="https://example.com")
        raw = fetch_page_as_markdown(args)
        result = PageMarkdownResult.model_validate_json(raw)

        assert result.error is not None
        assert "Fetch failed" in result.error
        assert result.markdown == ""

    @patch("tools.web_content.Fetcher")
    def test_custom_css_selector(self, mock_fetcher_cls):
        from scrapling.parser import Selector

        mock_page = Selector(_FULL_PAGE_HTML)
        mock_fetcher_cls.get.return_value = mock_page

        args = FetchPageInput(url="https://example.com", css_selector="article")
        raw = fetch_page_as_markdown(args)
        result = PageMarkdownResult.model_validate_json(raw)

        assert result.error is None
        assert "Main Article" in result.markdown
