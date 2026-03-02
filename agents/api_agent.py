from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from agents.base_agent import BaseAgent
from tools.api_client import TOOLS as API_TOOLS, TOOL_FUNCTIONS
from utils.config import settings

SYSTEM_PROMPT_API_AGENT = """You are the **Pokemon API Agent**.
Your role is to strictly fetch precise, raw data from the PokéAPI using the provided tools and summarize the tool responses in a human readable format.
You do NOT answer general questions or provide qualitative descriptions unless they are part of the API response (e.g. flavor text).

**Your capabilities:**
- **Stats & Data:** Get base stats, height, weight, abilities using `get_pokemon_details`.
- **Moves:** Get move power, accuracy, PP, and effects using `get_move_details`.
- **Evolutions:** Get evolution chains (via `get_pokemon_details`).
- **Items:** Get item cost and attributes using `get_item_info`.
- **Types:** Get type effectiveness using `get_type_info`.
- **Locations:** Get encounter locations using `get_encounters`.

**Guidelines:**
1.  **Tool Use is Mandatory:** You must ALWAYS use a tool to get information. Do not hallucinate stats.
2.  **Conciseness:** Provide the data asked for. You don't need to be overly conversional, just helpful and accurate.
3.  **Error Handling:** If a tool returns an error (e.g., "Pokemon not found"), report this clearly to the user.
4.  **Multiple Tools:** If the user asks for multiple things (e.g. "stats of Charizard and Bulbasaur"), call the tools in parallel.
5.  **Output**: Do not reference the tools or the API in your final response. Just provide the data asked for in a natural language summary.

**Input:** A specific request for data (e.g. "What is Charizard's attack?", "How much does a Potion cost?").
**Output:** A natural language summary of the data returned by the tools.
"""


class APIAgent(BaseAgent):
    """
    Agent responsible for interacting with the PokéAPI.
    """

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(
            name="APIAgent",
            model_name=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_API_AGENT,
            tools=API_TOOLS,
            functions=TOOL_FUNCTIONS,
            history_limit=40
        )

    def response(
        self, message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Respond to user message by querying the PokéAPI tools.

        Args:
            message: The user's input message.
            history: Optional chat history (unused, sub-agent is stateless).

        Returns:
            The response text from the API lookup.
        """
        return self._run(message, use_history=False)


# ---------------------------------------------------------------------------
# Lazy singleton — avoids reconstructing PokemonAPIClient on every tool call.
# ---------------------------------------------------------------------------

_api_agent: "APIAgent | None" = None


def run_api_agent(query: str) -> str:
    """
    Tool wrapper used by PokemonAgent.

    Lazily creates a single shared APIAgent instance and reuses it for
    subsequent calls within the same process lifetime.

    Args:
        query: The specific data request to delegate.

    Returns:
        The API lookup result as a natural language string.
    """
    global _api_agent
    if _api_agent is None:
        _api_agent = APIAgent()
    return _api_agent.response(query)


class RunApiAgentArgs(BaseModel):
    """Delegates a request to the API Specialist Agent. Use this for specific data lookups like 'What are Charizard's base stats?', 'How much power does Thunderbolt have?', 'Where can I find Pikachu?'. Do NOT use for aggregations (use TechDataAgent) or lore/qualitative questions (use RAGAgent)."""

    query: str = Field(description="The specific data request.")


API_AGENT_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "run_api_agent",
        "description": RunApiAgentArgs.__doc__,
        "parameters": RunApiAgentArgs.model_json_schema(),
    },
}
