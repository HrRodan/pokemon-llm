"""
Web content extraction tools using Scrapling and html-to-markdown.

Provides four tools for agent-driven web content processing:

- ``fetch_page_as_markdown``   — Fetch a URL and convert its main content to clean Markdown.
- ``extract_page_links``       — Extract all content-relevant links from a page with context.
- ``summarize_page``           — Generate an LLM-powered summary of a page for quick preview.
- ``extract_structured_data``  — Extract HTML tables from a page as structured JSON.
"""

import asyncio
import concurrent.futures
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from html_to_markdown import ConversionOptions
from html_to_markdown import convert as html_to_md
from lxml import etree
from pydantic import BaseModel, Field
from scrapling.fetchers import Fetcher, StealthyFetcher

from ai_tools.tool_definition import tool
from utils.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas — fetch_page_as_markdown
# ---------------------------------------------------------------------------


class FetchPageInput(BaseModel):
    """Input parameters for fetching a web page as Markdown."""

    url: str = Field(description="The URL of the page to fetch.")
    css_selector: str | None = Field(
        default=None,
        description=(
            "Optional CSS selector to extract specific content "
            "(e.g. 'article', '#main-content'). "
            "If omitted, auto-detects the main content area."
        ),
    )
    use_stealth: bool = Field(
        default=False,
        description="Use stealth browser mode for sites with anti-bot protection.",
    )


class PageMarkdownResult(BaseModel):
    """Structured output from fetching and converting a web page."""

    url: str = Field(description="The URL that was fetched.")
    title: str = Field(description="The page title.")
    timestamp: str = Field(description="The timestamp when the page was fetched.")
    markdown: str = Field(description="The sanitized Markdown content of the page.")
    error: str | None = Field(
        default=None,
        description="Error message if the fetch/conversion failed.",
    )


# ---------------------------------------------------------------------------
# Pydantic schemas — extract_page_links
# ---------------------------------------------------------------------------


class ExtractLinksInput(BaseModel):
    """Extract all content-relevant links from a web page with contextual snippets."""

    url: str = Field(description="The URL of the page to extract links from.")
    use_stealth: bool = Field(
        default=False,
        description="Use stealth browser mode for sites with anti-bot protection.",
    )
    include_external: bool = Field(
        default=False,
        description=(
            "Include links to external domains. "
            "If False (default), only links on the same domain as the source URL are returned."
        ),
    )
    domain_filter: str | None = Field(
        default=None,
        description=(
            "If set, only return links whose domain contains this string "
            "(e.g. 'bulbapedia.bulbagarden.net'). Takes precedence over include_external."
        ),
    )
    max_links: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of links to return after filtering. Defaults to 50.",
    )


class LinkItem(BaseModel):
    """A single extracted link with contextual metadata."""

    url: str = Field(description="The absolute URL of the link.")
    title: str = Field(description="The link text / anchor text.")
    context: str = Field(
        description=(
            "The surrounding text passage where the link appears, "
            "truncated to ~150 characters for token efficiency."
        ),
    )
    section: str = Field(
        default="",
        description="The nearest heading above the link, if any.",
    )


class ExtractLinksResult(BaseModel):
    """Structured output from link extraction."""

    source_url: str = Field(description="The URL that was analyzed.")
    source_title: str = Field(description="The page title.")
    total_found: int = Field(description="Total number of <a> tags found before filtering.")
    total_after_filter: int = Field(description="Number of links after all filters are applied.")
    links: list[LinkItem] = Field(description="Filtered, content-relevant links with context.")
    error: str | None = Field(default=None, description="Error message if extraction failed.")


# ---------------------------------------------------------------------------
# Pydantic schemas — summarize_page
# ---------------------------------------------------------------------------


class SummarizePageInput(BaseModel):
    """Generate an LLM-powered summary of a web page for quick preview."""

    url: str = Field(description="The URL of the page to summarize.")
    css_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to scope content extraction.",
    )
    use_stealth: bool = Field(
        default=False,
        description="Use stealth browser mode for sites with anti-bot protection.",
    )


