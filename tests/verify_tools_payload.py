import unittest
from unittest.mock import MagicMock, patch
from ai_tools import Agent

class TestToolsPayload(unittest.TestCase):
    @patch("ai_tools.tracing.get_current_trace_context")
    @patch("ai_tools.tracing.build_openrouter_trace_dict")
    def test_openrouter_payload_mirroring(self, mock_build, mock_get_ctx):
        """Verify that session_id and user_id are correctly placed for OpenRouter."""
        mock_trace = {"session_id": "test-session-123", "trace_id": "t1"}
        mock_get_ctx.return_value = MagicMock()
        mock_build.return_value = mock_trace

        q = Agent(model="openrouter/openai/gpt-oss-20b", user_id="test-user")
        q.session_id = "test-session-123"
        
        # Manually invoke _prepare_request_kwargs as if called from query()
        messages = [{"role": "user", "content": "hi"}]
        
        request_kwargs = q._prepare_request_kwargs(
            messages=messages,
            stream=False,
            json_format=False,
            model="openrouter/openai/gpt-oss-20b",
        )
        
        # Check root level (OpenAI standard)
        self.assertEqual(request_kwargs.get("user"), "test-user")
        
        # Check extra_body (OpenRouter specific)
        self.assertIn("extra_body", request_kwargs)
        eb = request_kwargs["extra_body"]
        
        # OpenRouter session_id is mirrored in extra_body
        self.assertEqual(eb.get("session_id"), "test-session-123")
        
        # Trace should be present because we mocked it
        self.assertIn("trace", eb)
        self.assertEqual(eb["trace"], mock_trace)

    def test_openai_payload_no_mirroring(self):
        """Verify that non-OpenRouter models don't get session_id mirrored."""
        q = Agent(model="openai/gpt-4o", user_id="test-user")
        q.session_id = "this-should-be-ignored"
        
        messages = [{"role": "user", "content": "hi"}]
        
        request_kwargs = q._prepare_request_kwargs(
            messages=messages,
            stream=False,
            json_format=False,
            model="openai/gpt-4o",
        )
        
        # user should be there because it's standard OpenAI
        self.assertEqual(request_kwargs.get("user"), "test-user")
        
        # extra_body should NOT have session_id mirroring for OpenAI
        if "extra_body" in request_kwargs:
            self.assertNotIn("session_id", request_kwargs["extra_body"])
            self.assertNotIn("trace", request_kwargs["extra_body"])
        
        # session_id should NOT be at root level
        self.assertNotIn("session_id", request_kwargs)

if __name__ == "__main__":
    unittest.main()
