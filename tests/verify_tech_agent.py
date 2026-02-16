import sys
import io

# Force stdout to handle utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from agents.tech_data_agent import run_tech_data_agent
import sys


def test_wrapper():
    print("--- Testing tech_data_agent_respond Wrapper ---")

    questions = ["Which Pokemon are strong against dragon type?"]

    for q in questions:
        print(f"\n{'=' * 20}\nQuestion: {q}\n{'=' * 20}")
        try:
            response = run_tech_data_agent(q)
            sys.stdout.buffer.write(f"Response:\n{response}\n".encode("utf-8"))
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_wrapper()
