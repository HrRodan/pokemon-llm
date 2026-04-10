
import json
from ai_tools.utils import _prepare_tool_dispatch
from ai_tools.agent import Agent
from unittest.mock import MagicMock

def test_tool_argument_repair():
    # User's malformed JSON example
    malformed_args = '{"columns": ["species_name"], "table": "pokemons", "where": {"logic": "AND", "filters": [{"column": "generation", "operator": "=", "value": 9}, {"column": "is_default", "operator": "=", "value": "trutrue}]}}'
    
    tool_call = {
        "id": "test_id",
        "function": {
            "name": "query_pokemon",
            "arguments": malformed_args
        }
    }
    
    def my_fn(columns, table, where):
        return "success"
        
    function_map = {"query_pokemon": my_fn}
    
    tool_id, function_name, arguments, function_to_call, pydantic_model, error_msg = _prepare_tool_dispatch(
        tool_call, function_map
    )
    
    print(f"Repaired arguments: {arguments}")
    assert error_msg is None
    assert isinstance(arguments, dict)
    assert arguments["table"] == "pokemons"
    assert arguments["where"]["filters"][1]["value"] == "trutrue"

def test_agent_formatted_response_repair():
    agent = Agent(model="gemini/gemini-flash-latest", json_format=True)
    
    # Mock the API response to return malformed JSON
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"greeting": "hello, "name": "world}' # Missing quotes/braces
    mock_message.tool_calls = None
    mock_message.reasoning = None
    mock_message.model_extra = None
    mock_message.model_dump.return_value = {"role": "assistant", "content": mock_message.content}
    
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock()
    
    agent._create_chat_completion = MagicMock(return_value=mock_response)
    agent._prepare_messages = MagicMock(return_value=[])
    agent._prepare_request_kwargs = MagicMock(return_value={})
    
    # Trigger a query
    agent.query("say hello")
    
    print(f"Repaired response: {agent.response}")
    # json_repair should fix it to something like {"greeting": "hello", "name": "world"}
    parsed = json.loads(agent.response)
    assert "greeting" in parsed
    assert "name" in parsed
    assert "hello" in parsed["greeting"]

if __name__ == "__main__":
    print("Running test_tool_argument_repair...")
    test_tool_argument_repair()
    print("Running test_agent_formatted_response_repair...")
    test_agent_formatted_response_repair()
    print("All tests passed!")
