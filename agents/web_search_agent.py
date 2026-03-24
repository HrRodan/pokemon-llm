from typing import Optional
from pydantic import BaseModel, Field

from ai_tools.agent import AgentConfig
from ai_tools.tool_definition import tool
from agents.base_agent import BaseAgent
from tools.web_search_ddg import duckduckgo_search, DuckDuckGoSearchInput
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
    # Use the DuckDuckGo search tool but with a strict site restriction
    ddg_input = DuckDuckGoSearchInput(
        query=args.query, site_restrict="bulbapedia.bulbagarden.net", max_results=10
    )
    return duckduckgo_search(ddg_input)


class BulbapediaIngestInput(BaseModel):
    url: str = Field(description="The Bulbapedia URL to download and ingest.")


@tool(schema=BulbapediaIngestInput)
def bulbapedia_ingest_page(args: BulbapediaIngestInput) -> str:
    """Downloads the content of a specific Bulbapedia URL and ingests it into the vector database."""
    return ingest_web_page(
        IngestWebPageArgs(
            url=args.url, css_selector=None, use_stealth=False, max_age_days=7
        )
    )


class BulbapediaQueryInput(BaseModel):
    query: str = Field(description="The semantic query string to search for.")
    filter_url: Optional[str] = Field(
        default=None,
        description="**Optional** exact URL to filter results by. Leave empty if you want to search all ingested pages (default).",
    )


@tool(schema=BulbapediaQueryInput)
def bulbapedia_query_content(args: BulbapediaQueryInput) -> str:
    """Performs semantic search against ingested Bulbapedia pages to extract answers."""
    return query_web_content(
        QueryWebContentArgs(query=args.query, n_results=5, filter_url=args.filter_url)
    )


SYSTEM_PROMPT_WEB_SEARCH_AGENT = """You are the **Web Search Agent**, the Real-time & Deep Lore Specialist.
Your goal is to answer questions by searching Bulbapedia, downloading relevant pages to the local vector database, and querying it for precise answers.

**Available Tools:**
1. `bulbapedia_search`: Searches Bulbapedia and returns a list of URLs and snippets.
2. `bulbapedia_ingest_page`: Downloads the content of a specific URL and ingests it into the vector database.
3. `bulbapedia_query_content`: Performs semantic search against ingested pages to extract your answer.

**Strict Execution Loop (MUST FOLLOW):**
- **Step 1:** Use `bulbapedia_search` to find the 1 or 2 most relevant URLs. Search for **at most 5 times** per user query.
- **Step 2:** Use `bulbapedia_ingest_page` to download the chosen URL. (CONSTRAINT: Do not ingest more than 2 websites per user query).
- **Step 3:** Use `bulbapedia_query_content` to find the exact paragraph answering the user's query. Exact URL is optional and should typically be omitted to search full database.

**Refinement Strategy:**
- If `bulbapedia_query_content` does not initially yield the correct answer, you MUST **refine your semantic query** for `bulbapedia_query_content` using different keywords, rather than immediately firing another `bulbapedia_search` to download a new page. Only search for a new page if you are certain the detail isn't on the ingested page.

**Restrictions:**
- Ingest **no more than 2** websites per search.
- Search for **no more than 6 times** per user query.
- Stop searching if you cannot find the answer after 6 searches and say so.
- You must **always** return a response or a tool call.

**Directness & Context:**
- Answer **exclusively** using the data retrieved via `bulbapedia_query_content`. Do NOT answer based on your general pre-trained knowledge (anti-hallucination).
- Describe what you found in your research, add supplementary information. The output should be concise, factual, and direct without any conversational padding (Do not say "Here is what I found").
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
                    bulbapedia_ingest_page,
                    bulbapedia_query_content,
                ],
                history_limit=120,
            )
        )
