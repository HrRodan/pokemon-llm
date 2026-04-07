import sys
import codecs
import os
import logging

if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from agents.pokemon_agent import PokemonAgent
from utils.logger import setup_logger

# Configure root logger to write to debug.log
setup_logger("root", level=logging.DEBUG, log_file="debug.log")
setup_logger("PokemonAgent", level=logging.DEBUG, log_file="debug.log")
setup_logger("TechDataAgent", level=logging.DEBUG, log_file="debug.log")
setup_logger("ai_tools.tools", level=logging.DEBUG, log_file="debug.log")


def reproduce_issue():
    print("Initializing PokemonAgent...")
    agent = PokemonAgent()

    # Query that requires TechDataAgent
    query = "What is the average attack of Fire type Pokemon?"
    print(f"Sending query: {query}")

    response = agent.query(query)
    print(f"\nInitial Response: {response}")

    # Execute tools
    if agent.tool_calls:
        print("Tools triggered. Executing...")
        final_response = agent.get_tool_responses()
        print(f"\nFinal Response: {final_response}")
    else:
        print("No tools triggered.")


if __name__ == "__main__":
    reproduce_issue()
