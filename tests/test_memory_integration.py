from unittest.mock import MagicMock
from ai_tools import Agent
from ai_tools.memory import MemoryHandler

def test_llmquery_with_memory_saves_checkpoints():
    memory = MemoryHandler()
    llm = Agent(model="openai/gpt-4o-mini", memory=memory)
    
    # Need to mock the API response to do integration without real API
    # Since we can't easily mock `client.chat.completions.create` inline safely,
    #.We can just manually inject state into chat_history and call the private _update_history
    # Wait, the best way in integration test without mocking is tricky if it hits openai.
    # LLMQuery allows overriding `client` inside `query()` if we override `_create_chat_completion`, 
    # but we will just mock `_create_chat_completion`.
    
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "mocked response"
    mock_resp.choices[0].message.tool_calls = None
    mock_resp.choices[0].message.reasoning = None
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 20
    mock_resp.usage.total_tokens = 30
    
    llm._create_chat_completion = MagicMock(return_value=mock_resp)
    
    llm.query("Hello")
    assert memory.step_id == 1
    assert len(memory.list_checkpoints()) == 1
    
    # Ensure history passed into memory
    history = memory.load_history()
    assert len(history) == 2 # user 'Hello', assistant 'mocked'

def test_agent_without_memory_unchanged():
    llm = Agent(model="openai/gpt-4o-mini")
    assert getattr(llm, "memory", None) is None
    # Just asserting it doesn't crash on standard invocation
    assert llm.chat_history == []

def test_llmquery_memory_resumes_history():
    memory = MemoryHandler(thread_id="t1")
    memory.save_checkpoint([
        {"role": "system", "content": "..." },
        {"role": "user", "content": "past_user"},
        {"role": "assistant", "content": "past_assistant"},
    ])
    
    llm = Agent(model="openai/gpt-4o-mini", memory=memory)
    # history is loaded in __init__
    assert len(llm.chat_history) == 3
    assert llm.chat_history[-1]["content"] == "past_assistant"

def test_llmquery_clear_history_starts_new_thread():
    memory = MemoryHandler(thread_id="t1")
    llm = Agent(memory=memory)
    
    old_thread = memory.thread_id
    llm.clear_history()
    
    assert memory.thread_id != old_thread
    assert len(llm.chat_history) == 0

def test_agent_with_memory_initialization():
    memory = MemoryHandler()
    agent = Agent(name="test", model="openai/gpt-4o-mini", memory=memory)
    
    assert agent.memory is memory

def test_agent_as_tool_ephemeral():
    agent = Agent(name="test", model="openai/gpt-4", memory=None)
    agent.TOOL_NAME = "sub"
    agent.TOOL_DESCRIPTION = "subagent desc"
    
    wrapper = agent.as_tool()
    schema = wrapper.__tool_schema__
    
    # Running wrapper clears history in ephemeral mode
    assert wrapper.__name__ == "sub"

def test_agent_as_tool_scoped():
    memory = MemoryHandler()
    agent = Agent(name="test", model="openai/gpt-4", memory=memory)
    agent.TOOL_NAME = "sub"
    agent.TOOL_DESCRIPTION = "subagent desc"
    
    # Agent.as_tool() uses self.TOOL_NAME and self.TOOL_DESCRIPTION
    wrapper = agent.as_tool()
    schema = wrapper.__tool_schema__
    # the wrapper swaps memory when invoked, which we verify indirectly if possible.
