"""
Manual verification script — runs API and RAG agents for smoke testing.

Requires a live LLM API key.

    uv run scripts/verify_agents.py
"""

import sys
import io

# Force stdout to handle utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents.api_agent import run_api_agent  # noqa: E402
from agents.rag_agent import run_rag_agent  # noqa: E402
from agents.pokemon_agent import PokemonAgent  # noqa: E402


def test_api_agent():
    print("\n" + "=" * 30)
    print("Testing API Agent")
    print("=" * 30)
    query = "What is the height and weight of Gengar?"
    print(f"Query: {query}")
    try:
        response = run_api_agent(query)
        print(f"Response:\n{response}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


def test_rag_agent():
    print("\n" + "=" * 30)
    print("Testing RAG Agent")
    print("=" * 30)
    query = "Tell me about the biology of Bulbasaur."
    print(f"Query: {query}")
    try:
        response = run_rag_agent(query)
        print(f"Response:\n{response}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


def test_pokemon_agent():
    print("\n" + "=" * 30)
    print("Testing Pokemon Agent (Orchestrator)")
    print("=" * 30)
    query = "Tell me about Mewtwo's lore and its base stats."
    print(f"Query: {query}")
    try:
        agent = PokemonAgent()
        response = agent.response(query)
        print(f"Response:\n{response}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_api_agent()
    test_rag_agent()
    test_pokemon_agent()
