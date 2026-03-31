import subprocess
from huggingface_hub import HfApi
from dotenv import load_dotenv

# Load environment variables (HF_TOKEN)
load_dotenv()

REPO_ID = "Rodan009/pokemon-chatbot"
REPO_TYPE = "space"

# Explicit exclude patterns for CLI
EXCLUDES = [
    ".git/*",
    ".venv/*",
    ".env",
    "**/__pycache__/*",
    "**/.pytest_cache/*",
    "**/.ruff_cache/*",
    "**/.pokemon_cache/*",
    ".agent/*",
    ".agents/*",
    ".cursor/*",
    "data/raw/*",
    "*.pyc",
    "*.ipynb",
    "GEMINI.md"
    ]

def run_cli_command(command):
    """Run a CLI command using uv run hf to ensure accessibility."""
    full_cmd = ["uv", "run", "hf"] + command
    print(f"\n--- Executing: {' '.join(full_cmd)} ---")
    
    # We use subprocess.run without capture_output=True to allow the user 
    # to see the CLI's own progress bars and output in real-time.
    result = subprocess.run(full_cmd)
    
    if result.returncode != 0:
        print(f"Error: Command failed with exit code {result.returncode}")
        return False
    return True

def main():
    api = HfApi()

    # 1. Step 1: Delete all current files in repo using CLI
    # This is more robust than delete_files in Python for clearing a whole repo.
    print(f"Step 1: Deleting all files in {REPO_ID}...")
    delete_success = run_cli_command([
        "repos", "delete-files", REPO_ID, "*", 
        "--repo-type", REPO_TYPE,
        "--commit-message", "Clear repository before fresh upload"
    ])
    if not delete_success:
        print("Note: Step 1 skipped or failed (might be empty).")

    # 2. Step 2: Upload project using hf upload CLI
    # We use 'upload' because 'upload-large-folder' currently has a bug 
    # that requires 'space_sdk' even for existing Spaces.
    print(f"\nStep 2: Uploading local folder to {REPO_ID}...")
    upload_cmd = [
        "upload", REPO_ID, ".", 
        "--repo-type", REPO_TYPE,
        "--commit-message", "Fresh project upload"
    ]
    for pattern in EXCLUDES:
        upload_cmd.extend(["--exclude", pattern])
    
    if not run_cli_command(upload_cmd):
        print("Critical Error: Step 2 failed. Aborting.")
        return

    # 3. Step 3: Supersquash history using Python API
    print(f"\nStep 3: Squashing history for {REPO_ID}...")
    try:
        api.super_squash_history(repo_id=REPO_ID, repo_type=REPO_TYPE)
        print("History squashed successfully!")
    except Exception as e:
        print(f"Notice: Squash failed (usually if history is already clean): {e}")

    print("\nRefactor complete. Deployment finished successfully.")

if __name__ == "__main__":
    main()
