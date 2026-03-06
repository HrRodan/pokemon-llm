from typing import List, Dict, Any, Optional

from ai_tools.tools import ModelName
from agents.base_agent import BaseAgent
from agents.api_agent import APIAgent
from agents.rag_agent import RAGAgent
from agents.tech_data_agent import TechDataAgent
from utils.config import settings
from utils.usage_tracker import UsageTracker

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
*   **When to use:** ONLY for chit-chat. Do **NOT** use world knowledge to answer questions about Pokémon, only use the agents.

## 3. Strategy
1.  **Analyze the Request:** What kind of data is needed?
    *   *Complex/Aggregated?* -> **Tech Data Agent**
    *   *Qualitative/Lore?* -> **RAG Agent**
    *   *Specific/Raw Data?* -> **API Agent**
2.  **Parallel Execution:** You can and **should** call multiple agents at once if the user asks for mixed info.
    *   *Example:* "Tell me about Charizard's lore and its base stats." -> Call `run_rag_agent` AND `run_api_agent`.
3.  **Synthesis:** Combine the reports from your agents into a helpful summary for the trainer.
4.  **Failure Handling:** If an agent fails, **DO NOT** use world knowledge. Instead, try again with a different agent or inform the user that the information is not available.

## 4. Formatting
*   **Tables:** Use Markdown tables for stats.
*   **Bold:** Highlight important names and values.
*   **Tone:** Be encouraging and scientific!

---
**Begin the interaction now."""


class PokemonAgent(BaseAgent):
    """
    Main orchestrator agent (Professor Oak) that interacts with the user
    and coordinates between specialised sub-agents via tool calls.

    Each sub-agent is a lazy singleton held on the instance.  Tool schemas
    and callable wrappers are derived via :meth:`BaseAgent.as_tool` and
    passed directly to the ``LLMQuery`` constructor — no separate schema
    dicts or function lists required.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        # Instantiate sub-agents — stateful singletons within this instance.
        self._tech = TechDataAgent()
        self._rag = RAGAgent()
        self._api = APIAgent()

        super().__init__(
            name="PokemonAgent",
            model_name=model_name or settings.DEFAULT_MODEL,
            system_prompt=SYSTEM_PROMPT_POKEMON_AGENT,
            # Each as_tool() returns a callable with .__tool_schema__ —
            # LLMQuery._resolve_tools() extracts the schema automatically.
            tools=[
                self._tech.as_tool(),
                self._rag.as_tool(),
                self._api.as_tool(),
            ],
            history_limit=50,
        )

    def query(self, user_prompt: str, **kwargs) -> str:
        """
        Delegate query to LLM.

        Args:
            user_prompt: The user's input text.
            **kwargs: Additional keyword arguments forwarded to ``LLMQuery.query``.

        Returns:
            The raw LLM response text.
        """
        return self.llm.query(user_prompt=user_prompt, **kwargs)

    def get_tool_responses(self, **kwargs) -> str:
        """
        Delegate tool execution loop to LLM.

        Args:
            **kwargs: Additional keyword arguments forwarded to ``LLMQuery.get_tool_responses``.

        Returns:
            The final assistant response after tool execution.
        """
        result = self.llm.get_tool_responses(**kwargs)
        self._collect_usage()
        return result

    @property
    def chat_history(self) -> List[Dict[str, Any]]:
        """Full chat history including tool messages."""
        return self.llm.chat_history

    @property
    def clean_chat_history(self) -> List[Dict[str, str]]:
        """Chat history filtered to user/assistant messages only."""
        return self.llm.clean_chat_history

    @property
    def reasoning_history(self) -> List[Any]:
        """List of reasoning traces from each LLM turn."""
        return self.llm.reasoning_history

    # ------------------------------------------------------------------
    # Usage properties — read from the global UsageTracker (includes
    # sub-agent usage) rather than only the local LLM counters.
    # ------------------------------------------------------------------

    @property
    def usage_tracker(self) -> UsageTracker:
        """Return the global UsageTracker instance."""
        return UsageTracker.get()

    @property
    def total_cost(self) -> float:
        """Accumulated cost across **all** agents."""
        return self.usage_tracker.get_totals().cost

    @property
    def total_tokens(self) -> int:
        """Accumulated total tokens across **all** agents."""
        return self.usage_tracker.get_totals().total_tokens

    @property
    def total_prompt_tokens(self) -> int:
        """Accumulated prompt tokens across **all** agents."""
        return self.usage_tracker.get_totals().prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        """Accumulated completion tokens across **all** agents."""
        return self.usage_tracker.get_totals().completion_tokens

    @property
    def total_reasoning_tokens(self) -> int:
        """Accumulated reasoning tokens across **all** agents."""
        return self.usage_tracker.get_totals().reasoning_tokens

    @property
    def model(self) -> str:
        """The currently configured LLM model name."""
        return self.llm.model

    @model.setter
    def model(self, value: "ModelName") -> None:
        self.llm.model = value

    def response(
        self, message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Respond to user message (full cycle: query + tool execution).

        Args:
            message: The user's input message.
            history: Optional chat history (unused, maintained internally).

        Returns:
            The final response text.
        """
        return self._run(message, use_history=True)

    def get_ui_state(self) -> Dict[str, Any]:
        """
        Expose internal state for the UI (tool calls, usage, etc.).

        Returns:
            A dict containing chat history, tool calls, reasoning,
            token counts, and cost.
        """
        totals = self.usage_tracker.get_totals()
        return {
            "chat_history": self.llm.chat_history,
            "tool_calls": self.llm.tool_calls,
            "reasoning_history": self.llm.reasoning_history,
            "tokens": {
                "prompt": totals.prompt_tokens,
                "completion": totals.completion_tokens,
                "total": totals.total_tokens,
                "reasoning": totals.reasoning_tokens,
            },
            "cost": totals.cost,
        }
