import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_models():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in .env")
        return
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
        models = resp.json().get("data", [])
        
        for m in models:
            model_id = m["id"]
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5
            }
            res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            if res.status_code == 200:
                print(f"{model_id}: OK")
            else:
                print(f"{model_id}: FAILED ({res.status_code})")

asyncio.run(test_models())
