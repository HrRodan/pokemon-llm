import os
import unittest
from unittest.mock import patch, MagicMock
from ai_tools.tools import LLMQuery
from ai_tools.tracing import get_openai_class
import ai_tools.tracing

class TestTracingSafety(unittest.TestCase):
    def setUp(self):
        # Reset tracing state
        ai_tools.tracing._tracing_checked = False
        ai_tools.tracing._tracing_enabled = False
        ai_tools.tracing._langfuse_client = None

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_no_illegal_kwargs_passed_to_openai(self, mock_get_api_key, mock_get_cls):
        """
        Verify that session_id and user_id are NOT passed as keyword arguments to create(),
        which would cause a TypeError in strictly-typed OpenAI SDK versions.
        """
        # 1. Setup Mock Instrumented Client
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        # 2. Mock environment to enable tracing
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        
        with patch.dict(os.environ, env):
            # 3. Initialize LLMQuery with a mocked memory object
            # In the previous buggy version, this session_id would leak to create()
            mock_memory = MagicMock()
            mock_memory.root_thread_id = "test-session-123"
            
            llm = LLMQuery(model="openai/gpt-4o-mini", memory=mock_memory)
            llm.user_id = "test-user-456"
            
            # Mock the response
            mock_client_instance = MockInstrumentedOpenAI.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Safe Response"
            mock_response.choices[0].message.tool_calls = None
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            # 4. Trigger query
            llm.query("Hello")
            
            # 5. Verify intercepted arguments
            args, kwargs = mock_client_instance.chat.completions.create.call_args
            
            # List of forbidden arguments that were causing the TypeError
            forbidden = [
                "langfuse_session_id", 
                "langfuse_user_id", 
                "langfuse_tags",
                "session_id", # Standard OpenAI does not accept this either
                "user_id"     # Standard OpenAI uses 'user', not 'user_id'
            ]
            
            for key in forbidden:
                self.assertNotIn(key, kwargs, f"Illegal argument '{key}' leaked to OpenAI create() call!")
            
            # Verify that 'name' and 'metadata' are still allowed (as Langfuse strips them)
            self.assertIn("name", kwargs)
            self.assertIn("metadata", kwargs)
            
            print("Safety check passed: No illegal Langfuse arguments leaked to OpenAI client.")

if __name__ == "__main__":
    unittest.main()
