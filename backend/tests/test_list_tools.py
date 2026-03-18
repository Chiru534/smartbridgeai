import asyncio
import sys
import os
import json

from platform_core.tool_registry import tool_registry

async def test_list():
    print("Fetching tools list for github_agent mode...")
    try:
        tools = await tool_registry.openai_tools_for_mode("github_agent")
        print(f"Found {len(tools)} tools:")
        
        for i, tool in enumerate(tools):
            fn = tool.get("function", {})
            print(f"\n[{i+1}] {fn.get('name')}")
            print(f"    Description: {fn.get('description')}")
            print(f"    Parameters: {json.dumps(fn.get('parameters'), indent=2)}")
            
    except Exception as e:
        print(f"Error fetching tools: {e}")

if __name__ == "__main__":
    asyncio.run(test_list())
