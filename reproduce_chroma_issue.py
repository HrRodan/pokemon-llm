import chromadb
from utils.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_chroma():
    try:
        logger.info(f"Connecting to ChromaDB at: {settings.VECTOR_DB_DIR}")
        client = chromadb.PersistentClient(path=settings.VECTOR_DB_DIR)
        logger.info("Client created.")
        
        # Explicitly listing collections might reveal something
        collections = client.list_collections()
        logger.info(f"Existing collections: {collections}")
        
        collection = client.get_or_create_collection(name="pokemon_web_content")
        logger.info(f"Collection '{collection.name}' ready. Count: {collection.count()}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chroma()