class PageSummaryResult(BaseModel):
    """Structured output from page summarization."""

    url: str = Field(description="The URL that was summarized.")
    title: str = Field(description="The page title.")
    meta_description: str = Field(
        default="",
        description="The <meta name='description'> or og:description content, if present.",
    )
    summary: str = Field(
        description="A ~200-word LLM-generated summary of the page content.",
    )
    headings: list[str] = Field(
        description="All section headings (h1-h6) found on the page, in document order.",
    )
    word_count: int = Field(
        description="Approximate word count of the full page markdown.",
    )
    error: str | None = Field(default=None, description="Error message if summarization failed.")


# ---------------------------------------------------------------------------
# Pydantic schemas — extract_structured_data
# ---------------------------------------------------------------------------


class ExtractStructuredDataInput(BaseModel):
    """Extract tables from a web page and return them as structured Markdown."""

    url: str = Field(description="The URL of the page to extract data from.")
    css_selector: str | None = Field(
        default=None,
        description=(
            "Optional CSS selector to target a specific table or section. "
            "If omitted, all tables in the main content area are extracted."
        ),
    )
    use_stealth: bool = Field(
        default=False,
        description="Use stealth browser mode for sites with anti-bot protection.",
    )
    min_rows: int = Field(
        default=3,
        ge=1,
        le=100,
        description=(
            "Minimum number of data rows (excluding header) for a table to be included. "
            "Filters out tiny layout tables. Defaults to 3."
        ),
    )
    min_columns: int = Field(
        default=2,
        ge=1,
        le=50,
        description=(
            "Minimum number of columns for a table to be included. "
            "Filters out single-column layout tables. Defaults to 2."
        ),
    )
    max_columns: int = Field(
        default=10,
        ge=2,
        le=100,
        description=(
            "Maximum number of columns allowed. Tables wider than this are likely "
            "navigation or layout tables and are excluded. Defaults to 10."
        ),
    )
    max_tables: int = Field(
        default=8,
        ge=1,
        le=50,
        description=(
            "Maximum number of tables to return after all filters. "
            "Applies after all other filters to cap token usage. Defaults to 8."
        ),
    )


class TableData(BaseModel):
    """A single extracted HTML table rendered as Markdown."""

    caption: str = Field(default="", description="Table caption, if present.")
    section: str = Field(
        default="",
        description="The nearest section heading above this table, if any.",
    )
    markdown: str = Field(description="The table rendered as a GitHub-Flavored Markdown table string.")
    row_count: int = Field(description="Number of data rows (excluding the header row).")
    column_count: int = Field(description="Number of columns.")


class ExtractStructuredDataResult(BaseModel):
    """Structured output from table extraction."""

    url: str = Field(description="The URL that was analyzed.")
    title: str = Field(description="The page title.")
    tables_found: int = Field(description="Total number of <table> elements found before filtering.")
    tables: list[TableData] = Field(
        description="Extracted tables that pass min_rows/min_columns filters."
    )
    markdown: str = Field(
        description=(
            "All extracted tables concatenated as a single Markdown string, "
            "ready for direct agent consumption."
        ),
    )
    error: str | None = Field(default=None, description="Error message if extraction failed.")


def _run_stealthy_fetch(url: str):
    """Run Scrapling's StealthyFetcher in a thread to bypass Playwright's sync API checks.

    Playwright's sync API will crash with 'It looks like you are using Playwright Sync
    API inside the asyncio loop' when run in Jupyter. We bypass this by executing it
    in a clean separate thread.
    """
    def _fetch():
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return StealthyFetcher.fetch(url, headless=True)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch)
            return future.result()
    else:
        return _fetch()


def _fetch_page(url: str, use_stealth: bool = False):
    """Fetch a web page and return the raw Scrapling page object.

    Centralises fetch logic shared across all tools. Raises on failure —
    callers must wrap in try/except.
    """
    if use_stealth:
        return _run_stealthy_fetch(url)
    return Fetcher.get(url, stealthy_headers=True, verify=False)


# ---------------------------------------------------------------------------
# Content extraction logic
# ---------------------------------------------------------------------------


# Priority-ordered selectors for auto-detecting the main content area.
_MAIN_CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    "#content",
    "#mw-content-text",       # MediaWiki / Bulbapedia
    ".mw-parser-output",      # MediaWiki parsed content
    "#bodyContent",           # Wikipedia
]

