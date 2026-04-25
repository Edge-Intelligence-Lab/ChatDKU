import json
import contextlib
import pytest
from fastapi.testclient import TestClient
from chatdku.backend.fastAPI import main

client = TestClient(main.app)


class FakePermanentMemory:
    def __init__(self, user_id):
        self.user_id = user_id

    def __call__(self, session_conversation, most_recent_conversation):
        return {"processed_by": self.user_id}

class FakeTracer:
    def start_as_current_span(self, *args, **kwargs):
        return contextlib.nullcontext()
class FakeSpan:
    def set_attribute(self, *args, **kwargs):
        pass

    def set_status(self, *args, **kwargs):
        pass

    def add_event(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass

class FakeSpanContext:
    def __enter__(self):
        return FakeSpan()
    
    def __exit__(self, exc_type, exc, tb):
        pass    

class FakeRedis:
    def __init__(self):
        self.publishes = []

    def publish(self, channel, message):
        self.publishes.append((channel, message))
        return 1


def test_memory_endpoint_success(monkeypatch):
    created = {"user_ids": []}

    fake_redis = FakeRedis()
    monkeypatch.setattr(main, "redis", fake_redis)

    class SpyPermanentMemory(FakePermanentMemory):
        def __init__(self, user_id):
            created["user_ids"].append(user_id)
            super().__init__(user_id)

    monkeypatch.setattr(main, "PermanentMemory", SpyPermanentMemory)
    monkeypatch.setattr(
            "chatdku.config.config.tracer",
            FakeTracer(),
            raising=False
        )

        # Patch span_ctx_start everywhere it's used
    monkeypatch.setattr(
        "chatdku.core.utils.span_ctx_start",
        lambda *args, **kwargs: FakeSpanContext()
    )

    monkeypatch.setattr(
        "chatdku.core.dspy_classes.memory.span_ctx_start",
        lambda *args, **kwargs: FakeSpanContext()
    )
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
    assert created["user_ids"] == ["test_user"]

    events = [json.loads(m) for (_, m) in fake_redis.publishes]
    types = [e["event"] for e in events]
    assert "memory_agent_started" in types
    assert "memory_agent_processing" in types
    assert "memory_agent_completed" in types


def test_memory_endpoint_validation_error():
    # missing required user_id and chat_id
    resp = client.post("/memory", json={"session_conversation": []})
    assert resp.status_code == 422
    
@pytest.mark.skip(
    reason=(
        "Integration test requiring full runtime setup (tracer/LLM/Redis). "
        "Run manually in a fully configured environment."
    )
)
def test_memory_endpoint_real_conversation():
    # This test would require a real PermanentMemory implementation and a running Redis instance.
    
    payload = {
        "user_id": "test_user",
        "session_conversation": [{"role": "user", "content": "My major is computer science."}, {"role": "assistant", "content": "Got it, you're a computer science major."}],
        "most_recent_conversation": [{"role": "user", "content": "My major is computer science."}, {"role": "assistant", "content": "Got it, you're a computer science major."}],
        "chat_id": "test_chat2",
    }
    resp = client.post("/memory", json=payload)
    assert resp.status_code == 200
