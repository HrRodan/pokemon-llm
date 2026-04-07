"""
Unit tests for the new unified Agent architecture.
All LLM calls are mocked.
"""

import unittest
from unittest.mock import MagicMock, patch
from ai_tools.agent import Agent
from ai_tools.memory import MemoryHandler

class TestAgentUnified(unittest.TestCase):
    def setUp(self):
        self.mock_response = MagicMock()
        self.mock_response.choices = [MagicMock()]
        self.mock_response.choices[0].message.content = "Mocked result"
        self.mock_response.choices[0].message.tool_calls = []
        self.mock_response.usage = MagicMock()
        self.mock_response.usage.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 5}

    @patch("ai_tools.agent.Agent._create_chat_completion")
    def test_basic_query(self, mock_create):
        mock_create.return_value = self.mock_response
        
        agent = Agent(name="TestAgent", model="openai/gpt-4o", system_prompt="You are helpful.")
        res = agent.run("Hello")
        
        self.assertEqual(res, "Mocked result")
        self.assertTrue(mock_create.called)

    def test_as_tool_schema(self):
        agent = Agent(name="TestAgent", model="openai/gpt-4o")
        agent.TOOL_NAME = "my_tool"
        agent.TOOL_DESCRIPTION = "My description"
        
        wrapper = agent.as_tool()
        schema = wrapper.__tool_schema__
        
        self.assertEqual(schema["function"]["name"], "my_tool")
        self.assertEqual(schema["function"]["description"], "My description")
        self.assertEqual(wrapper.__name__, "my_tool")

    @patch("ai_tools.agent.Agent._create_chat_completion")
    def test_agent_tool_call_delegation(self, mock_create):
        mock_create.return_value = self.mock_response
        
        agent = Agent(name="Parent", model="openai/gpt-4o")
        agent.TOOL_NAME = "parent_tool"
        agent.TOOL_DESCRIPTION = "Parent description"
        wrapper = agent.as_tool()
        
        # Calling the wrapper should trigger a run
        res = wrapper(query="test")
        self.assertEqual(res, "Mocked result")
        self.assertTrue(mock_create.called)

if __name__ == "__main__":
    unittest.main()
