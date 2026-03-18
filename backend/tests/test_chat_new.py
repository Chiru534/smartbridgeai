import requests

# Login
login_url = "http://localhost:8001/api/login"
login_data = {"username": "admin", "password": "admin123"}

response = requests.post(login_url, json=login_data)
if response.status_code == 200:
    token = response.json()["token"]
    print(f"Logged in, token: {token}")
    
    # Test chat
    chat_url = "http://localhost:8000/api/chat"
    headers = {"Authorization": f"Bearer {token}"}
    chat_data = {
        "model": "qwen2.5:3b",
        "mode": "github_agent",
        "messages": [
            {"role": "user", "content": "give me the files inside the backend folder of the project_agent repo"}
        ]
    }
    
    chat_resp = requests.post(chat_url, json=chat_data, headers=headers)
    print(f"Chat response status: {chat_resp.status_code}")
    if chat_resp.status_code == 200:
        print("Chat response:", chat_resp.json())
    else:
        print("Error:", chat_resp.text)
else:
    print("Login failed:", response.text)