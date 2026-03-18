from uuid import uuid4

from fastapi.testclient import TestClient

from main import app


def run_contract_check():
    client = TestClient(app)
    admin_headers = {"Authorization": "Bearer admin-token-123"}
    employee_headers = {"Authorization": "Bearer employee-token-456"}

    session_id = f"contract-{uuid4()}"
    expected_content = f"contract message {uuid4()}"

    # Contract 1: POST /api/chat/message persists a message with a session_id.
    create_resp = client.post(
        "/api/chat/message",
        json={
            "content": expected_content,
            "role": "user",
            "session_id": session_id,
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["session_id"] == session_id
    assert created["content"] == expected_content
    assert created["user_id"] == "admin"

    # Contract 2: GET /api/chat/history?session_id=... returns only the correct user's session messages.
    history_resp = client.get(f"/api/chat/history?session_id={session_id}", headers=admin_headers)
    assert history_resp.status_code == 200, history_resp.text
    history = history_resp.json()
    assert any(m["content"] == expected_content and m["session_id"] == session_id for m in history), history
    assert all(m["session_id"] == session_id for m in history), history
    assert all(m["user_id"] == "admin" for m in history), history

    # User isolation check: other users cannot see admin session history.
    other_user_history = client.get(f"/api/chat/history?session_id={session_id}", headers=employee_headers)
    assert other_user_history.status_code == 200, other_user_history.text
    assert other_user_history.json() == [], other_user_history.json()

    print("PASS: chat contract integrity checks passed")


if __name__ == "__main__":
    run_contract_check()
