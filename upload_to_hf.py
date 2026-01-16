import os
from huggingface_hub import HfApi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
REPO_ID = "Rodan009/pokemon-chatbot"
REPO_TYPE = "space"


def parse_gitignore(gitignore_path=".gitignore"):
    """
    Parse .gitignore file and return a list of patterns to ignore.
    Attempts to convert gitignore patterns to glob patterns used by huggingface_hub.
    """
    ignore_patterns = [
        "db/**"
        ".git",
        ".env",
        ".venv",
        ".venv/**",
        "**/.venv",
        "**/.venv/**",
        "__pycache__",
        "*.pyc",
        ".DS_Store",
        ".pokemon_cache",
        ".agent",
        "uv.lock",
    ]

    if not os.path.exists(gitignore_path):
        print(f"Warning: {gitignore_path} not found. Using default ignores.")
        return ignore_patterns

    with open(gitignore_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Basic conversion from gitignore to glob
            # This is not a perfect parser but handles common cases
            pattern = line

            # If directory match (ends with /), allow matching anywhere or root
            if pattern.endswith("/"):
                pattern = pattern[:-1]

            # If pattern doesn't contain /, it can match anywhere -> prepend **/
            if "/" not in pattern:
                ignore_patterns.append(f"**/{pattern}")
                ignore_patterns.append(pattern)  # match in root
            else:
                # If it starts with /, it is root-anchored. Remove leading /
                if pattern.startswith("/"):
                    ignore_patterns.append(pattern[1:])
                else:
                    # complex path, just add it and **/it
                    ignore_patterns.append(pattern)
                    ignore_patterns.append(f"**/{pattern}")

    return list(set(ignore_patterns))


def main():
    api = HfApi()

    print(f"Preparing to upload to {REPO_ID} (type={REPO_TYPE})...")

    ignore_patterns = parse_gitignore()
    print(f"Ignore patterns: {ignore_patterns}")

    print("Uploading folder...")
    try:
        api.upload_folder(
            folder_path=".",
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            ignore_patterns=ignore_patterns,
            path_in_repo=".",
        )
        print("Upload successful!")
    except Exception as e:
        print(f"Error during upload: {e}")


if __name__ == "__main__":
    main()

