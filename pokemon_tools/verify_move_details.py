import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from pokemon_tools.pokemon_client import PokemonAPIClient


def main():
    client = PokemonAPIClient(enable_cache=True)

    moves_to_test = ["pound", "flamethrower"]

    print("--- Test 1: Default behavior (Limit 20) ---")
    for move in moves_to_test:
        print(f"\nTesting move: {move}")
        try:
            details = client.get_move_details(move)

            # Check for new keys
            required_keys = [
                "id",
                "flavor_text",
                "learned_by",
                "total_learned_by",
                "contest_combos",
                "effect_chance",
                "machines",
            ]
            missing_keys = [key for key in required_keys if key not in details]

            if missing_keys:
                print(f"FAILED: Missing keys: {missing_keys}")
            else:
                print("SUCCESS: All new keys present.")
                print(f"ID: {details['id']}")
                print(f"Flavor Text: {details['flavor_text'][:50]}...")
                print(f"Learned By Count (Returned): {len(details['learned_by'])}")
                print(f"Total Learned By: {details['total_learned_by']}")
                print(f"Machines: {details['machines']}")

                if len(details["learned_by"]) > 20:
                    print("FAILED: Returned more than 20 items by default.")

        except Exception as e:
            print(f"ERROR: {e}")

    print("\n\n--- Test 2: Custom Limit (5) ---")
    details = client.get_move_details("pound", learned_by_limit=5)
    print(f"Learned By Count (Limit 5): {len(details['learned_by'])}")
    if len(details["learned_by"]) != 5:
        print(f"FAILED: Expected 5, got {len(details['learned_by'])}")

    print("\n\n--- Test 3: No Limit (-1) ---")
    details = client.get_move_details("pound", learned_by_limit=-1)
    print(f"Learned By Count (Limit -1): {len(details['learned_by'])}")
    if len(details["learned_by"]) != details["total_learned_by"]:
        print(
            f"FAILED: Expected {details['total_learned_by']}, got {len(details['learned_by'])}"
        )


if __name__ == "__main__":
    main()
