"""
Script to recreate the technical database (db_tech/tech.db) from raw JSON data.

This script:
1. Drops the existing database.
2. Creates tables using SQLAlchemy models.
3. Iterates through raw JSON files for Pokemon, Moves, and Items.
4. Parses the JSON data, ensuring robust handling of missing fields and nested structures.
5. Populates the SQLite database.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db_tech.models import Base, Pokemon, Move, Item

# Paths
BASE_DIR = Path(".")
DB_PATH = BASE_DIR / "db_tech" / "tech.db"
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_LIST_DIR = BASE_DIR / "data"

# Ensure db directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Delete existing DB
if DB_PATH.exists():
    os.remove(DB_PATH)
    print(f"Removed existing database at {DB_PATH}")

# Create engine and tables
engine = create_engine(f"sqlite:///{DB_PATH}")
Base.metadata.create_all(engine)
print("Created database tables.")


def load_json(path: Path) -> Any:
    """Refactoring helper to load JSON content from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_evo_names(chain_node: Dict[str, Any]) -> List[str]:
    """Recursively extract species names from evolution chain."""
    names = []
    if not chain_node or "species_name" not in chain_node:
        return names
    names.append(chain_node["species_name"])
    for child in chain_node.get("evolves_to", []):
        names.extend(get_evo_names(child))
    return names


def process_pokemons(session: Session) -> None:
    """
    Parses Pokemon JSON files and adds them to the database.
    Handles extraction of stats, types, abilities, and derived fields like generation.
    """
    print("Processing Pokemon...")
    pokemon_dir = DATA_RAW_DIR / "pokemon"
    count = 0

    for file_path in pokemon_dir.glob("*.json"):
        data = load_json(file_path)
        details = data.get("pokemon_details", {})
        type_info = data.get("type_info", [])

        # Extract Types (primary and secondary)
        types = details.get("types", [])
        type_1 = types[0] if len(types) > 0 else "unknown"
        type_2 = types[1] if len(types) > 1 else None

        # Extract Abilities
        # Logic attempts to map slot 1/2/hidden. Fallbacks for irregular data.
        abilities = details.get("abilities", [])
        ability_1 = next(
            (a["name"] for a in abilities if a.get("slot") == 1), "unknown"
        )
        ability_2 = next((a["name"] for a in abilities if a.get("slot") == 2), None)
        ability_hidden = next(
            (a["name"] for a in abilities if a.get("is_hidden")), None
        )
        # Fallback: if slots aren't strict 1/2 or missing, fill from non-hidden list
        non_hidden = [a["name"] for a in abilities if not a.get("is_hidden")]
        if ability_1 == "unknown" and non_hidden:
            ability_1 = non_hidden[0]
        if ability_2 is None and len(non_hidden) > 1:
            ability_2 = non_hidden[1]

        # Extract Weak/Strong type relations
        # These are stored as comma-separated strings for simple querying
        weak_1 = None
        strong_1 = None
        weak_2 = None
        strong_2 = None

        if len(type_info) > 0:
            t1 = type_info[0]
            weak_1 = ",".join(t1.get("weak_against", []))
            strong_1 = ",".join(t1.get("strong_against", []))

        if len(type_info) > 1:
            t2 = type_info[1]
            weak_2 = ",".join(t2.get("weak_against", []))
            strong_2 = ",".join(t2.get("strong_against", []))

        # Map generation string (e.g., "generation-i") to integer
        generation_str = details.get("generation", "")
        gen_map = {
            "generation-i": 1,
            "generation-ii": 2,
            "generation-iii": 3,
            "generation-iv": 4,
            "generation-v": 5,
            "generation-vi": 6,
            "generation-vii": 7,
            "generation-viii": 8,
            "generation-ix": 9,
        }
        generation = gen_map.get(generation_str, 0)

        # New Fields Extraction
        is_default = details.get("is_default", True)
        species_name = details.get("species_name")

        # Evolution Chain
        evo_data = details.get("evolution", {})
        chain_node = evo_data.get("chain", {})
        # If chain is missing (some forms might not have it?), default to empty
        if chain_node:
            evo_list = get_evo_names(chain_node)
            # Remove duplicates just in case, though traversal should be unique
            # Maintain order
            seen = set()
            unique_evo = [x for x in evo_list if not (x in seen or seen.add(x))]
            evolution_chain = ",".join(unique_evo)
        else:
            evolution_chain = ""

        name = details.get("name")
        if not name:
            print(f"Skipping pokemon in {file_path.name}: Name is missing.")
            continue

        p = Pokemon(
            id=details.get("id"),
            name=name,
            hit_points=details.get("stats", {}).get("hp") or 0,
            attack=details.get("stats", {}).get("attack") or 0,
            defense=details.get("stats", {}).get("defense") or 0,
            special_attack=details.get("stats", {}).get("special-attack") or 0,
            special_defense=details.get("stats", {}).get("special-defense") or 0,
            speed=details.get("stats", {}).get("speed") or 0,
            type_1=type_1,
            type_2=type_2,
            ability_1=ability_1,
            ability_2=ability_2,
            ability_hidden=ability_hidden,
            height_m=details.get("height_m") or 0.0,
            weight_kg=details.get("weight_kg") or 0.0,
            base_experience=details.get("base_experience") or 0,
            base_happiness=details.get("base_happiness") or 0,
            capture_rate=details.get("capture_rate") or 0,
            hatch_counter=details.get("hatch_counter") or 0,
            is_legendary=details.get("is_legendary") or False,
            is_mythical=details.get("is_mythical") or False,
            generation=generation,
            weak_against_1=weak_1,
            weak_against_2=weak_2,
            strong_against_1=strong_1,
            strong_against_2=strong_2,
            is_default=is_default,
            species_name=species_name,
            evolution_chain=evolution_chain,
        )
        session.add(p)
        count += 1

    print(f"Added {count} Pokemon.")