# Elements to strip from the extracted content to reduce noise and token usage.
_NOISY_ELEMENTS = [
    # Standard boilerplate tags
    "nav", "header", "footer", "aside", "script", "style", "noscript",
    # Wiki / generic noisy classes and IDs
    ".toc", "#toc",                   # Tables of contents
    ".mw-editsection",                # [edit] links
    ".reference", "sup.reference",    # [1], [2] superscript references
    ".reflist", ".references",        # Reference lists at the bottom
    ".navbox",                        # Navigation boxes at the bottom
    ".mw-jump-link",                  # "Jump to navigation" links
    ".catlinks", "#catlinks",         # Categories at the bottom
    "#siteNotice",                    # Site notices
    ".metadata", ".ambox",            # Article message boxes (e.g. "needs citations")
    ".printfooter",                   # Print footers
]

# Compiled regex patterns for filtering non-content links.
_BOILERPLATE_LINK_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(impressum|datenschutz|privacy[\.\-_]?polic|terms[\.\-_]?of|legal[\.\-_]?notice|cookie|disclaimer)",
        r"(login|log[\.\-_]?out|sign[\.\-_]?in|sign[\.\-_]?up|register|my[\.\-_]?account|profile)",
        r"(contact[\.\-_]?us|about[\.\-_]?us|careers|jobs|advertis|sponsor)",
        r"(facebook|twitter|instagram|youtube|linkedin|reddit|tiktok|pinterest)\.com",
        r"\.(css|js|json|xml|rss|atom|ico|png|jpg|jpeg|gif|svg|webp|woff|woff2|ttf|eot)(\?|$)",
        r"^(mailto:|tel:|javascript:|data:)",
        r"(Special:|User:|Talk:|Template:|File:|Category:|Help:|MediaWiki:)",  # MediaWiki internals
    ]
]

def _prune_noisy_elements(elements: list) -> str:
    """
    Remove noisy elements from a list of Scrapling Selector elements,
    flatten layout tables, and return their combined, cleaned HTML.
    """
    for el in elements:
        # Remove explicitly noisy classes/IDs
        for selector in _NOISY_ELEMENTS:
            for noisy_el in el.css(selector):
                lxml_el = noisy_el._root
                parent = lxml_el.getparent()
                if parent is not None:
                    parent.remove(lxml_el)
                    
        # Remove images entirely to save tokens
        for img_el in el.css("img"):
            lxml_el = img_el._root
            parent = lxml_el.getparent()
            if parent is not None:
                parent.remove(lxml_el)
                
        # Drop <a> tags but retain their text
        for a_el in el.css("a"):
            lxml_el = a_el._root
            lxml_el.drop_tag()
            
        # Unwrap single-cell layout tables to prevent markdown rendering issues
        # and unnecessary token overhead. MediaWiki platforms frequently wrap 
        # textual elements in layout tables.
        for table_el in el.css("table"):
            lxml_table = table_el._root
            cells = lxml_table.xpath(".//td | .//th")
            if len(cells) <= 1:
                lxml_table.drop_tag()
                for wrapper in lxml_table.xpath(".//tbody | .//thead | .//tfoot | .//tr | .//td | .//th"):
                    wrapper.drop_tag()
    
    return "".join(el.html_content for el in elements)


def _extract_title(page) -> str:
    """Extract the page title from <title> or first <h1>."""
    title_el = page.css("title")
    if title_el:
        text = title_el[0].text
        if text and text.strip():
            return text.strip()

    h1_el = page.css("h1")
    if h1_el:
        text = h1_el[0].text
        if text and text.strip():
            return text.strip()

    return ""


