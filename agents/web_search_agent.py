from typing import Optional
from pydantic import BaseModel, Field

from ai_tools.agent import AgentConfig
from ai_tools.tool_definition import tool
from agents.base_agent import BaseAgent
from tools.web_search_brave_llm_context import brave_llm_context_search, BraveLLMContextInput
from tools.web_content import (
    extract_page_links,
    extract_structured_data,
    ExtractLinksInput,
    ExtractStructuredDataInput,
)
from tools.web_vector_db import (
    ingest_web_page,
    query_web_content,
    IngestWebPageArgs,
    QueryWebContentArgs,
)
from utils.config import settings


class BulbapediaSearchInput(BaseModel):
    """Input parameters for Bulbapedia search."""

    query: str = Field(description="The search query string to look for on Bulbapedia.")


@tool(schema=BulbapediaSearchInput)
def bulbapedia_search(args: BulbapediaSearchInput) -> str:
    """Search Bulbapedia (Pokémon wiki) for the given query using deep LLM Context extraction."""
    brave_input = BraveLLMContextInput(
        query=args.query,
        site_restrict="bulbapedia.bulbagarden.net",
        max_results=10,
        maximum_number_of_tokens=4096,
        context_threshold_mode="balanced"
    )
    return brave_llm_context_search(brave_input)


class BulbapediaLinksInput(BaseModel):
    """Input parameters for extracting links from a Bulbapedia page."""

    url: str = Field(description="The Bulbapedia URL to extract links from.")
    max_links: int = Field(
        default=20,
        ge=1,
        le=60,
        description="Maximum number of links to return. Defaults to 20.",
    )


@tool(schema=BulbapediaLinksInput)
def bulbapedia_page_links(args: BulbapediaLinksInput) -> str:
    """Extract content-relevant links from a Bulbapedia page, restricted to bulbagarden.net.

    Use this to explore a page's structure and discover related article URLs
    before deciding which ones to ingest. Returns each link with its anchor
    text, surrounding context snippet, and nearest section heading.
    """
    return extract_page_links(
        ExtractLinksInput(
            url=args.url,
            domain_filter="bulbagarden.net",
            include_external=False,
            max_links=args.max_links,
        )
    )


class BulbapediaStructuredDataInput(BaseModel):
    """Input parameters for extracting structured table data from a Bulbapedia page."""

    url: str = Field(description="The Bulbapedia URL to extract tables from.")
    css_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to target a specific section of the page.",
    )


@tool(schema=BulbapediaStructuredDataInput)
def bulbapedia_structured_data(args: BulbapediaStructuredDataInput) -> str:
    """Extract data tables from a Bulbapedia page as Markdown.

    Returns stats tables, move lists, type charts, and other structured data
    as Markdown tables, labeled by caption or section heading. Use this for
    numerical or tabular Pokémon data — faster and cheaper than full ingestion.
    """
    return extract_structured_data(
        ExtractStructuredDataInput(
            url=args.url,
            css_selector=args.css_selector,
            min_rows=3,
            min_columns=2,
            max_columns=10,
            max_tables=8,
        )
    )


class BulbapediaIngestInput(BaseModel):
    url: str = Field(description="The Bulbapedia URL to download and ingest.")


@tool(schema=BulbapediaIngestInput)
def bulbapedia_ingest_page(args: BulbapediaIngestInput) -> str:
    """Download the content of a specific Bulbapedia URL and ingest it into the vector database."""
    return ingest_web_page(
        IngestWebPageArgs(
            url=args.url, css_selector=None, use_stealth=False, max_age_days=7
        )
    )


class BulbapediaQueryInput(BaseModel):
    query: str = Field(description="The semantic query string to search for.")
    filter_url: Optional[str] = Field(
        default=None,
        description="**Optional** exact URL to filter results by. Leave empty to search all ingested pages.",
    )


