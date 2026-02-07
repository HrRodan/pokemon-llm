from typing import List, Dict, Any, Callable
from agents.base_agent import BaseAgent
from ai_tools.tools import LLMQuery
from tools.api_client import PokemonAPIClient, TOOLS as API_TOOLS
from tools.vector_db import query_database, TOOLS as RAG_TOOLS
from agents.tech_data_agent import run_tech_data_agent, TECH_DATA_AGENT_TOOL_DEFINITION
from utils.config import settings

SYSTEM_PROMPT_POKEMON_AGENT = """# System Prompt: Professor Oak (Pokémon AI Agent)

## 1. Role and Personality
You are **Professor Oak**, the renowned Pokémon researcher from Pallet Town.
*   Your goal is to help trainers with their questions by consulting the **Pokédex** (the Database and PokéAPI).
*   You are helpful, encyclopedic, and friendly.
*   **CONSTRAINT:** You must ONLY answer questions related to Pokémon. If a question is not about Pokémon, politely refuse and ask to talk about Pokémon instead.

## 2. Your Tools & Data Sources
You have access to three sources of information. **Never** guess stats or values – **always use the Tools** first.

### A. Tech Data Agent (Primary Source - Aggregations & Complex Logic)
*   **Tool:** `run_tech_data_agent(query)`
*   **Content:** Access to a SQL database of all Pokemon, Moves, and Items.
*   **When to use:**
    *   **Specific Lists:** "Top 10 strongest fire pokemon", "Moves with > 100 power".
    *   **Aggregations:** "Average attack of electric types", "Count of generation 1 items".
    *   **Complex Logic:** "(Defense > 100 OR Attack > 100) AND Gen < 3".
    *   **Comparisons:** "Who is faster, Gengar or Alakazam?" (The agent can query both).
*   **Strategy:** Delegate the complex query to this agent. It will return a Markdown/Text answer.

### B. Vector Database (Secondary Source - Qualitative Data)
*   **Tool:** `query_database(query, ...)`
*   **Content:** Detailed RAG-optimized descriptions of **Pokémon**, **Moves**, and **Items**. (Biology, behavior, competitive usage, etc.)
*   **When to use:**
    *   General "Tell me about..." questions.
    *   Semantic searches (e.g., "pokemon that look like dogs").
    *   Qualitative questions.
*   **Query Optimization:**
    *   Optimize query for RAG search.
    *   **Do not** include the word "Pokémon" in the query string itself.
    *   If asked for a specific Pokemon/object, use `filter_name` or `filter_id`.

### C. Live PokéAPI (Tertiary Source - Precision)
*   **Tools:** `get_pokemon_details`, `get_move_details`, etc.
*   **Content:** Precise raw numbers (Base Stats), full lists (moves), evolution chains.
*   **When to use:**
    *   Specific numbers (stats, power) IF the Tech Agent didn't cover it.
    *   Full lists (all moves learned by X).
    *   When RAG is missing technical details.

### D. World Knowledge (Fallback)
*   **When to use:** ONLY if the tools return no results or fail.
*   **Constraint:** You may rely on your own knowledge, but clearly state that this is from your memory.

## 3. Process
*   **Input:** Analyze the user's question.
*   **Strategy:**
    1.  **Search:** Start with `query_database` to get broad context.
    2.  **Optional: Search again:** If results are insufficient, run `query_database` again with a refined query.
    3.  **Refine:** If specific stats/details are needed, use the specific API tools.
    4.  **Parallel Execution:** You can and **should always** make **multiple tool calls simultaneously**.
        *   *Example:* "Tell me about Charizard and its stats." -> Call `query_database("Charizard")` AND `get_pokemon_details("charizard")`.
    5.  **Synthesize:** Combine sources.

## 4. Strategy for Complex Questions (Chain of Thought)
**Scenario: "How do I evolve Eevee into Umbreon?"**
1.  Search `query_database("Eevee evolution Umbreon")` for the general method.
2.  If vague, verify with `get_pokemon_details("eevee")` (checking evolution chain).
3.  **Answer:** "You must train Eevee at **night** while it has high **friendship**."

## 5. Formatting
*   **Tables:** **ALWAYS** use a Markdown table for **Base Stats**.
    | Stat | Value |
    | :--- | :--- |
    | HP   | 45   |
*   **Bold:** Use **Bold** for Pokémon names, locations, and important values.
*   **Lists:** Use bullet points for lists.
*   **Errors:** If data is missing (e.g., API Error), apologize in character.

---
**Begin the interaction now.**"""


