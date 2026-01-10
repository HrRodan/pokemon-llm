"""
Unified PokéAPI v2 client with local caching and specific data retrieval functions.
Merged from pokemon_api_client.py and pokemon_api_functions.py.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import random

import requests


class PokemonAPIClient:
    """
    Generic client for PokéAPI v2 with built-in local caching and specific helper methods.

    Fair Use Policy:
    - Use local caching to avoid unnecessary requests.
    - Do not spam the API with high-frequency polling.
    - Handle errors gracefully.
    """

    BASE_URL = "https://pokeapi.co/api/v2"

    # Resource endpoints that support ID/name lookup
    NAMED_RESOURCES = {
        "ability",
        "berry",
        "berry-firmness",
        "berry-flavor",
        "characteristic",
        "contest-effect",
        "contest-type",
        "egg-group",
        "encounter-condition",
        "encounter-condition-value",
        "encounter-method",
        "evolution-chain",
        "evolution-trigger",
        "gender",
        "generation",
        "growth-rate",
        "item",
        "item-attribute",
        "item-category",
        "item-fusing",
        "item-pocket",
        "language",
        "location",
        "location-area",
        "machine",
        "move",
        "move-ailment",
        "move-battle-style",
        "move-category",
        "move-damage-class",
        "move-learn-method",
        "move-target",
        "nature",
        "pal-park-area",
        "pokeathlon-stat",
        "pokedex",
        "pokemon",
        "pokemon-color",
        "pokemon-form",
        "pokemon-habitat",
        "pokemon-shape",
        "pokemon-species",
        "region",
        "stat",
        "super-contest-effect",
        "type",
        "version",
        "version-group",
        "evolution-trigger",
        "item-category",
        "item-attribute",
    }

    # Static mapping for Generation info to avoid extra API calls
    GENERATION_DATA = {
        "generation-i": {"name": "Generation I", "region": "Kanto"},
        "generation-ii": {"name": "Generation II", "region": "Johto"},
        "generation-iii": {"name": "Generation III", "region": "Hoenn"},
        "generation-iv": {"name": "Generation IV", "region": "Sinnoh"},
        "generation-v": {"name": "Generation V", "region": "Unova"},
        "generation-vi": {"name": "Generation VI", "region": "Kalos"},
        "generation-vii": {"name": "Generation VII", "region": "Alola"},
        "generation-viii": {"name": "Generation VIII", "region": "Galar"},
        "generation-ix": {"name": "Generation IX", "region": "Paldea"},
    }

    def __init__(
        self,
        cache_dir: Optional[Union[str, Path]] = None,
        enable_cache: bool = True,
    ):
        self.enable_cache = enable_cache

        # Determine project root (parent of 'pokemon_tools' folder)
        project_root = Path(__file__).resolve().parent.parent

        if cache_dir is None:
            self.cache_dir = project_root / ".pokemon_cache"
        else:
            self.cache_dir = Path(cache_dir)

        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache expires after 24 hours by default
        self.cache_ttl = 160000

    def _get_url(self, endpoint: str, identifier: Union[str, int, None] = None) -> str:
        url = f"{self.BASE_URL}/{endpoint}"
        if identifier is not None:
            url = f"{url}/{identifier}"
        return url

    def _get_cache_path(self, endpoint: str, identifier: Union[str, int, None]) -> Path:
        if identifier is not None:
            safe_id = str(identifier).replace(" ", "_").lower()
            filename = f"{endpoint}_{safe_id}.json"
        else:
            filename = f"{endpoint}_list.json"
        return self.cache_dir / filename

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        if self.cache_ttl == 0:
            return True
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return (datetime.now() - mtime).total_seconds() < self.cache_ttl

    def _load_from_cache(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            if self._is_cache_valid(path):
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return None
        return None

    def _save_to_cache(self, path: Path, data: Dict[str, Any]) -> None:
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            # Cache write failure should not break main logic
            pass

    def _get(
        self, endpoint: str, identifier: Union[str, int, None] = None
    ) -> Dict[str, Any]:
        """
        Generic GET request with caching.
        """

        cache_path = None
        if self.enable_cache:
            cache_path = self._get_cache_path(endpoint, identifier)
            cached_data = self._load_from_cache(cache_path)
            if cached_data:
                return cached_data

        url = self._get_url(endpoint, identifier)
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if self.enable_cache and cache_path:
            self._save_to_cache(cache_path, data)
        return data

    def _clean_text(self, text: str) -> str:
        """Removes newlines and form feeds from text."""
        return text.replace("\n", " ").replace("\f", " ")

    def _get_generation_info(self, gen_name: Optional[str]) -> Dict[str, str]:
        """Helper to get sensible generation info from the static mapping."""
        if not gen_name:
            return {"name": "Unknown", "region": "Unknown"}
        return self.GENERATION_DATA.get(
            gen_name, {"name": gen_name, "region": "Unknown"}
        )

    def get_pokemon_details(self, name: str) -> Dict[str, Any]:
        """
        Retrieves technical data for a Pokemon.
        """
        try:
            data = self._get("pokemon", name.lower())

            stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
            types = [t["type"]["name"] for t in data["types"]]
            # Convert decimetres to meters
            height_m = data["height"] / 10
            # Convert hectograms to kg
            weight_kg = data["weight"] / 10

            # Expanded abilities with is_hidden flag
            abilities = [
                {
                    "name": a["ability"]["name"],
                    "is_hidden": a["is_hidden"],
                    "slot": a["slot"],
                }
                for a in data["abilities"]
            ]

            # Moves
            moves = [m["move"]["name"] for m in data["moves"]]

            # Forms
            forms = [f["name"] for f in data["forms"]]

            # Held items
            held_items = [h["item"]["name"] for h in data.get("held_items", [])]

            # Get Species Info
            species_data = {}
            evolution_chain_data = {}
            if "species" in data and "url" in data["species"]:
                species_name = data["species"]["name"]
                try:
                    sp_data = self._get("pokemon-species", species_name)

                    # Extract flavor text (English)
                    flavor_text = "No description available."
                    for entry in sp_data.get("flavor_text_entries", []):
                        if entry["language"]["name"] == "en":
                            flavor_text = self._clean_text(entry["flavor_text"])
                            break

                    # Extract Genus
                    genus = "Unknown"
                    for g in sp_data.get("genera", []):
                        if g["language"]["name"] == "en":
                            genus = g["genus"]
                            break

                    # Simple attributes
                    species_data = {
                        "species_name": sp_data["name"],
                        "flavor_text": flavor_text,
                        "genus": genus,
                        "is_legendary": sp_data.get("is_legendary", False),
                        "is_mythical": sp_data.get("is_mythical", False),
                        "is_baby": sp_data.get("is_baby", False),
                        "capture_rate": sp_data.get("capture_rate"),
                        "base_happiness": sp_data.get("base_happiness"),
                        "hatch_counter": sp_data.get("hatch_counter"),
                        "growth_rate": sp_data.get("growth_rate", {}).get("name"),
                        "habitat": sp_data.get("habitat", {}).get("name")
                        if sp_data.get("habitat")
                        else None,
                        "shape": sp_data.get("shape", {}).get("name")
                        if sp_data.get("shape")
                        else None,
                        "color": sp_data.get("color", {}).get("name")
                        if sp_data.get("color")
                        else None,
                        "egg_groups": [
                            egg["name"] for egg in sp_data.get("egg_groups", [])
                        ],
                        "evolution_chain_url": sp_data.get("evolution_chain", {}).get(
                            "url"
                        ),
                        "generation": sp_data.get("generation", {}).get("name"),
                        "generation_info": self._get_generation_info(
                            sp_data.get("generation", {}).get("name")
                        ),
                    }

                    evo_url = sp_data.get("evolution_chain", {}).get("url")
                    if evo_url:
                        try:
                            # Extract ID from URL: .../evolution-chain/1/
                            chain_id = int(evo_url.strip("/").split("/")[-1])
                            evolution_chain_data = self.get_evolution_chain(chain_id)
                        except Exception:
                            evolution_chain_data = {
                                "error": "Could not retrieve evolution chain"
                            }
                except Exception:
                    # If species fetch fails, we just don't have that extra info
                    species_data = {
                        "error_species": "Could not retrieve species details"
                    }

            result = {
                "id": data["id"],
                "name": data["name"],
                "stats": stats,
                "types": types,
                "height_m": height_m,
                "weight_kg": weight_kg,
                "abilities": abilities,
                "forms": forms,
                "moves": moves,
                "held_items": held_items,
                "base_experience": data.get("base_experience"),
                "is_default": data.get("is_default"),
                "order": data.get("order"),
                "sprites": {
                    "front_default": data["sprites"].get("front_default"),
                    "back_default": data["sprites"].get("back_default"),
                    "front_shiny": data["sprites"].get("front_shiny"),
                },
            }
            # Merge species data
            result.update(species_data)
            if evolution_chain_data:
                result["evolution"] = evolution_chain_data
            return result

        except requests.exceptions.RequestException:
            return {"error": f"Pokemon '{name}' not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_species_info(self, name: str) -> Dict[str, Any]:
        """
        Retrieves background information (species).
        """
        try:
            data = self._get("pokemon-species", name.lower())

            # Find English flavor text
            flavor_text = "No description available."
            for entry in data["flavor_text_entries"]:
                if entry["language"]["name"] == "en":
                    flavor_text = self._clean_text(entry["flavor_text"])
                    break

            is_legendary = data["is_legendary"] or data["is_mythical"]

            genus = "Unknown"
            for g in data.get("genera", []):
                if g["language"]["name"] == "en":
                    genus = g["genus"]
                    break

            return {
                "name": data["name"],
                "flavor_text": flavor_text,
                "is_legendary": is_legendary,
                "capture_rate": data["capture_rate"],
                "evolution_chain_url": data["evolution_chain"]["url"],
                "genus": genus,
                "generation": data.get("generation", {}).get("name"),
                "generation_info": self._get_generation_info(
                    data.get("generation", {}).get("name")
                ),
            }
        except requests.exceptions.RequestException:
            return {"error": "Species info not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_evolution_chain(self, chain_id: int) -> Dict[str, Any]:
        """
        Retrieves the evolution chain.
        """
        try:
            data = self._get("evolution-chain", chain_id)

            # Recursively parse the chain
            def parse_evolution(node):
                species_name = node["species"]["name"]
                evo_details = []

                # Check evolution details for this node (how it evolved from previous)
                for detail in node.get("evolution_details", []):
                    # Extract only relevant non-null/false triggers
                    conditions = {}
                    if detail.get("trigger"):
                        conditions["trigger"] = detail["trigger"]["name"]
                    if detail.get("item"):
                        conditions["item"] = detail["item"]["name"]
                    if detail.get("min_level"):
                        conditions["min_level"] = detail["min_level"]
                    if detail.get("min_happiness"):
                        conditions["min_happiness"] = detail["min_happiness"]
                    if detail.get("time_of_day"):
                        conditions["time_of_day"] = detail["time_of_day"]
                    if detail.get("held_item"):
                        conditions["held_item"] = detail["held_item"]["name"]
                    if detail.get("known_move"):
                        conditions["known_move"] = detail["known_move"]["name"]
                    if detail.get("known_move_type"):
                        conditions["known_move_type"] = detail["known_move_type"][
                            "name"
                        ]
                    if detail.get("location"):
                        conditions["location"] = detail["location"]["name"]
                    evo_details.append(conditions)

                result = {
                    "species_name": species_name,
                    "evolution_details": evo_details,
                }

                if node.get("evolves_to"):
                    result["evolves_to"] = [
                        parse_evolution(sub_node) for sub_node in node["evolves_to"]
                    ]
                else:
                    result["evolves_to"] = []

                return result

            chain_data = parse_evolution(data["chain"])

            return {"chain_id": data["id"], "chain": chain_data}
        except requests.exceptions.RequestException:
            return {"error": "Evolution chain not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_move_details(self, name: str, learned_by_limit: int = 20) -> Dict[str, Any]:
        """
        Retrieves details about a move.
        """
        try:
            data = self._get("move", name.lower())

            effect = "No description."
            effect_chance = data.get("effect_chance")
            if data["effect_entries"]:
                # Try to find English effect
                for entry in data["effect_entries"]:
                    if entry["language"]["name"] == "en":
                        effect = entry["effect"]
                        # Replace $effect_chance variable in text if present
                        if effect_chance is not None:
                            effect = effect.replace(
                                "$effect_chance", str(effect_chance)
                            )
                        break

            # Flavor Text
            flavor_text = "No description available."
            if data.get("flavor_text_entries"):
                for entry in data["flavor_text_entries"]:
                    if entry["language"]["name"] == "en":
                        flavor_text = self._clean_text(entry["flavor_text"])
                        # We just take the first English one we find
                        break

            # Learned By (with sampling)
            all_learned_by = [p["name"] for p in data.get("learned_by_pokemon", [])]
            total_learned_by = len(all_learned_by)

            if learned_by_limit == -1:
                learned_by = all_learned_by
            else:
                # Sample random candidates if limit is set
                limit = min(learned_by_limit, total_learned_by)
                if limit > 0:
                    learned_by = random.sample(all_learned_by, limit)
                else:
                    learned_by = []

            # Machines (TMs)
            machines = []
            if data.get("machines"):
                machines = [
                    m["version_group"]["name"] for m in data.get("machines", [])
                ]

            # Contest Combos
            contest_combos = data.get("contest_combos")

            return {
                "id": data["id"],
                "name": data["name"],
                "type": data["type"]["name"],
                "power": data["power"],
                "accuracy": data["accuracy"],
                "pp": data["pp"],
                "damage_class": data["damage_class"]["name"],
                "effect_description": self._clean_text(effect),
                "effect_chance": effect_chance,
                "flavor_text": flavor_text,
                "learned_by": learned_by,
                "total_learned_by": total_learned_by,
                "machines": machines,
                "contest_combos": contest_combos,
                "priority": data.get("priority"),
                "target": data.get("target", {}).get("name"),
                "generation": data.get("generation", {}).get("name"),
                "generation_info": self._get_generation_info(
                    data.get("generation", {}).get("name")
                ),
            }
        except requests.exceptions.HTTPError as e:
            return {
                "error": f"HTTP Error {e.response.status_code} for Move {name}: {e}"
            }
        except requests.exceptions.RequestException as e:
            return {"error": f"Request Error for Move {name}: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def get_type_info(self, name: str) -> Dict[str, Any]:
        """
        Retrieves strengths and weaknesses of a type.
        """
        try:
            data = self._get("type", name.lower())

            damage = data["damage_relations"]
            return {
                "name": data["name"],
                "weak_against": [x["name"] for x in damage["double_damage_from"]],
                "strong_against": [x["name"] for x in damage["double_damage_to"]],
                "immune_to": [x["name"] for x in damage["no_damage_from"]],
            }
        except requests.exceptions.RequestException:
            return {"error": "Type not found"}
        except Exception as e:
            return {"error": str(e)}

    def get_encounters(self, name: str) -> Dict[str, Any]:
        """
        Finds locations where a Pokemon can be caught in the game.
        """
        try:
            safe_name = name.lower().replace(" ", "_")
            cache_path = None
            if self.enable_cache:
                cache_path = self.cache_dir / f"encounters_{safe_name}.json"
                cached_data = self._load_from_cache(cache_path)
                if cached_data:
                    return cached_data

            url = f"{self.BASE_URL}/pokemon/{name.lower()}/encounters"
            response = requests.get(url)

            if response.status_code != 200:
                return {"error": "Locations could not be retrieved."}

            data = response.json()

            # Cache the raw list
            if self.enable_cache and cache_path:
                self._save_to_cache(cache_path, data)

            # Process data
            if not data:
                return {
                    "locations": [],
                    "message": "This Pokemon cannot be found in the wild (or is only available through evolution/trade).",
                }

            locations = [
                loc["location_area"]["name"].replace("-", " ") for loc in data[:5]
            ]

            return {
                "pokemon": name,
                "locations": locations,
                "total_locations_found": len(data),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_nature_info(self, name: str) -> Dict[str, Any]:
        """
        Explains a 'Nature'.
        """
        try:
            data = self._get("nature", name.lower())

            return {
                "name": data["name"],
                "increased_stat": data["increased_stat"]["name"]
                if data["increased_stat"]
                else "None",
                "decreased_stat": data["decreased_stat"]["name"]
                if data["decreased_stat"]
                else "None",
                "flavor_profile": data["likes_flavor"]["name"]
                if data["likes_flavor"]
                else "None",
            }
        except requests.exceptions.RequestException:
            return {"error": "Nature not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_pokemon_list_by_type(
        self, type_name: str, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Lists Pokemon of a specific type.
        """
        try:
            data = self._get("type", type_name.lower())

            pokemon_list = [p["pokemon"]["name"] for p in data["pokemon"]]

            selected_pokemon = random.sample(
                pokemon_list, min(len(pokemon_list), limit)
            )

            return {
                "type": type_name,
                "pokemon_examples": selected_pokemon,
                "total_count": len(pokemon_list),
            }
        except requests.exceptions.RequestException:
            return {"error": "Type not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_ability_details(self, name: str) -> Dict[str, Any]:
        """
        Detailed infos about an Ability.
        """
        try:
            clean_name = name.lower().replace(" ", "-")
            data = self._get("ability", clean_name)

            effect = "No description available."
            for entry in data["effect_entries"]:
                if entry["language"]["name"] == "en":
                    effect = entry["effect"]
                    break

            pokemon_candidates = [p["pokemon"]["name"] for p in data["pokemon"][:5]]

            return {
                "name": data["name"],
                "effect": self._clean_text(effect),
                "pokemon_candidates": pokemon_candidates,
                "generation": data.get("generation", {}).get("name"),
                "generation_info": self._get_generation_info(
                    data.get("generation", {}).get("name")
                ),
            }
        except requests.exceptions.RequestException:
            return {"error": "Ability not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_item_info(self, name: str, held_by_limit: int = 20) -> Dict[str, Any]:
        """
        Retrieves info about an Item.
        """
        try:
            clean_name = name.lower().replace(" ", "-")
            data = self._get("item", clean_name)

            # Effect Entries
            effect_entries = []
            if data.get("effect_entries"):
                for entry in data["effect_entries"]:
                    if entry["language"]["name"] == "en":
                        effect_entries.append(entry)
                        break

            # Flavor Text (Longest English entry)
            flavor_text_entries = []
            if data.get("flavor_text_entries"):
                english_entries = [
                    entry
                    for entry in data["flavor_text_entries"]
                    if entry["language"]["name"] == "en"
                ]
                if english_entries:
                    longest_entry = max(english_entries, key=lambda x: len(x["text"]))
                    longest_entry["text"] = self._clean_text(longest_entry["text"])
                    flavor_text_entries.append(longest_entry)

            # Held By Pokemon
            held_by_pokemon = []
            total_held_by = 0
            if data.get("held_by_pokemon"):
                all_held_by = [h["pokemon"]["name"] for h in data["held_by_pokemon"]]
                total_held_by = len(all_held_by)
                if held_by_limit == -1:
                    held_by_pokemon = all_held_by
                else:
                    held_by_pokemon = all_held_by[:held_by_limit]

            # Machines
            machines = []
            if data.get("machines"):
                machines = [m["version_group"]["name"] for m in data["machines"]]

            # Generation
            generation = None
            if data.get("game_indices"):
                # Sort by game index to find the earliest appearance roughly
                sorted_indices = sorted(
                    data["game_indices"], key=lambda x: x["game_index"]
                )
                if sorted_indices:
                    # The 'game_indices' list in Item objects contains generation information.
                    # We use the first index to approximate the generation.
                    first_index = sorted_indices[0]
                    if "generation" in first_index:
                        generation = first_index["generation"]["name"]

            return {
                "id": data["id"],
                "name": data["name"],
                "cost": data["cost"],
                "category": data["category"]["name"],
                "attributes": [a["name"] for a in data.get("attributes", [])],
                "effect_entries": effect_entries,
                "flavor_text_entries": flavor_text_entries,
                "held_by_pokemon": held_by_pokemon,
                "total_held_by": total_held_by,
                "machines": machines,
                "baby_trigger_for": data.get("baby_trigger_for"),
                "sling_power": data.get("fling_power"),
                "fling_effect": data.get("fling_effect", {}).get("name")
                if data.get("fling_effect")
                else None,
                "generation": generation,
                "generation_info": self._get_generation_info(generation),
            }
        except requests.exceptions.RequestException:
            return {"error": "Item not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_evolution_trigger_info(self, name: str) -> Dict[str, Any]:
        """
        Retrieves info about an evolution trigger.
        """
        try:
            data = self._get("evolution-trigger", name.lower())
            return {
                "name": data["name"],
                "pokemon_species": [s["name"] for s in data["pokemon_species"]],
            }
        except requests.exceptions.RequestException:
            return {"error": "Evolution trigger not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_item_category_info(self, name: str) -> Dict[str, Any]:
        """
        Retrieves info about an item category.
        """
        try:
            data = self._get("item-category", name.lower())
            return {
                "name": data["name"],
                "items": [i["name"] for i in data["items"]],
            }
        except requests.exceptions.RequestException:
            return {"error": "Item category not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_item_attribute_info(self, name: str) -> Dict[str, Any]:
        """
        Retrieves info about an item attribute.
        """
        try:
            data = self._get("item-attribute", name.lower())

            desc = "No description available."
            for d in data.get("descriptions", []):
                if d["language"]["name"] == "en":
                    desc = d["description"]
                    break

            return {
                "name": data["name"],
                "description": self._clean_text(desc),
                "items": [i["name"] for i in data["items"]],
            }
        except requests.exceptions.RequestException:
            return {"error": "Item attribute not found."}
        except Exception as e:
            return {"error": str(e)}

    def get_system_prompt(self) -> str:
        return """# System Prompt: Professor Oak (Pokémon API Agent)

## 1. Role and Personality
You are **Professor Oak**, the renowned Pokémon researcher from Pallet Town.
* Your goal is to help trainers with their questions by consulting the **Pokédex** (the PokéAPI).
* You are helpful, encyclopedic, and friendly.

## 2. Your Tools
You have access to external Python functions (Tools) to retrieve live data. **Never** guess stats, values, or other details – **always use the Tools.** The tools are crucial for correct answers.

## 3. Process
* **Input:** Use the name provided by the user (or search/infer the closest match if the name is not exact) for tool calls (e.g., "Charizard" -> `get_pokemon_details("charizard")`).
* **Parallel Execution:** You can and should make **multiple tool calls simultaneously** if you need data for more than one entity. For example, if asked about Charmander and Squirtle, call `get_pokemon_details("charmander")` and `get_pokemon_details("squirtle")` in the same turn.
* **Output:** Incorporate the returned JSON data naturally into your response.

## 4. Strategy for Complex Questions (Chain of Thought)
If an answer requires multiple steps, plan independently. Follow the references in the Tool Output.

**Scenario: "How do I evolve Eevee into Umbreon?"**
1.  I need evolution data -> Call `get_pokemon_details("eevee")`.
2.  I analyze the `evolution` key in the JSON response.
3.  I find "umbreon" in `evolves_to` and check its conditions.
4.  I see `time_of_day: night` and `min_happiness`.
5.  **Answer:** "You must train Eevee at **night** while it has high **friendship** with you."

## 5. Formatting
* Use **Bold** for Pokémon names, locations, and important values.
* Use bullet points for lists (e.g., moves or locations).
* If data is missing (e.g., API Error), apologize in character ("My Pokédex is currently not providing data on this").

---
**Begin the interaction now.**"""


# Tool definitions matching the class methods
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_pokemon_details",
            "description": "Retrieves comprehensive technical data for a Pokemon: base stats, types, height, weight, abilities (incl. hidden), moves, forms, held items, species info (flavor text, habitat, happiness, generation), AND full evolution chain. Use this for almost all Pokemon questions.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Pokemon (e.g. 'charizard').",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_move_details",
            "description": "Retrieves data about a move: power, accuracy, PP, damage class, generation, effect chance, flavor text, contest combos, machine details (TM/HM) and which Pokemon learn it.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the move (e.g. 'fireball').",
                    },
                    "learned_by_limit": {
                        "type": "integer",
                        "description": "Limit the number of Pokemon returned in 'learned_by'. Defaults to 20. Set to -1 to return all.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_type_info",
            "description": "Retrieves type effectiveness. Returns lists of what this type is weak or strong against.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the elemental type (e.g. 'electric').",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_encounters",
            "description": "Finds locations (routes, caves, areas) where a specific Pokemon can be found in the wild.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Pokemon (e.g. 'pikachu').",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_nature_info",
            "description": "Retrieves details about a Nature. Shows which stat is increased and which is decreased. Important for strategic questions.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Nature (e.g. 'adamant', 'jolly').",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pokemon_list_by_type",
            "description": "Returns a list of Pokemon that share a specific elemental type. Use this when the user asks for examples of a type.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "type_name": {
                        "type": "string",
                        "description": "The name of the type (e.g. 'fire', 'dragon').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "How many examples to return (Default: 10).",
                    },
                },
                "required": ["type_name", "limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ability_details",
            "description": "Explains exactly what a passive Ability does in battle and which Pokemon can have it.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Ability (e.g. 'static', 'levitate').",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_info",
            "description": "Retrieves info about an Item, including effects, flavor text, cost, attributes, who holds it (and total count), machines, and baby triggers.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Item (e.g. 'leftovers').",
                    },
                    "held_by_limit": {
                        "type": "integer",
                        "description": "Limit the number of pokemon shown to hold this item. Default 20. Set to -1 for all.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evolution_trigger_info",
            "description": "Returns info about which Pokemon evolve via a specific trigger (e.g. 'trade').",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Trigger (e.g. 'level-up', 'trade', 'use-item').",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_category_info",
            "description": "Lists items in a specific category (e.g. 'standard-balls', 'healing').",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The category name.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_attribute_info",
            "description": "Lists items with a specific attribute (e.g. 'consumable', 'holdable').",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The attribute name.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
]
