import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.tech_data_agent import tech_data_agent_respond


def test_complex_query():
    print("--- Testing Tech Data Agent with Complex Query ---")

    # Query logic: (defense < 100 OR attack < 100) AND generation < 6
    # This requires either:
    # 1. Splitting into multiple queries and merging.
    # 2. Clever use of NOT (if supported, but limited here).
    # 3. Failing gracefully if it tries to do it all in one go with current tool.
    query = "Get the average attack and defense per type for Pokemon where (defense < 100 or attack < 100) and generation < 6"

    print(f"\n{'=' * 20}\nQuestion: {query}\n{'=' * 20}")
    try:
        response = tech_data_agent_respond(query)
        sys.stdout.buffer.write(f"Response:\n{response}\n".encode("utf-8"))
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_complex_query()
