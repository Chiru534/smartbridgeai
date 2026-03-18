import asyncio
import sys
import os

from platform_core.mcp_stdio import default_mcp_manager

async def test_tool_call():
    print("Listing tools for github...")
    try:
        default_mcp_manager.register_server(
            "github",
            # We must load current loaded command
            # Just read from settings or hardcode it
            ["python", "-m", "platform_core.github_mcp_server"],
            cwd=str(os.path.abspath('.'))
        )
        
        print("Calling tool github_list_directory...")
        result = await default_mcp_manager.call(
            "github_list_directory",
            arguments={"owner": "Chiru534", "repo": "project_agent", "path": "backend"},
            injected_arguments={"connector_username": "Chiru534"}
        )
        import json
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_call())
