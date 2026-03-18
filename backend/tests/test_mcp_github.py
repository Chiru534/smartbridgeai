"""Diagnostic script to test GitHub MCP server functionality."""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from platform_core.mcp_stdio import MCPToolBinding, ManagedMCPServer
from platform_core.config import settings

async def test_github_mcp():
    """Test if GitHub MCP server starts and can list tools."""
    print("=" * 60)
    print("GitHub MCP Server Diagnostic Test")
    print("=" * 60)
    
    print(f"\n📋 Configuration:")
    print(f"  MCP Enabled: {settings.mcp_enabled}")
    print(f"  GitHub MCP Command: {settings.github_mcp_command}")
    print(f"  MCP Timeout: {settings.mcp_tool_timeout_secs}s")
    
    server = ManagedMCPServer(
        name="github",
        command=settings.github_mcp_command,
        timeout_secs=settings.mcp_tool_timeout_secs
    )
    
    print(f"\n🔧 Starting GitHub MCP server...")
    try:
        started = await asyncio.wait_for(server.ensure_started(), timeout=15)
        if not started:
            print(f"❌ Failed to start: {server.last_error}")
            return False
        print(f"✅ GitHub MCP server started successfully")
    except asyncio.TimeoutError:
        print(f"❌ Timeout starting server (15s exceeded)")
        print(f"   Error: {server.last_error}")
        return False
    except Exception as e:
        print(f"❌ Exception starting server: {e}")
        print(f"   Error: {server.last_error}")
        return False
    
    print(f"\n📦 Listing available tools...")
    try:
        tools = await asyncio.wait_for(server.list_tools(), timeout=10)
        print(f"✅ Found {len(tools)} tools")
        for tool in tools:
            print(f"   - {tool.exposed_name}: {tool.description[:50]}")
        
        # Check for github_get_file tool
        get_file_tools = [t for t in tools if "get_file" in t.exposed_name]
        if get_file_tools:
            print(f"\n✅ github_get_file tool is available")
        else:
            print(f"\n❌ github_get_file tool NOT found!")
            return False
            
    except asyncio.TimeoutError:
        print(f"❌ Timeout listing tools (10s exceeded)")
        return False
    except Exception as e:
        print(f"❌ Exception listing tools: {e}")
        return False
    
    print(f"\n✅ All diagnostic checks passed!")
    await server.close()
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_github_mcp())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
