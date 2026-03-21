import os
import sys
import chromadb

import utils.config
from utils.config import settings

chroma_client = chromadb.PersistentClient(path=str(settings.VECTOR_DB_DIR))
collection = chroma_client.get_collection(name='pokemon_web_content')
try:
    result = collection.get(include=['embeddings', 'documents', 'metadatas'], limit=1000)
    print("Success. Elements:", len(result['ids']))
except Exception as e:
    print(f"Error: {e}")

