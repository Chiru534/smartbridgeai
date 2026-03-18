import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(r"c:\Users\chiranjeevi madem\OneDrive\Документы\New folder\SmartbridgePlatform\backend")

from platform_core.github_workspace import _summarize_github_text

class DummyRequest:
    model = "llama-3.1-8b-instant"

async def main():
    try:
        req = DummyRequest()
        res = await _summarize_github_text(
            model=req.model,
            context_label="test:file",
            user_request="summarize this file",
            content="This is some content to summarize."
        )
        print("Summary Result:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure env is loaded
    from dotenv import load_dotenv
    load_dotenv(r"c:\Users\chiranjeevi madem\OneDrive\Документы\New folder\SmartbridgePlatform\backend\.env")
    asyncio.run(main())
