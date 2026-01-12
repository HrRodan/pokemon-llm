from typing import List, Dict, Optional, Literal, Union, Any
import os
import json
import chromadb
from tqdm import tqdm
from ai_tools.tools import LLMQuery
from pydantic import BaseModel, Field

# Initialize embedding client
embedding_client = LLMQuery(embedding_model="qwen/qwen3-embedding-8b")

# Initialize ChromaDB client
CHROMA_PATH = "./db"
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="pokemon_data")


# Generation mappings
GENERATION_MAPPING = {
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

INT_TO_DISPLAY_GENERATION = {
    1: "Generation I",
    2: "Generation II",
    3: "Generation III",
    4: "Generation IV",
    5: "Generation V",
    6: "Generation VI",
    7: "Generation VII",
    8: "Generation VIII",
    9: "Generation IX",
}


class MetaData(BaseModel):
    id: int = Field(description="ID according to PokéAPI")
    name: str = Field(description="Name according to PokéAPI")
    category: str = Field(
        description="Category of the object, e.g. item, pokemon, move"
    )
    generation: Optional[int] = Field(
        default=None, description="Generation ID of the object (e.g. 1 for Gen I)"
    )
    is_default: bool = Field(
        default=True,
        description="True if this is the default/standard version of the object (e.g. Bulbasaur), False if it is a variant (e.g. Mega Venusaur).",
    )
    # types removed per user request


class PokemonObject(BaseModel):
    page_content: str = Field(
        description="RAG optimized description of the object in Markdown"
    )
    metadatas: MetaData = Field(description="Metadata about the object")

    def to_formatted_string(self) -> str:
        """Returns the object formatted as a string for RAG context."""
        gen_str = "Unknown"
        if self.metadatas.generation:
            gen_str = INT_TO_DISPLAY_GENERATION.get(
                self.metadatas.generation, str(self.metadatas.generation)
            )

        return (
            f"### Entity: {self.metadatas.name}\n"
            f"- **Category**: {self.metadatas.category}\n"
            f"- **ID**: {self.metadatas.id}\n"
            f"- **Generation**: {gen_str}\n\n"
            f"{self.page_content}"
        )


class PokemonObjectList(BaseModel):
    objects: List[PokemonObject] = Field(description="List of Pokemon objects")

    def to_formatted_string(self) -> str:
        """Concatenates all objects into a single string with clear separation."""
        return "\n\n---\n\n".join([obj.to_formatted_string() for obj in self.objects])


def clean_database():
    """Removes entries from the database that are no longer valid or excluded."""
    print("Cleaning database...")
    base_path = "data/raw"
    categories = ["pokemon", "move", "item"]
    valid_ids = set()

    # Build set of valid IDs based on current file system and rules
    for category in categories:
        category_path = os.path.join(base_path, category)
        if not os.path.exists(category_path):
            continue

        files = os.listdir(category_path)
        json_files = [f for f in files if f.endswith(".json")]

        for json_file in json_files:
            # Filename format check/parsing if strictly needed,
            # but opening the file is safer for exact ID match
            try:
                # Optimized: file name usually starts with id "0001_bulbasaur.json"
                # But to be safe and consistent with exclusion rules, let's peek at JSON
                filepath = os.path.join(category_path, json_file)
                with open(filepath, "r") as f:
                    data = json.load(f)

                details = (
                    data.get("pokemon_details")
                    or data.get("move_details")
                    or data.get("item_details")
                )

                if not details:
                    continue

                item_id = details.get("id")

                if item_id is not None:
                    valid_ids.add(f"{category}_{item_id}")

            except Exception as e:
                print(f"Error checking file for cleanup {json_file}: {e}")

    # Get all existing IDs in DB
    existing_ids = collection.get()["ids"]

    ids_to_delete = [uid for uid in existing_ids if uid not in valid_ids]

    if ids_to_delete:
        print(f"Removing {len(ids_to_delete)} invalid/excluded entries...")
        # Delete in batches to be safe
        batch_size = 100
        for i in range(0, len(ids_to_delete), batch_size):
            batch = ids_to_delete[i : i + batch_size]
            collection.delete(ids=batch)
    else:
        print("Database is clean.")


def ingest_data():
    """Ingests data from /data/raw into ChromaDB using Pydantic validation."""
    base_path = "data/raw"
    categories = ["pokemon", "move", "item"]

    # Collect all items to process
    items_to_process = []

    print("Scanning files...")
    for category in categories:
        category_path = os.path.join(base_path, category)
        if not os.path.exists(category_path):
            continue

        files = os.listdir(category_path)
        # Filter for JSON files and ensure corresponding MD exists
        json_files = [f for f in files if f.endswith(".json")]

        for json_file in json_files:
            md_file = json_file.replace(".json", ".md")
            if md_file in files:
                items_to_process.append(
                    {
                        "category": category,
                        "json_path": os.path.join(category_path, json_file),
                        "md_path": os.path.join(category_path, md_file),
                    }
                )

    print(f"Found {len(items_to_process)} items on disk.")

    # Batch processing
    batch_size = 50
    current_batch_items = []

    for item in tqdm(items_to_process, desc="Ingesting"):
        current_batch_items.append(item)

        if len(current_batch_items) >= batch_size:
            _process_batch(current_batch_items)
            current_batch_items = []

    # Process remaining
    if current_batch_items:
        _process_batch(current_batch_items)


def _process_batch(batch_items):
    """Helper to process a batch of items."""
    ids_to_process = []
    objects_map = {}

    for item in batch_items:
        try:
            with open(item["json_path"], "r") as f:
                data = json.load(f)

            details = (
                data.get("pokemon_details")
                or data.get("move_details")
                or data.get("item_details")
            )

            if not details:
                continue

            item_id = details.get("id")

            # Determine is_default
            # For Pokemon, the API/JSON usually provides 'is_default'
            # For Moves/Items, we assume True as they don't have variants in the same way usually
            is_default = True
            if item["category"] == "pokemon":
                is_default = details.get("is_default", True)

            item_name = details.get("name")

            # Extract generation info
            # "generation" field usually contains slug like "generation-i"
            # "generation_info" usually contains name like "Generation I", but we prefer slug for mapping
            gen_slug = details.get("generation")

            # If slug not found, try to map from name if needed, but primary source is "generation" key in these files
            generation_id = None
            if gen_slug and isinstance(gen_slug, str):
                generation_id = GENERATION_MAPPING.get(gen_slug.lower())

            # Fallback/Edge case handling if needed
            if not generation_id and details.get("generation_info"):
                # Try to parse from "Generation I" etc if needed, but the simple mapping above handles "generation-x"
                pass

            if item_id is None or item_name is None:
                continue

            unique_id = f"{item['category']}_{item_id}"

            with open(item["md_path"], "r") as f:
                page_content = f.read()

            metadata = MetaData(
                id=item_id,
                name=item_name,
                category=item["category"],
                generation=generation_id,
                is_default=is_default,
            )
            pokemon_object = PokemonObject(
                page_content=page_content, metadatas=metadata
            )

            ids_to_process.append(unique_id)
            objects_map[unique_id] = pokemon_object

        except Exception as e:
            print(f"Error preparing item {item['json_path']}: {e}")

    if not ids_to_process:
        return

    # Check existence
    existing = collection.get(ids=ids_to_process)
    existing_ids = set(existing["ids"]) if existing["ids"] else set()

    # Split into new and existing
    new_ids = []
    new_docs = []
    new_metas = []

    update_ids = []
    update_metas = []

    for uid in ids_to_process:
        obj = objects_map[uid]
        meta_dict = obj.metadatas.model_dump(exclude_none=True)

        if uid in existing_ids:
            update_ids.append(uid)
            update_metas.append(meta_dict)
        else:
            new_ids.append(uid)
            new_docs.append(obj.page_content)
            new_metas.append(meta_dict)

    # Add new items
    if new_ids:
        try:
            embeddings = embedding_client.generate_embedding(new_docs)
            collection.add(
                ids=new_ids,
                documents=new_docs,
                embeddings=embeddings,
                metadatas=new_metas,
            )
        except Exception as e:
            print(f"Error adding batch: {e}")

    # Update existing items (metadata only)
    if update_ids:
        try:
            collection.update(
                ids=update_ids,
                metadatas=update_metas,
            )
        except Exception as e:
            print(f"Error updating batch: {e}")


def get_similar_objects(
    query: str,
    n_results: int = 5,
    category: Optional[Union[List[Literal["pokemon", "move", "item"]], str]] = None,
    max_generation: Union[int, str, None] = None,
    only_default_version: bool = True,
    filter_name: Optional[str] = None,
    filter_id: Optional[int] = None,
) -> PokemonObjectList:
    """Queries the database and returns a PokemonObjectList.

    Args:
        query: The query string.
        n_results: Number of results to return.
        category: Optional list of categories to filter by.
        max_generation: Optional maximum generation (inclusive) to filter by.
        only_default_version: If True, only returns default forms (is_default=True).

        filter_name: Optional name of the Pokemon, Move, or Item to filter by.
        filter_id: Optional ID of the Pokemon, Move, or Item to filter by.
    """
    where_clauses: List[Dict[str, Any]] = []

    if category:
        if isinstance(category, str):
            category = [category]  # type: ignore
        where_clauses.append({"category": {"$in": category}})

    if max_generation is not None:
        if isinstance(max_generation, str):
            if not max_generation.strip():
                max_generation = None
            elif max_generation.isdigit():
                max_generation = int(max_generation)

        if max_generation is not None:
            where_clauses.append({"generation": {"$lte": max_generation}})

    if filter_name:
        clean_name = filter_name.lower().strip().replace(" ", "-")
        if clean_name not in ["null", "none"]:
            where_clauses.append({"name": clean_name})
            only_default_version = False

    if filter_id is not None:
        where_clauses.append({"id": filter_id})
        only_default_version = False

    if only_default_version:
        where_clauses.append({"is_default": True})

    where: Any
    if len(where_clauses) > 1:
        where = {"$and": where_clauses}
    elif len(where_clauses) == 1:
        where = where_clauses[0]
    else:
        where = None

    query_embedding = embedding_client.generate_embedding([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding], n_results=n_results, where=where
    )

    ids = results["ids"][0]
    metadatas = results["metadatas"][0]
    documents = results["documents"][0]

    found_objects = []

    for i in range(len(ids)):
        meta = metadatas[i]
        doc = documents[i]

        metadata_obj = MetaData(**meta)
        pokemon_obj = PokemonObject(page_content=doc, metadatas=metadata_obj)
        found_objects.append(pokemon_obj)

    return PokemonObjectList(objects=found_objects)


def query_database(
    query: str,
    n_results: int = 5,
    category: Optional[Union[List[Literal["pokemon", "move", "item"]], str]] = None,
    max_generation: Union[int, str, None] = None,
    only_default_version: bool = True,
    filter_name: Optional[str] = None,
    filter_id: Optional[int] = None,
) -> str:
    """Queries the database and returns a formatted string."""
    n_results = min(n_results, 20)
    object_list = get_similar_objects(
        query,
        n_results,
        category=category,
        max_generation=max_generation,
        only_default_version=only_default_version,
        filter_name=filter_name,
        filter_id=filter_id,
    )
    return object_list.to_formatted_string()


TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Queries the vector database for relevant Pokemon information (Pokemon, Moves, Items) based on a semantic query string. returns a markdown formatted string with the results.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The semantic query string to search for (e.g. 'fire type pokemon that can learn fly', 'items that restore PP').",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return. Defaults to 5. Do NOT Exceed 10.",
                        "default": 5,
                    },
                    "category": {
                        "type": "array",
                        "description": "Optional list of categories to filter by. Valid values: 'pokemon', 'move', 'item'.",
                        "items": {
                            "type": "string",
                            "enum": ["pokemon", "move", "item"],
                        },
                    },
                    "max_generation": {
                        "type": ["integer", "null"],
                        "description": "Optional maximum generation (inclusive) to filter by. e.g. 1 for Gen I only, 3 for Gen I-III.",
                    },
                    "only_default_version": {
                        "type": "boolean",
                        "description": "Defaults to True. is_default: true: This is the 'main' version of the Pokémon (e.g., standard Bulbasaur, ID 1). is_default: false: This is a variant form (e.g., Mega Venusaur, ID 10033). Set to False to include variants.",
                        "default": True,
                    },
                    "filter_name": {
                        "type": ["string", "null"],
                        "description": "Optional name of the Pokemon, Move, or Item to filter by (e.g. 'charizard'). Use this when being asked for a specific Pokemon or object.",
                    },
                    "filter_id": {
                        "type": ["integer", "null"],
                        "description": "Optional ID of the Pokemon, Move, or Item to filter by (e.g. 6). Use this when being asked for a specific ID.",
                    },
                },
                "required": [
                    "query",
                    "n_results",
                    "category",
                    "max_generation",
                    "only_default_version",
                    "filter_name",
                    "filter_id",
                ],
                "additionalProperties": False,
            },
        },
    }
]


if __name__ == "__main__":
    # Check if we should ingest (simple check if DB is empty or just always try to resume)
    # For this task, we run ingest.
    clean_database()
    ingest_data()

    # Test query
    print("\nTesting Query: 'fire type pokemon' (defaults only)")
    print(query_database("fire type pokemon", n_results=2, only_default_version=True))

    print("\nTesting Query: 'mega evolution' (allow variants)")
    print(
        query_database("mega evolved pokemon", n_results=2, only_default_version=False)
    )
