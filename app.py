import gradio as gr
from chatbot import get_chatbot_client
from answer import respond, change_model

# 🎨 Modern Theme Definition
# Default theme requested

# 📱 Application Layout
with gr.Blocks(title="Pokémon AI Agent", fill_height=True) as app:
    # State Management
    client_state = gr.State(get_chatbot_client)

    # Header
    with gr.Row():
        gr.Markdown(
            """
            # ⚡ Pokémon AI Agent
            *Your intelligent companion for all things Pokémon. Powered by Vector Search & Function Calling.*
            """
        )

    with gr.Row(equal_height=True):
        # 💬 Left Column: Chat Interface
        with gr.Column(scale=3, min_width=400):
            chatbot = gr.Chatbot(
                height=600,
                label="Conversation",
                avatar_images=(
                    None,
                    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
                ),
                render=True,
            )

            with gr.Row():
                msg = gr.Textbox(
                    scale=4,
                    placeholder="Ask about Pokémon stats, moves, items, or lore...",
                    show_label=False,
                    container=False,
                    autofocus=True,
                )
                btn = gr.Button("Send", scale=1, variant="primary")

            # Examples for User Onboarding
            gr.Examples(
                examples=[
                    ["Tell me about a top fire pokemon."],
                    ["What Pokemon look like a dog?"],
                    ["Describe the move Hyper Beam."],
                    ["Who is Eevee?"],
                    ["How do I evolve Scyther?"],
                    ["What is the average attack of all fire pokemon with defense lower 100? Search for type 1 and type 2"]
                ],
                inputs=msg,
                label="📝 Try these examples (Vector DB & Tools)",
                elem_id="example-prompts",
            )

        # 🛠️ Right Column: Tools & Settings
        with gr.Column(scale=2, min_width=300):
            with gr.Tabs():
                with gr.TabItem("🛠️ Tool Activity"):
                    tool_output = gr.Chatbot(
                        height=550,
                        label="Tool Logs",
                        show_label=False,
                    )

                with gr.TabItem("🧠 Reasoning History"):
                    reasoning_output = gr.Chatbot(
                        height=550,
                        label="Reasoning History",
                        show_label=False,
                    )

                with gr.TabItem("⚙️ Settings"):
                    gr.Markdown("### 🧠 Model Configuration")
                    model_selector = gr.Dropdown(
                        choices=[
                            "deepseek/deepseek-v3.2",
                            "openai/gpt-oss-120b",
                            "openai/gpt-oss-20b",
                            "xiaomi/mimo-v2-flash:free",
                            "x-ai/grok-4.1-fast",
                            "nvidia/nemotron-3-nano-30b-a3b",
                        ],
                        value="deepseek/deepseek-v3.2",
                        label="Select LLM",
                        interactive=True,
                        info="Choose the underlying model processing your requests.",
                    )

    # 🔗 Event Wiring
    msg.submit(
        respond,
        inputs=[msg, client_state],
        outputs=[msg, chatbot, tool_output, reasoning_output, client_state],
    )

    btn.click(
        respond,
        inputs=[msg, client_state],
        outputs=[msg, chatbot, tool_output, reasoning_output, client_state],
    )

    # Model Change Handler
    model_selector.change(
        change_model, inputs=[model_selector, client_state], outputs=[client_state]
    )

if __name__ == "__main__":
    app.launch(inbrowser=True)
