import os
from unittest.mock import patch, MagicMock
from ai_tools.tools import LLMQuery
import ai_tools.tracing

# Ensure tracing is enabled but mock the API keys
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-test"
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-test"
os.environ["LANGFUSE_BASE_URL"] = "http://test"
os.environ["OPENAI_API_KEY"] = "sk-test"

# Force re-check
ai_tools.tracing._tracing_checked = False

llm = LLMQuery(model="openai/gpt-4o-mini")

# Mock the client instanced by _get_client_for_model
# We expect it to be a langfuse.openai.OpenAI instance
# Let's see what it actually is
client = llm._get_client_for_model("openai/gpt-4o-mini")
print(f"Client class: {type(client)}")
from langfuse.openai import OpenAI as LangfuseOpenAI
print(f"Is LangfuseOpenAI? {isinstance(client, LangfuseOpenAI)}")

# Now let's try to call create and see if it fails
try:
    # We need to mock the actual network call inside the create method
    # so it doesn't fail with network error before checking kwargs
    with patch("openai.resources.chat.completions.Completions.create") as mock_create:
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            langfuse_session_id="test-session"
        )
    print("Call successful!")
except TypeError as e:
    print(f"TypeError caught: {e}")
except Exception as e:
    print(f"Other exception: {e}")