def _extract_main_html(page, css_selector: str | None = None) -> str:
    """
    Extract the main content HTML from a Scrapling page response.

    Strategy:
    1. Explicit selector — if provided, use it directly.
    2. Semantic auto-detect — try selectors in priority order.
    3. Fallback — use body.
    In all cases, we strip out boilerplate and noisy elements to minimize token size.
    """
    # 1. Explicit selector
    if css_selector:
        elements = page.css(css_selector)
        if elements:
            logger.info("Extracted content using explicit selector: %s", css_selector)
            return _prune_noisy_elements(elements)
        logger.warning(
            "Explicit selector %r matched nothing, falling back to auto-detect",
            css_selector,
        )

    # 2. Semantic auto-detect
    for selector in _MAIN_CONTENT_SELECTORS:
        elements = page.css(selector)
        if elements:
            logger.info("Auto-detected content using selector: %s", selector)
            return _prune_noisy_elements(elements)

    # 3. Fallback — use body
    logger.info("No semantic content element found, falling back to cleaned <body>")
    body = page.css("body")
    if not body:
        return page.html_content

    return _prune_noisy_elements(body)


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


@tool(schema=FetchPageInput)
def fetch_page_as_markdown(args: FetchPageInput) -> str:
    """Fetch a web page and return its main content as clean Markdown.

    Uses Scrapling for fetching (with optional stealth mode) and
    html-to-markdown for high-performance HTML-to-Markdown conversion.
    """
    logger.info(
        "Fetching page: url=%s stealth=%s selector=%s",
        args.url, args.use_stealth, args.css_selector,
    )

    timestamp = datetime.now(timezone.utc).astimezone().isoformat()

    # Fetch the page
    try:
        page = _fetch_page(args.url, args.use_stealth)
    except Exception as e:
        logger.error("Page fetch failed for %s: %s", args.url, e)
        result = PageMarkdownResult(
            url=args.url,
            title="",
            timestamp=timestamp,
            markdown="",
            error=f"Fetch failed: {e}",
        )
        return result.model_dump_json()

    # Extract title and main content HTML
    try:
        title = _extract_title(page)
        main_html = _extract_main_html(page, args.css_selector)
    except Exception as e:
        logger.error("Content extraction failed for %s: %s", args.url, e)
        result = PageMarkdownResult(
            url=args.url,
            title="",
            timestamp=timestamp,
            markdown="",
            error=f"Content extraction failed: {e}",
        )
        return result.model_dump_json()

    # Convert HTML to Markdown
    try:
        # We do not preserve raw HTML tags as user requested strictly markdown.
        markdown = html_to_md(
            main_html, 
            options=ConversionOptions(
                br_in_tables=True, 
                skip_images=True
            )
        )
        
        # Clean up excessive blank lines (more than 2 consecutive newlines)
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        # Clean up completely empty markdown table rows (e.g., `| | |`)
        markdown = re.sub(r'^(?:\|\s*)+\|$', '', markdown, flags=re.MULTILINE)
        
        # Clean up remaining <br> tags sometimes emitted
        markdown = re.sub(r'(?i)<br\s*/?>', ' ', markdown)
    except Exception as e:
        logger.error("Markdown conversion failed for %s: %s", args.url, e)
        result = PageMarkdownResult(
            url=args.url,
            title=title,
            timestamp=timestamp,
            markdown="",
            error=f"Markdown conversion failed: {e}",
        )
        return result.model_dump_json()

    # Create YAML metadata header
    yaml_header = (
        f"---\n"
        f"title: \"{title}\"\n"
        f"url: \"{args.url}\"\n"
        f"timestamp: \"{timestamp}\"\n"
        f"---\n\n"
    )
    full_markdown = yaml_header + markdown

    # Save to file
    try:
        safe_title = re.sub(r'[^a-zA-Z0-9]+', '_', title)[:50].strip('_')
        if not safe_title:
            safe_title = "untitled"
        
        save_dir = Path(settings.WEB_SCRAPER_DIR)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / f"{safe_title}.md"
            
        filepath.write_text(full_markdown, encoding="utf-8")
        logger.info("Saved page markdown to %s", filepath)
    except Exception as e:
        logger.error("Failed to save markdown file for %s: %s", args.url, e)

    result = PageMarkdownResult(
        url=args.url,
        title=title,
        timestamp=timestamp,
        markdown=markdown,
    )
    logger.info(
        "Page fetched: url=%s title=%r markdown_len=%d",
        args.url, title, len(markdown),
    )
    return result.model_dump_json()


