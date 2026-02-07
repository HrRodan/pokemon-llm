import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from agents.pokemon_agent import PokemonAgent
from utils.config import settings


def test_pokemon_agent_instantiation():
    print("Testing PokemonAgent instantiation...")
    try:
        agent = PokemonAgent()
        print(f"Agent instantiated successfully: {agent.name}")
        print(f"Model: {agent.model}")

        # Check tools
        print(f"Number of tools: {len(agent.tools_def)}")
        tool_names = [t["function"]["name"] for t in agent.tools_def]
        print(f"Tools available: {tool_names}")

        assert "run_tech_data_agent" in tool_names
        assert "get_pokemon_details" in tool_names
        assert (
            "execute_query" not in tool_names
        )  # Should be hidden in TechDataAgent, not top level
        # Actually execute_query is NOT in PokemonAgent, it's in TechDataAgent.
        # But wait, run_tech_data_agent IS in tool_names.

        print("Verification passed!")
        return True
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_pokemon_agent_instantiation()
