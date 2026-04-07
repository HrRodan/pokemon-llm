import os
import unittest
from unittest.mock import patch, MagicMock
from ai_tools.agent import Agent
import ai_tools.tracing

class TestDynamicNaming(unittest.TestCase):
    def setUp(self):
        # Reset tracing state
        ai_tools.tracing._tracing_checked = False
        ai_tools.tracing._tracing_enabled = False
        ai_tools.tracing._langfuse_client = None

    @patch("ai_tools.client.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    @patch("ai_tools.tracing.is_tracing_enabled", return_value=True)
    def test_naming_with_agent_name(self, mock_tracing_enabled, mock_get_api_key, mock_get_cls):
        """Verify name format: generation:<AgentName>"""
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        # We need to mock the client instance returned by get_client(model)
        with patch("ai_tools.agent.get_client") as mock_get_client:
            mock_client_instance = MagicMock()
            mock_get_client.return_value = mock_client_instance
            
            env = {
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_BASE_URL": "http://test"
            }
            
            with patch.dict(os.environ, env):
                agent = Agent(model="openai/gpt-4o", name="PokemonAgent")
                
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Oak here!"
                mock_response.choices[0].message.tool_calls = None
                mock_client_instance.chat.completions.create.return_value = mock_response
                
                agent.query("Hello")
                
                # Verify intercepted arguments
                args, kwargs = mock_client_instance.chat.completions.create.call_args
                self.assertEqual(kwargs["name"], "generation:PokemonAgent")

    @patch("ai_tools.client.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    @patch("ai_tools.tracing.is_tracing_enabled", return_value=True)
    def test_naming_without_agent_name(self, mock_tracing_enabled, mock_get_api_key, mock_get_cls):
        """Verify name format: generation:Agent when name is default"""
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        with patch("ai_tools.agent.get_client") as mock_get_client:
            mock_client_instance = MagicMock()
            mock_get_client.return_value = mock_client_instance
            
            env = {
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_BASE_URL": "http://test"
            }
            
            with patch.dict(os.environ, env):
                # When name=None, Agent defaults name to "Agent"
                agent = Agent(model="openai/gpt-4o", name=None)
                
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Direct answer"
                mock_response.choices[0].message.tool_calls = None
                mock_client_instance.chat.completions.create.return_value = mock_response
                
                agent.query("Hello")
                
                args, kwargs = mock_client_instance.chat.completions.create.call_args
                self.assertEqual(kwargs["name"], "generation:Agent")

    @patch("ai_tools.agent.get_client")
    def test_behavior_without_langfuse(self, mock_get_client):
        """Verify that everything works normally when Langfuse is disabled/missing"""
        mock_client_instance = MagicMock()
        mock_get_client.return_value = mock_client_instance
        
        # Ensure tracing is disabled
        with patch.dict(os.environ, {}, clear=True):
            # Reset tracing state for this test
            ai_tools.tracing._tracing_checked = False
            ai_tools.tracing._tracing_enabled = False
            
            agent = Agent(model="openai/gpt-4o")
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "No tracing answer"
            mock_response.choices[0].message.tool_calls = None
            mock_client_instance.chat.completions.create.return_value = mock_response
            
            agent.query("Hello")
            
            args, kwargs = mock_client_instance.chat.completions.create.call_args
            # 'name' is NOT a standard OpenAI kwarg
            self.assertNotIn("name", kwargs)
            # Model is stripped from openai/gpt-4o to gpt-4o
            self.assertEqual(kwargs["model"], "gpt-4o")

    @patch("ai_tools.client.get_openai_class")
    @patch("ai_tools.config.get_api_key", return_value="sk-test")
    @patch("ai_tools.tracing.is_tracing_enabled", return_value=True)
    def test_embedding_naming(self, mock_tracing_enabled, mock_get_api_key, mock_get_cls):
        """Verify name format: embedding:<AgentName>:<Model>"""
        MockInstrumentedOpenAI = MagicMock()
        mock_get_cls.return_value = MockInstrumentedOpenAI
        
        with patch("ai_tools.agent.get_client") as mock_get_client:
            mock_client_instance = MagicMock()
            mock_get_client.return_value = mock_client_instance
            
            env = {
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_BASE_URL": "http://test"
            }
            
            with patch.dict(os.environ, env):
                agent = Agent(model="openai/gpt-4o", name="RAGAgent")
                
                mock_response = MagicMock()
                mock_data = MagicMock()
                mock_data.embedding = [0.1, 0.2, 0.3]
                mock_response.data = [mock_data]
                mock_client_instance.embeddings.create.return_value = mock_response
                
                agent.generate_embedding(["Hello"], model="openai/gpt-4o")
                
                args, kwargs = mock_client_instance.embeddings.create.call_args
                self.assertEqual(kwargs["name"], "embedding:RAGAgent:gpt-4o")
                # Verify provider is in metadata
                self.assertEqual(kwargs["metadata"]["provider"], "openai")

if __name__ == "__main__":
    unittest.main()
