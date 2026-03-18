import asyncio
from llm_client import llm_client

async def test_tools():
    # Define a dummy tool
    tools = [{
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    }
                },
                "required": ["location"]
            }
        }
    }]
    
    messages = [
        {"role": "user", "content": "What is the weather like in New York?"}
    ]
    
    print("Sending request to LLM with tools...")
    try:
        resp = await llm_client.chat_completion(
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print("Response JSON:")
        import json
        print(json.dumps(data, indent=2))
        
        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls")
        if tool_calls:
            print("\n✅ Success! Tool calls output found:")
            for tc in tool_calls:
                print(f" - ID: {tc.get('id')}")
                print(f" - Function: {tc.get('function', {}).get('name')}")
                print(f" - Args: {tc.get('function', {}).get('arguments')}")
        else:
            print("\n❌ No structured tool_calls found in the response object.")
            print(f"Message Content: {message.get('content')}")
            
    except Exception as e:
        print(f"Error testing tools: {e}")

if __name__ == "__main__":
    asyncio.run(test_tools())
