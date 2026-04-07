"""
Comprehensive unit tests for ai_tools.agent.Agent core logic.

Covers:
  - Agent initialization and configuration overrides
  - History management (chat_history, history_limit)
  - Tool and function tracking
"""

import pytest
from ai_tools.agent import Agent


class TestAgentInitialization:
    def test_default_config(self):
        agent = Agent()
        assert agent.system_prompt == ""
        # The model depends on default settings, but should be a string:
        assert isinstance(agent.model, str)
        assert agent.stream is False
        assert agent.json_format is False
        assert agent.chat_history == []
        assert agent.tools == []
        assert agent.functions == []
        assert agent.history_limit is None

    def test_overrides(self):
        agent = Agent(
            system_prompt="Be concise",
            model="openai/gpt-4o-mini",
            stream=True,
            json_format=True,
            history_limit=5,
        )
        assert agent.system_prompt == "Be concise"
        assert agent.model == "openai/gpt-4o-mini"
        assert agent.stream is True
        assert agent.json_format is True
        assert agent.history_limit == 5

    def test_chat_history_is_isolated(self):
        # Two distinct objects should not share history
        agent1 = Agent()
        agent2 = Agent()

        agent1.chat_history.append({"role": "user", "content": "hi"})
        assert len(agent1.chat_history) == 1
        assert len(agent2.chat_history) == 0


class TestHistoryManagement:
    def test_add_to_history(self):
        agent = Agent()
        # _update_history is now more complex, we test its side effect
        from unittest.mock import MagicMock
        msg = MagicMock()
        msg.model_dump.return_value = {"role": "assistant", "content": "Hi there"}
        agent._update_history(msg)
        
        # Note: _update_history appends the dumped message. 
        # In actual usage, query() adds the user prompt first.
        assert len(agent.chat_history) == 1
        assert agent.chat_history[0]["role"] == "assistant"

    def test_history_limit_truncation(self):
        agent = Agent(history_limit=2)
        agent.chat_history.extend(
            [
                {"role": "user", "content": "Msg 1"},
                {"role": "assistant", "content": "Reply 1"},
            ]
        )

        msgs = agent._prepare_messages("Msg 2", use_history=True, history_limit=2)

        # history limit is 2, so it takes the last 2 from history + 1 new prompt + 1 system prompt
        assert len(msgs) == 4
        assert msgs[0] == {"role": "system", "content": ""}
        assert msgs[1] == {"role": "user", "content": "Msg 1"}
        assert msgs[2] == {"role": "assistant", "content": "Reply 1"}
        assert msgs[3] == {"role": "user", "content": "Msg 2"}

    def test_prepare_messages_adds_system_prompt_conditionally(self):
        agent = Agent(system_prompt="Be honest.")
        agent.chat_history.append({"role": "user", "content": "What is 2+2?"})

        msgs = agent._prepare_messages(
            "Are you sure?", use_history=True, history_limit=None
        )

        assert len(msgs) == 3
        # First must be the system prompt
        assert msgs[0] == {"role": "system", "content": "Be honest."}
        # Second is the history
        assert msgs[1] == {"role": "user", "content": "What is 2+2?"}
        # Third is the immediate user prompt
        assert msgs[2] == {"role": "user", "content": "Are you sure?"}

    def test_prepare_messages_no_system_prompt(self):
        agent = Agent(system_prompt="")
        msgs = agent._prepare_messages("Hi", use_history=True, history_limit=None)
        assert len(msgs) == 2
        assert msgs[0] == {"role": "system", "content": ""}
        assert msgs[1] == {"role": "user", "content": "Hi"}

    def test_prepare_messages_does_not_modify_internal_history(self):
        agent = Agent()
        agent.chat_history.append({"role": "user", "content": "History item"})

        msgs = agent._prepare_messages(
            "Incoming query", use_history=True, history_limit=None
        )
        assert len(msgs) == 3

        assert len(agent.chat_history) == 1
        assert agent.chat_history[0] == {"role": "user", "content": "History item"}
