import threading
from chatbot import get_chatbot_client, ALLOWED_MODELS


def extract_tool_info(client_state):
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


def extract_reasoning_info(client_state):
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


def extract_usage_info(client_state):
    """
    Extracts usage statistics from the client state.
    Returns a markdown string displaying the accumulated stats.
    """
    if not client_state:
        # Return default stats if no state exists
        return """### 📊 Token Usage (Accumulated)
| Metric | Value |
| :--- | :--- |
| **Total Cost** | `$0.000000` |
| **Total Tokens** | `0` |
| **Prompt Tokens** | `0` |
| **Completion Tokens** | `0` |
| **Reasoning Tokens** | `0` |
"""

    return f"""### 📊 Token Usage (Accumulated)
| Metric | Value |
| :--- | :--- |
| **Total Cost** | `${client_state.total_cost:.6f}` |
| **Total Tokens** | `{client_state.total_tokens:,}` |
| **Prompt Tokens** | `{client_state.total_prompt_tokens:,}` |
| **Completion Tokens** | `{client_state.total_completion_tokens:,}` |
| **Reasoning Tokens** | `{client_state.total_reasoning_tokens:,}` |
"""


def change_model(model_name, client_state):
    if client_state and model_name in ALLOWED_MODELS:
        client_state.model = model_name
    return client_state


def respond(message, client_state, model_name=None):
    # Ensure client exists
    if client_state is None:
        client_state = get_chatbot_client()

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

    # Yield 1: Direct list of dicts + tool history
    yield (
        "",
        preview_history,
        current_tool_history,
        current_reasoning_history,
        current_usage_info,
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
        client_state,
    )

    # Handle tool calls using a separate thread for UI responsiveness
    t = threading.Thread(target=client_state.get_tool_responses)
    t.start()

    # Poll thread status and yield updates to UI
    while t.is_alive():
        # Wait up to 5 seconds for the thread to finish
        t.join(timeout=5)
        # If still alive, yield an update to show we are still processing
        if t.is_alive():
            yield (
                "",
                client_state.clean_chat_history
                + [{"role": "assistant", "content": "..."}],
                extract_tool_info(client_state),
                extract_reasoning_info(client_state),
                extract_usage_info(client_state),
                client_state,
            )

    # Ensure thread is fully joined
    t.join()

    # Yield 3: Final state
    yield (
        "",
        client_state.clean_chat_history
        + [{"role": "assistant", "content": "--end of response--"}],
        extract_tool_info(client_state),
        extract_reasoning_info(client_state),
        extract_usage_info(client_state),
        client_state,
    )
