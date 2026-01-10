from ai_tools.tools import LLMQuery
from pydantic import BaseModel, Field

embedding_client = LLMQuery(embedding_model="qwen/qwen3-embedding-8b")

class MetaData(BaseModel):
    id: int = Field(description="ID according to PokéAPI")
    name: str = Field(description="Name according to PokéAPI")
    category: str = Field(description="Category of the object, e.g. item, pokemon, move")
    types: list[str] = Field(description="Types of the object if applicable, e.g. ['water', 'electric']")
    
    

class PokemonObject(BaseModel):
    page_content: str = Field(description="RAG optimized description of the object in Markdown")
    metadatas: MetaData = Field(description="Metadata about the object")

# TODO: ingest all items from /data/raw/... into a chroma vector database
# loop through the json and md files, extract the metadata from the json and the page_content from the md file 
# use the pydantic models defined above to create the objects
# use the embedding client to create the embeddings
# use the chromadb client to create the vector database
# use the chromadb client to add the objects to the vector database
# add tqdm to show progress
# pay attention to the huge amount of files, pay attention, that the process is able to resume without embedding everything again
# pay attention to the types metadata and the support of lists in chroma db, omit the types if necessary

# TODO: create a function that takes a query and returns the most similar objects
# The returned objects should be concatenated by {id + ' ' + name +  \n page_content} \n\n {next object}