# ---------------------------------------------------------------------------
# extract_page_links helpers
# ---------------------------------------------------------------------------


def _is_boilerplate_link(url: str, anchor_text: str) -> bool:
    """Return True if the URL or anchor text matches any boilerplate pattern."""
    for pattern in _BOILERPLATE_LINK_PATTERNS:
        if pattern.search(url) or pattern.search(anchor_text):
            return True
    return False


def _normalize_url(href: str, base_url: str) -> str | None:
    """Resolve a relative href to an absolute URL.

    Returns None for non-HTTP(S) schemes or unparseable strings.
    Fragment-only anchors (#) are also discarded.
    """
    try:
        absolute = urljoin(base_url, href.strip())
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            return None
        # Strip fragment to deduplicate page-internal anchor variants
        return parsed._replace(fragment="").geturl()
    except Exception:
        return None


def _matches_domain_filter(
    url: str,
    domain_filter: str | None,
    source_domain: str,
    include_external: bool,
) -> bool:
    """Check whether a URL passes the domain constraint.

    Priority order:
    1. If domain_filter is set — only allow URLs whose netloc contains it.
    2. Else if include_external is False — only allow same domain as source.
    3. Otherwise — allow all.
    """
    link_domain = urlparse(url).netloc.lower()

    if domain_filter:
        return domain_filter.lower() in link_domain

    if not include_external:
        return link_domain == source_domain.lower()

    return True


def _extract_link_context(a_element) -> tuple[str, str]:
    """Extract the surrounding text context and nearest section heading for an <a> element.

    Returns:
        A tuple of (context_snippet, section_heading). Both may be empty strings.
    """
    # Context: parent element text, truncated and centered around the anchor.
    parent = a_element._root.getparent()
    context = ""
    if parent is not None:
        parent_text = etree.tostring(parent, method="text", encoding="unicode").strip()
        if len(parent_text) > 150:
            anchor = (a_element.text or "").strip()
            idx = parent_text.find(anchor)
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(parent_text), idx + len(anchor) + 60)
                context = parent_text[start:end].strip()
                if start > 0:
                    context = "\u2026" + context
                if end < len(parent_text):
                    context = context + "\u2026"
            else:
                context = parent_text[:150].strip() + "\u2026"
        else:
            context = parent_text

    # Section: walk DOM upward, checking preceding siblings for h1-h6.
    section = ""
    node = a_element._root
    _heading_tags = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
    while node is not None:
        prev = node.getprevious()
        while prev is not None:
            if prev.tag in _heading_tags:
                heading_text = etree.tostring(prev, method="text", encoding="unicode").strip()
                if heading_text:
                    section = heading_text
                    return context, section
            prev = prev.getprevious()
        node = node.getparent()

    return context, section


# ---------------------------------------------------------------------------
# extract_page_links
# ---------------------------------------------------------------------------


@tool(schema=ExtractLinksInput)
def extract_page_links(args: ExtractLinksInput) -> str:
    """Extract all content-relevant links from a web page with contextual metadata.

    Fetches the page, scopes to the main content area, filters out boilerplate
    links (privacy, login, social media, MediaWiki internals, asset files), and
    enriches each surviving link with surrounding text context and the nearest
    section heading. Returns a token-efficient list of links.
    """
    logger.info(
        "Extracting links: url=%s stealth=%s domain_filter=%s",
        args.url, args.use_stealth, args.domain_filter,
    )

    # 1. Fetch the page
    try:
        page = _fetch_page(args.url, args.use_stealth)
    except Exception as e:
        logger.error("Page fetch failed for %s: %s", args.url, e)
        return ExtractLinksResult(
            source_url=args.url, source_title="", total_found=0,
            total_after_filter=0, links=[], error=f"Fetch failed: {e}",
        ).model_dump_json()

    title = _extract_title(page)
    source_domain = urlparse(args.url).netloc

    # 2. Scope to main content area
    content_elements = None
    for selector in _MAIN_CONTENT_SELECTORS:
        content_elements = page.css(selector)
        if content_elements:
            break
    if not content_elements:
        content_elements = page.css("body")

    # 3. Collect all <a href> tags within the scoped area
    all_a_tags = []
    for el in (content_elements or []):
        all_a_tags.extend(el.css("a[href]"))
    total_found = len(all_a_tags)

    # 4. Filter, normalize, deduplicate, and enrich
    seen_urls: set[str] = set()
    items: list[LinkItem] = []

    for a_el in all_a_tags:
        if len(items) >= args.max_links:
            break

        href = a_el.attrib.get("href", "").strip()
        if not href:
            continue

        absolute_url = _normalize_url(href, args.url)
        if absolute_url is None:
            continue

        if absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)

        anchor_text = (a_el.text or a_el.get_all_text(separator=" ", strip=True) or "").strip()

        if _is_boilerplate_link(absolute_url, anchor_text):
            continue

        if not _matches_domain_filter(absolute_url, args.domain_filter, source_domain, args.include_external):
            continue

        if not anchor_text:
            continue

        context, section = _extract_link_context(a_el)

        items.append(LinkItem(
            url=absolute_url,
            title=anchor_text,
            context=context,
            section=section,
        ))

    result = ExtractLinksResult(
        source_url=args.url,
        source_title=title,
        total_found=total_found,
        total_after_filter=len(items),
        links=items,
    )
    logger.info(
        "Extracted links: url=%s total_found=%d total_after_filter=%d",
        args.url, total_found, len(items),
    )
    return result.model_dump_json()


