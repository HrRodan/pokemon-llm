# Plan: Remove UsageTracker and Simplify Agent Concurrency

## Objective
Remove all references to the global `UsageTracker` and the internal `AgentUsage` token tracking across the codebase, as usage tracking is now handled entirely via tracing. Leverage this statelessness to refactor the `as_tool` methods in `ai_tools/agent.py` and `ai_tools/tools.py` so they instantiate a fresh agent per invocation. This simplifies concurrency by removing the need to manage shared state (like clearing history and temporarily swapping memory handlers) across tool calls.

## Key Files & Context
- **Files to delete:** 
  - `utils/usage_tracker.py`
  - `tests/unit/test_usage_tracker.py`
- **Agent Base Classes:** 
  - `ai_tools/agent.py`
  - `ai_tools/tools.py`
  - `agents/base_agent.py`
- **Specific Implementations:** 
  - `agents/pokemon_agent.py`
  - `utils/ui_utils.py`
- **Tests:** 
  - `tests/unit/test_agents.py`
  - `tests/integration/test_agent_llm.py`
- **Documentation:** 
  - `README.md`
  - `ai_tools/__init__.py`

## Implementation Steps

### 1. Remove the UsageTracker Module
- Delete `utils/usage_tracker.py`.
- Delete `tests/unit/test_usage_tracker.py`.
- Remove `AgentUsage` imports and references in `ai_tools/__init__.py`.

### 2. Clean Up `ai_tools/agent.py`
- Remove the `AgentUsage` dataclass entirely.
- In `LLMAgent.__init__`: Remove `_call_count` and `usage` initialization.
- Remove the `_update_usage()` method from `LLMAgent`.
- Refactor `LLMAgent.as_tool()` to spawn a new instance instead of capturing `self` and managing state:
  - `new_agent = self.__class__(self.config)`
  - If a memory handler is in use, create a scoped handler for the invocation and attach it to `new_agent.llm.memory`.
  - Execute `new_agent.run(query)`.
  - This eliminates the need for `agent_ref.llm.clear_history()` and temporary memory handler swaps on the original instance.

### 3. Clean Up `ai_tools/tools.py`
- In `LLMQuery.__init__`: Save the initialization parameters into `self._init_kwargs` to allow easy reconstruction.
- Refactor `LLMQuery.as_tool()` to spawn a fresh instance instead of capturing `self`:
  - `new_llm = self.__class__(**self._init_kwargs)`
  - Apply the scoped memory handler if `self.memory` exists.
  - Execute `new_llm.query(prompt)` and `new_llm.get_tool_responses()`.
- Leave internal token counters (`total_tokens`, `total_cost`, etc.) in `LLMQuery` as they might still be relevant for Langfuse tracing or checkpointing, but decouple them from any global usage tracking logic.

### 4. Update Project-Specific Agents
- **`agents/base_agent.py`**: 
  - Remove `TrackerAgentUsage` imports.
  - Remove the `_collect_usage()` method.
  - Remove the `run()` override entirely, allowing it to naturally fall back to `LLMAgent.run()`.
- **`agents/pokemon_agent.py`**: 
  - Remove the `usage_tracker`, `cost`, `total_tokens`, `prompt_tokens`, `completion_tokens`, and `reasoning_tokens` properties.
  - Remove any custom `print_usage` methods that depend on it.
- **`utils/ui_utils.py`**: 
  - Remove `UsageTracker.get().reset()` and other usage tracker imports and references.

### 5. Update Tests & Documentation
- **`tests/unit/test_agents.py`**: Remove tests verifying `UsageTracker` updates.
- **`tests/integration/test_agent_llm.py`**: Remove `UsageTracker` validations.
- **`README.md`**: Remove mentions of the global singleton `UsageTracker`.

## Verification & Testing
- Ensure the project successfully imports without module errors.
- Run `uv run pytest` to ensure all tests pass (specifically those checking agent tool calls).
- Verify sub-agent execution works cleanly and histories don't bleed between invocations by running the `scripts/verify_agents.py` script or notebook tests.
