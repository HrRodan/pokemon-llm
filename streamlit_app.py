import streamlit as st
import threading
import time
from utils.ui_utils import (
    get_agent_client,
    respond,
    format_empty_usage,
    extract_tool_info,
    extract_reasoning_info,
    extract_usage_info,
)
from utils.config import settings
from utils.logger import get_log_buffer

# --- Page Configuration ---
st.set_page_config(
    page_title="Pokémon AI Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session State Initialization ---
if "agent" not in st.session_state:
    st.session_state.agent = get_agent_client()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "tool_history" not in st.session_state:
    st.session_state.tool_history = []

if "reasoning_history" not in st.session_state:
    st.session_state.reasoning_history = extract_reasoning_info(None)

if "usage_info" not in st.session_state:
    st.session_state.usage_info = format_empty_usage()

if "logs" not in st.session_state:
    st.session_state.logs = ""

# --- Sidebar: Settings ---
with st.sidebar:
    st.title("⚙️ Settings")

    st.markdown("### 🧠 Model Configuration")

    selected_model = st.selectbox(
        "Select LLM",
        options=settings.ALLOWED_MODELS,
        index=settings.ALLOWED_MODELS.index(st.session_state.agent.model)
        if st.session_state.agent.model in settings.ALLOWED_MODELS
        else 0,
        help="Choose the underlying model processing your requests.",
    )

    if selected_model != st.session_state.agent.model:
        st.session_state.agent.model = selected_model
        st.toast(f"Model changed to {selected_model}")

    st.divider()
    if st.button("Clear Conversation", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.agent = get_agent_client(model=selected_model)
        st.session_state.tool_history = []
        st.session_state.reasoning_history = extract_reasoning_info(None)
        st.session_state.usage_info = format_empty_usage()
        st.session_state.logs = ""
        st.rerun()

    st.markdown("---")
    st.caption("⚡ Pokémon AI Agent v1.0")

# --- Custom CSS for Styling ---
bg_color = "#ffffff"
text_color = "#31333F"
border_color = "#e0e2e6"
secondary_bg = "#f0f2f6"
assistant_bg = "#f8f9fb"
user_bg = "#ffffff"
sidebar_bg = "#f0f2f6"

st.markdown(
    f"""
<style>
    /* Global Background and Text Color */
    .stApp {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    
    /* Narrower Sidebar */
    [data-testid="stSidebar"] {{
        min-width: 220px !important;
        max-width: 220px !important;
        background-color: {sidebar_bg} !important;
    }}
    
    /* Reduce Main Padding */
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
    }}

    /* Chat Message Styling */
    div[data-testid="stChatMessage"] {{
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        border: 1px solid {border_color};
    }}
    
    /* Assistant specific styling */
    div[data-testid="stChatMessage"]:has(img[src*="pokemon"]) {{
        background-color: {assistant_bg} !important;
        border-left: 4px solid #ff4b4b !important;
    }}
    
    /* User specific styling */
    div[data-testid="stChatMessage"]:not(:has(img[src*="pokemon"])) {{
        background-color: {user_bg} !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}

    /* Narrower Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background-color: transparent;
        padding: 0px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        border-radius: 15px;
        padding: 4px 12px;
        background-color: {secondary_bg} !important;
        border: 1px solid {border_color} !important;
        color: {text_color} !important;
        transition: all 0.2s ease;
        font-size: 0.85rem;
        height: auto;
    }}
    
    .stTabs [aria-selected="true"] {{
        background-color: #ff4b4b !important;
        color: white !important;
        border-color: #ff4b4b !important;
    }}
    
    /* Hide the default tab underline */
    .stTabs [data-baseweb="tab-highlight"] {{
        display: none;
    }}

    /* Scrollbar Styling */
    ::-webkit-scrollbar {{
        width: 6px;
    }}
    ::-webkit-scrollbar-track {{
        background: transparent;
    }}
    ::-webkit-scrollbar-thumb {{
        background: {border_color};
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: #ff4b4b;
    }}
</style>
""",
    unsafe_allow_html=True,
)

# --- Header ---
st.title("⚡ Pokémon AI Agent")
st.markdown(
    "*Your intelligent companion for all things Pokémon. Powered by Vector Search & Function Calling.*"
)

# --- Layout: Main Content ---
col_chat, col_aux = st.columns([3, 2], gap="medium")

# --- Column 2: Tools & Settings ---
with col_aux:
    # Use tabs but ensure they align with the left chat container top
    tabs = st.tabs(["🛠️ Tool Activity", "🧠 Reasoning", "📜 Logs", "📊 Usage"])

    with tabs[0]:
        with st.container(height=650, border=True):
            st.markdown("### Tool Execution History")
            tool_placeholder = st.empty()

    with tabs[1]:
        with st.container(height=650, border=True):
            st.markdown("### Model Reasoning")
            reasoning_placeholder = st.empty()

    with tabs[2]:
        with st.container(height=650, border=True):
            st.markdown("### Real-time Logs")
            log_placeholder = st.empty()

    with tabs[3]:
        with st.container(height=650, border=True):
            usage_placeholder = st.empty()


# Function to render auxiliary content into placeholders
def render_aux_content():
    with tool_placeholder.container():
        if not st.session_state.tool_history:
            st.info("No tool activity yet.")
        else:
            for tool_msg in st.session_state.tool_history:
                with st.chat_message(tool_msg["role"]):
                    st.markdown(tool_msg["content"])

    with reasoning_placeholder.container():
        for r_msg in st.session_state.reasoning_history:
            if r_msg["role"] == "assistant":
                with st.chat_message("assistant"):
                    st.markdown(r_msg["content"])
            else:
                st.markdown(r_msg["content"])

    # Use the logger's built-in HTML formatter and scrollable div
    log_placeholder.markdown(st.session_state.logs, unsafe_allow_html=True)
    usage_placeholder.markdown(st.session_state.usage_info)


# Initial render
render_aux_content()

# --- Column 1: Chat Interface ---
with col_chat:
    # Match the height of the right side (including tab bar overhead)
    chat_container = st.container(height=700)

    with chat_container:
        for msg in st.session_state.messages:
            avatar = (
                "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"
                if msg["role"] == "assistant"
                else None
            )
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # Suggestion Chips (Examples)
    EXAMPLES = [
        "Tell me about a top fire pokemon.",
        "What Pokemon look like a dog?",
        "Describe the move Hyper Beam.",
        "Who is Eevee?",
        "How do I evolve Scyther?",
        "What is the average attack of all fire pokemon with defense lower 100? Search for type 1 and type 2",
        "Count how many Ghost types were introduced in Generation 3.",
        "I need a tanky Water type that is immune to Electric attacks. Who should I use?",
        "How does the ability 'Guts' interact with the 'Burn' status condition?",
    ]

    def copy_example_to_prompt():
        if st.session_state.examples_pills:
            st.session_state.user_prompt = st.session_state.examples_pills

    # Use a key for chat_input to allow programmatic population
    prompt = st.chat_input(
        "Ask about Pokémon stats, moves, items, or lore...", key="user_prompt"
    )

    # Examples are now below the input box
    st.pills(
        "📝 Try these examples:",
        EXAMPLES,
        key="examples_pills",
        on_change=copy_example_to_prompt,
        label_visibility="collapsed",
    )

    if prompt:
        # 1. Add user message to UI state (will be rendered on next rerun or manually now)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        # 2. Process with Agent
        with chat_container:
            with st.chat_message(
                "assistant",
                avatar="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
            ):
                response_placeholder = st.empty()
                response_placeholder.markdown("Thinking...")

                # Iterate through the generator
                for (
                    _,
                    chatbot,
                    tool_out,
                    reasoning_out,
                    usage_out,
                    logs_out,
                    _,
                ) in respond(prompt, st.session_state.agent):
                    # Update session state
                    st.session_state.tool_history = tool_out
                    st.session_state.reasoning_history = reasoning_out
                    st.session_state.usage_info = usage_out
                    st.session_state.logs = logs_out

                    # Update auxiliary placeholders
                    render_aux_content()

                    # Update main response placeholder
                    if chatbot:
                        last_msg = chatbot[-1]
                        if last_msg["role"] == "assistant":
                            content = last_msg["content"]
                            if content == "...":
                                response_placeholder.markdown("Processing tools...")
                            else:
                                response_placeholder.markdown(content)

        # After loop finishes, sync final history and rerun to clean up UI
        st.session_state.messages = st.session_state.agent.clean_chat_history
        st.rerun()

# --- Bottom Note ---
st.markdown("---")
st.caption("Built with Streamlit & Pokémon AI Engine.")
