import os
import unittest
from unittest.mock import patch, MagicMock
from ai_tools.tools import LLMQuery
import ai_tools.tracing

class TestDynamicNaming(unittest.TestCase):
    def setUp(self):
        # Reset tracing state
        ai_tools.tracing._tracing_checked = False
        ai_tools.tracing._tracing_enabled = False
        ai_tools.tracing._langfuse_client = None

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_naming_with_agent_name(self, mock_get_api_key, mock_get_cls):
        """Verify name format: generation:<AgentName>"""
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        
        with patch.dict(os.environ, env):
            llm = LLMQuery(model="openai/gpt-4o", agent_name="PokemonAgent")
            
            mock_client_instance = MockInstrumentedOpenAI.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Oak here!"
            mock_response.choices[0].message.tool_calls = None
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            llm.query("Hello")
            
            args, kwargs = mock_client_instance.chat.completions.create.call_args
            self.assertEqual(kwargs["name"], "generation:PokemonAgent")

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_naming_without_agent_name(self, mock_get_api_key, mock_get_cls):
        """Verify name format: generation:LLMQuery when agent_name is None"""
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        
        with patch.dict(os.environ, env):
            llm = LLMQuery(model="openai/gpt-4o", agent_name=None)
            
            mock_client_instance = MockInstrumentedOpenAI.return_value
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Direct answer"
            mock_response.choices[0].message.tool_calls = None
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            llm.query("Hello")
            
            args, kwargs = mock_client_instance.chat.completions.create.call_args
            self.assertEqual(kwargs["name"], "generation:LLMQuery")

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_behavior_without_langfuse(self, mock_get_api_key, mock_get_cls):
        """Verify that everything works normally when Langfuse is disabled/missing"""
        from openai import OpenAI
        mock_get_cls.return_value = OpenAI
        
        # Ensure tracing is disabled
        with patch.dict(os.environ, {}, clear=True):
            llm = LLMQuery(model="openai/gpt-4o")
            
            with patch("openai.resources.chat.completions.Completions.create") as mock_create:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "No tracing answer"
                mock_response.choices[0].message.tool_calls = None
                mock_create.return_value = mock_response
                
                llm.query("Hello")
                
                args, kwargs = mock_create.call_args
                # 'name' is NOT a standard OpenAI kwarg
                self.assertNotIn("name", kwargs)
                # Model is stripped from openai/gpt-4o to gpt-4o
                self.assertEqual(kwargs["model"], "gpt-4o")

    @patch("ai_tools.tools.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    def test_embedding_naming(self, mock_get_api_key, mock_get_cls):
        """Verify name format: embedding:<AgentName>:<Model>"""
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        env = {
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_BASE_URL": "http://test"
        }
        
        with patch.dict(os.environ, env):
            from ai_tools.tools import LLMQuery
            llm = LLMQuery(model="openai/gpt-4o", agent_name="RAGAgent")
            
            mock_client_instance = MockInstrumentedOpenAI.return_value
            mock_response = MagicMock()
            mock_data = MagicMock()
            mock_data.embedding = [0.1, 0.2, 0.3]
            mock_response.data = [mock_data]
            mock_client_instance.embeddings.create.return_value = mock_response
            
            # Explicitly pass model to avoid using instance default from config
            llm.generate_embedding(["Hello"], model="openai/gpt-4o")
            
            args, kwargs = mock_client_instance.embeddings.create.call_args
            self.assertEqual(kwargs["name"], "embedding:RAGAgent:gpt-4o")
            # Verify provider is in metadata
            self.assertEqual(kwargs["metadata"]["provider"], "openai")

if __name__ == "__main__":
    unittest.main()
