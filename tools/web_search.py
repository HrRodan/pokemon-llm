"""
Google Web Search tool using Scrapling's stealth fetcher.

Searches Google and returns structured results (title, URL, snippet) as JSON.
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
    """A single Google search result entry."""

    title: str = Field(description="Title of the search result.")
    url: str = Field(description="URL of the search result.")
    snippet: str = Field(description="Text snippet / description from Google.")


class GoogleSearchInput(BaseModel):
    """Input parameters for Google web search."""

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
    timeout: int = Field(
        default=30000,
        ge=5000,
        le=60000,
        description="Timeout in milliseconds for the search request.",
    )


class GoogleSearchResult(BaseModel):
    """Structured output from a Google search."""

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


# Google frequently changes class names — this approach uses structural
# relationships (h3 → parent <a> → grandparent container) which are more stable.


def _build_google_url(query: str, num: int = 10) -> str:
    """Build a Google search URL with the given query and result count."""
    encoded = quote_plus(query)
    return f"https://www.google.com/search?q={encoded}&num={num}&hl=en"


def _run_stealthy_fetch(url: str, timeout: int = 30000):
    """Run Scrapling's StealthyFetcher in a thread to bypass Playwright's sync API checks.
    
    Playwright's sync API will crash with 'It looks like you are using Playwright Sync 
    API inside the asyncio loop' when run in Jupyter. We bypass this by executing it
    in a clean separate thread.
    """
    def _fetch():
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return StealthyFetcher.fetch(url, headless=True, google_search=True, timeout=timeout)
        
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


def _parse_results(page, max_results: int) -> list[SearchResultItem]:
    """Extract search result items from a Scrapling page response.

    Strategy: find all <h3> elements (result titles), walk up the DOM
    to find the enclosing <a> tag (URL), and search the grandparent
    container for snippet text. This is more resilient to Google's
    frequent class-name changes than using specific CSS classes.
    """
    items: list[SearchResultItem] = []
    h3_elements = page.css("h3")

    for h3 in h3_elements:
        if len(items) >= max_results:
            break

        title = str(h3.text).strip() if h3.text else ""
        if not title:
            continue

        # Walk up to find the enclosing <a> tag for the URL
        url = ""
        parent = h3.parent
        while parent:
            if parent.tag == "a":
                href = str(parent.attrib.get("href", ""))
                if href.startswith("http"):
                    url = href
                break
            parent = parent.parent

        if not url:
            continue

        # Walk to the result container (grandparent of the <a>) to find snippet.
        # Google nests results as:  container > div.yuRUbf > a > h3
        snippet = ""
        container = h3.parent
        # Go up 2-3 levels from h3 to find the top-level result container
        for _ in range(3):
            if container and container.parent:
                container = container.parent
            else:
                break

        if container:
            # Try known snippet container selectors first
            snippet_candidates = container.css("div.VwiC3b, div.tF2Cxc, span.st")
            if snippet_candidates:
                snippet = str(snippet_candidates[0].get_all_text(separator=" ", strip=True))
            else:
                # Fallback: look for any text-heavy div using recursive text extraction
                for div in container.css("div"):
                    all_text = str(div.get_all_text(separator=" ", strip=True))
                    if len(all_text) > 30 and title not in all_text:
                        snippet = all_text
                        break

        items.append(
            SearchResultItem(title=title, url=url, snippet=snippet.strip())
        )

    return items


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


@tool(schema=GoogleSearchInput)
def google_search(args: GoogleSearchInput) -> str:
    """Search Google and return structured results as JSON.

    Uses Scrapling's StealthyFetcher to bypass Google's bot detection.
    Supports optional site restriction via the site: operator.
    """
    # Build effective query
    effective_query = args.query
    if args.site_restrict:
        effective_query = f"site:{args.site_restrict} {args.query}"

    search_url = _build_google_url(effective_query, num=args.max_results)
    logger.info("Google search: query=%r url=%s timeout=%dms", effective_query, search_url, args.timeout)

    try:
        page = _run_stealthy_fetch(search_url, timeout=args.timeout)
    except Exception as e:
        logger.error("Google search fetch failed: %s", e)
        result = GoogleSearchResult(
            query=effective_query,
            results=[],
            total_returned=0,
            error=f"Fetch failed: {e}",
        )
        return result.model_dump_json()

    try:
        items = _parse_results(page, args.max_results)
    except Exception as e:
        logger.error("Google search parse failed: %s", e)
        result = GoogleSearchResult(
            query=effective_query,
            results=[],
            total_returned=0,
            error=f"Parse failed: {e}",
        )
        return result.model_dump_json()

    result = GoogleSearchResult(
        query=effective_query,
        results=items,
        total_returned=len(items),
    )
    logger.info("Google search returned %d results", len(items))
    return result.model_dump_json()


TOOL_FUNCTIONS = [google_search]
