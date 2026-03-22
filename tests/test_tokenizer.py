import glob
import logging
from chonkie import RecursiveChunker
from chonkie.refinery.overlap import OverlapRefinery

# Suppress chonkie logs
logging.getLogger("chonkie").setLevel(logging.ERROR)

def prepare_markdown(markdown):
    import re
    _YAML_FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
    clean = _YAML_FRONT_MATTER_RE.sub("", markdown, count=1)
    return clean.strip()

def test_tokenizer_comparison():
    # 1. CHARACTER TOKENIZER (Current)
    chunker_char = RecursiveChunker.from_recipe("markdown", lang="en", chunk_size=1024, tokenizer="character")
    refinery_char = OverlapRefinery(context_size=256)
    
    # 2. CL100K_BASE TOKENIZER (Proposed)
    try:
        chunker_token = RecursiveChunker.from_recipe("markdown", lang="en", chunk_size=512, tokenizer="cl100k_base") # 512 tokens is approx 2048 chars
        refinery_token = OverlapRefinery(context_size=128) # 128 tokens overlap
    except Exception as e:
        print(f"Failed to load cl100k_base tokenizer: {e}")
        chunker_token = None

    import os
    from utils.config import settings
    files = glob.glob(os.path.join(settings.WEB_SCRAPER_DIR, "*.md"))
    if not files:
        print("No files found!")
        return
        
    for f in files[:2]:
        with open(f, "r") as file:
            content = prepare_markdown(file.read())
            
        print(f"\n--- File: {f} ---")
        print(f"Total text length: {len(content)}")
        
        # CHAR
        char_chunks = refinery_char(chunker_char(content))
        char_lengths = [len(c.text) for c in char_chunks]
        print("\n[CHARACTER TOKENIZER - size=1024, overlap=256]")
        if char_chunks:
            print(f"  Total chunks: {len(char_chunks)}")
            print(f"  Average length (chars): {sum(char_lengths) / len(char_chunks):.2f}")
            print(f"  Min length (chars): {min(char_lengths)}")
            print(f"  Max length (chars): {max(char_lengths)}")
            
        # TOKEN
        if chunker_token:
            try:
                token_chunks = refinery_token(chunker_token(content))
                token_lengths = [len(c.text) for c in token_chunks]
                # Also count estimated tokens for statistics
                token_counts = [len(c.text) / 4 for c in token_chunks] # Rough estimate just for text display
                print(f"\n[CL100K_BASE TOKENIZER - size=512 tokens, overlap=128 tokens]")
                if token_chunks:
                    print(f"  Total chunks: {len(token_chunks)}")
                    print(f"  Average length (chars): {sum(token_lengths) / len(token_chunks):.2f}")
                    print(f"  Min length (chars): {min(token_lengths)}")
                    print(f"  Max length (chars): {max(token_lengths)}")
                    print(f"  (Note: chunk_size=512 tokens roughly = 2048 chars, 512 chunks might be larger.)")
            except Exception as e:
                print(f"Token chunking failed: {e}")

if __name__ == "__main__":
    test_tokenizer_comparison()
