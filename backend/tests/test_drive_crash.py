import asyncio
import sys
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import platform_core.google_drive_workspace as gw
from types import SimpleNamespace

async def test():
    class DummyMsg:
        def __init__(self, r, c): self.role = r; self.content = c

    req = SimpleNamespace(
        messages=[DummyMsg('user', 'give me the summary of the CSA exam topics.pdf')],
        model=None
    )
    
    ctx = SimpleNamespace(current_user={'username': 'admin'}, db=None)
    gw._is_google_drive_connected = lambda ctx: True
    
    async def mock_call(tool, args, *rest):
        print('_call_drive_tool called:', tool, args)
        # Simulate a successful drive response payload
        return {
            "content": '{"selected_item": {"id": "123", "name": "CSA exam topics.pdf"}, "content": "Some PDF Text content here"}'
        }, None

    gw._call_drive_tool = mock_call
    
    try:
        res = await gw.maybe_handle_google_drive_request(req, ctx)
        print('RESULT:', res)
    except Exception as e:
        import traceback
        print('CRASHED:')
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
