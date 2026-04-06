import os
import requests
import json
from dotenv import load_dotenv

def test_user_provided_fetch_style():
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # User's exact requested style
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{ "role": "user", "content": "Hi there, testing top-level session_id." }],
        "session_id": "my-session-789-user-check"
    }

    print(f"Testing TOP-LEVEL session_id: {payload['session_id']}")
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Response (first choice):", response.json().get("choices", [{}])[0].get("message", {}).get("content", "No content"))
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_user_provided_fetch_style()
