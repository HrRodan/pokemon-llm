"""
Web content extraction tool using Scrapling and html-to-markdown.

Fetches a URL and converts the main content to clean Markdown,
stripping navigation, ads, and boilerplate.
"""

import asyncio
import concurrent.futures
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from html_to_markdown import ConversionOptions
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
    timestamp: str = Field(description="The timestamp when the page was fetched.")
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

# Elements to strip from the extracted content to reduce noise and token usage
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
        if args.use_stealth:
            page = _run_stealthy_fetch(args.url)
        else:
            page = Fetcher.get(args.url, stealthy_headers=True, verify=False)
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
        
        save_dir = Path("data/web_scraper")
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


TOOL_FUNCTIONS = [fetch_page_as_markdown]
