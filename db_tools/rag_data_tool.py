from typing import List, Dict, Optional, Literal, Union, Any
import json
import chromadb
from ai_tools.tools import LLMQuery
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

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


# Valid categories
CATEGORY_LITERAL = Literal["pokemon", "move", "item"]


class QueryDatabaseArgs(BaseModel):
    """Queries the vector database for relevant Pokemon information (Pokemon, Moves, Items) based on a semantic query string. returns a markdown formatted string with the results."""

    query: str = Field(
        description="The semantic query string to search for (e.g. 'fire type pokemon that can learn fly', 'items that restore PP')."
    )
    n_results: int = Field(
        default=3,
        ge=1,
        le=7,
        description="Number of results to return. Defaults to 3. Do NOT Exceed 7.",
    )
    category: Optional[List[CATEGORY_LITERAL]] = Field(
        default=None,
        description="Optional list of categories to filter by. Valid values: 'pokemon', 'move', 'item', e.g. for only listing Pokemon, use ['pokemon']. If not specified, all categories are included.",
    )
    max_generation: Optional[int] = Field(
        default=None,
        description="Optional maximum generation (inclusive) to filter by. e.g. 1 for Gen I only, 3 for Gen I-III.",
    )
    only_default_version: bool = Field(
        default=True,
        description="Defaults to True. is_default: true: This is the 'main' version of the Pokémon (e.g., standard Bulbasaur, ID 1). is_default: false: This is a variant form (e.g., Mega Venusaur, ID 10033). Set to **False** to include variants like **Mega Forms** or **Giga Forms**.",
    )
    filter_name: Optional[str] = Field(
        default=None,
        description="Optional name of the Pokemon, Move, or Item to filter by (e.g. 'charizard'). Use this when being asked for a specific Pokemon or object.",
    )
    filter_id: Optional[int] = Field(
        default=None,
        description="Optional ID of the Pokemon, Move, or Item to filter by (e.g. 6). Use this when being asked for a specific ID.",
    )

    @field_validator("category", mode="before")
    @classmethod
    def parse_category(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [v]
            except json.JSONDecodeError:
                return [v]
        return v

    @field_validator("max_generation", mode="before")
    @classmethod
    def parse_max_generation(cls, v: Any) -> Any:
        if v == "" or v is None:
            return None
        return v

    @field_validator("filter_name", mode="before")
    @classmethod
    def parse_filter_name(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            clean_v = v.strip().lower()
            if clean_v in ["null", "none", ""]:
                return None
            return clean_v.replace(" ", "-")
        return v

    @model_validator(mode="after")
    def check_filters(self) -> "QueryDatabaseArgs":
        if self.filter_name is not None or self.filter_id is not None:
            self.only_default_version = False
        return self


def get_similar_objects(args: QueryDatabaseArgs) -> PokemonObjectList:
    """Queries the database and returns a PokemonObjectList.

    Args:
        args: Validated QueryDatabaseArgs object.
    """
    where_clauses: List[Dict[str, Any]] = []

    if args.category:
        where_clauses.append({"category": {"$in": args.category}})

    if args.max_generation is not None:
        where_clauses.append({"generation": {"$lte": args.max_generation}})

    if args.filter_name:
        where_clauses.append({"name": args.filter_name})

    if args.filter_id is not None:
        where_clauses.append({"id": args.filter_id})

    if args.only_default_version:
        where_clauses.append({"is_default": True})

    where: Any
    if len(where_clauses) > 1:
        where = {"$and": where_clauses}
    elif len(where_clauses) == 1:
        where = where_clauses[0]
    else:
        where = None

    query_embedding = embedding_client.generate_embedding([args.query])[0]
    results = collection.query(
        query_embeddings=[query_embedding], n_results=args.n_results, where=where
    )

    if not results or not results.get("ids") or not results["ids"][0]:
        return PokemonObjectList(objects=[])

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


def query_database(**kwargs) -> str:
    """Queries the database and returns a formatted string. Accepts variable arguments that are validated against QueryDatabaseArgs."""
    try:
        # Validate arguments using Pydantic
        args = QueryDatabaseArgs(**kwargs)
    except ValidationError as e:
        return f"Argument Validation Error: {e.json()}"

    object_list = get_similar_objects(args)
    return object_list.to_formatted_string()


# Define tool schema
tool_schema = QueryDatabaseArgs.model_json_schema()

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": QueryDatabaseArgs.__doc__,
            "parameters": tool_schema,
        },
    }
]
