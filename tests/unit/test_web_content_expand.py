"""
Unit tests for the new web content tools in tools/web_content.py.

Covers:
- _is_boilerplate_link
- _normalize_url
- _matches_domain_filter
- _extract_headings_from_markdown
- _extract_table_data
- extract_page_links (Pydantic schema validation + mocked fetch)
- summarize_page  (mocked fetch + mocked LLMQuery)
- extract_structured_data (mocked fetch)
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.web_content import (
    ExtractLinksInput,
    ExtractLinksResult,
    ExtractStructuredDataInput,
    ExtractStructuredDataResult,
    SummarizePageInput,
    PageSummaryResult,
    _is_boilerplate_link,
    _matches_domain_filter,
    _normalize_url,
    _extract_headings_from_markdown,
    _extract_table_data,
    extract_page_links,
    extract_structured_data,
    summarize_page,
)


# ---------------------------------------------------------------------------
# _is_boilerplate_link
# ---------------------------------------------------------------------------


class TestIsBoilerplateLink:
    @pytest.mark.parametrize("url,anchor", [
        ("https://example.com/impressum", "Impressum"),
        ("https://example.com/datenschutz", "Datenschutz"),
        ("https://example.com/privacy-policy", "Privacy"),
        ("https://example.com/terms-of-service", "Terms"),
        ("https://example.com/cookie-policy", "Cookies"),
        ("https://example.com/login", "Login"),
        ("https://example.com/sign-in", "Sign In"),
        ("https://example.com/register", "Register"),
        ("https://facebook.com/page", "Follow us"),
        ("https://twitter.com/handle", "Twitter"),
        ("https://example.com/image.png", "Logo"),
        ("https://example.com/style.css", ""),
        ("mailto:info@example.com", "Contact"),
        ("https://en.wikipedia.org/wiki/Special:Search", "Search"),
        ("https://en.wikipedia.org/wiki/Category:Pokemon", "Category"),
    ])
    def test_boilerplate_detected(self, url: str, anchor: str) -> None:
        assert _is_boilerplate_link(url, anchor) is True

    @pytest.mark.parametrize("url,anchor", [
        ("https://bulbapedia.bulbagarden.net/wiki/Pikachu", "Pikachu"),
        ("https://example.com/articles/news-2025", "Latest News"),
        ("https://example.com/products/widget", "Widget"),
        ("https://example.com/about-our-team", "Our Team"),  # Not "about us"
    ])
    def test_content_link_not_blocked(self, url: str, anchor: str) -> None:
        assert _is_boilerplate_link(url, anchor) is False


# ---------------------------------------------------------------------------
# _normalize_url
# ---------------------------------------------------------------------------


class TestNormalizeUrl:
    def test_absolute_url_unchanged(self) -> None:
        result = _normalize_url("https://example.com/page", "https://example.com/")
        assert result == "https://example.com/page"

    def test_relative_url_resolved(self) -> None:
        result = _normalize_url("/wiki/Pikachu", "https://bulbapedia.bulbagarden.net/")
        assert result == "https://bulbapedia.bulbagarden.net/wiki/Pikachu"

    def test_fragment_stripped(self) -> None:
        result = _normalize_url("https://example.com/page#section", "https://example.com/")
        assert result == "https://example.com/page"

    def test_mailto_returns_none(self) -> None:
        assert _normalize_url("mailto:foo@bar.com", "https://example.com/") is None

    def test_javascript_returns_none(self) -> None:
        assert _normalize_url("javascript:void(0)", "https://example.com/") is None

    def test_bare_fragment_returns_base(self) -> None:
        result = _normalize_url("#top", "https://example.com/page")
        assert result == "https://example.com/page"

    def test_query_params_preserved(self) -> None:
        result = _normalize_url("https://example.com/search?q=pikachu", "https://example.com/")
        assert result == "https://example.com/search?q=pikachu"


# ---------------------------------------------------------------------------
# _matches_domain_filter
# ---------------------------------------------------------------------------


class TestMatchesDomainFilter:
    SOURCE = "bulbapedia.bulbagarden.net"

    def test_domain_filter_exact_match(self) -> None:
        assert _matches_domain_filter(
            "https://bulbapedia.bulbagarden.net/wiki/Pikachu",
            domain_filter="bulbapedia.bulbagarden.net",
            source_domain=self.SOURCE,
            include_external=False,
        ) is True

    def test_domain_filter_partial_match(self) -> None:
        assert _matches_domain_filter(
            "https://bulbapedia.bulbagarden.net/wiki/Pikachu",
            domain_filter="bulbagarden",
            source_domain=self.SOURCE,
            include_external=False,
        ) is True

    def test_domain_filter_no_match(self) -> None:
        assert _matches_domain_filter(
            "https://external.com/page",
            domain_filter="bulbapedia.bulbagarden.net",
            source_domain=self.SOURCE,
            include_external=True,
        ) is False

    def test_domain_filter_takes_precedence_over_include_external(self) -> None:
        # domain_filter set → only matching domain allowed, regardless of include_external
        assert _matches_domain_filter(
            "https://external.com/page",
            domain_filter="bulbapedia.bulbagarden.net",
            source_domain=self.SOURCE,
            include_external=True,
        ) is False

    def test_same_domain_allowed_without_filter(self) -> None:
        assert _matches_domain_filter(
            f"https://{self.SOURCE}/wiki/Charmander",
            domain_filter=None,
            source_domain=self.SOURCE,
            include_external=False,
        ) is True

    def test_external_blocked_by_default(self) -> None:
        assert _matches_domain_filter(
            "https://external.com/page",
            domain_filter=None,
            source_domain=self.SOURCE,
            include_external=False,
        ) is False

    def test_external_allowed_with_flag(self) -> None:
        assert _matches_domain_filter(
            "https://external.com/page",
            domain_filter=None,
            source_domain=self.SOURCE,
            include_external=True,
        ) is True

    def test_case_insensitive(self) -> None:
        assert _matches_domain_filter(
            "https://BULBAPEDIA.bulbagarden.net/wiki/Pikachu",
            domain_filter="bulbapedia.bulbagarden.net",
            source_domain=self.SOURCE,
            include_external=False,
        ) is True


# ---------------------------------------------------------------------------
# _extract_headings_from_markdown
# ---------------------------------------------------------------------------


class TestExtractHeadingsFromMarkdown:
    def test_extracts_all_levels(self) -> None:
        md = "# H1 Title\n\nSome text.\n\n## H2 Section\n\n### H3 Sub\n\nMore text."
        assert _extract_headings_from_markdown(md) == ["H1 Title", "H2 Section", "H3 Sub"]

    def test_empty_markdown_returns_empty_list(self) -> None:
        assert _extract_headings_from_markdown("") == []

    def test_no_headings_returns_empty_list(self) -> None:
        assert _extract_headings_from_markdown("Just plain text\nAnother line.") == []

    def test_strips_whitespace(self) -> None:
        md = "#   Heading With Spaces   \n"
        assert _extract_headings_from_markdown(md) == ["Heading With Spaces"]

    def test_ignores_inline_hash(self) -> None:
        md = "Some text with a # in the middle\n## Real Heading"
        assert _extract_headings_from_markdown(md) == ["Real Heading"]


# ---------------------------------------------------------------------------
# _extract_table_data (via mock lxml elements)
# ---------------------------------------------------------------------------


def _make_mock_table(headers: list[str], rows: list[list[str]], caption: str = "") -> MagicMock:
    """Build a minimal Scrapling-like mock with an ._root lxml element."""
    from lxml import etree

    table_el = etree.Element("table")
    if caption:
        cap = etree.SubElement(table_el, "caption")
        cap.text = caption

    if headers:
        header_row = etree.SubElement(table_el, "tr")
        for h in headers:
            th = etree.SubElement(header_row, "th")
            th.text = h

    for row in rows:
        tr = etree.SubElement(table_el, "tr")
        for cell in row:
            td = etree.SubElement(tr, "td")
            td.text = cell

    mock = MagicMock()
    mock._root = table_el
    return mock


class TestExtractTableData:
    def test_basic_table(self) -> None:
        mock = _make_mock_table(["Name", "Type"], [["Pikachu", "Electric"], ["Charmander", "Fire"], ["Bulbasaur", "Grass"]])
        result = _extract_table_data(mock, min_rows=1, min_columns=2, max_columns=50)
        assert result is not None
        assert result.row_count == 3
        assert result.column_count == 2
        assert "| Name | Type |" in result.markdown
        assert "|---|---|" in result.markdown
        assert "| Pikachu | Electric |" in result.markdown
        assert "| Charmander | Fire |" in result.markdown

    def test_caption_extracted(self) -> None:
        mock = _make_mock_table(["A", "B"], [["value one", "value two"], ["row two", "content"], ["row 3", "more"]], caption="Stats")
        result = _extract_table_data(mock, min_rows=1, min_columns=1, max_columns=50)
        assert result is not None
        assert result.caption == "Stats"
        assert "| A | B |" in result.markdown

    def test_filtered_by_min_rows(self) -> None:
        mock = _make_mock_table(["A", "B"], [["value", "other"]])
        result = _extract_table_data(mock, min_rows=2, min_columns=1, max_columns=50)
        assert result is None

    def test_filtered_by_min_columns(self) -> None:
        mock = _make_mock_table(["A"], [["value one"], ["value two"], ["value three"]])
        result = _extract_table_data(mock, min_rows=1, min_columns=2, max_columns=50)
        assert result is None

    def test_filtered_by_max_columns(self) -> None:
        headers = ["A", "B", "C", "D", "E"]
        rows = [["val1", "val2", "val3", "val4", "val5"]] * 3
        mock = _make_mock_table(headers, rows)
        result = _extract_table_data(mock, min_rows=1, min_columns=2, max_columns=4)
        assert result is None

    def test_no_explicit_headers_uses_first_row(self) -> None:
        # Table with no <th>, first <tr> of <td>s becomes headers
        mock = _make_mock_table([], [["Name", "Type"], ["Pikachu", "Electric"], ["Charmander", "Fire"]])
        result = _extract_table_data(mock, min_rows=1, min_columns=2, max_columns=50)
        assert result is not None
        assert "| Name | Type |" in result.markdown
        assert "| Pikachu | Electric |" in result.markdown

    def test_empty_table_returns_none(self) -> None:
        from lxml import etree
        table_el = etree.Element("table")
        mock = MagicMock()
        mock._root = table_el
        result = _extract_table_data(mock, min_rows=1, min_columns=1, max_columns=50)
        assert result is None


# ---------------------------------------------------------------------------
# Pydantic schema validation
# ---------------------------------------------------------------------------


class TestPydanticSchemas:
    def test_extract_links_input_defaults(self) -> None:
        inp = ExtractLinksInput(url="https://example.com")
        assert inp.include_external is False
        assert inp.domain_filter is None
        assert inp.max_links == 50
        assert inp.use_stealth is False

    def test_extract_links_input_max_links_bounds(self) -> None:
        with pytest.raises(Exception):
            ExtractLinksInput(url="https://example.com", max_links=0)
        with pytest.raises(Exception):
            ExtractLinksInput(url="https://example.com", max_links=201)

    def test_structured_data_input_defaults(self) -> None:
        inp = ExtractStructuredDataInput(url="https://example.com")
        assert inp.min_rows == 3
        assert inp.min_columns == 2
        assert inp.max_columns == 10
        assert inp.max_tables == 8

    def test_structured_data_input_bounds(self) -> None:
        with pytest.raises(Exception):
            ExtractStructuredDataInput(url="https://example.com", min_rows=0)
        with pytest.raises(Exception):
            ExtractStructuredDataInput(url="https://example.com", min_columns=51)
        with pytest.raises(Exception):
            ExtractStructuredDataInput(url="https://example.com", max_columns=1)
        with pytest.raises(Exception):
            ExtractStructuredDataInput(url="https://example.com", max_tables=0)

    def test_summarize_page_input_defaults(self) -> None:
        inp = SummarizePageInput(url="https://example.com")
        assert inp.css_selector is None
        assert inp.use_stealth is False


# ---------------------------------------------------------------------------
# extract_page_links — mocked fetch
# ---------------------------------------------------------------------------


_SIMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <main>
    <h2>Pokémon</h2>
    <p>See <a href="/wiki/Pikachu">Pikachu</a> for details.</p>
    <p>Also see <a href="/wiki/Charmander">Charmander</a>.</p>
    <p>External: <a href="https://external.com/page">Other site</a></p>
    <p>Login: <a href="/login">Login</a></p>
    <p>Privacy: <a href="/privacy-policy">Privacy</a></p>
    <a href="mailto:test@test.com">Email us</a>
  </main>
</body>
</html>
"""