# ---------------------------------------------------------------------------
# summarize_page helpers
# ---------------------------------------------------------------------------


def _extract_meta_description(page) -> str:
    """Extract the meta description from a Scrapling page.

    Tries <meta name='description'> first, then og:description.
    Returns an empty string if neither is present.
    """
    for selector in ('meta[name="description"]', 'meta[name="Description"]'):
        els = page.css(selector)
        if els:
            content = els[0].attrib.get("content", "").strip()
            if content:
                return content
    og_els = page.css('meta[property="og:description"]')
    if og_els:
        content = og_els[0].attrib.get("content", "").strip()
        if content:
            return content
    return ""


def _extract_headings_from_markdown(markdown: str) -> list[str]:
    """Extract all headings from markdown text, returning their text without the # prefix."""
    headings = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            headings.append(match.group(2).strip())
    return headings


_SUMMARIZE_SYSTEM_PROMPT = (
    "You are a precise content summarizer. "
    "Given the markdown content of a web page, write a concise factual summary "
    "of approximately 150-200 words. Focus on the key topics, facts, and purpose "
    "of the page. Do not include meta-commentary or phrases like 'This page covers'. "
    "Write in plain prose, third person, present tense."
)


def _llm_summarize(markdown: str) -> str:
    """Generate a ~200-word LLM summary from page markdown.

    Uses LLMQuery with `settings.SUB_AGENT_MODEL`. Only the first 2000 words
    of the markdown are passed to the model to keep token usage bounded.
    """
    from ai_tools import Agent
    
    word_limit = 2000
    words = markdown.split()
    truncated = " ".join(words[:word_limit])
    if len(words) > word_limit:
        truncated += "\n\n[Content truncated]"

    llm = Agent(
        model=settings.SUB_AGENT_MODEL,
        system_prompt=_SUMMARIZE_SYSTEM_PROMPT,
        use_history=False,
    )
    return llm.query(truncated)


# ---------------------------------------------------------------------------
# summarize_page
# ---------------------------------------------------------------------------


