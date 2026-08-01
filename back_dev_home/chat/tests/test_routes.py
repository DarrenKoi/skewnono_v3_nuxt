import pytest
from flask import Flask, g

from back_dev_home.chat import data, guard, llm
from back_dev_home.chat.routes import bp
from back_dev_home.chat.runtime.contracts import (
    RuntimeDenied,
    RuntimeLimitExceeded,
    RuntimeTimeout,
    RuntimeUnavailable,
    RuntimeUpstreamError,
)
from back_dev_home.chat.scope.contracts import ScopeUnavailable


REQUEST_ID = "64d35cd4-9e07-4be8-90a3-683f94c29408"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")
    monkeypatch.setenv("SKEWNONO_CHAT_RUNTIME", "direct")
    monkeypatch.setenv("SKEWNONO_CHAT_SCOPE_PROVIDER", "mock")
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
    monkeypatch.setattr(
        llm,
        "send_chat",
        lambda model, messages: {
            "content": "pong",
            "prompt_tokens": 3,
            "completion_tokens": 1,
            "latency_ms": 7,
        },
    )
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert r.status_code == 200
    body = r.get_json()["data"]
    assert body["role"] == "assistant"
    assert body["content"] == "pong"
    assert body["latency_ms"] == 7
    roles = [
        m["role"]
        for m in client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    ]
    assert roles == ["user", "assistant"]


def test_send_message_timeout_preserves_user_message(client, monkeypatch):
    def _boom(model, messages):
        raise llm.ChatTimeout("too slow")

    monkeypatch.setattr(llm, "send_chat", _boom)
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert r.status_code == 504
    msgs = client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    assert [m["role"] for m in msgs] == ["user"]  # user msg kept, no assistant


def test_send_message_egress_blocked_returns_403(client, monkeypatch):
    def _blocked(model, messages):
        raise guard.ChatEgressBlocked("OpenRouter is blocked in office mode")

    monkeypatch.setattr(llm, "send_chat", _blocked)
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "egress_blocked"
    # user turn preserved, no assistant appended
    msgs = client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    assert [m["role"] for m in msgs] == ["user"]


def test_send_message_upstream_failure_preserves_502_envelope(client, monkeypatch):
    def _failed(model, messages):
        raise llm.ChatUpstreamError("gateway failed")

    monkeypatch.setattr(llm, "send_chat", _failed)
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]

    response = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "bad_gateway"
    messages = client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    assert [message["role"] for message in messages] == ["user"]


def test_send_message_requires_content(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "  ", "request_id": REQUEST_ID},
    )
    assert r.status_code == 400


@pytest.mark.parametrize("body", [["alarm", REQUEST_ID], {"content": 42}])
def test_send_rejects_malformed_json_shapes(client, body):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]

    response = client.post(f"/api/chat/threads/{tid}/messages", json=body)

    assert response.status_code == 400


def test_send_requires_request_id(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    response = client.post(
        f"/api/chat/threads/{tid}/messages", json={"content": "ping"}
    )
    assert response.status_code == 400


@pytest.mark.parametrize("request_id", ["not-a-uuid", REQUEST_ID.upper(), 42])
def test_send_requires_canonical_uuid(client, request_id):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    response = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": request_id},
    )
    assert response.status_code == 400


def test_retry_after_failure_does_not_duplicate_user_message(client, monkeypatch):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]

    def _boom(model, messages):
        raise llm.ChatTimeout("slow")

    monkeypatch.setattr(llm, "send_chat", _boom)
    assert (
        client.post(
            f"/api/chat/threads/{tid}/messages",
            json={"content": "alarm", "request_id": REQUEST_ID},
        ).status_code
        == 504
    )

    captured = {}

    def _ok(model, messages):
        captured["messages"] = messages
        return {
            "content": "pong",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "latency_ms": 5,
        }

    monkeypatch.setattr(llm, "send_chat", _ok)
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert r.status_code == 200

    roles = [
        m["role"]
        for m in client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    ]
    assert roles == ["user", "assistant"]  # exactly one user row, not two
    # the LLM payload contained the user turn exactly once
    assert (
        sum(
            1
            for message in captured["messages"]
            if message["role"] == "user" and message["content"] == "alarm"
        )
        == 1
    )


