import urllib.request
import json
import sys

headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer 6BSzOCon3D7kmsCCg0GqJBZkS_eSWFsy9IQeqOYKP_hz0A9SNQkFWhDumTbucjiY'
}

data = {
    'model': 'qwen2.5:3b',
    'mode': 'github_agent',
    'messages': [
        {'role': 'user', 'content': 'give me the files in the dir backend'},
        {'role': 'assistant', 'content': '1. dir backend/__pycache__\n2. file backend/llm_agent.py\n3. file backend/llm_client.py'},
        {'role': 'user', 'content': 'give me the code in the llm_agent.py'}
    ]
}

req = urllib.request.Request(
    'http://localhost:8000/api/chat',
    headers=headers,
    data=json.dumps(data).encode('utf-8')
)

try:
    response = urllib.request.urlopen(req)
    # Output with standard print
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Exception: {e}")
