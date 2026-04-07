import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Make sure we can import from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ui_utils import respond
from ai_tools import Agent

def test_respond_no_errors():
    """
    Test that the respond generator executes completely without throwing errors,
    especially AttributeError related to the client_state.response.
    """
    # Create a mock agent
    mock_agent = MagicMock()
    mock_agent.name = "TestAgent"
    mock_agent.model = "test-model"
    mock_agent.clean_chat_history = [{"role": "assistant", "content": "Hello"}]
    mock_agent.user_id = "test-user"
    
    # Mock the internal Agent structure
    mock_agent.memory = MagicMock()
    mock_agent.memory.root_thread_id = "test-thread-id"
    mock_agent.response = "This is a mock final response from the agent"
    
    # We want get_tool_responses to just return a string and not block forever
    mock_agent.get_tool_responses.return_value = "Mock tool response"
    
    # Mock extract functions to return simple empty structures so UI updates do not fail
    with patch("utils.ui_utils.extract_tool_info", return_value=[]), \
         patch("utils.ui_utils.extract_reasoning_info", return_value=[]), \
         patch("utils.ui_utils.get_log_buffer", return_value=""):
         
        # Run the generator fully
        results = list(respond("Test message", mock_agent))
        
        # It should yield several tuples of state
        assert len(results) >= 3
        
        # The final result should contain the clean chat history
        final_yield = results[-1]
        assert isinstance(final_yield, tuple)
        assert len(final_yield) == 6
        
        # Verify query was called
        mock_agent.query.assert_called_once_with("Test message")