@pytest.fixture
def completed_assistant(client, monkeypatch):
    monkeypatch.setattr(
        llm,
        "send_chat",
        lambda model, messages: {
            "content": "pong",
            "prompt_tokens": 3,
            "completion_tokens": 1,
            "latency_ms": 7,
        },
    )
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    response = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert response.status_code == 200
    return response.get_json()["data"]


def test_feedback_can_be_replaced_and_removed(client, completed_assistant):
    path = f"/api/chat/messages/{completed_assistant['id']}/feedback"
    assert client.put(path, json={"rating": "up", "reasons": []}).status_code == 200
    changed = client.put(
        path,
        json={
            "rating": "down",
            "reasons": ["wrong_source"],
            "comment": "Wrong manual",
        },
    )
    assert changed.get_json()["data"]["rating"] == "down"
    assert client.delete(path).status_code == 200
    thread = client.get(
        f"/api/chat/threads/{completed_assistant['thread_id']}"
    ).get_json()["data"]
    assert thread["messages"][-1]["feedback"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"rating": "sideways", "reasons": []},
        {"rating": [], "reasons": []},
        {"rating": "down", "reasons": "wrong_source"},
        {"rating": "down", "reasons": ["not_allowed"]},
        {"rating": "down", "reasons": [], "comment": 42},
        {"rating": "down", "reasons": [], "comment": "x" * 501},
    ],
)
def test_invalid_feedback_is_rejected_without_replacing_existing(
    client, completed_assistant, payload
):
    path = f"/api/chat/messages/{completed_assistant['id']}/feedback"
    assert client.put(path, json={"rating": "up", "reasons": []}).status_code == 200

    response = client.put(path, json=payload)

    assert response.status_code == 400
    thread = client.get(
        f"/api/chat/threads/{completed_assistant['thread_id']}"
    ).get_json()["data"]
    assert thread["messages"][-1]["feedback"]["rating"] == "up"


def test_feedback_missing_or_unowned_message_is_hidden(client):
    thread = data.create_thread("u2", "m1")
    data.append_user_message(thread["id"], "alarm", REQUEST_ID)
    assistant = data.complete_turn(
        thread["id"],
        REQUEST_ID,
        {
            "content": "private",
            "runtime": "direct",
            "model": "m1",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "latency_ms": 1,
            "sources": [],
            "tool_traces": [],
        },
    )

    for message_id in ("missing", assistant["id"]):
        path = f"/api/chat/messages/{message_id}/feedback"
        assert client.put(path, json={"rating": "up", "reasons": []}).status_code == 404
        assert client.delete(path).status_code == 404


def test_feedback_rejects_owned_user_message_before_writing(client, monkeypatch):
    thread = data.create_thread("u1", "m1")
    user_message = data.append_user_message(thread["id"], "alarm", REQUEST_ID)
    path = f"/api/chat/messages/{user_message['id']}/feedback"

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("invalid feedback target must be rejected before storage mutation")

    monkeypatch.setattr(data, "put_feedback", unexpected_write)
    monkeypatch.setattr(data, "delete_feedback", unexpected_write)

    assert client.put(path, json={"rating": "up", "reasons": []}).status_code == 400
    assert client.delete(path).status_code == 400


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (RuntimeDenied("denied"), 403),
        (RuntimeUnavailable("offline"), 503),
        (ScopeUnavailable("scope offline"), 503),
        (RuntimeTimeout("slow"), 504),
        (RuntimeUpstreamError("gateway failed"), 502),
        (RuntimeLimitExceeded("too many"), 422),
    ],
)
def test_runtime_errors_map_to_typed_http_statuses(client, monkeypatch, error, status):
    from back_dev_home.chat import routes

    def _raise(*args):
        raise error

    monkeypatch.setattr(routes.orchestrator, "send_message", _raise)
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    response = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert response.status_code == status
    assert set(response.get_json()["error"]) == {"code", "message"}


def test_get_unknown_thread_404(client):
    assert client.get("/api/chat/threads/nope").status_code == 404


def test_delete_thread(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"][
        "id"
    ]
    assert client.delete(f"/api/chat/threads/{tid}").status_code == 200
    assert client.get(f"/api/chat/threads/{tid}").status_code == 404
