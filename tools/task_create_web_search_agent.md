# Task: Create Web Search Agent

## 🎯 Goal
Implement a new specialized Agent (`WebSearchAgent`) designed to fetch real-time and obscure Pokémon information from the web. It will accomplish this by searching Bulbapedia, downloading relevant pages into the local vector database, and querying that ingested data to provide precise answers.

---

## 🛠️ Required Tools
The Web Search Agent will utilize a sequential pipeline of three powerful tools:

1. **`bulbapedia_search` (New Specialized Tool)**
   - **Purpose:** Searches the web to find the most relevant URL answering the user's query.
   - **Implementation:** Create a wrapper around the existing `google_search` tool that strictly hardcodes the parameter `site_restrict="bulbapedia.bulbagarden.net"`.
   - **Benefit:** Reduces the LLM's cognitive load and securely enforces the domain limit without relying on the agent to remember the `site_restrict` parameter.

2. **`ingest_web_page` (Existing Tool)**
   - **Purpose:** Downloads the content of the chosen URL and ingests it into the ChromaDB vector database for semantic retrieval.

3. **`query_web_content` (Existing Tool)**
   - **Purpose:** Performs a semantic search against the newly ingested database to find the exact paragraph answering the user's query.

---

## 🚦 Guidelines & System Prompt Logic
To ensure fast, cheap, and accurate answers—and to avoid infinite scraping loops—the agent's `SYSTEM_PROMPT` must strictly enforce the following behaviors:

### 1. Strict Execution Loop
The agent must execute its tools in a rigorous 1-2-3 sequential order:
  - First: Find the page (`bulbapedia_search`).
  - Second: Download the page (`ingest_web_page`).
  - Third: Extract the answer (`query_web_content`).

### 2. Strict Ingestion Limits
  - **Constraint:** The agent should ideally ingest only **1** website per user query, with an absolute maximum of **2** websites. Do not spam the website.

### 3. Refinement Strategy
  - **Constraint:** If `query_web_content` does not initially yield the correct answer from the ingested page, the agent must **refine its semantic query** for `query_web_content` first, rather than immediately firing another `bulbapedia_search` to download a new page.

### 4. Anti-Hallucination & Directness
  - **Constraint:** The agent must base its final answer **exclusively** on the extracted data from `query_web_content`—not on its general pre-trained knowledge.
  - **Constraint:** The output should be concise, factual, and direct without any conversational padding or filler.

---

## 🧩 Orchestrator Integration
The new Agent needs to be seamlessly integrated into the `PokemonAgent` orchestrator:

- Add `WebSearchAgent` to `agents/pokemon_agent.py`.
- Expose its tool (`run_web_search_agent(query)`).
- **Update the Orchestrator's System Prompt:** Introduce the Web Search Agent as the "Real-time & Deep Lore Specialist."
  - **When to trigger:** For deep lore not natively in the internal Tech/RAG DBs, specific anime episode summaries, game walkthrough details, or as the ultimate fallback when the other local agents fail to answer.
