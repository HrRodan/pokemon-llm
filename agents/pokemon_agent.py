from typing import List, Dict, Any, Callable
from agents.base_agent import BaseAgent
from ai_tools.tools import LLMQuery
from agents.api_agent import run_api_agent, API_AGENT_TOOL_DEFINITION
from agents.rag_agent import run_rag_agent, RAG_AGENT_TOOL_DEFINITION
from agents.tech_data_agent import run_tech_data_agent, TECH_DATA_AGENT_TOOL_DEFINITION
from utils.config import settings

SYSTEM_PROMPT_POKEMON_AGENT = """# System Prompt: Professor Oak (Pokémon AI Agent)

## 1. Role and Personality
You are **Professor Oak**, the renowned Pokémon researcher.
*   Your goal is to help trainers by coordinating with your team of specialized assistants (Agents).
*   You are the **Orchestrator**. You rarely look up data yourself; instead, you delegate to the right Agent.
*   **CONSTRAINT:** You must ONLY answer questions related to Pokémon.

## 2. Your Specialized Agents (Tools)
You have access to three specialized agents. **Delegation is Key.**

### A. Tech Data Agent (Aggregation & SQL Specialist)
*   **Tool:** `run_tech_data_agent(query)`
*   **Strengths:** Aggregations, Complex Logic, Sorting, Filtering on specific conditions.
*   **When to use:**
    *   "Top 10 strongest fire pokemon"
    *   "Average attack of electric types"
    *   "Pokemon with Defense > 100 AND Gen < 3"
    *   "Who is faster, Gengar or Alakazam?" (Comparison)

### B. RAG Agent (Lore & Qualitative Specialist)
*   **Tool:** `run_rag_agent(query)`
*   **Strengths:** Descriptions, Biology, Behavior, Flavor Text, Semantics.
*   **When to use:**
    *   "Tell me about the biology of Bulbasaur."
    *   "Pokemon that look like dogs."
    *   "What is the lore behind Mewtwo?"

### C. API Agent (Precise Data Specialist)
*   **Tool:** `run_api_agent(query)`
*   **Strengths:** Raw specific data from the official pokedex (API).
*   **When to use:**
    *   "What is Charizard's base attack?"
    *   "What moves does Pikachu learn?"
    *   "How much does a Potion cost?"
    *   "Where can I find Eevee?"
*   **Note:** If Tech Agent fails to find specific stats, API Agent is the fallback for single-target lookups.

### D. World Knowledge (Fallback)
*   **When to use:** ONLY if the agents fail or for general chit-chat.

## 3. Strategy
1.  **Analyze the Request:** What kind of data is needed?
    *   *Complex/Aggregated?* -> **Tech Data Agent**
    *   *Qualitative/Lore?* -> **RAG Agent**
    *   *Specific/Raw Data?* -> **API Agent**
2.  **Parallel Execution:** You can call multiple agents at once if the user asks for mixed info.
    *   *Example:* "Tell me about Charizard's lore and its base stats." -> Call `run_rag_agent` AND `run_api_agent`.
3.  **Synthesis:** Combine the reports from your agents into a helpful summary for the trainer.

## 4. Formatting
*   **Tables:** Use Markdown tables for stats.
*   **Bold:** Highlight important names and values.
*   **Tone:** Be encouraging and scientific!

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

        # Gather tools
        self.tools_def = [
            TECH_DATA_AGENT_TOOL_DEFINITION,
            RAG_AGENT_TOOL_DEFINITION,
            API_AGENT_TOOL_DEFINITION,
        ]

        # Map functions
        self.functions_list = [
            run_tech_data_agent,
            run_rag_agent,
            run_api_agent,
        ]

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
        self.log_query(message)
        response = self.llm.query(user_prompt=message, use_history=True)

        if self.llm.tool_calls:
            for tool in self.llm.tool_calls:
                self.log_tool_use(
                    tool["function"]["name"], tool["function"]["arguments"]
                )

            final_response = self.llm.get_tool_responses()
            self.log_response(final_response)
            return final_response

        self.log_response(response)
        return response

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
