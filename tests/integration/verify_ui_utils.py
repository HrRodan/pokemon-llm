import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

try:
    from utils.ui_utils import get_agent_client

    print("Imports successful.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)


def test_ui_utils():
    print("Testing get_agent_client...")
    try:
        agent = get_agent_client()
        print(f"Agent instantiated: {agent.name}")
        assert agent.name == "PokemonAgent"
        print("get_agent_client passed.")
    except Exception as e:
        print(f"get_agent_client failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_ui_utils()
