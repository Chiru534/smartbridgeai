"""Full API smoke test for Smartbridge Platform stabilization."""
import httpx

BASE = "http://localhost:8000"

print("===== TEST 1: Login as admin =====")
r = httpx.post(f"{BASE}/api/login", json={"username": "admin", "password": "admin123"})
print(f"  Status: {r.status_code}")
token = r.json()["token"]
h = {"Authorization": f"Bearer {token}"}
print(f"  Token: {token}")

print("\n===== TEST 2: Login as employee =====")
r2 = httpx.post(f"{BASE}/api/login", json={"username": "employee", "password": "emp123"})
print(f"  Status: {r2.status_code}")
print(f"  Token: {r2.json()['token']}")

print("\n===== TEST 3: Fetch tasks (with auth) =====")
r3 = httpx.get(f"{BASE}/api/tasks", headers=h)
print(f"  Status: {r3.status_code}, Tasks: {len(r3.json())}")

print("\n===== TEST 4: Fetch tasks (NO auth - should 403) =====")
r4 = httpx.get(f"{BASE}/api/tasks")
print(f"  Status: {r4.status_code}")

print("\n===== TEST 5: Create task =====")
r5 = httpx.post(f"{BASE}/api/tasks", json={"title": "Code Review Bug Fix", "assignee": "Ananya Patel", "status": "Pending"}, headers=h)
print(f"  Status: {r5.status_code}, ID: {r5.json().get('id')}")
tid = r5.json()["id"]

print("\n===== TEST 6: Add comment =====")
r6 = httpx.post(f"{BASE}/api/tasks/{tid}/comments", json={"author_name": "Admin", "comment": "Fixed all critical bugs"}, headers=h)
print(f"  Status: {r6.status_code}, Comment ID: {r6.json().get('id')}")

print("\n===== TEST 7: Update task =====")
r7 = httpx.put(f"{BASE}/api/tasks/{tid}", json={"status": "Completed"}, headers=h)
print(f"  Status: {r7.status_code}, Comments: {len(r7.json().get('comments', []))}")

print("\n===== TEST 8: Models (with auth) =====")
r8 = httpx.get(f"{BASE}/api/available-models", headers=h, timeout=30)
print(f"  Status: {r8.status_code}, Models: {len(r8.json().get('models', []))}")

print("\n===== TEST 9: Models (NO auth - should 403) =====")
r9 = httpx.get(f"{BASE}/api/available-models")
print(f"  Status: {r9.status_code}")

print("\n===== TEST 10: Health (public) =====")
r10 = httpx.get(f"{BASE}/api/health")
print(f"  Status: {r10.status_code}")

print("\nALL TESTS COMPLETE")
