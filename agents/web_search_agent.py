from typing import Optional
from pydantic import BaseModel, Field

from ai_tools.agent import Agent
from ai_tools.tool_definition import tool
from tools.web_search_brave_llm_context import (
    brave_llm_context_search,
    BraveLLMContextInput,
)
from utils.config import settings
from utils.logger import setup_logger


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
        context_threshold_mode="balanced",
    )
    return brave_llm_context_search(brave_input)


SYSTEM_PROMPT_WEB_SEARCH_AGENT = """\
You are the **Web Search Agent**, the Real-time & Deep Lore Specialist for Pokémon data.
Your goal is to answer questions by efficiently exploring Bulbapedia, retrieving only what
you need.

## Tools

| Tool | Purpose |
|---|---|
| `bulbapedia_search` | Brave LLM Context search on Bulbapedia. Returns URLs + deeply extracted content snippets. |

## Execution Strategy

**Phase 1 — Locate & Extract**
- Call `bulbapedia_search` to find candidate URLs and extract their deep context. 
- **Check Snippets First:** The `snippet` fields returned by this tool contain dense, raw content (including markdown tables and text blocks) extracted directly from the pages. Read them carefully!
- If the deep snippets completely answer the user's question, **stop here and answer immediately**.

## Hard Limits
- `bulbapedia_search`: ≤ 3 calls per query.
- Total tool calls: ≤ 10. Stop and report what you found if you hit this limit.

## Output Rules
- Answer **exclusively** from data retrieved via tools. Do not use pre-trained knowledge (anti-hallucination).
- Be direct and factual. Do not add conversational padding ("Here is what I found…").
- Do **not** include urls in the response.
"""


class WebSearchAgent(Agent):
    """
    Agent responsible for fetching and querying real-time web data from Bulbapedia.
    """

    TOOL_NAME = "run_web_search_agent"
    TOOL_DESCRIPTION = (
        "Delegates a request to the Web Search Agent. "
        "Use this for deep lore not natively in the internal Database, specific anime episode summaries, "
        "game walkthrough details, newest generation info, or as the ultimate fallback when Tech, API, or RAG agents fail."
    )

    def __init__(self, model_name: Optional[str] = None, user_id: Optional[str] = None) -> None:
        super().__init__(
            name="WebSearchAgent",
            model=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_WEB_SEARCH_AGENT,
            tools=[
                bulbapedia_search,
            ],
            history_limit=120,
            logger=setup_logger("WebSearchAgent"),
            user_id=user_id,
        )
