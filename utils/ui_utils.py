import threading
from typing import List, Dict, Any, Optional
from agents.pokemon_agent import PokemonAgent
from utils.config import settings
from utils.logger import get_log_buffer
from utils.usage_tracker import UsageTracker


def get_agent_client(model: str = settings.DEFAULT_MODEL) -> PokemonAgent:
    """
    Factory function to get the Pokemon agent.

    Resets the global usage tracker so each session starts fresh.

    Args:
        model: The LLM model name to use.

    Returns:
        A new PokemonAgent instance.
    """
    UsageTracker.get().reset()
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


def format_empty_usage() -> str:
    """Return the default (zeroed) usage markdown when no data is available."""
    return """### 📊 Token Usage (Accumulated)
| Metric | Value |
| :--- | :--- |
| **Total Cost** | `$0.000000` |
| **Total Tokens** | `0` |
| **Prompt Tokens** | `0` |
| **Completion Tokens** | `0` |
| **Reasoning Tokens** | `0` |

*No agent activity yet.*
"""


def extract_usage_info(client_state: Any) -> str:
    """
    Build a Markdown string with accumulated usage statistics.

    Shows a **totals** summary table followed by a **per-agent** breakdown.
    Data is read from the global :class:`UsageTracker` so it includes
    sub-agent usage that would otherwise be lost between instantiations.

    Args:
        client_state: The current PokemonAgent (may be ``None``).

    Returns:
        A Markdown-formatted string for the Gradio UI.
    """
    tracker = UsageTracker.get()
    totals = tracker.get_totals()

    # If nothing has been tracked yet, show a clean default
    if totals.total_tokens == 0 and totals.cost == 0.0:
        return format_empty_usage()

    # --- Totals table ---
    md = f"""### 📊 Token Usage (Accumulated)
| Metric | Value |
| :--- | :--- |
| **Total Cost** | `${totals.cost:.6f}` |
| **Total Tokens** | `{totals.total_tokens:,}` |
| **Prompt Tokens** | `{totals.prompt_tokens:,}` |
| **Completion Tokens** | `{totals.completion_tokens:,}` |
| **Reasoning Tokens** | `{totals.reasoning_tokens:,}` |

"""

    # --- Per-agent breakdown ---
    all_agents = tracker.get_all()
    if all_agents:
        md += "### 🤖 Per-Agent Breakdown\n"
        md += "| Agent | Calls | Prompt | Completion | Reasoning | Total | Cost |\n"
        md += "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
        for name, usage in all_agents.items():
            md += (
                f"| **{name}** "
                f"| {usage.call_count} "
                f"| {usage.prompt_tokens:,} "
                f"| {usage.completion_tokens:,} "
                f"| {usage.reasoning_tokens:,} "
                f"| {usage.total_tokens:,} "
                f"| `${usage.cost:.6f}` |\n"
            )

    return md


def change_model(model_name: str, client_state: Any) -> Any:
    """
    Updates the model in the client state.
    """
    if client_state and model_name in settings.ALLOWED_MODELS:
        client_state.model = model_name
    return client_state


def respond(message: str, client_state: Any, model_name: Optional[str] = None):
    """
    Main generator function for the chat interface.
    Handles user input, agent queries, and UI updates.
    """
    # Ensure client exists
    if client_state is None:
        client_state = get_agent_client()

    # Sync model if provided
    if model_name:
        change_model(model_name, client_state)

    # Optimistic update: Show user message immediately
    current_history = client_state.clean_chat_history
    preview_history = current_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "..."},
    ]

    current_tool_history = extract_tool_info(client_state)
    current_reasoning_history = extract_reasoning_info(client_state)
    current_usage_info = extract_usage_info(client_state)
    current_logs = get_log_buffer()

    # Yield 1: Direct list of dicts + tool history
    yield (
        "",
        preview_history,
        current_tool_history,
        current_reasoning_history,
        current_usage_info,
        current_logs,
        client_state,
    )

    # Query logic
    client_state.query(message)

    # Yield 2: Show tool calls if any (before execution loop finishes)
    yield (
        "",
        client_state.clean_chat_history + [{"role": "assistant", "content": "..."}],
        extract_tool_info(client_state),
        extract_reasoning_info(client_state),
        extract_usage_info(client_state),
        get_log_buffer(),
        client_state,
    )

    # Handle tool calls using a separate thread for UI responsiveness
    t = threading.Thread(target=client_state.get_tool_responses)
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
                extract_usage_info(client_state),
                get_log_buffer(),
                client_state,
            )

    # Ensure thread is fully joined
    t.join()

    # Yield 3: Final state
    yield (
        "",
        client_state.clean_chat_history,
        extract_tool_info(client_state),
        extract_reasoning_info(client_state),
        extract_usage_info(client_state),
        get_log_buffer(),
        client_state,
    )
