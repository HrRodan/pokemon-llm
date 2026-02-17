from typing import List, Dict, Optional
from agents.base_agent import BaseAgent
from tools.api_client import PokemonAPIClient, TOOLS as API_TOOLS
from utils.config import settings

SYSTEM_PROMPT_API_AGENT = """You are the **Pokemon API Agent**.
Your role is to strictly fetch precise, raw data from the PokéAPI using the provided tools.
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

**Input:** A specific request for data (e.g. "What is Charizard's attack?", "How much does a Potion cost?").
**Output:** A natural language summary of the data returned by the tools.
"""


class APIAgent(BaseAgent):
    """
    Agent responsible for interacting with the PokéAPI.
    """

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(
            name="APIAgent", model_name=model_name or settings.SUB_AGENT_MODEL
        )

        # Initialize API Client
        self.pokemon_client = PokemonAPIClient()

        # Map functions
        # API Client functions need to be bound to the instance
        self.functions_map = {
            tool["function"]["name"]: getattr(
                self.pokemon_client, tool["function"]["name"]
            )
            for tool in API_TOOLS
        }
        self.functions_list = list(self.functions_map.values())

        # Configure LLM
        self.llm.system_prompt = SYSTEM_PROMPT_API_AGENT
        self.llm.tools = API_TOOLS
        self.llm.functions = self.functions_list

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
        self.log_query(message)
        response = self.llm.query(user_prompt=message, use_history=False)

        if self.llm.tool_calls:
            final_response = self.llm.get_tool_responses()
            self.log_response(final_response)
            self._collect_usage()
            return final_response

        self.log_response(response)
        self._collect_usage()
        return response


def run_api_agent(query: str) -> str:
    """
    Function to be used as a tool by other agents.
    Instantiates the agent and gets a response.
    """
    agent = APIAgent()
    return agent.response(query)


API_AGENT_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "run_api_agent",
        "description": "Delegates a request to the API Specialist Agent. Use this for specific data lookups like 'What are Charizard's base stats?', 'How much power does Thunderbolt have?', 'Where can I find Pikachu?'. Do NOT use for aggregations (use TechDataAgent) or lore/qualitative questions (use RAGAgent).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific data request.",
                }
            },
            "required": ["query"],
        },
    },
}
