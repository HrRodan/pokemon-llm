"""
DuckDuckGo Web Search tool using Scrapling's stealth fetcher.

Searches DuckDuckGo and returns structured results (title, URL, snippet) as JSON.
Supports optional site-scoping via the ``site:`` operator.
"""

import asyncio
import concurrent.futures
import logging
from urllib.parse import quote_plus

from pydantic import BaseModel, Field
from scrapling.fetchers import StealthyFetcher

from ai_tools.tool_definition import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SearchResultItem(BaseModel):
    """A single DuckDuckGo search result entry."""

    title: str = Field(description="Title of the search result.")
    url: str = Field(description="URL of the search result.")
    snippet: str = Field(description="Text snippet / description from DuckDuckGo.")


class DuckDuckGoSearchInput(BaseModel):
    """Input parameters for DuckDuckGo web search."""

    query: str = Field(description="The search query string.")
    site_restrict: str | None = Field(
        default=None,
        description=(
            "Optional domain to restrict results to "
            "(e.g. 'bulbapedia.bulbagarden.net')."
        ),
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of results to return.",
    )


class DuckDuckGoSearchResult(BaseModel):
    """Structured output from a DuckDuckGo search."""

    query: str = Field(
        description="The effective search query (including site: prefix if used)."
    )
    results: list[SearchResultItem] = Field(
        description="List of search result entries."
    )
    total_returned: int = Field(
        description="Number of results actually returned."
    )
    error: str | None = Field(
        default=None,
        description="Error message if the search failed.",
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _build_ddg_url(query: str) -> str:
    """Build a DuckDuckGo search URL with the given query.
    Note: DuckDuckGo doesn't officially support 'num' via GET parameters in this format.
    """
    encoded = quote_plus(query)
    # t=h_ specifies the app (html fallback or similar), ia=web specifies instant answer origin
    return f"https://duckduckgo.com/?q={encoded}&t=h_&ia=web"


def _run_stealthy_fetch(url: str):
    """Run Scrapling's StealthyFetcher in a thread to bypass Playwright's sync API checks."""
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


_AD_URL_PATTERNS = (
    "duckduckgo.com/y.js",  # DDG ad click-tracker
    "ad.doubleclick.net",
    "googleadservices.com",
    "bing.com/aclick",
)

_AD_CLASSES = frozenset({"result--ad", "sponsored", "ad-result", "results_ad"})


def _is_ad_element(element) -> bool:
    """Return True if the element is a DDG advertisement container."""
    # Check data-testid="ad" or data-sponsored attribute
    attribs = element.attrib
    if attribs.get("data-testid", "") == "ad":
        return True
    if "data-sponsored" in attribs:
        return True

    # Check element class list for known ad class names
    classes = set(attribs.get("class", "").split())
    if classes & _AD_CLASSES:
        return True

    return False


def _is_ad_url(url: str) -> bool:
    """Return True if the URL routes through an ad redirect."""
    return any(pattern in url for pattern in _AD_URL_PATTERNS)


def _parse_results(page, max_results: int) -> list[SearchResultItem]:
    """Extract organic (non-ad) search result items from a Scrapling page response.

    Strategy: Find result containers (e.g., <article> or elements with data-testid="result").
    Ad containers are detected by their attributes/classes and skipped.
    Results whose URLs route through ad redirects are also discarded.
    """
    items: list[SearchResultItem] = []

    # DuckDuckGo uses <article> or data-testid="result" for search results.
    articles = page.css('article')
    div_results = page.css('div[data-testid="result"]')
    results = articles + div_results

    for r in results:
        if len(items) >= max_results:
            break

        # --- Ad filter: skip sponsored containers ---
        if _is_ad_element(r):
            logger.debug("Skipping ad container")
            continue

        # Usually title is in an h2 -> a
        title_el = r.css('h2 a')
        if not title_el:
            title_el = r.css('a[data-testid="result-title-a"]')

        if not title_el:
            continue

        title = title_el[0].get_all_text(separator=" ", strip=True)
        url = title_el[0].attrib.get('href', '')

        if not url or not title:
            continue

        # --- Ad filter: skip ad redirect URLs ---
        if _is_ad_url(url):
            logger.debug("Skipping ad URL: %s", url)
            continue

        # Snippet usually in a div that contains the description
        snippet_el = r.css('div[data-result="snippet"]') or r.css('.yD50T_hI')
        snippet = ""

        if snippet_el:
            snippet = snippet_el[0].get_all_text(separator=" ", strip=True)
        else:
            # Fallback: find a span or div that has lots of text, skipping typical UI elements
            for div in r.css('div') + r.css('span'):
                text = div.get_all_text(separator=" ", strip=True)
                ui_markers = ["Clear filter", "Redo search", "Block this site", "Share feedback", "All results"]
                if len(text) > 40 and not any(marker in text for marker in ui_markers) and title not in text:
                    snippet = text
                    break

        items.append(
            SearchResultItem(title=title, url=url, snippet=snippet.strip())
        )

    return items


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


@tool(schema=DuckDuckGoSearchInput)
def duckduckgo_search(args: DuckDuckGoSearchInput) -> str:
    """Search DuckDuckGo and return structured results as JSON.

    Uses Scrapling's StealthyFetcher to bypass bot detection.
    Supports optional site restriction via the site: operator.
    """
    # Build effective query
    effective_query = args.query
    if args.site_restrict:
        effective_query = f"site:{args.site_restrict} {args.query}"

    search_url = _build_ddg_url(effective_query)
    logger.info("DuckDuckGo search: query=%r url=%s", effective_query, search_url)

    try:
        page = _run_stealthy_fetch(search_url)
    except Exception as e:
        logger.error("DuckDuckGo search fetch failed: %s", e)
        result = DuckDuckGoSearchResult(
            query=effective_query,
            results=[],
            total_returned=0,
            error=f"Fetch failed: {e}",
        )
        return result.model_dump_json()

    try:
        items = _parse_results(page, args.max_results)
    except Exception as e:
        logger.error("DuckDuckGo search parse failed: %s", e)
        result = DuckDuckGoSearchResult(
            query=effective_query,
            results=[],
            total_returned=0,
            error=f"Parse failed: {e}",
        )
        return result.model_dump_json()

    result = DuckDuckGoSearchResult(
        query=effective_query,
        results=items,
        total_returned=len(items),
    )
    logger.info("DuckDuckGo search returned %d results", len(items))
    return result.model_dump_json()


TOOL_FUNCTIONS = [duckduckgo_search]
