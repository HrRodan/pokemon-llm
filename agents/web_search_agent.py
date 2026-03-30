from typing import Optional
from pydantic import BaseModel, Field

from ai_tools.agent import AgentConfig
from ai_tools.tool_definition import tool
from agents.base_agent import BaseAgent
from tools.web_search_ddg import duckduckgo_search, DuckDuckGoSearchInput
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
    """Search Bulbapedia (Pokémon wiki) for the given query and return a list of matching URLs."""
    ddg_input = DuckDuckGoSearchInput(
        query=args.query, site_restrict="bulbapedia.bulbagarden.net", max_results=10
    )
    return duckduckgo_search(ddg_input)


class BulbapediaLinksInput(BaseModel):
    """Input parameters for extracting links from a Bulbapedia page."""

    url: str = Field(description="The Bulbapedia URL to extract links from.")
    max_links: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum number of links to return. Defaults to 30.",
    )


@tool(schema=BulbapediaLinksInput)
def bulbapedia_page_links(args: BulbapediaLinksInput) -> str:
    """Extract content-relevant links from a Bulbapedia page, restricted to bulbagarden.net.

    Use this to explore a page's structure and discover related article URLs
    before deciding which ones to ingest. Returns each link with its anchor
    text, surrounding context snippet, and nearest section heading.
    """
    return extract_page_links(ExtractLinksInput(
        url=args.url,
        domain_filter="bulbagarden.net",
        include_external=False,
        max_links=args.max_links,
    ))


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
    return extract_structured_data(ExtractStructuredDataInput(
        url=args.url,
        css_selector=args.css_selector,
        min_rows=3,
        min_columns=2,
        max_columns=10,
        max_tables=8,
    ))


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
| `bulbapedia_search` | DuckDuckGo site-search on Bulbapedia. Returns URLs + snippets. |
| `bulbapedia_page_links` | List content-relevant internal links from a page with context snippets. Use to explore article structure before ingesting. |
| `bulbapedia_structured_data` | Extract data tables (stats, move lists, type charts) as Markdown. Use for numerical or tabular data — faster and cheaper than full ingestion. |
| `bulbapedia_ingest_page` | Download and chunk a full page into the vector database. Use only for prose/lore queries. |
| `bulbapedia_query_content` | Semantic search over ingested pages. Use after ingestion to find exact answers. |

## Execution Strategy

**Phase 1 — Locate** (at most 1–2 calls)
- Call `bulbapedia_search` to find candidate URLs. Do not search more than 3 times per query.

**Phase 2 — Preview**
- For structured/numerical questions (stats, moves, types, evolution chains):
  → Call `bulbapedia_structured_data` directly on the best URL. If it returns the answer, **stop here**.
- For lore/prose questions where you need to pick the right sub-page:
  → Call `bulbapedia_page_links` to inspect the page's link structure and identify the relevant sub-article before ingesting.

**Phase 3 — Ingest**
- Call `bulbapedia_ingest_page` for the most relevant URL.
- **Limit: ingest at most 3 pages per user query.**

**Phase 4 — Query**
- Call `bulbapedia_query_content` to extract the exact answer from ingested content.
- If the first query does not yield the answer, **reformulate the semantic query** with different keywords before ingesting another page.

## Hard Limits
- `bulbapedia_search`: ≤ 3 calls per query.
- `bulbapedia_ingest_page`: ≤ 3 calls per query.
- Total tool calls: ≤ 10. Stop and report what you found if you hit this limit.

## Output Rules
- Answer **exclusively** from data retrieved via tools. Do not use pre-trained knowledge (anti-hallucination).
- Be direct and factual. Do not add conversational padding ("Here is what I found…").
- Cite the Bulbapedia URL(s) used at the end of your answer.
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
