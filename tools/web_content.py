"""
Web content extraction tool using Scrapling and html-to-markdown.

Fetches a URL and converts the main content to clean Markdown,
stripping navigation, ads, and boilerplate.
"""

import asyncio
import concurrent.futures
import logging

from html_to_markdown import convert as html_to_md
from pydantic import BaseModel, Field
from scrapling.fetchers import Fetcher, StealthyFetcher

from ai_tools.tool_definition import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas
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
    markdown: str = Field(description="The sanitized Markdown content of the page.")
    error: str | None = Field(
        default=None,
        description="Error message if the fetch/conversion failed.",
    )


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
    "#bodyContent",            # Wikipedia
]

# Tags to strip when falling back to <body>
_BOILERPLATE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "noscript"]


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
    3. Fallback — use body with boilerplate tags removed.
    """
    # 1. Explicit selector
    if css_selector:
        elements = page.css(css_selector)
        if elements:
            logger.info("Extracted content using explicit selector: %s", css_selector)
            return "".join(el.html_content for el in elements)
        logger.warning(
            "Explicit selector %r matched nothing, falling back to auto-detect",
            css_selector,
        )

    # 2. Semantic auto-detect
    for selector in _MAIN_CONTENT_SELECTORS:
        elements = page.css(selector)
        if elements:
            logger.info("Auto-detected content using selector: %s", selector)
            return "".join(el.html_content for el in elements)

    # 3. Fallback — use body, strip boilerplate
    logger.info("No semantic content element found, falling back to cleaned <body>")
    body = page.css("body")
    if not body:
        return page.html_content

    body_el = body[0]
    # Remove boilerplate elements via lxml's native API.
    # Scrapling's Selector wraps lxml HtmlElement in `_root`.
    for tag in _BOILERPLATE_TAGS:
        for el in body_el.css(tag):
            lxml_el = el._root
            parent = lxml_el.getparent()
            if parent is not None:
                parent.remove(lxml_el)

    return body_el.html_content


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

    # Fetch the page
    try:
        if args.use_stealth:
            page = _run_stealthy_fetch(args.url)
        else:
            page = Fetcher.get(args.url, stealthy_headers=True, verify=False)
    except Exception as e:
        logger.error("Page fetch failed for %s: %s", args.url, e)
        result = PageMarkdownResult(
            url=args.url,
            title="",
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
            markdown="",
            error=f"Content extraction failed: {e}",
        )
        return result.model_dump_json()

    # Convert HTML to Markdown
    try:
        markdown = html_to_md(main_html)
    except Exception as e:
        logger.error("Markdown conversion failed for %s: %s", args.url, e)
        result = PageMarkdownResult(
            url=args.url,
            title=title,
            markdown="",
            error=f"Markdown conversion failed: {e}",
        )
        return result.model_dump_json()

    result = PageMarkdownResult(
        url=args.url,
        title=title,
        markdown=markdown,
    )
    logger.info(
        "Page fetched: url=%s title=%r markdown_len=%d",
        args.url, title, len(markdown),
    )
    return result.model_dump_json()


TOOL_FUNCTIONS = [fetch_page_as_markdown]
