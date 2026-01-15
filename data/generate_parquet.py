import re
import pandas as pd
from pathlib import Path


def generate_parquet(raw_dir: str = "data/raw", output_dir: str = "data/dataset"):
    raw_path = Path(raw_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    data = []

    # Iterate through categories (pokemon, move, item)
    if not raw_path.exists():
        print(f"Error: Raw data directory not found at {raw_path}")
        return

    for category_dir in raw_path.iterdir():
        if not category_dir.is_dir():
            continue

        category = category_dir.name
        print(f"Processing category: {category}...")

        # Iterate through json files
        files = list(category_dir.glob("*.json"))
        print(f"Found {len(files)} JSON files in {category}")

        for json_file in files:
            md_file = json_file.with_suffix(".md")

            if not md_file.exists():
                # It's possible some files don't have descriptions, skip or include empty?
                # Based on requirements "description (from md file)", implying it exists.
                # However, safe to assume if raw data is consistent, it should be there.
                # Let's use empty string if missing to avoid data loss.
                description = ""
            else:
                description = md_file.read_text(encoding="utf-8")

            # Extract ID and Name from filename
            # Format: {id}_{name}.json
            file_stem = json_file.stem
            match = re.match(r"^(\d+)_(.+)$", file_stem)

            if match:
                id_val = int(match.group(1))
                name = match.group(2)
            else:
                # Fallback attempt
                parts = file_stem.split("_", 1)
                if len(parts) == 2 and parts[0].isdigit():
                    id_val = int(parts[0])
                    name = parts[1]
                else:
                    # If no ID found, maybe use hash or 0? or just try to parse integer if filename is just number
                    if file_stem.isdigit():
                        id_val = int(file_stem)
                        name = file_stem
                    else:
                        id_val = 0  # Default/Unknown
                        name = file_stem

            try:
                json_content = json_file.read_text(encoding="utf-8")

                data.append(
                    {
                        "category": category,
                        "id": id_val,
                        "name": name,
                        "description": description,
                        "json": json_content,
                    }
                )
            except Exception as e:
                print(f"Error reading files for {file_stem}: {e}")

    if not data:
        print("No data found!")
        return

    df = pd.DataFrame(data)

    # Sort for consistency
    df = df.sort_values(by=["category", "id"])

    output_file = output_path / "pokemon_data.parquet"
    df.to_parquet(output_file)
    print(f"Parquet file generated at: {output_file}")
    print(f"Total records: {len(df)}")
    print(df.head())


if __name__ == "__main__":
    generate_parquet()
