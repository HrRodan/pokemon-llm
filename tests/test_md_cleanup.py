import json
import pytest
from tools.web_content import fetch_page_as_markdown, FetchPageInput

@pytest.mark.integration
def test_markdown_cleanup_optimization_remains_efficient():
    """
    Test that the HTML-to-Markdown unwrapping and cleanup logic prevents token explosion.
    Before optimizations, Bulbapedia could generate ~190k chars; now it should be < 100k.
    """
    urls = [
        "https://bulbapedia.bulbagarden.net/wiki/Bulbasaur_(Pok%C3%A9mon)",
        "https://en.wikipedia.org/wiki/Bulbasaur",
    ]
    
    for url in urls:
        result_json = fetch_page_as_markdown(FetchPageInput(url=url, use_stealth=True, selector="main" if "wikipedia" in url else None))
        result = json.loads(result_json)
        
        assert "error" not in result, f"Failed to fetch {url}: {result.get('error')}"
        assert "markdown" in result
        assert len(result["markdown"]) > 5000, f"Markdown for {url} is suspiciously short, parsing may be broken."
        assert len(result["markdown"]) < 80000, f"Markdown for {url} is severely bloated ({len(result['markdown'])} chars). Efficiency optimization failed."
