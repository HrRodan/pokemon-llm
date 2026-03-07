"""
Integration test: Tech Data Agent complex query.

Requires a live LLM API key. Run manually — NOT part of the default pytest suite.

    uv run python tests/integration/test_complex_query.py
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agents.tech_data_agent import TechDataAgent


def test_complex_query():
    print("--- Testing Tech Data Agent with Complex Query ---")

    # Query logic: (defense < 100 OR attack < 100) AND generation < 6
    # Requires either splitting into multiple queries and merging,
    # or failing gracefully with the structured query tool.
    query = "Get the average attack and defense per type for Pokemon where (defense < 100 or attack < 100) and generation < 6"

    print(f"\n{'=' * 20}\nQuestion: {query}\n{'=' * 20}")
    try:
        agent = TechDataAgent()
        response = agent.run(query)
        sys.stdout.buffer.write(f"Response:\n{response}\n".encode("utf-8"))
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_complex_query()
