# Web Search & Content Extraction Tools

## Goal

Build two generic, reusable tools for web information retrieval:

1. **`google_search`** — Search Google and return structured results.
2. **`fetch_page_as_markdown`** — Fetch a URL and return its main content as clean Markdown.

Both tools are generic (not Pokémon-specific), but must support site-scoped search (e.g. `site:bulbapedia.bulbagarden.net`) for domain-specific use cases.

> [!NOTE]
> The outputs of these tools will later feed into a RAG knowledge base via vector
> embeddings. Design output schemas with that downstream use in mind — clean text,
> stable structure, and predictable field names matter.

---

## Dependencies

| Package | Purpose | Install |
|---|---|---|
| `scrapling` | Fetching & parsing HTML (anti-bot, stealth, JS rendering) | `uv add "scrapling[all]>=0.4.2"` |
| `html-to-markdown` | High-performance HTML → Markdown conversion (Rust core) | `uv add html-to-markdown` |

Both are **new** dependencies — neither is currently in `pyproject.toml`.

After installing `scrapling`, run once:

```bash
uv run scrapling install --force
```

---

## Tool 1: `google_search`

### How It Works

1. Construct a Google search URL from the `query` string.
   - If `site_restrict` is provided, prepend `site:<domain>` to the query.
2. Fetch the Google results page using **Scrapling** (`StealthyFetcher`).
   - Google actively blocks automated access — `Fetcher.get()` will fail.
   - Use `StealthyFetcher.fetch()` with `google_search=True` to handle bot detection.
3. Parse the result HTML to extract individual result entries (title, URL, snippet).
4. Respect `max_results` to limit the output list length.
5. Return a validated `GoogleSearchResult` Pydantic model.

### Pydantic Schema

```python
from pydantic import BaseModel, Field

class SearchResultItem(BaseModel):
    """A single Google search result entry."""
    title: str = Field(description="Title of the search result.")
    url: str = Field(description="URL of the search result.")
    snippet: str = Field(description="Text snippet / description from Google.")

class GoogleSearchInput(BaseModel):
    """Input parameters for Google web search."""
    query: str = Field(description="The search query string.")
    site_restrict: str | None = Field(
        default=None,
        description="Optional domain to restrict results to (e.g. 'bulbapedia.bulbagarden.net')."
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return."
    )

class GoogleSearchResult(BaseModel):
    """Structured output from a Google search."""
    query: str = Field(description="The original search query (including site: prefix if used).")
    results: list[SearchResultItem] = Field(description="List of search result entries.")
    total_returned: int = Field(description="Number of results actually returned.")
```

### Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Google blocks request or returns CAPTCHA | Use `StealthyFetcher` with `google_search=True`. Add retry with back-off. |
| Google changes HTML structure | CSS selectors may break. Use Scrapling's adaptive parsing where possible. Document selectors clearly for easy updates. |
| Empty results for niche queries | Return empty list gracefully, never raise. |

### Registration

```python
@tool(schema=GoogleSearchInput)
def google_search(args: GoogleSearchInput) -> str:
    """Search Google and return structured results as JSON."""
    ...

TOOL_FUNCTIONS = [google_search]
```

---

## Tool 2: `fetch_page_as_markdown`

### How It Works

1. Fetch the target URL using **Scrapling**.
   - Start with `Fetcher.get()` for speed.
   - If the page requires JS rendering (SPA, dynamic content), escalate to `DynamicFetcher.fetch()`.
   - Accept an optional `use_stealth` flag for protected sites.
2. Extract the **main content** element only — strip nav, header, footer, sidebar, ads.
   - Use Scrapling's CSS selector to target `main`, `article`, `#content`, or similar.
   - Fallback to `body` if no semantic content element is found.
3. Convert the extracted HTML to Markdown using `html-to-markdown`.
   - Use the library's built-in sanitization (ammonia-based).
4. Return a validated `PageMarkdownResult` Pydantic model.

