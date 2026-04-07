import os
import unittest
from unittest.mock import patch, MagicMock
from ai_tools import Agent
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

    @patch("ai_tools.tracing.get_openai_class")
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
                
                llm = Agent(model="openai/gpt-4o-mini")
                res = llm.query("Hi")
                
                self.assertEqual(res, "Hello")
                # Ensure no langfuse_ params were passed to create()
                args, kwargs = mock_create.call_args
                self.assertFalse(any(k.startswith("langfuse_") for k in kwargs))

    @patch("ai_tools.agent.Agent._create_chat_completion")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_query_flow_with_tracing(self, mock_get_api_key, mock_create):
        """Verify that query() passes name attribute for tracing when tracing is enabled."""
        from ai_tools.agent import Agent
        from ai_tools.tracing import TraceContext

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello traced"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock()
        mock_response.usage.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 5}
        mock_create.return_value = mock_response

        # Use an existing trace context
        ctx = TraceContext(
            trace_id="t1", 
            observation_id="o1", 
            session_id="s1", 
            user_id="u1", 
            trace_name="test", 
            environment="test"
        )
        
        with patch("ai_tools.tracing.is_tracing_enabled", return_value=True), \
             patch("ai_tools.tracing.get_current_trace_context", return_value=ctx):
            
            llm = Agent(name="Agent", model="openai/gpt-4o-mini")
            res = llm.query("Hi")
            
            self.assertEqual(res, "Hello traced")
            # Check if request_kwargs contains tracing params
            args, kwargs = mock_create.call_args
            request_kwargs = args[1] # second positional arg is request_kwargs
            
            # The 'name' (used for trace naming) should be passed in request_kwargs
            self.assertEqual(request_kwargs["name"], "generation:Agent")

if __name__ == "__main__":
    unittest.main()
