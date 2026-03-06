"""
Comprehensive unit tests for ai_tools.tools.LLMQuery and its pipeline syntax.

Covers:
  - LLMQuery initialization and configuration overrides
  - Pipeline operator (`|`) chaining mechanism
  - History management (`chat_history`, `history_limit`)
  - Tool and function tracking
"""

from ai_tools.tools import LLMQuery
from ai_tools.pipeline import _Pipeline, _PipeableString


class TestLLMQueryInitialization:
    def test_default_config(self):
        llm = LLMQuery()
        assert llm.system_prompt == ""
        # The model depends on default settings, but should be a string:
        assert isinstance(llm.model, str)
        assert llm.stream is False
        assert llm.json_format is False
        assert llm.chat_history == []
        assert llm.tools == []
        assert llm.functions == []
        assert llm.history_limit is None

    def test_overrides(self):
        llm = LLMQuery(
            system_prompt="Be concise",
            model="gpt-4o-mini",
            stream=True,
            json_format=True,
            history_limit=5,
        )
        assert llm.system_prompt == "Be concise"
        assert llm.model == "gpt-4o-mini"
        assert llm.stream is True
        assert llm.json_format is True
        assert llm.history_limit == 5

    def test_chat_history_is_isolated(self):
        # Two distinct objects should not share history
        llm1 = LLMQuery()
        llm2 = LLMQuery()

        llm1.chat_history.append({"role": "user", "content": "hi"})
        assert len(llm1.chat_history) == 1
        assert len(llm2.chat_history) == 0


class TestPipelineSyntax:
    def test_pipe_string_to_llm(self):
        llm = LLMQuery(system_prompt="Translate.")
        # Patch invoke to avoid hitting API
        llm.invoke = lambda data, **kwargs: _PipeableString(f"mocked: {data}")

        result = "Hello" | llm
        assert result == "mocked: Hello"
        assert isinstance(result, _PipeableString)

    def test_pipe_llm_to_llm(self):
        llm1 = LLMQuery()
        llm2 = LLMQuery()

        pipeline = llm1 | llm2
        assert isinstance(pipeline, _Pipeline)
        assert pipeline.step1 is llm1
        assert pipeline.step2 is llm2

    def test_pipeline_length(self):
        llm1 = LLMQuery()
        llm2 = LLMQuery()
        llm3 = LLMQuery()

        pipeline = llm1 | llm2 | llm3
        assert isinstance(pipeline, _Pipeline)
        # pipeline is (llm1 | llm2) | llm3
        assert pipeline.step2 is llm3
        assert isinstance(pipeline.step1, _Pipeline)
        assert pipeline.step1.step1 is llm1
        assert pipeline.step1.step2 is llm2


class TestHistoryManagement:
    def test_add_to_history(self):
        llm = LLMQuery()
        llm._update_history("Hello", "Hi there")
        assert len(llm.chat_history) == 2
        assert llm.chat_history[0] == {"role": "user", "content": "Hello"}
        assert llm.chat_history[1] == {"role": "assistant", "content": "Hi there"}

    def test_history_limit_truncation(self):
        llm = LLMQuery(history_limit=2)
        llm.chat_history.extend(
            [
                {"role": "user", "content": "Msg 1"},
                {"role": "assistant", "content": "Reply 1"},
            ]
        )

        msgs = llm._prepare_messages("Msg 2", use_history=True, history_limit=2)

        # history limit is 2, so it takes the last 2 from history + 1 new prompt + 1 system prompt
        assert len(msgs) == 4
        assert msgs[0] == {"role": "system", "content": ""}
        assert msgs[1] == {"role": "user", "content": "Msg 1"}
        assert msgs[2] == {"role": "assistant", "content": "Reply 1"}
        assert msgs[3] == {"role": "user", "content": "Msg 2"}

    def test_prepare_messages_adds_system_prompt_conditionally(self):
        llm = LLMQuery(system_prompt="Be honest.")
        llm.chat_history.append({"role": "user", "content": "What is 2+2?"})

        msgs = llm._prepare_messages(
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
        llm = LLMQuery(system_prompt="")
        msgs = llm._prepare_messages("Hi", use_history=True, history_limit=None)
        assert len(msgs) == 2
        assert msgs[0] == {"role": "system", "content": ""}
        assert msgs[1] == {"role": "user", "content": "Hi"}

    def test_prepare_messages_does_not_modify_internal_history(self):
        llm = LLMQuery()
        llm.chat_history.append({"role": "user", "content": "History item"})

        msgs = llm._prepare_messages(
            "Incoming query", use_history=True, history_limit=None
        )
        assert len(msgs) == 3

        assert len(llm.chat_history) == 1
        assert llm.chat_history[0] == {"role": "user", "content": "History item"}
