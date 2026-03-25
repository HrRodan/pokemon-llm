from typing import Optional
from ai_tools.agent import AgentConfig
from agents.base_agent import BaseAgent
from tools.api_client import TOOL_FUNCTIONS
from tools.fuzzy_search import TOOL_FUNCTIONS as FUZZY_FUNCTIONS
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
- **Name Lookup:** Find exact valid names from partial strings using `search_exact_name`. Use this if the API fails with "not found" due to typos or missing forms/suffixes (e.g. pumpkaboo-small).

**Guidelines:**
1.  **Tool Use is Mandatory:** You must ALWAYS use a tool to get information. **Do not hallucinate** stats or other information. If certain information is not avaiable, say so.
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

    TOOL_NAME = "run_api_agent"
    TOOL_DESCRIPTION = (
        "Delegates a request to the API Specialist Agent. "
        "Use this for **specific** data lookups on **concrete** names of moves, items or pokemon like 'What are Charizard's base stats?', "
        "'How much power does Thunderbolt have?', 'Where can I find Pikachu?'. "
        "Do NOT use for aggregations (use run_tech_data_agent) or "
        "lore/qualitative questions (use run_rag_agent)."
    )

    def __init__(self, model_name: Optional[str] = None) -> None:
        super().__init__(
            config=AgentConfig(
                name="APIAgent",
                model_name=model_name or settings.SUB_AGENT_MODEL,
                system_prompt=SYSTEM_PROMPT_API_AGENT,
                tools=TOOL_FUNCTIONS + FUZZY_FUNCTIONS,
                history_limit=40,
            )
        )

    def run(self, message: str, use_history: bool = False) -> str:
        """
        Respond to user message by querying the PokéAPI tools.

        Args:
            message: The user's input message.
            use_history: Optional flag, defaults to False for API lookup.

        Returns:
            The response text from the API lookup.
        """
        return super().run(message, use_history=use_history)