def _build_scrapling_page(html: str):
    """Build a real Scrapling page object from an HTML string for unit testing."""
    from scrapling import Selector
    return Selector(content=html)


class TestExtractPageLinks:
    def test_filters_boilerplate_and_returns_content_links(self) -> None:
        page = _build_scrapling_page(_SIMPLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_page_links(ExtractLinksInput(
                url="https://bulbapedia.bulbagarden.net/",
                include_external=False,
            ))
        result = ExtractLinksResult.model_validate_json(result_json)
        assert result.error is None
        urls = [lnk.url for lnk in result.links]
        assert any("Pikachu" in u for u in urls)
        assert any("Charmander" in u for u in urls)
        assert not any("login" in u.lower() for u in urls)
        assert not any("privacy" in u.lower() for u in urls)
        assert not any("mailto" in u.lower() for u in urls)

    def test_domain_filter_applied(self) -> None:
        page = _build_scrapling_page(_SIMPLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_page_links(ExtractLinksInput(
                url="https://bulbapedia.bulbagarden.net/",
                domain_filter="bulbapedia.bulbagarden.net",
                include_external=True,
            ))
        result = ExtractLinksResult.model_validate_json(result_json)
        assert result.error is None
        for lnk in result.links:
            assert "bulbapedia.bulbagarden.net" in lnk.url

    def test_max_links_respected(self) -> None:
        page = _build_scrapling_page(_SIMPLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_page_links(ExtractLinksInput(
                url="https://bulbapedia.bulbagarden.net/",
                max_links=1,
                include_external=True,
                domain_filter=None,
            ))
        result = ExtractLinksResult.model_validate_json(result_json)
        assert len(result.links) <= 1

    def test_fetch_failure_returns_error(self) -> None:
        with patch("tools.web_content._fetch_page", side_effect=RuntimeError("timeout")):
            result_json = extract_page_links(ExtractLinksInput(url="https://example.com"))
        result = ExtractLinksResult.model_validate_json(result_json)
        assert result.error is not None
        assert "timeout" in result.error

    def test_result_has_source_metadata(self) -> None:
        page = _build_scrapling_page(_SIMPLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_page_links(ExtractLinksInput(
                url="https://bulbapedia.bulbagarden.net/",
            ))
        result = ExtractLinksResult.model_validate_json(result_json)
        assert result.source_url == "https://bulbapedia.bulbagarden.net/"
        assert result.total_found >= result.total_after_filter


# ---------------------------------------------------------------------------
# summarize_page — mocked fetch + mocked LLMQuery
# ---------------------------------------------------------------------------


_ARTICLE_HTML = """
<html>
<head>
  <title>Pikachu - Bulbapedia</title>
  <meta name="description" content="Pikachu is an Electric-type Pokémon.">
</head>
<body>
  <main>
    <h1>Pikachu</h1>
    <p>Pikachu is a small, yellow Electric-type Pokémon that generates electricity in its cheek pouches.</p>
    <h2>Biology</h2>
    <p>Its tail is shaped like a lightning bolt.</p>
    <h2>In the anime</h2>
    <p>Pikachu is Ash's partner and appears in every episode.</p>
  </main>
</body>
</html>
"""


class TestSummarizePage:
    def test_returns_structured_summary(self) -> None:
        page = _build_scrapling_page(_ARTICLE_HTML)
        with (
            patch("tools.web_content._fetch_page", return_value=page),
            patch("tools.web_content._llm_summarize", return_value="Pikachu is Electric."),
        ):
            result_json = summarize_page(SummarizePageInput(url="https://example.com/pikachu"))
        result = PageSummaryResult.model_validate_json(result_json)
        assert result.error is None
        assert result.title == "Pikachu - Bulbapedia"
        assert result.summary == "Pikachu is Electric."
        assert "Biology" in result.headings
        assert "In the anime" in result.headings
        assert result.word_count > 0

    def test_meta_description_extracted(self) -> None:
        page = _build_scrapling_page(_ARTICLE_HTML)
        with (
            patch("tools.web_content._fetch_page", return_value=page),
            patch("tools.web_content._llm_summarize", return_value="summary"),
        ):
            result_json = summarize_page(SummarizePageInput(url="https://example.com/pikachu"))
        result = PageSummaryResult.model_validate_json(result_json)
        assert result.meta_description == "Pikachu is an Electric-type Pokémon."

    def test_fetch_failure_returns_error(self) -> None:
        with patch("tools.web_content._fetch_page", side_effect=ConnectionError("refused")):
            result_json = summarize_page(SummarizePageInput(url="https://example.com"))
        result = PageSummaryResult.model_validate_json(result_json)
        assert result.error is not None
        assert "refused" in result.error

    def test_llm_failure_returns_error(self) -> None:
        page = _build_scrapling_page(_ARTICLE_HTML)
        with (
            patch("tools.web_content._fetch_page", return_value=page),
            patch("tools.web_content._llm_summarize", side_effect=RuntimeError("api error")),
        ):
            result_json = summarize_page(SummarizePageInput(url="https://example.com"))
        result = PageSummaryResult.model_validate_json(result_json)
        assert result.error is not None
        assert "api error" in result.error
        # Headings and word_count should still be populated even on LLM failure
        assert len(result.headings) > 0
        assert result.word_count > 0


# ---------------------------------------------------------------------------
# extract_structured_data — mocked fetch
# ---------------------------------------------------------------------------


_TABLE_HTML = """
<html>
<head><title>Stats</title></head>
<body>
  <main>
    <table>
      <caption>Base Stats</caption>
      <tr><th>Stat</th><th>Value</th></tr>
      <tr><td>HP</td><td>35 points</td></tr>
      <tr><td>Attack</td><td>55 points</td></tr>
      <tr><td>Defense</td><td>40 points</td></tr>
    </table>
    <table>
      <tr><td>Only one row</td><td>here</td></tr>
    </table>
    <table>
      <tr><td>Single column</td></tr>
      <tr><td>Row 2</td></tr>
      <tr><td>Row 3</td></tr>
    </table>
  </main>
</body>
</html>
"""


class TestExtractStructuredData:
    def test_extracts_valid_table(self) -> None:
        page = _build_scrapling_page(_TABLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_structured_data(ExtractStructuredDataInput(
                url="https://example.com",
                min_rows=2,
                min_columns=2,
                max_columns=50,
            ))
        result = ExtractStructuredDataResult.model_validate_json(result_json)
        assert result.error is None
        assert len(result.tables) == 1
        table = result.tables[0]
        assert table.caption == "Base Stats"
        assert table.row_count == 3
        assert table.column_count == 2
        assert "| Stat | Value |" in table.markdown
        assert "| HP |" in table.markdown
        # Top-level markdown should include caption as heading
        assert "### Base Stats" in result.markdown
        assert "| HP |" in result.markdown

    def test_filters_small_tables(self) -> None:
        page = _build_scrapling_page(_TABLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_structured_data(ExtractStructuredDataInput(
                url="https://example.com",
                min_rows=2,
                min_columns=2,
                max_columns=50,
            ))
        result = ExtractStructuredDataResult.model_validate_json(result_json)
        # The single-row table and single-column table should be filtered out
        assert result.tables_found == 3
        assert len(result.tables) == 1

    def test_fetch_failure_returns_error(self) -> None:
        with patch("tools.web_content._fetch_page", side_effect=TimeoutError("timed out")):
            result_json = extract_structured_data(ExtractStructuredDataInput(url="https://example.com"))
        result = ExtractStructuredDataResult.model_validate_json(result_json)
        assert result.error is not None
        assert "timed out" in result.error
        assert result.markdown == ""

    def test_page_title_in_result(self) -> None:
        page = _build_scrapling_page(_TABLE_HTML)
        with patch("tools.web_content._fetch_page", return_value=page):
            result_json = extract_structured_data(ExtractStructuredDataInput(url="https://example.com"))
        result = ExtractStructuredDataResult.model_validate_json(result_json)
        assert result.title == "Stats"