@tool(schema=SummarizePageInput)
def summarize_page(args: SummarizePageInput) -> str:
    """Fetch a web page and generate a concise LLM-powered summary for quick preview.

    Returns the page title, meta description, a ~200-word summary, all section
    headings, and word count. Use this to assess whether a page is worth fully
    ingesting via ingest_web_page before committing to vector DB storage.
    """
    logger.info("Summarizing page: url=%s", args.url)

    # 1. Fetch the page once; derive both meta description and markdown from it.
    try:
        page = _fetch_page(args.url, args.use_stealth)
    except Exception as e:
        logger.error("Page fetch failed for summarize_page %s: %s", args.url, e)
        return PageSummaryResult(
            url=args.url, title="", summary="", headings=[],
            word_count=0, error=f"Fetch failed: {e}",
        ).model_dump_json()

    title = _extract_title(page)
    meta_description = _extract_meta_description(page)

    # 2. Extract and convert main content to markdown
    try:
        main_html = _extract_main_html(page, args.css_selector)
        markdown = html_to_md(
            main_html,
            options=ConversionOptions(br_in_tables=True, skip_images=True),
        )
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        markdown = re.sub(r"(?i)<br\s*/?>" , " ", markdown)
    except Exception as e:
        logger.error("Markdown conversion failed for summarize_page %s: %s", args.url, e)
        return PageSummaryResult(
            url=args.url, title=title, meta_description=meta_description,
            summary="", headings=[], word_count=0,
            error=f"Markdown conversion failed: {e}",
        ).model_dump_json()

    headings = _extract_headings_from_markdown(markdown)
    word_count = len(markdown.split())

    # 3. LLM-powered summary
    try:
        summary = _llm_summarize(markdown)
    except Exception as e:
        logger.error("LLM summarization failed for %s: %s", args.url, e)
        return PageSummaryResult(
            url=args.url, title=title, meta_description=meta_description,
            summary="", headings=headings, word_count=word_count,
            error=f"LLM summarization failed: {e}",
        ).model_dump_json()

    result = PageSummaryResult(
        url=args.url,
        title=title,
        meta_description=meta_description,
        summary=summary,
        headings=headings,
        word_count=word_count,
    )
    logger.info(
        "Summarized page: url=%s title=%r headings=%d words=%d",
        args.url, title, len(headings), word_count,
    )
    return result.model_dump_json()


# ---------------------------------------------------------------------------
# extract_structured_data helpers
# ---------------------------------------------------------------------------


def _extract_nearest_heading(element) -> str:
    """Walk up the DOM from *element* to find the nearest preceding h1-h6 sibling.

    Checks preceding siblings at each DOM level before moving to the parent.
    Returns the heading text, or an empty string if none is found.
    """
    _heading_tags = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
    node = element._root
    while node is not None:
        prev = node.getprevious()
        while prev is not None:
            if prev.tag in _heading_tags:
                text = etree.tostring(prev, method="text", encoding="unicode").strip()
                if text:
                    return text
            prev = prev.getprevious()
        node = node.getparent()
    return ""


def _is_nested_table(table_element) -> bool:
    """Return True if this table is a descendant of another table element.

    Nested tables are almost always layout/formatting constructs rather than
    data tables, and skipping them is the single most effective filter for
    Bulbapedia and other wiki-based sites.
    """
    node = table_element._root.getparent()
    while node is not None:
        if node.tag == "table":
            return True
        node = node.getparent()
    return False


