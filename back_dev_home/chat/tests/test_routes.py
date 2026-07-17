import pytest
from flask import Flask, g

from back_dev_home.chat import llm
from back_dev_home.chat.routes import bp


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")

    @app.before_request
    def _uid():
        g.user_id = "u1"

    return app.test_client()


def test_models_endpoint(client):
    r = client.get("/api/chat/models")
    assert r.status_code == 200
    assert isinstance(r.get_json()["data"], list)


def test_create_and_list_thread(client):
    r = client.post("/api/chat/threads", json={"model": "m1"})
    assert r.status_code == 201
    tid = r.get_json()["data"]["id"]
    listed = client.get("/api/chat/threads").get_json()["data"]
    assert [t["id"] for t in listed] == [tid]


def test_create_requires_model(client):
    r = client.post("/api/chat/threads", json={})
    assert r.status_code == 400


def test_send_message_persists_reply(client, monkeypatch):
    monkeypatch.setattr(llm, "send_chat", lambda model, messages: {
        "content": "pong", "prompt_tokens": 3, "completion_tokens": 1, "latency_ms": 7,
    })
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "ping"})
    assert r.status_code == 200
    body = r.get_json()["data"]
    assert body["role"] == "assistant"
    assert body["content"] == "pong"
    assert body["latency_ms"] == 7
    roles = [m["role"] for m in client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]]
    assert roles == ["user", "assistant"]


def test_send_message_timeout_preserves_user_message(client, monkeypatch):
    def _boom(model, messages):
        raise llm.ChatTimeout("too slow")
    monkeypatch.setattr(llm, "send_chat", _boom)
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "ping"})
    assert r.status_code == 504
    msgs = client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    assert [m["role"] for m in msgs] == ["user"]  # user msg kept, no assistant


def test_send_message_requires_content(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "  "})
    assert r.status_code == 400


def test_retry_after_failure_does_not_duplicate_user_message(client, monkeypatch):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]

    def _boom(model, messages):
        raise llm.ChatTimeout("slow")
    monkeypatch.setattr(llm, "send_chat", _boom)
    assert client.post(f"/api/chat/threads/{tid}/messages", json={"content": "ping"}).status_code == 504

    captured = {}
    def _ok(model, messages):
        captured["messages"] = messages
        return {"content": "pong", "prompt_tokens": 1, "completion_tokens": 1, "latency_ms": 5}
    monkeypatch.setattr(llm, "send_chat", _ok)
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "ping"})
    assert r.status_code == 200

    roles = [m["role"] for m in client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]]
    assert roles == ["user", "assistant"]  # exactly one user row, not two
    # the LLM payload contained the user turn exactly once
    assert sum(1 for m in captured["messages"] if m["role"] == "user" and m["content"] == "ping") == 1


def test_get_unknown_thread_404(client):
    assert client.get("/api/chat/threads/nope").status_code == 404


def test_delete_thread(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    assert client.delete(f"/api/chat/threads/{tid}").status_code == 200
    assert client.get(f"/api/chat/threads/{tid}").status_code == 404
