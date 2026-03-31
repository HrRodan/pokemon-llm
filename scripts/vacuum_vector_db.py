import sys
import os
import sqlite3

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.config import settings

def get_file_size_mb(path: str) -> float:
    """Returns the size of a file in MB."""
    if not os.path.exists(path):
        return 0.0
    return os.path.getsize(path) / (1024 * 1024)

def vacuum_sqlite_db(path: str):
    """Performs VACUUM and ANALYZE on a SQLite database."""
    if not os.path.exists(path):
        print(f"Database not found at: {path}")
        return

    size_before = get_file_size_mb(path)
    print(f"\n--- Optimizing {os.path.basename(path)} ---")
    print(f"Size before: {size_before:.2f} MB")

    try:
        conn = sqlite3.connect(path)
        # WAL mode can make files larger due to the .wal file. 
        # Vacuuming while in WAL mode works, but we can also checkpoint.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.execute("VACUUM;")
        conn.execute("ANALYZE;")
        conn.close()
        
        size_after = get_file_size_mb(path)
        print(f"Size after:  {size_after:.2f} MB")
        if size_before > 0:
            reduction = size_before - size_after
            percent = (1 - size_after/size_before)*100
            print(f"Reduction:   {reduction:.2f} MB ({percent:.1f}%)")
        else:
            print("Size unchanged or file was empty.")
    except Exception as e:
        print(f"Error optimizing {path}: {e}")

def main():
    # 1. Vacuum ChromaDB metadata
    chroma_sqlite_path = os.path.join(settings.VECTOR_DB_DIR, "chroma.sqlite3")
    vacuum_sqlite_db(chroma_sqlite_path)

    # 2. Vacuum Tech DB
    tech_db_path = settings.TECH_DB_PATH
    vacuum_sqlite_db(tech_db_path)

    print("\nOptimization complete.")

if __name__ == "__main__":
    main()
