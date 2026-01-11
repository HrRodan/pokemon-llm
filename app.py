import gradio as gr
from chatbot import get_chatbot_client
from answer import respond, change_model


with gr.Blocks() as app:
    gr.Markdown("# Pokémon Chatbot")

    # Create unique client per session
    client_state = gr.State(get_chatbot_client)

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
