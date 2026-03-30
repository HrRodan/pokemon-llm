# Expand Web Content Tools

## Goal

Expand the `tools/web_content.py` module with three new `@tool`-decorated functions that give agents fine-grained control over **exploring**, **previewing**, and **structuring** web content. These tools fill the gap between URL discovery (`duckduckgo_search`) and full ingestion (`ingest_web_page`).

All new code lives in `tools/web_content.py`, following the same patterns as the existing `fetch_page_as_markdown`.

---

## Tool 1: `extract_page_links` — Link Discovery & Context

Fetch all content-relevant links from a web page, filter out boilerplate, and return each link enriched with contextual metadata. Gives the agent a token-efficient "table of contents" of a page's link structure.

### `ExtractLinksInput` (Pydantic)

- `url: str` — The URL to extract links from.
- `use_stealth: bool = False` — Stealth mode for anti-bot sites.
- `include_external: bool = False` — Include cross-domain links.
- `domain_filter: str | None = None` — Only return links whose domain contains this string (e.g. `"bulbapedia.bulbagarden.net"`). Overrides `include_external`.
- `max_links: int = 50` — Cap on returned links (1–200).

### `LinkItem` (Pydantic)

- `url: str` — Absolute URL.
- `title: str` — Anchor text.
- `context: str` — Surrounding text snippet (~150 chars).
- `section: str` — Nearest heading above the link.

### `ExtractLinksResult` (Pydantic)

- `source_url`, `source_title`, `total_found`, `total_after_filter`, `links`, `error`

### Extraction Strategy

1. Fetch page via `_fetch_page()`.
2. Scope to main content area (reuse `_MAIN_CONTENT_SELECTORS` chain).
3. Extract all `<a href>` tags.
4. Normalize relative → absolute URLs (`urllib.parse.urljoin`).
5. Filter boilerplate via regex blocklist:
   - Privacy/legal: `impressum`, `datenschutz`, `privacy`, `terms`, `cookie`
   - Auth: `login`, `sign-in`, `register`, `account`
   - Social: `facebook.com`, `twitter.com`, `youtube.com`, etc.
   - Files: `.css`, `.js`, `.png`, `.jpg`, `.svg`, etc.
   - Protocols: `mailto:`, `tel:`, `javascript:`, `#`
   - MediaWiki internals: `Special:`, `User:`, `Talk:`, `Template:`, `Category:`
6. Apply domain filter (`domain_filter` > `include_external` > same-domain).
7. Skip empty anchor text (image-only links).
8. Deduplicate by URL (keep first occurrence).
9. Enrich each link with:
   - `context` — parent element's text, truncated around the anchor.
   - `section` — walk up DOM to find nearest `h1-h6`.
10. Cap at `max_links`.

---

## Tool 2: `summarize_page` — Quick Page Preview

Generate a concise extractive preview of a web page. No LLM call — purely rule-based, zero cost.

### `SummarizePageInput` (Pydantic)

- `url: str`, `css_selector: str | None = None`, `use_stealth: bool = False`

### `PageSummaryResult` (Pydantic)

- `url`, `title`, `meta_description`, `summary`, `headings: list[str]`, `word_count`, `error`

### Extraction Strategy

1. Fetch page via `_fetch_page()`.
2. Extract `<meta name="description">` / `<meta property="og:description">`.
3. Convert to markdown via existing pipeline.
4. Parse all `## Heading` lines from markdown.
5. Extract first 3 non-heading, non-table paragraphs (>30 chars each).
6. Count words.

---

## Tool 3: `extract_structured_data` — Tables → JSON

Extract HTML `<table>` elements from a page into structured JSON (headers + rows). Useful for stats, type charts, move lists.

### `ExtractStructuredDataInput` (Pydantic)

- `url: str`, `css_selector: str | None = None`, `use_stealth: bool = False`
- `min_rows: int = 2` — Minimum data rows to include a table (1–100).
- `min_columns: int = 2` — Minimum columns to include (1–50).

