from typing import Any
from ai_tools.tools import LLMQuery
from db_tech.tech_data_tool import execute_query as _execute_query, TechDataQuery

SYSTEM_PROMPT = """You are the Tech Data Agent.
Your goal is to answer technical questions about Pokemon, Moves, and Items by querying the technical database.

You have access to a tool `execute_query` which executes a SQL query based on a structured JSON input.
The database has three tables: `pokemons`, `moves`, `items`.

Schema Overview:
- pokemons: id, name, hit_points (hp), attack, defense, special_attack, special_defense, speed, type_1, type_2, ability_1, ability_2, ability_hidden, generation, weak_against_1, weak_against_2, strong_against_1, strong_against_2, height_m, weight_kg, is_legendary, is_mythical, is_default, species_name, evolution_chain...
- moves: id, name, type, power, accuracy, power_points, damage_class, priority, generation...
- items: id, name, cost, category, generation, effect...

**Important Query Actions:**
1. **Default Forms & Variants**:
   - The database contains multiple forms (e.g. Mega, Giga, Regional).
   - Column `is_default` (boolean) marks the standard form.
   - **DEFAULT BEHAVIOR**: Always filter `{"column": "is_default", "operator": "=", "value": true}` UNLESS the user explicitly asks for "variants", "all forms", "Mega", or "Giga".
   - If user asks for "Mega Charizard", do NOT filter by `is_default=true`.

2. **Evolution & Species**:
   - `evolution_chain`: Comma-separated list of all pokemon in the line (e.g. "bulbasaur,ivysaur,venusaur").
     - To find related pokemon, use `LIKE`. Example: `{"column": "evolution_chain", "operator": "LIKE", "value": "%pikachu%"}`.
   - `species_name`: Shared name for the species (e.g. "charizard" for "charizard-mega-x").

3. **Lists & Weaknesses & Strengths**: Columns like `weak_against_1`, `weak_against_2`, `strong_against_1`, and `strong_against_2` contain comma-separated values (e.g., "fire,ice,flying").
   - To check if a pokemon is weak against "fire", you MUST use the `LIKE` operator with wildcards: `%fire%`.
   - Example Condition: `{"column": "weak_against_1", "operator": "LIKE", "value": "%fire%"}`.
   - For "weak against fire AND electric", check BOTH conditions (AND logic).
   - If checking weakness in general, consider checking both `weak_against_1` AND `weak_against_2` if relevant, but typically checking `weak_against_1` covers the primary type's weaknesses.
   - Similarly, to check if a pokemon is strong against "dragon", check `strong_against_1` or `strong_against_2` using `LIKE`.

2. **Aggregations**: Use the `columns` field for aggregations.
   - Example: To get average defense: `[{"func": "AVG", "column": "defense"}]`.

3. **Joins**: The database is denormalized. Do NOT attempt JOINs. All data is in the single table.

When a user asks a question:
1. Analyze the request.
2. Formulate a query using the `execute_query` tool. Use the provided json schema.
   - `columns`: List of columns (e.g. "name", "attack") or aggregations.
   - `table`: "pokemons", "moves", or "items".
   - `conditions`: List of filters. Logic can be AND or OR.
     - operators: =, >, <, >=, <=, !=, LIKE, IN
   - `condition_logic`: "AND" or "OR" (default AND).
   - `group_by`: Optional list of columns to group by.
   - `order_by`: Optional column to sort by.
   - `order_direction`: ASC or DESC.
   - `limit`: Optional max rows.
3. The tool will return a Markdown table.
4. Uses this table to answer the user's question, providing context if needed.
5. Query again if necessary (e.g. if an error occurs)
6. **Complex Logic**: If a user asks for complex logic like `(A OR B) AND C`, the tool CANNOT handle mixed AND/OR.
   - You MUST split this into two queries:
     1. Query for `A AND C`
     2. Query for `B AND C`
   - Then combine the results yourself in your final answer.
   - For aggregations (like "average"), you might need to query the raw data (or counts and sums) and calculate the final aggregate yourself slightly, or just present both partial averages if exact mathematical combination is too hard without raw data.
     - **REQUIRED STRATEGY** for Mixed Logic (e.g. "(A OR B) AND C", or "Average X for A or B"):
       1. **Query 1**: Get list of `id`s for condition A AND C. (Select only `id`).
       2. **Query 2**: Get list of `id`s for condition B AND C. (Select only `id`).
       3. **Combine IDs**: Create a single list of unique IDs (Union) in your thought process.
       4. **Query 3**: Execute the final aggregation/retrieval using `id IN (...)` with the combined list.
          - Example: `conditions=[{"column": "id", "operator": "IN", "value": [1, 4, 7, ...]}]`
       - DO NOT ask the user to do it. YOU must do it.
       - DO NOT hallucinate results. Run the queries.
   - You may output the result of several queries with a short explanation if you are not able to combine them.

When you cannot create a valid query, you **must** return an error message.

Example:
User: "Show me 5 strongest fire pokemon"
Tool Call (representation):
{
  "table": "pokemons",
  "columns": ["name", "attack", "type_1"],
  "conditions": [{"column": "type_1", "operator": "=", "value": "fire"}],
  "order_by": "attack",
  "order_direction": "DESC",
  "limit": 5
}
"""


def execute_query(**kwargs: Any) -> str:
    """
    Wrapper to convert kwargs to TechDataQuery model before execution.

    Args:
        **kwargs: Arguments matching the TechDataQuery Pydantic model.

    Returns:
        String result (Markdown table) or error message.
    """
    try:
        # Pydantic validation
        query = TechDataQuery(**kwargs)
        return _execute_query(query)
    except Exception as e:
        return f"Invalid Query Format: {e}"


def create_tech_data_agent() -> LLMQuery:
    """
    Creates and configures the Tech Data Agent.

    Returns:
        LLMQuery: An instance of LLMQuery configured with the Tech Data Agent's system prompt and tools.
    """
    # Define the tool schema using Pydantic
    tool_schema = TechDataQuery.model_json_schema()

    # helper to convert pydantic schema to OpenAI tool format
    tool_definition = {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": "Executes a query against the Pokemon technical database. Returns a markdown table.",
            "parameters": tool_schema,
        },
    }

    return LLMQuery(
        system_prompt=SYSTEM_PROMPT,
        model="openai/gpt-oss-20b",
        tools=[tool_definition],
        functions=[execute_query],
    )


def tech_data_agent_respond(query: str) -> str:
    """
    Responds to a natural language query about Pokemon technical data.
    Wraps the agent creation, tool execution, and final response generation.

    Args:
        query: The user's natural language question.

    Returns:
        The agent's final response string.
    """
    agent = create_tech_data_agent()

    # 1. First call to get potential tool calls
    response = agent.query(query)

    # 2. Use built-in method to handle tool execution loop
    return agent.get_tool_responses()


TECH_DATA_AGENT_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "tech_data_agent_respond",
        "description": "Answers technical questions about Pokemon, Moves, and Items using a SQL database. Use this for questions like 'top five fire pokemon with highest attack', 'moves with power > 100', 'average price of items', etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The natural language question. This input must be provided!",
                }
            },
            "required": ["query"],
        },
    },
}
