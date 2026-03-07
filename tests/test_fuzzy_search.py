import pytest
from tools.fuzzy_search import search_exact_name, FuzzySearchQuery


def test_search_exact_name_pokemon_suffix():
    result = search_exact_name(
        FuzzySearchQuery(query="pumpkaboo", query_type="pokemon")
    )
    # Asserting that rapidfuzz accurately ranked these at the top and included them
    assert "pumpkaboo-small" in result
    assert "pumpkaboo-average" in result
    assert "pumpkaboo-large" in result
    assert "pumpkaboo-super" in result


def test_search_exact_name_pokemon_typo():
    result = search_exact_name(FuzzySearchQuery(query="charizad", query_type="pokemon"))
    assert "charizard" in result


def test_search_exact_name_move_fuzzy():
    result = search_exact_name(FuzzySearchQuery(query="thundr", query_type="move"))
    assert "thunder" in result


def test_search_exact_name_item_fuzzy():
    result = search_exact_name(FuzzySearchQuery(query="masterbal", query_type="item"))
    assert "master-ball" in result
