from typing import List, Dict, Any, Optional
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

**Input:** A natural language question or topic.
**Output:** A direct, concise summary of the database content.
"""


class RAGAgent(BaseAgent):
    """
    Agent responsible for interacting with the Vector Database (RAG).
    """

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(
            name="RAGAgent", model_name=model_name or settings.SUB_AGENT_MODEL
        )

        # Configure LLM
        self.llm.system_prompt = SYSTEM_PROMPT_RAG_AGENT
        self.llm.tools = RAG_TOOLS
        self.llm.functions = [query_database]

    def response(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """
        Respond to user message.
        """
        self.log_query(message)
        response = self.llm.query(user_prompt=message)

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


def run_rag_agent(query: str) -> str:
    """
    Function to be used as a tool by other agents.
    Instantiates the agent and gets a response.
    """
    agent = RAGAgent()
    return agent.response(query)


RAG_AGENT_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "run_rag_agent",
        "description": "Delegates a request to the RAG Specialist Agent. Use this for qualitative questions, lore, behavior, biology, or semantic searches like 'pokemon that look like dogs', 'tell me about Mewtwo'. Do NOT use for raw stats (use APIAgent) or aggregations (use TechDataAgent).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The natural language query.",
                }
            },
            "required": ["query"],
        },
    },
}
