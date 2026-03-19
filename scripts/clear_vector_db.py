import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chromadb
from utils.config import settings

def main():
    try:
        # Connect to your existing persistent database
        chroma_client = chromadb.PersistentClient(path=settings.VECTOR_DB_DIR)
        
        # Delete the specific collection for web content
        chroma_client.delete_collection(name="pokemon_web_content")
        print("Successfully deleted 'pokemon_web_content' collection.")
        
    except ValueError:
        print("The collection doesn't exist yet, nothing to clear!")
    except Exception as e:
        print(f"Error resetting database: {e}")

if __name__ == "__main__":
    main()
