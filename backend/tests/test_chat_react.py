import httpx
import asyncio

async def test_chat():
    tokens = {
        "admin": "admin-token-123"
    }
    
    headers = {
        "Authorization": f"Bearer {tokens['admin']}",
        "Content-Type": "application/json"
    }

    test_queries = [
        "What time is it now?",
        "Latest news in India today",
        "Create task for Ravi to check news",
        "Hi"
    ]
    
    async with httpx.AsyncClient() as client:
        for query in test_queries:
            print(f"\n\n===== TEST: '{query}' =====")
            try:
                response = await client.post(
                    "http://127.0.0.1:8000/api/chat",
                    headers=headers,
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "user", "content": query}
                        ]
                    },
                    timeout=60.0
                )
                print(f"Status: {response.status_code}")
                print(f"Response:\n{response.json().get('reply')}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())
