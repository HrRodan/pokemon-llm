from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from agents.base_agent import BaseAgent
from tools.vector_db import query_database, TOOLS as RAG_TOOLS
from utils.config import settings

SYSTEM_PROMPT_RAG_AGENT = """You are the **Pokemon RAG Agent**.
Your role is to fetch qualitative and lore-based information from the Vector Database.
You excel at answering "Tell me about...", description, behavior, and biology questions.

**Important Instructions:**
1.  **Directness:** Do NOT be conversational. Do NOT say "Here is the information" or "I found the following". Just output the relevant information.
2.  **Tool Use:** You must ALWAYS use `query_database` to get information.
3.  **Accuracy:** Return the information from the database clearly and concisely.
4.  **No Fluff:** Remove unnecessary introductory or concluding remarks.
5.  **Refinement:** If the first search is not good enough, you can search again with better terms.

**Input:** A natural language question or topic. Rephrase this query to be more suitable for the RAG vector database.
**Output:** Depending on the exact question the complete response from the database might be returned or a direct, concise summary.
"""


class RAGAgent(BaseAgent):
    """
    Agent responsible for interacting with the Vector Database (RAG).
    """

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(
            name="RAGAgent",
            model_name=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_RAG_AGENT,
            tools=RAG_TOOLS,
            functions=[query_database],
            history_limit=20
        )

    def response(
        self, message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Respond to user message by searching the vector database.

        Args:
            message: The user's input message.
            history: Optional chat history (unused, sub-agent is stateless).

        Returns:
            The response text synthesised from RAG results.
        """
        return self._run(message)


# ---------------------------------------------------------------------------
# Lazy singleton — avoids reconstructing RAGAgent on every tool call.
# ---------------------------------------------------------------------------

_rag_agent: "RAGAgent | None" = None


def run_rag_agent(query: str) -> str:
    """
    Tool wrapper used by PokemonAgent.

    Lazily creates a single shared RAGAgent instance and reuses it for
    subsequent calls within the same process lifetime.

    Args:
        query: The natural language query to delegate.

    Returns:
        The RAG lookup result as a natural language string.
    """
    global _rag_agent
    if _rag_agent is None:
        _rag_agent = RAGAgent()
    return _rag_agent.response(query)


class RunRagAgentArgs(BaseModel):
    """Delegates a request to the RAG Specialist Agent. Use this for qualitative questions, lore, behavior, biology, or semantic searches like 'pokemon that look like dogs', 'tell me about Mewtwo'. Do NOT use for raw stats (use APIAgent) or aggregations (use TechDataAgent)."""

    query: str = Field(description="The natural language query.")


RAG_AGENT_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "run_rag_agent",
        "description": RunRagAgentArgs.__doc__,
        "parameters": RunRagAgentArgs.model_json_schema(),
    },
}
