import unittest
from unittest.mock import MagicMock, patch
from ai_tools.tools import LLMQuery

class TestToolsPayload(unittest.TestCase):
    def test_openrouter_payload_mirroring(self):
        """Verify that session_id and user_id are correctly placed for OpenRouter."""
        q = LLMQuery(model="openrouter/google/gemini-flash-1.5", user_id="test-user")
        
        # Manually invoke _prepare_request_kwargs as if called from query()
        messages = [{"role": "user", "content": "hi"}]
        openrouter_trace = {"session_id": "test-session-123", "trace_id": "trace-456"}
        
        request_kwargs = q._prepare_request_kwargs(
            messages=messages,
            stream=False,
            json_format=False,
            model="openrouter/google/gemini-flash-1.5",
            openrouter_trace=openrouter_trace,
            session_id="test-session-123",
            user_id="test-user"
        )
        
        # Check root level
        self.assertEqual(request_kwargs.get("user"), "test-user")
        self.assertEqual(request_kwargs.get("session_id"), "test-session-123")
        self.assertEqual(request_kwargs.get("trace"), openrouter_trace)
        
        # Check extra_body (Broadcast)
        self.assertIn("extra_body", request_kwargs)
        self.assertIn("trace", request_kwargs["extra_body"])
        self.assertEqual(request_kwargs["extra_body"]["trace"]["session_id"], "test-session-123")
        self.assertEqual(request_kwargs["extra_body"]["trace"]["trace_id"], "trace-456")

    def test_openai_payload_no_mirroring(self):
        """Verify that non-OpenRouter models don't get session_id mirrored (unless passed as kwarg)."""
        q = LLMQuery(model="openai/gpt-4o", user_id="test-user")
        
        messages = [{"role": "user", "content": "hi"}]
        
        request_kwargs = q._prepare_request_kwargs(
            messages=messages,
            stream=False,
            json_format=False,
            model="openai/gpt-4o",
            user_id="test-user",
            session_id="this-should-be-ignored-by-default-logic"
        )
        
        # user should be there because it's standard OpenAI
        self.assertEqual(request_kwargs.get("user"), "test-user")
        
        # session_id should NOT be there because it's not OpenRouter and we don't mirror it for others
        self.assertNotIn("session_id", request_kwargs)

if __name__ == "__main__":
    unittest.main()
