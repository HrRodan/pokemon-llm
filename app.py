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


def respond(message, client_state):
    # Ensure client exists
    if client_state is None:
        client_state = get_llm_client()

    # Optimistic update: Show user message immediately
    current_history = client_state.clean_chat_history
    # Create a temporary display history with the new user message AND pending indicator
    preview_history = current_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "..."},
    ]

    # Yield 1: Direct list of dicts
    yield "", preview_history, client_state

    # Query logic
    response = client_state.query(message)
    # Handle tool calls
    response = client_state.get_tool_responses()

    # Yield 2: Direct list of dicts
    yield "", client_state.clean_chat_history, client_state


with gr.Blocks() as app:
    gr.Markdown("# Pokémon Chatbot")

    # Create unique client per session
    client_state = gr.State(get_llm_client)

    # Chatbot without explicit type, allowing auto-detection of dict items
    chatbot = gr.Chatbot(height=500)

    with gr.Row():
        msg = gr.Textbox(
            scale=4,
            placeholder="Ask me about Pokémon...",
            show_label=False,
            container=False,
        )
        btn = gr.Button("Submit", scale=1, variant="primary")

    # Bind events
    dataset = gr.Dataset(
        components=[msg],
        samples=[
            ["How do I evolve Eevee?"],
            ["Tell me about Pikachu."],
            ["Tell me something about fire Pokemon."]
        ],
    )

    def fill_input(sample):
        return sample[0]

    dataset.click(fill_input, inputs=dataset, outputs=msg)

    msg.submit(
        respond, inputs=[msg, client_state], outputs=[msg, chatbot, client_state]
    )
    btn.click(respond, inputs=[msg, client_state], outputs=[msg, chatbot, client_state])

if __name__ == "__main__":
    app.launch(inbrowser=True)
