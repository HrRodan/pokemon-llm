from pokemon_tools.pokemon_client import PokemonAPIClient, TOOLS
import gradio as gr
from ai_tools.tools import LLMQuery

# Global resources
pokemon_client = PokemonAPIClient()
functions = [getattr(pokemon_client, tool["function"]["name"]) for tool in TOOLS]


def get_llm_client():
    return LLMQuery(
        system_prompt=pokemon_client.get_system_prompt(),
        functions=functions,
        tools=TOOLS,
        model="deepseek/deepseek-v3.2",
    )


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


def change_model(model_name, client_state):
    if client_state:
        client_state.model = model_name
    return client_state


def respond(message, client_state):
    # Ensure client exists
    if client_state is None:
        client_state = get_llm_client()

    # Optimistic update: Show user message immediately
    current_history = client_state.clean_chat_history
    preview_history = current_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "..."},
    ]

    current_tool_history = extract_tool_info(client_state)

    # Yield 1: Direct list of dicts + tool history
    yield "", preview_history, current_tool_history, client_state

    # Query logic
    response = client_state.query(message)

    # Yield 2: Show tool calls if any (before execution loop finishes)
    yield (
        "",
        client_state.clean_chat_history,
        extract_tool_info(client_state),
        client_state,
    )

    # Handle tool calls
    response = client_state.get_tool_responses()

    # Yield 3: Final state
    yield (
        "",
        client_state.clean_chat_history,
        extract_tool_info(client_state),
        client_state,
    )


with gr.Blocks() as app:
    gr.Markdown("# Pokémon Chatbot")

    # Create unique client per session
    client_state = gr.State(get_llm_client)

    with gr.Row():
        with gr.Column(scale=3):
            # Main Chatbot
            chatbot = gr.Chatbot(height=500, label="Chat History")

            with gr.Row():
                msg = gr.Textbox(
                    scale=4,
                    placeholder="Ask me about Pokémon...",
                    show_label=False,
                    container=False,
                )
                btn = gr.Button("Submit", scale=1, variant="primary")

            gr.Markdown("### ⚙️ Settings")
            model_selector = gr.Dropdown(
                choices=[
                    "deepseek/deepseek-v3.2",
                    "openai/gpt-oss-120b",
                    "openai/gpt-oss-20b",
                ],
                value="deepseek/deepseek-v3.2",
                label="Model",
                interactive=True,
            )

        with gr.Column(scale=2):
            # Settings and Tool Outputs

            gr.Markdown("### 🛠️ Tool Activity")
            tool_output = gr.Chatbot(
                height=500,
                label="Tool Output",
                show_label=True,
            )
    # Bind events
    dataset = gr.Dataset(
        components=[msg],
        samples=[
            ["How do I evolve Eevee?"],
            ["Tell me about Pikachu."],
            ["Tell me something about fire Pokemon."],
        ],
    )

    def fill_input(sample):
        return sample[0]

    dataset.click(fill_input, inputs=dataset, outputs=msg)

    # Update respond event to include tool_output
    msg.submit(
        respond,
        inputs=[msg, client_state],
        outputs=[msg, chatbot, tool_output, client_state],
    )
    btn.click(
        respond,
        inputs=[msg, client_state],
        outputs=[msg, chatbot, tool_output, client_state],
    )

    # Model change event
    model_selector.change(
        change_model, inputs=[model_selector, client_state], outputs=[client_state]
    )

if __name__ == "__main__":
    app.launch(inbrowser=True)
