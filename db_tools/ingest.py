from typing import List, Dict, Any, Optional
import os
import json
from tqdm import tqdm
from db_tools.rag_data_tool import (
    embedding_client,
    collection,
    MetaData,
    PokemonObject,
    GENERATION_MAPPING,
)


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
            try:
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


if __name__ == "__main__":
    # Check if we should ingest (simple check if DB is empty or just always try to resume)
    # For this task, we run ingest.
    clean_database()
    ingest_data()
