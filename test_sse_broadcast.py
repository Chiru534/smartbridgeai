import urllib.request, json, threading, time

def listen_sse():
    req = urllib.request.Request('http://localhost:8000/api/events?token=admin-token-123')
    try:
        resp = urllib.request.urlopen(req)
        for line in resp:
            line = line.decode('utf-8').strip()
            if line.startswith('data:'):
                print("SSE RECEIVED:", line)
                return
    except Exception as e:
        print("SSE Error:", e)

t = threading.Thread(target=listen_sse)
t.start()
time.sleep(1) # wait for connection

task_data = json.dumps({'title': 'SSE Task', 'description': 'Testing SSE', 'assignee': 'Ananya Rai', 'status': 'Pending'}).encode('utf-8')
req_task = urllib.request.Request('http://localhost:8000/api/tasks', headers={'Authorization': 'Bearer admin-token-123', 'Content-Type': 'application/json'}, data=task_data)
urllib.request.urlopen(req_task)

t.join(timeout=3)
print("Done")
