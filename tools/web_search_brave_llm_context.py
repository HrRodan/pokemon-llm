"""
Brave Web Search tool using the official Brave LLM Context API.

This API returns pre-extracted, relevance-scored web content optimized for RAG.
It extracts actual page content (text chunks, tables) directly.
Requires BRAVE_SEARCH_API_KEY environment variable.
Supports optional site-scoping via the ``site:`` operator.
"""

import logging
import os
from typing import Literal

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
    snippet: str = Field(
        description="Text snippet / extracted context from Brave Search."
    )


class BraveLLMContextInput(BaseModel):
    """Input parameters for Brave LLM Context web search."""

    query: str = Field(description="The search query string.")
    site_restrict: str | None = Field(
        default=None,
        description=(
            "Optional domain to restrict results to "
            "(e.g. 'bulbapedia.bulbagarden.net')."
        ),
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results (URLs) to return. Smaller budgets keep responses fast.",
    )
    maximum_number_of_tokens: int = Field(
        default=2048,
        ge=512,
        le=8192,
        description="Maximum tokens allowed for the generated context.",
    )
    context_threshold_mode: Literal["strict", "balanced", "lenient"] = Field(
        default="balanced",
        description="Relevance filtering threshold mode. Use 'strict' when precision matters more than recall.",
    )
    search_lang: str = Field(
        default="en",
        description="Language preference (2+ char language code).",
    )
    country: str = Field(
        default="US",
        description="Search country (2-letter country code or 'ALL').",
    )
    freshness: str | None = Field(
        default=None,
        description="Freshness filter (e.g. 'pd', 'pw', 'pm', 'py', '2022-04-01to2022-07-30').",
    )


class BraveLLMContextSearchResult(BaseModel):
    """Structured output from a Brave LLM Context search."""

    query: str = Field(
        description="The effective search query (including site: prefix if used)."
    )
    results: list[SearchResultItem] = Field(
        description="List of search result entries containing extracted context."
    )
    total_returned: int = Field(description="Number of results actually returned.")
    error: str | None = Field(
        default=None,
        description="Error message if the search failed.",
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _perform_brave_llm_context_search(
    query: str,
    max_results: int,
    maximum_number_of_tokens: int,
    context_threshold_mode: str,
    search_lang: str,
    country: str,
) -> dict:
    """Execute the HTTP request to the Brave LLM Context API."""
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not api_key:
        raise ValueError("BRAVE_SEARCH_API_KEY environment variable is not set.")

    url = "https://api.search.brave.com/res/v1/llm/context"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": min(max_results, 20),
        "maximum_number_of_tokens": maximum_number_of_tokens,
        "context_threshold_mode": context_threshold_mode,
        "search_lang": search_lang,
        "country": country,
    }

    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------


@tool(schema=BraveLLMContextInput)
def brave_llm_context_search(args: BraveLLMContextInput) -> str:
    """Search the web using Brave's LLM Context API and return deep-extracted results as JSON.

    Unlike standard web search which returns short UI snippets, this retrieves actual
    content chunks (paragraphs, tables) directly from the pages, optimizing for RAG.
    Requires BRAVE_SEARCH_API_KEY environment variable.
    """
    effective_query = args.query
    if args.site_restrict:
        effective_query = f"site:{args.site_restrict} {args.query}"

    logger.info("Brave LLM Context search: query=%r", effective_query)

    try:
        data = _perform_brave_llm_context_search(
            query=effective_query,
            max_results=args.max_results,
            maximum_number_of_tokens=args.maximum_number_of_tokens,
            context_threshold_mode=args.context_threshold_mode,
            search_lang=args.search_lang,
            country=args.country,
        )
    except Exception as e:
        logger.error("Brave LLM Context search failed: %s", e)
        result = BraveLLMContextSearchResult(
            query=effective_query,
            results=[],
            total_returned=0,
            error=f"Search failed: {e}",
        )
        return result.model_dump_json()

    items: list[SearchResultItem] = []

    # Generic grounding results containing the extracted snippets
    generic_results = data.get("grounding", {}).get("generic", [])

    for r in generic_results:
        if len(items) >= args.max_results:
            break

        title = r.get("title", "")
        url = r.get("url", "")

        # In LLM Context, actual data chunks are under 'snippets'
        snippets = r.get("snippets", [])

        # Safely concatenate all the snippets to form a single robust block of context
        snippet_texts = [str(s) for s in snippets if s]
        concatenated_snippet = "\\n\\n".join(snippet_texts)

        if not title or not url or not concatenated_snippet:
            continue

        items.append(
            SearchResultItem(
                title=title,
                url=url,
                snippet=concatenated_snippet.strip(),
            )
        )

    result = BraveLLMContextSearchResult(
        query=effective_query,
        results=items,
        total_returned=len(items),
    )
    logger.info("Brave LLM Context search returned %d results", len(items))
    return result.model_dump_json()


TOOL_FUNCTIONS = [brave_llm_context_search]
