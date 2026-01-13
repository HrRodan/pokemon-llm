# TASK: Create Tech Data Agent and Tech Database

## SUMMARY

Create a Database containing the technical data of the Pokemon universe extracted from the JSON files. The database will be used by the Tech Data Agent to answer technical questions about the Pokemon universe. The agent will use a tool to query the database. The tech agent in turn will be provided as a TOOL to the chatbot (the central orchestrator). The tech agent should be a highly specialized helper focused on understanding the schema of the database and helper for the chatbot.

Typical questions the Tech Data Agent should be able to answer:

- List all Pokemon of type fire with attack > 100 and defense < 50.
- List all pokemon with type fire and generation 1.
- What is the average defense value of all fire pokemon?
- List all moves of generation 1 with type fire
- Which Pokemons are weak against fire and electric?
- List all items with price > 1000
- List the top 10 most expensive items

## General Rules
- The code must be maintainable
- The code must be well documented
- The code must be expandable
- The implemented logic will be used for other agents, so the principial boilerplate should be reusable
- You may deviate from this description if you see fit. Find optimizations and improvements.

## Core components

### The database

- derived from the JSON files in the data/raw directory
- implemented as sqlite database
- contains technical data of items, pokemons and moves in separate tables
- does not contain flavor text, sprites, urls, etc.
- is in contrast to the RAG database focused on answering technical questions which are hard to answer with RAG
- located in the db_tech directory
- created by the create_tech_database.py script
- the schema of the database should be saved as a pydantic class and includ detailed information about the data and is the basis for the Tech Data Agent and the TOOL, e.g.:
    - include ranges
    - include descriptions
    - include possible values / enum for columns with fixed and low number of values (e.g. type, generation)
    - include examples for columns with lots of different values (e.g. names)
    - think about more metadata to help the Tech Data Agent formulate queries via the TOOL to the database
- convert datatypes if sensible, e.g. (id to int, Generation to int, is_default to bool)

### The Tech database query TOOL

- The tech database query tool is a tool which accepts a strict json format, converts it to a sql query and returns the result as Markdown
- included in tech_data_agent.py
- create the detailed schema for the json in form of a pydantic class which in turn is derived from the pydantic class of the database
- The json input will be created by the Tech Data Agent
- the json schema should support the standard sql query operations:
    - SELECT (e.g. Select pokemon, generation from pokemon ...)
    - WHERE (type = fire and generation = 1, smaller then, larger then, ...)
    - ORDER BY (e.g. order by attack desc)
    - LIMIT (e.g. limit 10)
    - group by (e.g. group by type)
    - Aggregation funtions (e.g. max, min, avg, sum, count)
    - NO JOINs
- The tool should check the the received json format against the pydantic class and return a specific error which helps the Tech Data Agent to formulate a correct query
- small, easily correctable errors in the json format should be accepted and corrected by the tool (e.g. missing quotes, wrong datatypes, etc.) 
- write the TOOL Json with descriptions which will be provided to the Tech Data Agent

### The Tech data Agent

- The Tech Data Agent accepts a query in natural language and translates this to a json format which is then provided to the TOOL
- Use response format with the Pydantic class of the TOOL
- The agent is an LLMQuery instance
- The tool calling is executed via the get_tool_responses to allow the agent to react on the result of the tool call and improve the query or correct it if errors are returned
- Create a fitting system prompt for the agent and its specialized task, encourage tool usage
- Agent should use a small and fast model like "openai/gpt-oss-20b"
- The agent outputs the final received markdown as a response, if necessary with a short explanation of the interpretation and the executed query. This allows the chatbot to react on the result of the tool call and include it in further steps.
- The agent should be returned by distinct function (e.g. create_tech_data_agent) to allow for easy reuse and several parallel intances of the chatbot
- The usage of history should be turned on to allow for reasoning



