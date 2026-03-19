import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tools.web_vector_db import ingest_web_page, IngestWebPageArgs, query_web_content, QueryWebContentArgs

def run():
    print("Ingesting page...")
    args = IngestWebPageArgs(
        url="https://bulbapedia.bulbagarden.net/wiki/Charmander_(Pok%C3%A9mon)",
        css_selector="#mw-content-text"
    )
    result = ingest_web_page(args)
    print("Ingest result:", result)
    
    print("\nQuerying...")
    q_args = QueryWebContentArgs(query="What is the flame on Charmander's tail?", n_results=3)
    q_result = query_web_content(q_args)
    print("Query result:")
    print(q_result)

if __name__ == "__main__":
    run()
