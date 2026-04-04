from langfuse import observe, get_client
from openai import OpenAI

client = OpenAI()
langfuse = get_client()

@observe(as_type="generation")
def call_with_tools(user_message: str):
    # Define your tools
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city, e.g. San Francisco",
                    },
                },
                "required": ["location"],
            },
        },
    }]
    
    # Update the current generation with input and model info
    langfuse.update_current_generation(
        model="gpt-4o",
        input=[{"role": "user", "content": user_message}],
        metadata={"tools": tools}
    )
    
    # Make the OpenAI call
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_message}],
        tools=tools,
        tool_choice="auto"
    )
    
    # Update with output and usage
    langfuse.update_current_generation(
        output=response.choices[0].message.content,
        usage_details={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens
        }
    )
    
    return response

# Call the function
call_with_tools("What's the weather like in Berlin?")