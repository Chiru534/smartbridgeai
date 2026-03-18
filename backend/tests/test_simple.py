import asyncio
from llm_client import llm_client

async def test_simple():
    messages = [
        {"role": "user", "content": "Hello, what is 2+2?"}
    ]
    
    print("Sending simple request to LLM...")
    try:
        resp = await llm_client.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=100
        )
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print("Response:")
        print(data["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple())