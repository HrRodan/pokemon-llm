# Plan: Make AI Tools Race Condition Safe

## Problem
Currently, the `as_tool()` method in both `LLMQuery` (`ai_tools/tools.py`) and `LLMAgent` (`ai_tools/agent.py`) returns a wrapper function that captures and reuses the parent `self` instance. When these wrapped tools are invoked concurrently (e.g. by another `LLMQuery` using `concurrent_tool_calls=True`), multiple threads execute against the exact same instance simultaneously. This causes race conditions on shared stateful attributes like `chat_history`, `tool_calls`, and `response`, leading to mixed contexts and corrupted histories.

## Solution Strategy
Ensure each invocation of a sub-agent/tool gets its own isolated instance while correctly aggregating usage metrics (cost, tokens) back to the parent instance.

### Step 1: `LLMQuery` Changes (`ai_tools/tools.py`)

1. **Add Usage Lock:** 
   Add a thread lock in `__init__` to safely aggregate usage metrics when tools run concurrently.
   ```python
   import threading
   self._usage_lock = threading.Lock()
   ```

2. **Implement Thread-Safe Usage Updates:**
   Update `_update_usage` to wrap token accumulations in `with self._usage_lock:`.

3. **Implement `.clone()` Method:**
   Add a method to safely create a fresh run-state copy of the query object:
   ```python
   def clone(self) -> "LLMQuery":
       import copy
       import threading
       new_llm = copy.copy(self)
       
       # Reset stateful attributes for isolated execution
       new_llm.chat_history = []
       new_llm.tool_calls = []
       new_llm.response = ""
       new_llm.reasoning_history = []
       
       # Reset usage counters and assign a fresh lock
       new_llm._usage_lock = threading.Lock()
       new_llm.total_cost = 0.0
       new_llm.total_prompt_tokens = 0
       new_llm.total_completion_tokens = 0
       new_llm.total_reasoning_tokens = 0
       new_llm.total_tokens = 0
       
       return new_llm
   ```

4. **Update `as_tool()` Wrapper:**
   Modify the inner `_wrapper` function to use a clone:
   ```python
   def _wrapper(**kwargs) -> str:
       prompt = kwargs.get(input_arg, "")
       local_llm = llm_ref.clone()
       original_memory = getattr(llm_ref, "memory", None)

       if original_memory:
           scoped = original_memory.create_scoped_handler(name)
           local_llm.memory = scoped

       local_llm.query(prompt)
       result = local_llm.get_tool_responses()

       # Aggregate usage back to parent safely
       with llm_ref._usage_lock:
           llm_ref.total_cost += local_llm.total_cost
           llm_ref.total_prompt_tokens += local_llm.total_prompt_tokens
           llm_ref.total_completion_tokens += local_llm.total_completion_tokens
           llm_ref.total_reasoning_tokens += local_llm.total_reasoning_tokens
           llm_ref.total_tokens += local_llm.total_tokens
       
       return result
   ```

### Step 2: `LLMAgent` Changes (`ai_tools/agent.py`)

1. **Update `as_tool()` Wrapper:**
   Modify the inner `_wrapper` function to instantiate a shallow copy of the agent and clone its underlying `LLMQuery`:
   ```python
   def _wrapper(**kwargs) -> str:
       import copy
       query = kwargs.get("query", "")
       
       local_agent = copy.copy(agent_ref)
       local_agent.llm = agent_ref.llm.clone()
       
       original_memory = getattr(agent_ref.llm, "memory", None)

       if original_memory:
           scoped = original_memory.create_scoped_handler(agent_ref.TOOL_NAME)
           local_agent.llm.memory = scoped
           
       result = local_agent.run(query)
       
       # Aggregate usage back to parent safely
       with agent_ref.llm._usage_lock:
           agent_ref.llm.total_cost += local_agent.llm.total_cost
           agent_ref.llm.total_prompt_tokens += local_agent.llm.total_prompt_tokens
           agent_ref.llm.total_completion_tokens += local_agent.llm.total_completion_tokens
           agent_ref.llm.total_reasoning_tokens += local_agent.llm.total_reasoning_tokens
           agent_ref.llm.total_tokens += local_agent.llm.total_tokens
           
       return result
   ```

This solution is minimal, clean, avoids deeply nested copying, and completely resolves concurrency risks without breaking the existing API footprint.