import os
import pytest
from ai_tools import tracing
from openai import OpenAI as RealOpenAI

def test_repro_langfuse_tags_error():
    # Force tracing enabled for the repro
    os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-123"
    os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-123"
    os.environ["LANGFUSE_BASE_URL"] = "https://cloud.langfuse.com"
    
    # Reset tracing state to pick up env vars
    tracing._tracing_checked = False
    
    assert tracing.is_tracing_enabled() is True
    
    OpenAIClass = tracing.get_openai_class()
    # It should be the langfuse wrapper
    print(f"DEBUG: OpenAIClass is {OpenAIClass}")
    
    client = OpenAIClass(api_key="sk-dummy")
    
    # Try to call it with tags. We expect this to FAIL with TypeError if the bug is present.
    # We use a dummy model and no real API call is expected to succeed, 
    # but the TypeError happens BEFORE the network call.
    try:
        client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "hi"}],
            tags=["test-repro"]
        )
    except TypeError as e:
        print(f"DEBUG: Caught expected TypeError: {e}")
        raise
    except Exception as e:
        print(f"DEBUG: Caught other exception (which means TypeError didn't happen): {type(e).__name__}: {e}")

if __name__ == "__main__":
    try:
        test_repro_langfuse_tags_error()
    except Exception:
        import traceback
        traceback.print_exc()
