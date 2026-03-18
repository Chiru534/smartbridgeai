import asyncio
import sys
import os

from platform_core.groq_tools_agent import run_workspace_chat
from platform_core.tool_registry import ToolExecutionContext
from database import SessionLocal

class MockRequest:
    def __init__(self, mode, messages):
        self.mode = mode
        self.messages = messages

async def diagnose_agent():
    print("Initializing test wrapper...")
    db = SessionLocal()
    
    ctx = ToolExecutionContext(
        db=db,
        current_user={"username": "Chiru534"},
        session_id="diagnostic-session-001",
        mode="github_agent"
    )
    
    request = MockRequest(
        mode="github_agent",
        messages=[{"role": "user", "content": "give me the files inside the backend of the project_agent repo"}]
    )
    
    print("\nRunning Workspace Chat trigger to see Agent thoughts...")
    try:
        # We modify run_workspace_chat slightly to or print directly from it
        # Actually, let's just run it and print ctx.tool_events
        response = await run_workspace_chat(
            request=request,
            base_system_prompt="You are a helper.",
            ctx=ctx
        )
        print("\n=== Agent Response ===")
        print(response.get("reply"))
        
        print("\n=== Tool History ===")
        for event in ctx.tool_events:
            print(f"Tool: {event.get('tool_name')}")
            print(f"Arguments: {event.get('arguments')}")
            
    except Exception as e:
        print(f"Error during agent chat: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(diagnose_agent())
