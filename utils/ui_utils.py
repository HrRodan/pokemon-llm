import threading
import contextvars
from typing import List, Dict, Any, Optional
from agents.pokemon_agent import PokemonAgent
from utils.config import settings
from utils.logger import get_log_buffer
from ai_tools import flush_tracing, trace_span


def get_agent_client(model: str = settings.DEFAULT_MODEL) -> PokemonAgent:
    """
    Factory function to get the Pokemon agent.

    Args:
        model: The LLM model name to use.

    Returns:
        A new PokemonAgent instance.
    """
    return PokemonAgent(model_name=model)


def extract_tool_info(client_state: Any) -> List[Dict[str, str]]:
    """
    Extracts tool calls and results from the chat history.
    Returns a list of messages for the chatbot.
    """
    if not client_state:
        return []

    history = client_state.chat_history
    tool_history = []

    # Map tool_call_id to the tool output message
    tool_outputs = {
        msg["tool_call_id"]: msg for msg in history if msg["role"] == "tool"
    }

    for msg in history:
        if msg["role"] == "assistant" and "tool_calls" in msg and msg["tool_calls"]:
            for tool_call in msg["tool_calls"]:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]

                # Format call
                call_display = (
                    f"🛠️ **Tool Call**\n`{tool_name}`\nArguments: `{tool_args}`"
                )
                tool_history.append({"role": "user", "content": call_display})

                # Find result
                result_display = "⏳ Processing..."
                if tool_id in tool_outputs:
                    output_content = tool_outputs[tool_id]["content"]
                    # Truncate if too long (optional, but good for UI)
                    result_display = f"✅ **Result**\n```json\n{output_content}\n```"

                tool_history.append({"role": "assistant", "content": result_display})

    return tool_history


def extract_reasoning_info(client_state: Any) -> List[Dict[str, str]]:
    """
    Extracts reasoning history from the client state.
    Returns a list of assistant messages for the reasoning chatbot.
    """
    hint_message = {
        "role": "user",
        "content": "ℹ️ **Note:** Not all models provide reasoning tokens. Try **DeepSeek-R2** or **GPT-OSS** models to see thoughts here.",
    }

    if not client_state:
        return [hint_message]

    reasoning_items = [r for r in client_state.reasoning_history if r]

    if not reasoning_items:
        return [hint_message]

    return [{"role": "assistant", "content": r} for r in reasoning_items]




def respond(message: str, client_state: Any):
    """
    Main generator function for the chat interface.
    Handles user input, agent queries, and UI updates.
    """
    # Ensure client exists
    if client_state is None:
        client_state = get_agent_client()


    # Optimistic update: Show user message immediately
    current_history = client_state.clean_chat_history
    preview_history = current_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "..."},
    ]

    current_tool_history = extract_tool_info(client_state)
    current_reasoning_history = extract_reasoning_info(client_state)
    current_logs = get_log_buffer()

    # Yield 1: Direct list of dicts + tool history
    yield (
        "",
        preview_history,
        current_tool_history,
        current_reasoning_history,
        current_logs,
        client_state,
    )

    # ------------------------------------------------------------------
    # Agent Interaction within a Tracing Turn
    # ------------------------------------------------------------------
    user_id = getattr(client_state, "user_id", None)
    session_id = client_state.session_id

    try:
        with trace_span(
            name=client_state.name,
            input=message,
            user_id=user_id,
            session_id=session_id,
            tags=[client_state.name, client_state.model.split("/")[0]],
            metadata={"model": client_state.model},
            as_type="agent"
        ) as span:
            # Query logic
            client_state.query(message)

            # Yield 2: Show tool calls if any (before execution loop finishes)
            yield (
                "",
                client_state.clean_chat_history + [{"role": "assistant", "content": "..."}],
                extract_tool_info(client_state),
                extract_reasoning_info(client_state),
                get_log_buffer(),
                client_state,
            )

            # Handle tool calls using a separate thread for UI responsiveness
            ctx = contextvars.copy_context()
            
            def thread_target():
                ctx.run(client_state.get_tool_responses)
                    
            t = threading.Thread(target=thread_target)
            t.start()

            # Poll thread status and yield updates to UI
            while t.is_alive():
                # Wait up to 5 seconds for the thread to finish
                t.join(timeout=2)  # Shorter timeout for faster log updates
                # If still alive, yield an update to show we are still processing
                if t.is_alive():
                    yield (
                        "",
                        client_state.clean_chat_history
                        + [{"role": "assistant", "content": "..."}],
                        extract_tool_info(client_state),
                        extract_reasoning_info(client_state),
                        get_log_buffer(),
                        client_state,
                    )

            # Ensure thread is fully joined
            t.join()
            
            # Update the turn span with the final output
            from ai_tools.tracing import update_span
            update_span(span, output=client_state.response)
            
    finally:
        flush_tracing()

    # Yield 3: Final state
    yield (
        "",
        client_state.clean_chat_history,
        extract_tool_info(client_state),
        extract_reasoning_info(client_state),
        get_log_buffer(),
        client_state,
    )


