"""
Brave Web Search tool using the official Brave Search API.

Searches the web and returns structured results (title, URL, snippet) as JSON.
Requires BRAVE_SEARCH_API_KEY environment variable.
Supports optional site-scoping via the ``site:`` operator.
"""

import logging
import os

import requests
from pydantic import BaseModel, Field

from ai_tools.tool_definition import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SearchResultItem(BaseModel):
    """A single Brave search result entry."""

    title: str = Field(description="Title of the search result.")
    url: str = Field(description="URL of the search result.")
    snippet: str = Field(description="Text snippet / description from Brave Search.")


class BraveSearchInput(BaseModel):
    """Input parameters for Brave web search."""

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


class BraveSearchResult(BaseModel):
    """Structured output from a Brave search."""

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


def _perform_brave_search(query: str, max_results: int) -> dict:
    """Execute the HTTP request to the Brave Search API."""
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise ValueError("BRAVE_SEARCH_API_KEY environment variable is not set.")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": min(max_results, 20),
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


@tool(schema=BraveSearchInput)
def brave_search(args: BraveSearchInput) -> str:
    """Search the web using Brave Search API and return structured results as JSON.

    Supports optional site restriction via the site: operator.
    Requires BRAVE_SEARCH_API_KEY environment variable.
    """
    effective_query = args.query
    if args.site_restrict:
        effective_query = f"site:{args.site_restrict} {args.query}"

    logger.info("Brave search: query=%r", effective_query)

    try:
        data = _perform_brave_search(effective_query, args.max_results)
    except Exception as e:
        logger.error("Brave search failed: %s", e)
        result = BraveSearchResult(
            query=effective_query,
            results=[],
            total_returned=0,
            error=f"Search failed: {e}",
        )
        return result.model_dump_json()

    items: list[SearchResultItem] = []
    web_results = data.get("web", {}).get("results", [])

    for r in web_results:
        if len(items) >= args.max_results:
            break

        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("description", "")

        # Fallback to extra_snippets if description is missing
        if not snippet:
            extra = r.get("extra_snippets", [])
            if extra:
                snippet = " ".join(extra)

        if not title or not url:
            continue

        items.append(
            SearchResultItem(
                title=title,
                url=url,
                snippet=snippet.strip(),
            )
        )

    result = BraveSearchResult(
        query=effective_query,
        results=items,
        total_returned=len(items),
    )
    logger.info("Brave search returned %d results", len(items))
    return result.model_dump_json()


TOOL_FUNCTIONS = [brave_search]