### Pydantic Schema

```python
class FetchPageInput(BaseModel):
    """Input parameters for fetching a web page as Markdown."""
    url: str = Field(description="The URL of the page to fetch.")
    css_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to extract specific content (e.g. 'article', '#main-content'). "
                    "If omitted, auto-detects the main content area."
    )
    use_stealth: bool = Field(
        default=False,
        description="Use stealth browser mode for sites with anti-bot protection."
    )

class PageMarkdownResult(BaseModel):
    """Structured output from fetching and converting a web page."""
    url: str = Field(description="The URL that was fetched.")
    title: str = Field(description="The page title extracted from <title> or <h1>.")
    markdown: str = Field(description="The sanitized Markdown content of the page.")
```

### Content Extraction Strategy

The main challenge is isolating useful content from boilerplate. Strategy:

1. **Explicit selector** — If `css_selector` is provided, use it directly.
2. **Semantic auto-detect** — Try CSS selectors in priority order:
   `article`, `main`, `[role="main"]`, `#content`, `#mw-content-text` (for wikis like Bulbapedia), `.mw-parser-output`.
3. **Fallback** — Use `body` and strip known boilerplate tags: `nav`, `header`, `footer`, `aside`, `script`, `style`, `noscript`.

### Registration

```python
@tool(schema=FetchPageInput)
def fetch_page_as_markdown(args: FetchPageInput) -> str:
    """Fetch a web page and return its main content as clean Markdown."""
    ...

TOOL_FUNCTIONS = [fetch_page_as_markdown]
```

---

## Implementation Guidelines

- Follow existing patterns in `tools/tech_data_tools.py`:
  - Pydantic models for input/output schemas.
  - `@tool(schema=...)` decorator from `ai_tools.tool_definition`.
  - Export a `TOOL_FUNCTIONS` list.
- All public functions must have type hints and docstrings (Google style).
- Handle errors gracefully — return error info in the result model, never raise unhandled exceptions.
- Log key events (fetch attempts, retries, selector used) via `logging`.

---

## File Structure

```
tools/
├── web_search.py          # [NEW] google_search tool
├── web_content.py         # [NEW] fetch_page_as_markdown tool
└── task_websearch_tool.md # This plan
```

> [!TIP]
> Splitting into two files keeps each tool independently testable and avoids
> coupling the Google-scraping logic with the generic page fetcher.

---

## Verification Plan

### Unit Tests

Create `tests/unit/test_web_search.py` and `tests/unit/test_web_content.py`:

- **Schema validation** — Verify Pydantic models accept valid input and reject invalid input.
- **Content extraction logic** — Test the CSS-selector priority chain with mock HTML.
- **Markdown conversion** — Feed known HTML snippets and assert expected Markdown output.
- **Error handling** — Simulate network failures and verify graceful error responses.

Run with:
```bash
uv run pytest tests/unit/test_web_search.py tests/unit/test_web_content.py -v
```

### Integration Tests

Create `tests/integration/test_web_tools_live.py`:

- **`google_search`** — Search for `"Pikachu"` and verify results contain expected fields.
- **`google_search` with `site_restrict`** — Search `"Bulbasaur" site:bulbapedia.bulbagarden.net`.
- **`fetch_page_as_markdown`** — Fetch a stable public page (e.g. `https://example.com`) and verify Markdown output.
- **`fetch_page_as_markdown` on Bulbapedia** — Fetch a Pokémon wiki page and check content quality.

Run with:
```bash
uv run pytest tests/integration/test_web_tools_live.py -v
```

> [!IMPORTANT]
> Integration tests hit live websites and may be flaky. Mark them with
> `@pytest.mark.integration` so they can be excluded from CI runs.

### Manual Verification

Run each tool standalone and inspect the output:
```bash
uv run python -c "from tools.web_search import google_search; ..."
uv run python -c "from tools.web_content import fetch_page_as_markdown; ..."
```
