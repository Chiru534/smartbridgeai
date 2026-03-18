import urllib.request, json, os

content = "The secret password to the Smartbridge vault is PineappleExpress2026."
with open("dummy.txt", "w") as f:
    f.write(content)

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
data = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="dummy.txt"\r\nContent-Type: text/plain\r\n\r\n{content}\r\n--{boundary}--\r\n'.encode('utf-8')

req = urllib.request.Request('http://localhost:8000/api/knowledge/upload', headers={
    'Authorization': 'Bearer admin-token-123',
    'Content-Type': f'multipart/form-data; boundary={boundary}'
})
resp = urllib.request.urlopen(req, data=data)
print('Upload:', resp.read().decode('utf-8'))

req_chat = urllib.request.Request('http://localhost:8000/api/chat', headers={
    'Authorization': 'Bearer admin-token-123',
    'Content-Type': 'application/json'
}, data=json.dumps({
    'model':'llama-3.1-8b-instant', 
    'messages':[{'role':'user', 'content':'What is the secret password to the Smartbridge vault?'}]
}).encode())

chat_resp = json.loads(urllib.request.urlopen(req_chat).read())
print('Chat Reply:', chat_resp['reply'])