def process_moves(session: Session) -> None:
    """
    Parses Move JSON files and adds them to the database.
    Handles nested 'move_details' structure and generation mapping.
    """
    print("Processing Moves...")
    move_dir = DATA_RAW_DIR / "move"
    count = 0

    gen_map = {
        "generation-i": 1,
        "generation-ii": 2,
        "generation-iii": 3,
        "generation-iv": 4,
        "generation-v": 5,
        "generation-vi": 6,
        "generation-vii": 7,
        "generation-viii": 8,
        "generation-ix": 9,
    }

    for file_path in move_dir.glob("*.json"):
        data = load_json(file_path)
        # Handle potential nesting variations
        details = data.get("move_details", {})
        if not details:
            details = data

        m_id = details.get("id")
        name = details.get("name")
        if not name:
            continue

        # Helper to extract 'name' from dict-like fields if present
        type_data = details.get("type", {})
        type_name = (
            type_data.get("name", "unknown")
            if isinstance(type_data, dict)
            else str(type_data)
            if type_data
            else "unknown"
        )

        gen_data = details.get("generation", {})
        gen_str = (
            gen_data.get("name", "")
            if isinstance(gen_data, dict)
            else str(gen_data)
            if gen_data
            else ""
        )
        generation = gen_map.get(str(gen_str), 0)

        damage_class_data = details.get("damage_class", {})
        damage_class = (
            damage_class_data.get("name", "status")
            if isinstance(damage_class_data, dict)
            else str(damage_class_data)
            if damage_class_data
            else "status"
        )

        m = Move(
            id=m_id,
            name=name,
            type=type_name,
            power=details.get("power"),
            accuracy=details.get("accuracy"),
            power_points=details.get("pp"),
            damage_class=damage_class,
            priority=details.get("priority", 0),
            generation=generation,
        )
        session.add(m)
        count += 1
    print(f"Added {count} Moves.")


def process_items(session: Session) -> None:
    """
    Parses Item JSON files and adds them to the database.
    Extracts effect descriptions (in English) and categories.
    """
    print("Processing Items...")
    item_dir = DATA_RAW_DIR / "item"
    count = 0

    for file_path in item_dir.glob("*.json"):
        data = load_json(file_path)
        details = data.get("item_details", {})
        if not details:
            details = data

        name = details.get("name")
        if not name:
            # Skip items without names to ensure integrity
            # print(f"Skipping item in {file_path.name}: Name is missing.")
            continue

        # Extract English effect description
        effect = ""
        entries = details.get("effect_entries", [])
        for e in entries:
            if e.get("language", {}).get("name") == "en":
                effect = e.get("short_effect", "") or e.get("effect", "")
                break

        category_data = details.get("category", "unknown")
        category = "unknown"
        if isinstance(category_data, dict):
            category = category_data.get("name", "unknown")
        elif category_data:
            category = str(category_data)

        i = Item(
            id=details.get("id"),
            name=name,
            cost=details.get("cost", 0),
            category=category,
            generation=0,  # Generation info is often missing or inconsistent in item data
            effect=effect,
        )
        session.add(i)
        count += 1
    print(f"Added {count} Items.")


with Session(engine) as session:
    process_pokemons(session)
    session.commit()
    print("Committed Pokemons.")

    process_moves(session)
    session.commit()
    print("Committed Moves.")

    process_items(session)
    session.commit()
    print("Committed Items.")

    print("Database populated successfully.")