### `TableData` (Pydantic)

- `caption: str`, `headers: list[str]`, `rows: list[list[str]]`, `row_count`, `column_count`

### `ExtractStructuredDataResult` (Pydantic)

- `url`, `title`, `tables_found`, `tables: list[TableData]`, `error`

### Extraction Strategy

1. Fetch page via `_fetch_page()`.
2. Scope to content area (or explicit `css_selector`).
3. Find all `<table>` elements.
4. For each table:
   - Extract `<caption>` text.
   - Extract `<th>` cells as headers (fallback: first `<tr>`).
   - Extract `<td>` rows as data.
   - Skip if rows < `min_rows` or columns < `min_columns`.
5. Return list of `TableData`.

---

## Internal Refactors

### `_fetch_page()` — Shared Fetch Helper

Extract the duplicated Scrapling fetch logic from `fetch_page_as_markdown` into a reusable private function:

```python
def _fetch_page(url: str, use_stealth: bool = False):
    if use_stealth:
        return _run_stealthy_fetch(url)
    return Fetcher.get(url, stealthy_headers=True, verify=False)
```

Update `fetch_page_as_markdown`, `extract_page_links`, `summarize_page`, and `extract_structured_data` to call `_fetch_page()`.

---

## Other Useful Tools (Recommendations)

| Tool | Purpose | Priority |
|------|---------|----------|
| **Per-domain rate limiter** | Middleware in `_fetch_page` to enforce minimum delays between requests to the same domain. Prevents IP bans. | **High** |
| **`check_page_freshness`** | HTTP HEAD request for `Last-Modified`/`ETag` headers before fetching. | Medium |
| **`extract_sitemap`** | Parse `/sitemap.xml` to discover all page URLs on a domain. | Medium |
| **`page_diff`** | Compare current page vs. last saved version in `WEB_SCRAPER_DIR`. | Medium |
| **`extract_metadata`** | Extract OpenGraph, JSON-LD, `<meta>` tags for author, date, description. | Low |
| **`detect_content_type`** | HEAD request for `Content-Type` to avoid fetching PDFs, images, etc. | Low |

---

## Module Exports

```python
TOOL_FUNCTIONS = [
    fetch_page_as_markdown,
    extract_page_links,
    summarize_page,
    extract_structured_data,
]
```

---

## Implementation Guidelines

- Follow existing patterns in `tools/web_content.py`:
  - Pydantic `BaseModel` for input/output schemas with `Field(description=...)`.
  - `@tool(schema=...)` decorator from `ai_tools.tool_definition`.
  - JSON-serialized return via `.model_dump_json()`.
  - All errors caught and returned in the result model — never raise.
  - Logging via `logging.getLogger(__name__)`.
- Type hints on all functions. Google-style docstrings.
- No AI slop — no unnecessary comments or reasoning artifacts.

---

## Verification Plan

### Unit Tests (`tests/unit/test_web_content_expand.py`)

Run: `uv run pytest tests/unit/test_web_content_expand.py -v`

- Boilerplate link filtering (each pattern category).
- URL normalization (relative paths, fragments, invalid schemes).
- Domain filtering (`domain_filter` set, `include_external`, case insensitivity).
- Context extraction (mock HTML with headings and paragraphs).
- Heading extraction from markdown.
- Paragraph extraction (skip headings, tables, lists, short fragments).
- Table extraction (headers/no-headers, `min_rows`/`min_columns` filtering).
- Schema validation (valid/invalid input for all Pydantic models).

### Integration Tests (`tests/integration/test_web_content_expand.py`)

Run: `uv run pytest tests/integration/test_web_content_expand.py -v`

- `extract_page_links` on Bulbapedia Pikachu page → content-relevant links with context.
- `extract_page_links` with `domain_filter="bulbapedia.bulbagarden.net"` → only Bulbapedia links.
- `summarize_page` on a known page → title, headings, word count > 0.
- `extract_structured_data` on a Pokémon page → at least one table with stats.
