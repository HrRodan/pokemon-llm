import json
from pathlib import Path
from typing import Literal, List

from pydantic import BaseModel, Field
from rapidfuzz import process, fuzz

from ai_tools.tool_definition import tool

DATA_DIR = Path("data")


def _load_json_list(filename: str) -> List[str]:
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# Caches
_pokemon_list: List[str] = []
_moves_list: List[str] = []
_items_list: List[str] = []


def _get_list(query_type: str) -> List[str]:
    global _pokemon_list, _moves_list, _items_list
    if query_type == "pokemon":
        if not _pokemon_list:
            _pokemon_list = _load_json_list("pokemon_list.json")
        return _pokemon_list
    elif query_type == "move":
        if not _moves_list:
            _moves_list = _load_json_list("moves_list.json")
        return _moves_list
    elif query_type == "item":
        if not _items_list:
            _items_list = _load_json_list("items_list.json")
        return _items_list
    return []


class FuzzySearchQuery(BaseModel):
    query: str = Field(
        description="The partial name, misspelling, or base name to search for (e.g., 'pumpkaboo', 'charizad'). Use this tool if you are unsure about the exact spelling in the Pokemon API."
    )
    query_type: Literal["pokemon", "move", "item"] = Field(
        description="The category to search within."
    )


@tool(schema=FuzzySearchQuery)
def search_exact_name(request: FuzzySearchQuery) -> str:
    """
    Finds the exact name available in the database (API) by applying fuzzy matching
    to a partial name, misspelling, or base name. Returns the top possible matches.
    Useful for discovering exact spellings or required suffixes (e.g., for forms).
    """
    query = request.query
    query_type = request.query_type

    target_list = _get_list(query_type)
    if not target_list:
        return f"Error: Could not load the data list for {query_type}."

    # WRatio is excellent for a mix of typos, partial substrings, and different word orders.
    results = process.extract(
        query.lower(), target_list, scorer=fuzz.WRatio, limit=10, score_cutoff=50.0
    )

    if not results:
        return f"No matches found for '{query}' in {query_type}."

    formatted_results = [
        f"- {match} (Score: {score:.1f})" for match, score, _ in results
    ]

    return (
        f"Top matches for '{query}' in {query_type} (use the exact name from this list):\n"
        + "\n".join(formatted_results)
    )


TOOL_FUNCTIONS = [search_exact_name]
