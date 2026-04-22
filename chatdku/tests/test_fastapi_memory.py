import json
from fastapi.testclient import TestClient
from chatdku.backend.fastAPI import main

client = TestClient(main.app)


class FakePermanentMemory:
    def __init__(self, user_id):
        self.user_id = user_id

    def __call__(self, session_conversation, most_recent_conversation):
        return {"processed_by": self.user_id}


class FakeRedis:
    def __init__(self):
        self.publishes = []

    def publish(self, channel, message):
        self.publishes.append((channel, message))
        return 1


def test_memory_endpoint_success(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(main, "redis", fake_redis)
    monkeypatch.setattr(main, "PermanentMemory", FakePermanentMemory)

    payload = {
        "user_id": "test_user",
        "session_conversation": [],
        "most_recent_conversation": [],
        "chat_id": "test_chat1",
    }

    resp = client.post("/memory", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["result"] == {"processed_by": "test_user"}

    events = [json.loads(m) for (_, m) in fake_redis.publishes]
    types = [e["event"] for e in events]
    assert "memory_agent_started" in types
    assert "memory_agent_processing" in types
    assert "memory_agent_completed" in types


def test_memory_endpoint_validation_error():
    # missing required user_id and chat_id
    resp = client.post("/memory", json={"session_conversation": []})
    assert resp.status_code == 422
    
def test_memory_endpoint_real_conversation():
    # This test would require a real PermanentMemory implementation and a running Redis instance.
    
    payload = {
        "user_id": "test_user",
        "session_conversation": [{"role": "user", "content": "My major is computer science."}],
        "most_recent_conversation": [{"role": "user", "content": "My major is computer science."}],
        "chat_id": "test_chat2",
    }
    resp = client.post("/memory", json=payload)
    assert resp.status_code == 200
