import httpx
import json

async def test_ollama():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("http://localhost:11434/api/chat", json={
                "model": "alibayram/smollm3",
                "messages": [{"role": "user", "content": "Hello!"}],
                "stream": False
            })
            print(resp.status_code)
            print(resp.json())
    except Exception as e:
        print(f"Error: {e}")

import asyncio
asyncio.run(test_ollama())
