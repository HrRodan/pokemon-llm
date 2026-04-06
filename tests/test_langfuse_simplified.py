import os
import unittest
from unittest.mock import patch, MagicMock
from ai_tools.tools import LLMQuery
from ai_tools.tracing import get_openai_class, is_tracing_enabled
import ai_tools.tracing

class TestLangfuseSimplified(unittest.TestCase):
    def setUp(self):
        # Reset the global tracing state before each test
        ai_tools.tracing._tracing_checked = False
        ai_tools.tracing._tracing_enabled = False
        ai_tools.tracing._langfuse_client = None

    def test_client_class_selection_no_tracing(self):
        """Verify that get_openai_class returns standard OpenAI when tracing is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            cls = get_openai_class()
            from openai import OpenAI
            self.assertEqual(cls, OpenAI)

    def test_client_class_selection_with_tracing_partial_installation(self):
        """Verify that it falls back if langfuse.openai is missing but langfuse is present."""
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        # Simulate langfuse.openai being missing by patching sys.modules
        with patch.dict(os.environ, env):
            with patch.dict("sys.modules", {"langfuse.openai": None}):
                cls = get_openai_class()
                from openai import OpenAI as StandardOpenAI
                self.assertEqual(cls, StandardOpenAI)
                
                # is_tracing_enabled() must now return False
                self.assertFalse(is_tracing_enabled())
                
                # get_langfuse_params() must return empty dict
                params = ai_tools.tracing.get_langfuse_params(model="gpt", session_id="test")
                self.assertEqual(params, {})

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_query_flow_no_tracing(self, mock_get_api_key, mock_get_cls):
        """Verify that query() works without tracing and doesn't pass langfuse_ params."""
        from openai import OpenAI as StandardOpenAI
        mock_get_cls.return_value = StandardOpenAI
        
        with patch.dict(os.environ, {}, clear=True):
            with patch("openai.resources.chat.completions.Completions.create") as mock_create:
                # Mock the response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Hello"
                mock_response.choices[0].message.tool_calls = None
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 10
                mock_response.usage.completion_tokens = 5
                mock_response.usage.total_tokens = 15
                mock_create.return_value = mock_response
                
                llm = LLMQuery(model="openai/gpt-4o-mini")
                res = llm.query("Hi")
                
                self.assertEqual(res, "Hello")
                # Ensure no langfuse_ params were passed to create()
                args, kwargs = mock_create.call_args
                self.assertFalse(any(k.startswith("langfuse_") for k in kwargs))

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_query_flow_with_tracing(self, mock_get_api_key, mock_get_cls):
        """Verify that query() passes langfuse_ params when tracing is enabled."""
        # Force tracing enabled
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        
        # Mock Langfuse version of OpenAI
        MockLangfuseOpenAI = MagicMock()
        mock_get_cls.return_value = MockLangfuseOpenAI
        
        with patch.dict(os.environ, env):
            llm = LLMQuery(model="openai/gpt-4o-mini")
            
            # Mock the client instance and its create method
            mock_client_instance = MockLangfuseOpenAI.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Hello traced"
            mock_response.choices[0].message.tool_calls = None
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            res = llm.query("Hi")
            
            self.assertEqual(res, "Hello traced")
            # Ensure langfuse_ params (legacy) are NOT passed
            args, kwargs = mock_client_instance.chat.completions.create.call_args
            self.assertFalse(any(k.startswith("langfuse_") for k in kwargs))
            # But 'name' (used for trace naming) should be passed
            self.assertEqual(kwargs["name"], "generation:LLMQuery")

if __name__ == "__main__":
    unittest.main()
