from typing import Optional
from ai_tools.agent import Agent
from tools.vector_db import TOOL_FUNCTIONS as RAG_TOOL_FUNCTIONS
from utils.config import settings
from utils.logger import setup_logger

SYSTEM_PROMPT_RAG_AGENT = """You are the **Pokemon RAG Agent**.
Your role is to fetch qualitative and lore-based information from the Vector Database.
You excel at answering "Tell me about...", description, behavior, and biology questions.

**Important Instructions:**
1.  **Directness:** Do NOT be conversational. Do NOT say "Here is the information" or "I found the following". Just output the relevant information.
2.  **Tool Use:** You must ALWAYS use `query_database` to get information.
3.  **Accuracy:** Return the information from the database clearly and concisely.
4.  **No Fluff:** Remove unnecessary introductory or concluding remarks.
5.  **Refinement:** If the first search is not good enough, you can search again with better terms. Maximum number of searches is 5, do **NOT** exceed.

**Input:** A natural language question or topic. Rephrase and expand this query with more keywords to be more suitable for the RAG vector database.
**Output:** Depending on the exact question the complete response from the database might be returned or a direct, concise summary.
"""


class RAGAgent(Agent):
    """
    Agent responsible for interacting with the Vector Database (RAG).
    """

    TOOL_NAME = "run_rag_agent"
    TOOL_DESCRIPTION = (
        "Delegates a request to the RAG Specialist Agent. "
        "Use this for qualitative questions, lore, behavior, biology, or semantic "
        "searches like 'pokemon that look like dogs', 'tell me about Mewtwo'. "
        "Do NOT use for raw stats (use run_api_agent) or aggregations (use run_tech_data_agent)."
    )

    def __init__(self, model_name: Optional[str] = None, user_id: Optional[str] = None) -> None:
        super().__init__(
            name="RAGAgent",
            model=model_name or settings.SUB_AGENT_MODEL,
            system_prompt=SYSTEM_PROMPT_RAG_AGENT,
            tools=RAG_TOOL_FUNCTIONS,
            history_limit=20,
            logger=setup_logger("RAGAgent"),
            user_id=user_id,
        )
