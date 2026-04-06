import os
import json
from openai import OpenAI
from dotenv import load_dotenv

def test_openai_sdk_openrouter():
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return

    # Initialize OpenAI client pointing to OpenRouter
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # In tools.py we use:
    # extra_body = {"trace": {"session_id": "...", ...}}
    
    session_id = "test-session-sdk-" + os.urandom(4).hex()
    trace_id = "test-trace-sdk-" + os.urandom(4).hex()
    
    print(f"Testing SDK with trace.session_id: {session_id}")
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello, this is a test for SDK-based session tracking."}],
            extra_body={
                "trace": {
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "environment": "development"
                }
            }
        )
        print("Status: SUCCESS")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_openai_sdk_openrouter()
