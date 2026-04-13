import pytest
from fastapi.testclient import TestClient

from chatdku.backend.fastAPI.main import app

client = TestClient(app)

# Sample test data
USER_ID = "Chat_DKU"
SESSION_ID = "test_session"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_memories():
    payload = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "query": "test query",
        "limit": 3,
        "filters": None
    }

    response = client.post("/memory/search", json=payload)
    assert response.status_code == 200
    assert "result" in response.json()


def test_store_memory():
    payload = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "content": "test memory content",
        "metadata": None
    }

    response = client.post("/memory/store", json=payload)
    assert response.status_code == 200
    assert "result" in response.json()


def test_update_memory():
    payload = {
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "idx": 0,
        "new_content": "updated memory content"
    }

    response = client.post("/memory/update", json=payload)
    assert response.status_code == 200
    assert "result" in response.json()


def test_delete_memory():
    memory_id = "test-memory-id"

    response = client.delete(
        f"/memory/{memory_id}",
        params={"user_id": USER_ID, "session_id": SESSION_ID}
    )

    # Could be success or failure depending on backend state
    assert response.status_code in [200, 400]

    data = response.json()
    assert "result" in data or "detail" in data


def test_cleanup_memory():
    response = client.post(
        "/memory/cleanup",
        params={
            "user_id": USER_ID,
            "session_id": SESSION_ID,
            "max_memories": 50
        }
    )

    assert response.status_code == 200
    assert "result" in response.json()