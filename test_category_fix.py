import sys
import os

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from ingest import query_database


def test_category_handling():
    print("Testing string category input...")
    try:
        # Test with string
        result_str = query_database(query="fire type", category="pokemon", n_results=1)
        print("Success: String category accepted.")
    except Exception as e:
        print(f"Failed: String category raised exception: {e}")
        return

    print("\nTesting list category input...")
    try:
        # Test with list
        result_list = query_database(
            query="fire type", category=["pokemon"], n_results=1
        )
        print("Success: List category accepted.")
    except Exception as e:
        print(f"Failed: List category raised exception: {e}")
        return

    print("\nVerification passed!")


if __name__ == "__main__":
    test_category_handling()
