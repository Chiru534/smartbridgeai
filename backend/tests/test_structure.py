import asyncio
import sys
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import platform_core.github_workspace as gw
from types import SimpleNamespace

async def test():
    class DummyMsg:
        def __init__(self, r, c): self.role = r; self.content = c

    req = SimpleNamespace(
        messages=[DummyMsg('user', 'give me the structure of the project_agent')]
    )
    
    ctx = SimpleNamespace(current_user={'username': 'admin'})
    gw._is_github_connected = lambda ctx: True
    
    # Mock repositories inventory
    fake_inventory = {
        "items": [
            {"name": "project_agent", "full_name": "Chiru534/project_agent"},
            {"name": "backend", "full_name": "Chiru534/backend"}
        ]
    }
    async def mock_call(tool, args, *rest):
        print('_call_github_tool called:', tool, args)
        if tool == "github_list_my_repositories":
            return fake_inventory, None
        return {}, None

    gw._call_github_tool = mock_call
    tool_events = []
    
    repo_ref, items = await gw._resolve_repo_reference(req, ctx, tool_events)
    print('RESOLVED REPO:', repo_ref)

if __name__ == '__main__':
    asyncio.run(test())
