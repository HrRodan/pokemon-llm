import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from pokemon_tools.pokemon_client import PokemonAPIClient


def main():
    client = PokemonAPIClient(enable_cache=True)
    # Fetch raw data using internal _get method
    # "pound" is a simple move
    try:
        data = client._get("move", "pound")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # keys to look for based on request:
    # combos, id, flavor text, learned_by, info for effects

    # We print keys to see what's available
    print("Top level keys:", list(data.keys()))

    print("\n--- ID ---")
    print(data.get("id"))

    print("\n--- Flavor Text Entries (Sample) ---")
    entries = data.get("flavor_text_entries", [])
    if entries:
        # Filter for English
        en_entries = [e for e in entries if e["language"]["name"] == "en"]
        if en_entries:
            print(en_entries[0])
        else:
            print("No English flavor text found")
    else:
        print("No flavor text entries")

    print("\n--- Learned By (Sample) ---")
    learned_by = data.get("learned_by_pokemon", [])
    if learned_by:
        print(learned_by[0])
        print(f"Total learned by: {len(learned_by)}")

    print("\n--- Contest Combos ---")
    print(data.get("contest_combos"))

    print("\n--- Effect Entries ---")
    print(data.get("effect_entries"))

    print("\n--- Effect Changes ---")
    print(data.get("effect_changes"))

    print("\n--- Machines ---")
    print(data.get("machines"))


if __name__ == "__main__":
    main()