@tool(schema=BulbapediaQueryInput)
def bulbapedia_query_content(args: BulbapediaQueryInput) -> str:
    """Perform semantic search against ingested Bulbapedia pages to extract answers."""
    return query_web_content(
        QueryWebContentArgs(query=args.query, n_results=5, filter_url=args.filter_url)
    )


SYSTEM_PROMPT_WEB_SEARCH_AGENT = """\
You are the **Web Search Agent**, the Real-time & Deep Lore Specialist for Pokémon data.
Your goal is to answer questions by efficiently exploring Bulbapedia, retrieving only what
you need, and avoiding unnecessary ingestion.

## Tools

| Tool | Purpose |
|---|---|
| `bulbapedia_search` | Brave LLM Context search on Bulbapedia. Returns URLs + deeply extracted content snippets. |
| `bulbapedia_page_links` | List content-relevant internal links from a page with context snippets. Use to explore article structure before ingesting. |
| `bulbapedia_structured_data` | Extract data tables (stats, move lists, type charts) as Markdown. Use for numerical or tabular data — faster and cheaper than full ingestion. |
| `bulbapedia_ingest_page` | Download and chunk a full page into the vector database. Use only as a fallback. |
| `bulbapedia_query_content` | Semantic search over ingested pages. Use after ingestion to find exact answers. |

## Execution Strategy

**Phase 1 — Locate & Extract** (at **most** 1–2 calls)
- Call `bulbapedia_search` to find candidate URLs and extract their deep context. 
- **Check Snippets First:** The `snippet` fields returned by this tool contain dense, raw content (including markdown tables and text blocks) extracted directly from the pages. Read them carefully!
- If the deep snippets completely answer the user's question, **stop here and answer immediately**. Ingestion is not required.

**Phase 2 — Preview (If needed)**
- For structured/numerical questions (stats, moves, types, evolution chains) that weren't in the snippets:
  → Call `bulbapedia_structured_data` directly on the best URL from Phase 1. If it returns the answer, **stop here**.
- For dense lore where you need to find an exact sub-page:
  → Call `bulbapedia_page_links` to review page structure before resorting to ingestion.

**Phase 3 — Ingest (Optional Fallback)**
- Only call `bulbapedia_ingest_page` if Phases 1 and 2 failed to provide the required knowledge.
- **Limit: ingest at most 3 pages per user query.**

**Phase 4 — Query (If ingested)**
- Call `bulbapedia_query_content` to extract the exact answer from ingested content.
- If the first query does not yield the answer, **reformulate the semantic query** with different keywords before ingesting another page.

## Hard Limits
- `bulbapedia_search`: ≤ 3 calls per query.
- `bulbapedia_ingest_page`: ≤ 3 calls per query.
- Total tool calls: ≤ 10. Stop and report what you found if you hit this limit.

## Output Rules
- Answer **exclusively** from data retrieved via tools. Do not use pre-trained knowledge (anti-hallucination).
- Be direct and factual. Do not add conversational padding ("Here is what I found…").
- Do **not** include urls in the response.
"""


class WebSearchAgent(BaseAgent):
    """
    Agent responsible for fetching and querying real-time web data from Bulbapedia.
    """

    TOOL_NAME = "run_web_search_agent"
    TOOL_DESCRIPTION = (
        "Delegates a request to the Web Search Agent. "
        "Use this for deep lore not natively in the internal Database, specific anime episode summaries, "
        "game walkthrough details, newest generation info, or as the ultimate fallback when Tech, API, or RAG agents fail."
    )

    def __init__(self, model_name: Optional[str] = None) -> None:
        super().__init__(
            config=AgentConfig(
                name="WebSearchAgent",
                model_name=model_name or settings.SUB_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT_WEB_SEARCH_AGENT,
                tools=[
                    bulbapedia_search,
                    bulbapedia_page_links,
                    bulbapedia_structured_data,
                    bulbapedia_ingest_page,
                    bulbapedia_query_content,
                ],
                history_limit=120,
            )
        )
