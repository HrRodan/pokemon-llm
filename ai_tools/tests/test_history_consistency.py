
from ai_tools.tools import LLMQuery

def test_get_consistent_history_backtracks_to_user():
    """
    Ensure history slicing always backtracks to the nearest 'user' message
    to satisfy strict provider requirements (e.g., Mistral, Claude).
    """
    llm = LLMQuery(system_prompt="sys")
    llm.chat_history = [
        {"role": "user", "content": "1"},                                     # idx 0
        {"role": "assistant", "content": "2", "tool_calls": [{"id": "c1"}]},  # idx 1
        {"role": "tool", "content": "3", "tool_call_id": "c1"},               # idx 2
        {"role": "assistant", "content": "4"},                                # idx 3
        {"role": "user", "content": "5"},                                     # idx 4
        {"role": "assistant", "content": "6", "tool_calls": [{"id": "c2"}]},  # idx 5
        {"role": "tool", "content": "7", "tool_call_id": "c2"},               # idx 6
    ]

    # limit=1: Suggested slice [idx 6] (tool).
    # Backtrack should stop at idx 4 (user).
    hist = llm._get_consistent_history(1)
    assert len(hist) == 3
    assert hist[0]["role"] == "user"
    assert hist[0]["content"] == "5"

    # limit=3: Suggested slice [idx 4, 5, 6] (user, assistant, tool).
    # Already starts with user, no backtracking needed.
    hist = llm._get_consistent_history(3)
    assert len(hist) == 3
    assert hist[0]["role"] == "user"

    # limit=4: Suggested slice [idx 3, 4, 5, 6] (assistant, user, assistant, tool).
    # Starts with assistant, must backtrack to idx 0 (user).
    hist = llm._get_consistent_history(4)
    assert len(hist) == 7
    assert hist[0]["role"] == "user"
    assert hist[0]["content"] == "1"

def test_get_consistent_history_skips_forward_if_no_preceding_user():
    """
    If no 'user' message exists before the suggested slice, skip forward
    to find the first 'user' message instead of sending an invalid role.
    """
    llm = LLMQuery(system_prompt="sys")
    llm.chat_history = [
        {"role": "assistant", "content": "orphaned"},
        {"role": "tool", "content": "3", "tool_call_id": "c1"},
        {"role": "user", "content": "first user"},
    ]
    # limit=2: Suggested slice [tool, user].
    # Backtrack reaches idx 0 (assistant), then skip-forward finds idx 2 (user).
    hist = llm._get_consistent_history(2)
    assert len(hist) == 1
    assert hist[0]["role"] == "user"
    assert hist[0]["content"] == "first user"

def test_get_consistent_history_empty():
    llm = LLMQuery(system_prompt="sys")
    assert llm._get_consistent_history(5) == []
    assert llm._get_consistent_history(0) == []
    assert llm._get_consistent_history(-1) == []
