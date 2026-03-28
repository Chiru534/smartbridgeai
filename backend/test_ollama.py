import asyncio
from llm_client import llm_client, ChatRequest, ChatMessage

async def test_connection():
    print("Testing connection to Ollama...")
    request = ChatRequest(
        messages=[ChatMessage(role="user", content="Hello! Can you confirm you are connected?")]
    )
    
    try:
        response = await llm_client.chat_completion(
            request=request,
            system_prompt="You are a helpful AI assistant."
        )
        data = response.json()
        message = data["choices"][0]["message"]["content"]
        print("\n--- RESPONSE FROM OLLAMA (alibayram/smollm3) ---")
        print(message)
        print("------------------------------------------------")
        print("Connection Successful!")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
