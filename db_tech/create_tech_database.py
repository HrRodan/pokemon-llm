import sqlite3
import json
import os
import glob
from typing import Optional

DB_PATH = "db_tech/tech.db"
DATA_DIR = "data/raw"


def get_generation_int(gen_str: Optional[str]) -> Optional[int]:
    """
    Parses 'generation-iii' string relative to integer.

    Args:
        gen_str: Generation string (e.g., 'generation-iii').

    Returns:
        Integer generation format or None.
    """
    if not gen_str:
        return None

    parts = gen_str.split("-")
    if len(parts) != 2:
        return None

    roman = parts[1].upper()
    mapping = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
        "V": 5,
        "VI": 6,
        "VII": 7,
        "VIII": 8,
        "IX": 9,
        "X": 10,
    }
    return mapping.get(roman, None)


def create_tables(cursor: sqlite3.Cursor) -> None:
    """
    Creates SQLite tables for pokemons, moves, and items if they do not exist.

    Args:
        cursor: SQLite database cursor.
    """
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pokemons (
        id INTEGER PRIMARY KEY,
        name TEXT,
        hit_points INTEGER,
        attack INTEGER,
        defense INTEGER,
        special_attack INTEGER,
        special_defense INTEGER,
        speed INTEGER,
        type_1 TEXT,
        type_2 TEXT,
        ability_1 TEXT,
        ability_2 TEXT,
        ability_hidden TEXT,
        height_m REAL,
        weight_kg REAL,
        base_experience INTEGER,
        base_happiness INTEGER,
        capture_rate INTEGER,
        hatch_counter INTEGER,
        is_legendary BOOLEAN,
        is_mythical BOOLEAN,
        generation INTEGER,
        weak_against_1 TEXT,
        weak_against_2 TEXT,
        strong_against_1 TEXT,
        strong_against_2 TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS moves (
        id INTEGER PRIMARY KEY,
        name TEXT,
        type TEXT,
        power INTEGER,
        accuracy INTEGER,
        power_points INTEGER,
        damage_class TEXT,
        priority INTEGER,
        generation INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        name TEXT,
        cost INTEGER,
        category TEXT,
        generation INTEGER,
        effect TEXT
    )
    """)


def process_pokemons(conn: sqlite3.Connection) -> None:
    """
    Reads Pokemon JSON data and populates the pokemons table.

    Args:
        conn: SQLite database connection.
    """
    print("Processing Pokemons...")
    cursor = conn.cursor()
    files = glob.glob(os.path.join(DATA_DIR, "pokemon", "*.json"))

    records = []
    for f_path in files:
        with open(f_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            details = data.get("pokemon_details", {})

            # Ability extraction
            abilities = details.get("abilities", [])
            ability_1 = None
            ability_2 = None
            ability_hidden = None

            normal_abilities = [a for a in abilities if not a.get("is_hidden")]
            hidden_abilities = [a for a in abilities if a.get("is_hidden")]

            if len(normal_abilities) > 0:
                ability_1 = normal_abilities[0].get("name")
            if len(normal_abilities) > 1:
                ability_2 = normal_abilities[1].get("name")
            if len(hidden_abilities) > 0:
                ability_hidden = hidden_abilities[0].get("name")

            # Type extraction
            types = details.get("types", [])
            type_1 = types[0] if len(types) > 0 else None
            type_2 = types[1] if len(types) > 1 else None

            # Weakness and Strength extraction
            type_info = data.get("type_info", [])
            weak_against_1 = None
            weak_against_2 = None
            strong_against_1 = None
            strong_against_2 = None

            if len(type_info) > 0:
                weak_against_1 = ",".join(type_info[0].get("weak_against", []))
                strong_against_1 = ",".join(type_info[0].get("strong_against", []))

            if len(type_info) > 1:
                weak_against_2 = ",".join(type_info[1].get("weak_against", []))
                strong_against_2 = ",".join(type_info[1].get("strong_against", []))

            # Stats
            stats = details.get("stats", {})

            # Generation
            gen_str = details.get("generation")
            generation = get_generation_int(gen_str)

            record = (
                details.get("id"),
                details.get("name"),
                stats.get("hp"),
                stats.get("attack"),
                stats.get("defense"),
                stats.get("special-attack"),
                stats.get("special-defense"),
                stats.get("speed"),
                type_1,
                type_2,
                ability_1,
                ability_2,
                ability_hidden,
                details.get("height_m"),
                details.get("weight_kg"),
                details.get("base_experience"),
                details.get("base_happiness"),
                details.get("capture_rate"),
                details.get("hatch_counter"),
                details.get("is_legendary"),
                details.get("is_mythical"),
                generation,
                weak_against_1,
                weak_against_2,
                strong_against_1,
                strong_against_2,
            )
            records.append(record)

    cursor.executemany(
        """
        INSERT OR REPLACE INTO pokemons VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """,
        records,
    )
    conn.commit()
    print(f"Inserted {len(records)} pokemons.")


def process_moves(conn: sqlite3.Connection) -> None:
    """
    Reads Move JSON data and populates the moves table.

    Args:
        conn: SQLite database connection.
    """
    print("Processing Moves...")
    cursor = conn.cursor()
    files = glob.glob(os.path.join(DATA_DIR, "move", "*.json"))

    records = []
    for f_path in files:
        with open(f_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            details = data.get("move_details", {})

            gen_str = details.get("generation")
            generation = get_generation_int(gen_str)

            record = (
                details.get("id"),
                details.get("name"),
                details.get("type"),
                details.get("power"),
                details.get("accuracy"),
                details.get("pp"),
                details.get("damage_class"),
                details.get("priority"),
                generation,
            )
            records.append(record)

    cursor.executemany(
        """
        INSERT OR REPLACE INTO moves VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """,
        records,
    )
    conn.commit()
    print(f"Inserted {len(records)} moves.")


def process_items(conn: sqlite3.Connection) -> None:
    """
    Reads Item JSON data and populates the items table.

    Args:
        conn: SQLite database connection.
    """
    print("Processing Items...")
    cursor = conn.cursor()
    files = glob.glob(os.path.join(DATA_DIR, "item", "*.json"))

    records = []
    for f_path in files:
        with open(f_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            details = data.get("item_details", {})

            gen_str = details.get("generation")
            generation = get_generation_int(gen_str)

            # Extract short effect
            effect = None
            effect_entries = details.get("effect_entries", [])
            for entry in effect_entries:
                if entry.get("language", {}).get("name") == "en":
                    effect = entry.get("short_effect")
                    # Fallback to full effect if short is missing
                    if not effect:
                        effect = entry.get("effect")
                    break

            record = (
                details.get("id"),
                details.get("name"),
                details.get("cost"),
                details.get("category"),
                generation,
                effect,
            )
            records.append(record)

    cursor.executemany(
        """
        INSERT OR REPLACE INTO items VALUES (
            ?, ?, ?, ?, ?, ?
        )
    """,
        records,
    )
    conn.commit()
    print(f"Inserted {len(records)} items.")


def main() -> None:
    """
    Main function to initialize database and process all data.
    """
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    try:
        create_tables(conn.cursor())

        process_pokemons(conn)
        process_moves(conn)
        process_items(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