def _extract_table_data(
    table_element, min_rows: int, min_columns: int, max_columns: int
) -> TableData | None:
    """Extract a single table element and render it as a Markdown table.

    Returns None if the table fails any threshold:
    - Fewer than min_rows data rows
    - Fewer than min_columns or more than max_columns columns
    - Average non-empty cell length < 5 chars (icon/image-only tables)
    - No parsable rows
    """
    lxml_table = table_element._root

    caption_els = lxml_table.xpath(".//caption")
    caption = ""
    if caption_els:
        caption = etree.tostring(caption_els[0], method="text", encoding="unicode").strip()

    all_rows = lxml_table.xpath(".//tr")
    if not all_rows:
        return None

    headers: list[str] = []
    data_rows: list[list[str]] = []

    for row in all_rows:
        th_cells = row.xpath("./th")
        td_cells = row.xpath("./td")

        if th_cells and not headers:
            headers = [
                etree.tostring(cell, method="text", encoding="unicode").strip()
                for cell in th_cells
            ]
        elif td_cells:
            data_rows.append([
                etree.tostring(cell, method="text", encoding="unicode").strip()
                for cell in td_cells
            ])
        elif th_cells and headers:
            # Sub-header row — treat as a data row
            data_rows.append([
                etree.tostring(cell, method="text", encoding="unicode").strip()
                for cell in th_cells
            ])

    if not headers and data_rows:
        headers = data_rows.pop(0)

    column_count = max(
        len(headers),
        max((len(r) for r in data_rows), default=0),
    )

    if column_count < min_columns or column_count > max_columns:
        return None
    if len(data_rows) < min_rows:
        return None

    # Heuristic: tables whose cells are mostly images/icons have very short text.
    # Require a mean non-empty cell length of at least 5 characters.
    all_cells = [c for row in data_rows for c in row if c]
    if all_cells:
        avg_cell_len = sum(len(c) for c in all_cells) / len(all_cells)
        if avg_cell_len < 5:
            return None

    # Pad all rows to column_count so the markdown table is well-formed
    def _pad(cells: list[str]) -> list[str]:
        return cells + [""] * (column_count - len(cells))

    # Escape pipe characters inside cell text to avoid breaking markdown table syntax
    def _escape(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ").strip()

    header_row = "| " + " | ".join(_escape(h) for h in _pad(headers)) + " |"
    separator  = "|" + "|".join(["---"] * column_count) + "|"
    data_lines = [
        "| " + " | ".join(_escape(c) for c in _pad(row)) + " |"
        for row in data_rows
    ]
    markdown = "\n".join([header_row, separator] + data_lines)
    section = _extract_nearest_heading(table_element)

    return TableData(
        caption=caption,
        section=section,
        markdown=markdown,
        row_count=len(data_rows),
        column_count=column_count,
    )


# ---------------------------------------------------------------------------
# extract_structured_data
# ---------------------------------------------------------------------------


@tool(schema=ExtractStructuredDataInput)
def extract_structured_data(args: ExtractStructuredDataInput) -> str:
    """Extract tables from a web page and return them as structured JSON.

    Fetches the page, finds all <table> elements in the main content area
    (or the given CSS selector), and converts each to a structured headers + rows
    object. Small layout tables are filtered by min_rows and min_columns.
    """
    logger.info(
        "Extracting structured data: url=%s selector=%s",
        args.url, args.css_selector,
    )

    # 1. Fetch the page
    try:
        page = _fetch_page(args.url, args.use_stealth)
    except Exception as e:
        logger.error("Page fetch failed for %s: %s", args.url, e)
        return ExtractStructuredDataResult(
            url=args.url, title="", tables_found=0, tables=[], markdown="",
            error=f"Fetch failed: {e}",
        ).model_dump_json()

    title = _extract_title(page)

    # 2. Scope to content area
    if args.css_selector:
        scope = page.css(args.css_selector)
        if not scope:
            logger.warning(
                "Selector %r matched nothing for %s, falling back to body",
                args.css_selector, args.url,
            )
            scope = page.css("body")
    else:
        scope = None
        for selector in _MAIN_CONTENT_SELECTORS:
            scope = page.css(selector)
            if scope:
                break
        if not scope:
            scope = page.css("body")

    # 3. Collect all <table> elements within scope
    all_tables = []
    for el in (scope or []):
        all_tables.extend(el.css("table"))
    tables_found = len(all_tables)

    # 4. Extract and filter: skip nested tables, apply all thresholds, cap at max_tables
    extracted: list[TableData] = []
    for table_el in all_tables:
        if _is_nested_table(table_el):
            continue
        table_data = _extract_table_data(
            table_el, args.min_rows, args.min_columns, args.max_columns
        )
        if table_data is not None:
            extracted.append(table_data)
            if len(extracted) >= args.max_tables:
                break

    # 5. Build combined top-level markdown.
    #    Label priority: explicit caption > nearest DOM heading > unlabelled.
    parts: list[str] = []
    for t in extracted:
        label = t.caption or t.section
        if label:
            parts.append(f"### {label}\n\n{t.markdown}")
        else:
            parts.append(t.markdown)
    combined_markdown = "\n\n".join(parts)

    result = ExtractStructuredDataResult(
        url=args.url,
        title=title,
        tables_found=tables_found,
        tables=extracted,
        markdown=combined_markdown,
    )
    logger.info(
        "Extracted structured data: url=%s tables_found=%d tables_returned=%d",
        args.url, tables_found, len(extracted),
    )
    return result.model_dump_json()


TOOL_FUNCTIONS = [
    fetch_page_as_markdown,
    extract_page_links,
    summarize_page,
    extract_structured_data,
]
