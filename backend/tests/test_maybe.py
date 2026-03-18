import asyncio
import sys
import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from platform_core.github_workspace import maybe_handle_github_request, _extract_file_path, _resolve_file_path, _contains_hint, FILE_HINTS

async def test():
    class DummyUser(dict):
        def __getitem__(self, k): return 'admin'
        def get(self, k): return 'admin'

    class DummyCtx:
        current_user = DummyUser()
        db = None
        session_id = '123'
        def __init__(self):
            pass

    class DummyMsg:
        def __init__(self, r, c): self.role = r; self.content = c

    class DummyReq:
        messages = [
            DummyMsg('user', 'give me the list of the repos present in the github'),
            DummyMsg('assistant', 'Here are the GitHub repositories I found:\n1. Chiru534/project_agent'),
            DummyMsg('user', 'give me the structure of the repo project_agent'),
            DummyMsg('assistant', 'project_agent/\n├── backend/\n'),
            DummyMsg('user', 'give the files inside the backend'),
            DummyMsg('assistant', 'Files in backend of Chiru534/project_agent:\n1. file backend/main.py'),
            DummyMsg('user', 'what is the code inside main.py')
        ]
        mode = 'github_agent'

    print('Testing maybe_handle')
    import platform_core.github_workspace as gw
    gw._is_github_connected = lambda ctx: True
    
    async def mock_call(*args, **kwargs):
        print('called:', args[0], args[1])
        return {'content': 'mock_base64_decoded_content'}, None
        
    gw._call_github_tool = mock_call
    
    async def mock_classify(*args):
        print('llm_classify called')
        return 'get_file'
        
    gw._llm_classify_intent = mock_classify
    
    ctx = DummyCtx()
    req = DummyReq()
    res = await maybe_handle_github_request(req, ctx)
    print('RES:', res)

if __name__ == '__main__':
    asyncio.run(test())
