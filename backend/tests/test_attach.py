import urllib.request, json, os

content = b'This is a test invoice'
with open('invoice.pdf', 'wb') as f:
    f.write(content)

boundary = '----WebKitFormBoundaryABCD'
data = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="invoice.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode('utf-8') + content + f'\r\n--{boundary}--\r\n'.encode('utf-8')

req = urllib.request.Request('http://localhost:8000/api/upload_attachment', headers={
    'Authorization': 'Bearer admin-token-123',
    'Content-Type': f'multipart/form-data; boundary={boundary}'
})

try:
    resp = json.loads(urllib.request.urlopen(req, data=data).read().decode('utf-8'))
    print('Upload response:', resp)

    task_data = json.dumps({
        'title': 'Process Invoice',
        'description': 'review this',
        'assignee': 'Ananya Rai',
        'status': 'Pending',
        'attachment_filename': resp['filename'],
        'attachment_url': resp['url']
    }).encode('utf-8')

    req_task = urllib.request.Request('http://localhost:8000/api/tasks', headers={
        'Authorization': 'Bearer admin-token-123',
        'Content-Type': 'application/json'
    }, data=task_data)
    task_res = json.loads(urllib.request.urlopen(req_task).read().decode('utf-8'))
    print('Task response title:', task_res['title'])
    print('Task response attachment:', task_res.get('attachment_filename'))
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
