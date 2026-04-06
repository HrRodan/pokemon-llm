"""
Integration tests — real LLM API calls, no mocking.

Requirements:
  - A valid API key in .env (OPENROUTER_API_KEY or equivalent)
  - The SQLite tech DB at data/tech_db/tech.db (run scripts/create_tech_db.py)
  - The ChromaDB vector store at data/vector_db/ (run scripts/ingest.py)

Run:
    uv run python -m pytest tests/integration/test_agent_llm.py -v

These tests are intentionally NOT part of the default `tests/unit/` suite
because they require a live network connection and a billable API key.

Design principles:
  - We test that the agent returns a **non-empty, coherent string** for a
    well-defined question — not the exact wording (LLMs are non-deterministic).
  - Each test uses a query with a known, narrow answer so we can assert that
    a key term appears in the response (case-insensitive).
  - Lazy singletons are reset before each test class so agents are fresh.
"""

import agents.api_agent as api_mod
import agents.rag_agent as rag_mod
import agents.tech_data_agent as tda_mod


# ---------------------------------------------------------------------------
# TechDataAgent — SQL queries via LLM
# ---------------------------------------------------------------------------


class TestTechDataAgentIntegration:
    """Live SQL-agent tests: the agent must translate a natural language question
    into a structured query and synthesise the result."""

    def test_known_pokemon_hp(self):
        """Bulbasaur's base HP is 45 — TechDataAgent should confirm this."""
        response = tda_mod.TechDataAgent().run(
            "What is Bulbasaur's base hit points (HP)?"
        )
        assert isinstance(response, str)
        assert len(response) > 0, "Expected a non-empty response"
        assert "45" in response, f"Expected HP '45' in response, got: {response[:300]}"

    def test_fire_type_top_attack(self):
        """Top-attack fire Pokémon query: response should contain Pokémon names."""
        response = tda_mod.TechDataAgent().run(
            "Which 5 fire-type Pokémon have the highest attack stat?"
        )
        assert isinstance(response, str)
        assert len(response) > 20
        # The response should mention at least one well-known fire type
        lower = response.lower()
        found = any(
            name in lower
            for name in ["charizard", "arcanine", "infernape", "darmanitan", "blaziken"]
        )
        assert found, f"Expected a known fire Pokémon name in: {response[:400]}"

    def test_average_aggregation(self):
        """Aggregation query: average speed must be a numeric value."""
        response = tda_mod.TechDataAgent().run(
            "What is the average speed of all water-type Pokémon?"
        )
        assert isinstance(response, str)
        assert len(response) > 0
        # Should contain a number
        import re

        assert re.search(r"\d+\.?\d*", response), (
            f"Expected a number in response: {response[:300]}"
        )

    def test_no_results_handled_gracefully(self):
        """A question about a non-existent Pokémon should return a meaningful answer,
        not raise an exception."""
        response = tda_mod.TechDataAgent().run("What are the stats of Fakemon9999?")
        assert isinstance(response, str)
        assert len(response) > 0


# ---------------------------------------------------------------------------
# RAGAgent — vector DB semantic search
# ---------------------------------------------------------------------------


class TestRAGAgentIntegration:
    """Live RAG-agent tests: the agent must query the vector DB and return
    lore/description content."""

    def test_bulbasaur_biology(self):
        """The RAG store contains Bulbasaur's biology — the response must mention it."""
        response = rag_mod.RAGAgent().run("Tell me about the biology of Bulbasaur.")
        assert isinstance(response, str)
        assert len(response) > 20
        assert "bulbasaur" in response.lower(), (
            f"Expected 'bulbasaur' in: {response[:400]}"
        )

    def test_semantic_dog_pokemon(self):
        """Semantic query for dog-like Pokémon — should return at least one."""
        response = rag_mod.RAGAgent().run("Pokémon that look like dogs")
        assert isinstance(response, str)
        assert len(response) > 20
        lower = response.lower()
        found = any(
            name in lower
            for name in [
                "growlithe",
                "arcanine",
                "houndour",
                "houndoom",
                "rockruff",
                "lycanroc",
                "furfrou",
                "dachsbun",
                "poochyena",
                "yamper",
                "herdier",
                "watchog",
            ]
        )
        assert found, f"Expected a dog-like Pokémon in: {response[:400]}"

    def test_mewtwo_lore(self):
        """Mewtwo lore query — response must mention 'mewtwo'."""
        response = rag_mod.RAGAgent().run("What is the lore behind Mewtwo?")
        assert isinstance(response, str)
        assert len(response) > 20
        assert "mewtwo" in response.lower(), f"Expected 'mewtwo' in: {response[:400]}"


# ---------------------------------------------------------------------------
# APIAgent — live PokéAPI lookups
# ---------------------------------------------------------------------------


class TestAPIAgentIntegration:
    """Live API-agent tests: the agent must call PokéAPI tools and synthesise results."""

    def test_charizard_type(self):
        """Charizard is Fire/Flying — the response must confirm at least one type."""
        response = api_mod.APIAgent().run("What is Charizard's type?")
        assert isinstance(response, str)
        assert len(response) > 0
        lower = response.lower()
        assert "fire" in lower or "flying" in lower, (
            f"Expected fire or flying type in: {response[:400]}"
        )

    def test_pikachu_base_stats(self):
        """Pikachu has speed 90 — response should contain a relevant stat."""
        response = api_mod.APIAgent().run("What are Pikachu's base stats?")
        assert isinstance(response, str)
        assert len(response) > 0
        lower = response.lower()
        # Should mention common stat names
        assert any(stat in lower for stat in ["attack", "defense", "speed", "hp"]), (
            f"Expected stat names in: {response[:400]}"
        )

    def test_potion_cost(self):
        """A Potion costs 200 — the response must mention the cost."""
        response = api_mod.APIAgent().run("How much does a Potion cost?")
        assert isinstance(response, str)
        assert len(response) > 0
        assert "200" in response, f"Expected cost '200' in: {response[:400]}"

    def test_unknown_pokemon_error_handling(self):
        """Querying an invalid Pokémon should not raise — agent should report the error."""
        response = api_mod.APIAgent().run("What are the stats of Fakemon9999?")
        assert isinstance(response, str)
        assert len(response) > 0
