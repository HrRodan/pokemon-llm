## Overall Goal

The goal is to create a set of tools than can be used to search the web for information. The tools itself should be generic and not specific to pokemon, but can be tuned to search special pokemon related websites like bulbapedia.bulbagarden.net.

## Tools

### Google WebSearchTool

This tool utilizes Serper API to search the web for information. An optional parameter can be used to limit the search to a specific website.

```python

import requests
url = "https://google.serper.dev/search"

payload = {
  "q": "charizard site:///bulbapedia.bulbagarden.net"
}
headers = {
  'X-API-KEY': 'f0d7837d400aac5f20576f359811f83c06f1af57',
  'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, json=payload)

print(response.text)

```

### PokemonWebSearchTool

This tool should be able to search the web for pokemon related information using a search engine.

### PokemonWebSearchTool

This tool should be able to search the web for pokemon related information using a search engine.
