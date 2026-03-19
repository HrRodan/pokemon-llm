## Overall Goal

The goal is to create a set of tools than can be used to search the web for information and extract the content of a website in a token efficient format. The tools itself should be generic and not specific to pokemon, but can be tuned to search special pokemon related websites like bulbapedia.bulbagarden.net. 

Later the outputs of the tools should be used to create a knowledge base via vector embeddings and rag retrieval (will be implemented later). Keep that in mind when designing the tools.

## Impplementation guidelines

- Adhere to coding guidelines
- Test with differen websites
- Write tests for each tool
- Use pydantic for input and output definitions

## Tools

### Google WebSearchTool

This tool uses the scrapling python library (see skills) to get search results from google. The search results are parsed via this scrapling package and returned as strict json (use pydantic class to define output). The output should contain the title, url and snippet of each search result. Add Option (via site://) to restrict the search to a specific website. Add option to limit the number of results.

Output is a json object with the following fields for each query result:
- title: the title of the search result
- url: the url of the search result
- snippet: the snippet of the search result

### Fetch website and convert to markdown

This tool uses the scrapling python library (see skills) to fetch a website and convert it to markdown. The markdown conversion should be done via the html-to-markdown converter from https://github.com/kreuzberg-dev/html-to-markdown/tree/main?tab=readme-ov-file . Goal for the markdown representation is to have a token efficient representation of the website content. Remove all unnecessary junk, like headers, footers, sidebars, ads, etc, focus on the main content of the website. Use the functioanly of the scrapling and html-to-markdown library to achieve this. 

The output should a json object with the following fields, use pydantic to define the output:
- url: the url of the website
- title: the title of the website
- markdown: the sanitized markdown content of the website.
