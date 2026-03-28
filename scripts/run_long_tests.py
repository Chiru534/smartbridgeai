import asyncio
import sys

sys.stdout.reconfigure(encoding='utf-8')
from backend.llm_agent import call_groq_api, ChatRequest, ChatMessage

test_queries = [
    "Write a detailed 500-word explanation of Python decorators",
    "Tell me a long story about a day in Hyderabad"
]

async def run_tests():
    for q in test_queries:
        req = ChatRequest(
            model="llama-3.3-70b-versatile",
            messages=[ChatMessage(role="user", content=q)]
        )
        print(f"=== TEST: {q} ===")
        res = await call_groq_api(req)
        print(res)
        print("="*40 + "\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
