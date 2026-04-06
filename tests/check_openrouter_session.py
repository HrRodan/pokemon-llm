import os
import requests
import json
from dotenv import load_dotenv

def test_openrouter_session():
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/HrRodan/pokemon-llm", # Optional
        "X-Title": "Pokemon LLM Test", # Optional
    }
    
    # We'll try both: top-level session_id and trace dict as implemented
    payloads = [
        {
            "name": "Top-level session_id",
            "body": {
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello, this is a test for session_id tracking."}],
                "session_id": "test-session-top-level-" + os.urandom(4).hex()
            }
        },
        {
            "name": "Trace dictionary (Broadcast style)",
            "body": {
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello, this is a test for broadcast tracing."}],
                "trace": {
                    "session_id": "test-session-broadcast-" + os.urandom(4).hex(),
                    "trace_id": "test-trace-" + os.urandom(4).hex()
                }
            }
        }
    ]

    for p in payloads:
        print(f"\n--- Testing: {p['name']} ---")
        print(f"Payload: {json.dumps(p['body'], indent=2)}")
        response = requests.post(url, headers=headers, json=p['body'])
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            resp_json = response.json()
            print("Response (first choice):", resp_json.get("choices", [{}])[0].get("message", {}).get("content", "No content"))
            # OpenRouter doesn't usually return the trace status in the completion response
            # we have to check the OpenRouter dashboard or Langfuse
        else:
            print(f"Error: {response.text}")

if __name__ == "__main__":
    test_openrouter_session()
