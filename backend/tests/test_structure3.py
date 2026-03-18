import asyncio
import sys
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import platform_core.github_workspace as gw
from types import SimpleNamespace

async def test():
    class DummyMsg:
        def __init__(self, r, c): self.role = r; self.content = c

    # Previous response contains the comment
    req = SimpleNamespace(
        messages=[
            DummyMsg('assistant', '# For production/multi-user scenarios\nFile content for backend/database.py in Chiru534/project_agent'),
            DummyMsg('user', 'give me the summary of the code')
        ]
    )
    
    ctx = SimpleNamespace(current_user={'username': 'admin'})
    gw._is_github_connected = lambda ctx: True
    
    # Mock fallback to prevent hit
    async def mock_call(*args): return {}, None
    gw._call_github_tool = mock_call

    tool_events = []
    
    repo_ref, items = await gw._resolve_repo_reference(req, ctx, tool_events)
    print('RESOLVED REPO FROM HISTORY:', repo_ref)

if __name__ == '__main__':
    asyncio.run(test())