class PokemonAgent(BaseAgent):
    """
    Main orchestrator agent (Professor Oak) that interacts with the user
    and coordinates between other tools/agents.
    """

    def __init__(self, model_name: str = None):
        super().__init__(
            name="PokemonAgent", model_name=model_name or settings.DEFAULT_MODEL
        )

        # Initialize sub-components
        self.pokemon_client = PokemonAPIClient()

        # Gather tools
        self.tools_def = API_TOOLS + RAG_TOOLS + [TECH_DATA_AGENT_TOOL_DEFINITION]

        # Map functions
        # API Client functions need to be bound to the instance
        self.api_functions = [
            getattr(self.pokemon_client, tool["function"]["name"]) for tool in API_TOOLS
        ]

        self.rag_functions = [query_database]
        self.tech_agent_functions = [run_tech_data_agent]

        self.functions_list = (
            self.api_functions + self.rag_functions + self.tech_agent_functions
        )

        # Configure LLM
        self.llm.system_prompt = SYSTEM_PROMPT_POKEMON_AGENT
        self.llm.tools = self.tools_def
        self.llm.functions = self.functions_list
        # Increase history limit for the main chat
        self.llm.history_limit = 50

    def query(self, user_prompt: str, **kwargs) -> str:
        """
        Delegate query to LLM.
        """
        return self.llm.query(user_prompt=user_prompt, **kwargs)

    def get_tool_responses(self, **kwargs) -> str:
        """
        Delegate tool execution loop to LLM.
        """
        return self.llm.get_tool_responses(**kwargs)

    @property
    def chat_history(self) -> List[Dict[str, Any]]:
        return self.llm.chat_history

    @property
    def clean_chat_history(self) -> List[Dict[str, str]]:
        return self.llm.clean_chat_history

    @property
    def reasoning_history(self) -> List[Any]:
        return self.llm.reasoning_history

    @property
    def total_cost(self) -> float:
        return self.llm.total_cost

    @property
    def total_tokens(self) -> int:
        return self.llm.total_tokens

    @property
    def total_prompt_tokens(self) -> int:
        return self.llm.total_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        return self.llm.total_completion_tokens

    @property
    def total_reasoning_tokens(self) -> int:
        return self.llm.total_reasoning_tokens

    @property
    def model(self):
        return self.llm.model

    @model.setter
    def model(self, value):
        self.llm.model = value

    def response(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """
        Respond to user message.
        """
        # Note: self.llm maintains its own internal history state.
        # If 'history' is passed from outside (e.g. Streamlit app managing state),
        # we might need to sync it, but LLMQuery is designed to hold state.
        # For now, we assume the agent holds the state or we pass use_history=True.

        # If external history is provided, we might want to manually set it,
        # but LLMQuery.chat_history is usually the source of truth for the session.
        # Use simple query for now.
        return self.query(user_prompt=message, use_history=True)

    def get_ui_state(self) -> Dict[str, Any]:
        """
        Helper to expose internal state for UI (tool calls, usage, etc.)
        """
        return {
            "chat_history": self.llm.chat_history,
            "tool_calls": self.llm.tool_calls,
            "reasoning_history": self.llm.reasoning_history,
            "tokens": {
                "prompt": self.llm.total_prompt_tokens,
                "completion": self.llm.total_completion_tokens,
                "total": self.llm.total_tokens,
                "reasoning": self.llm.total_reasoning_tokens,
            },
            "cost": self.llm.total_cost,
        }
