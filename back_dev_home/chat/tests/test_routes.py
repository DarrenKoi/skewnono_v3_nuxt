import pytest
from flask import Flask, g

from back_dev_home.chat import store
from back_dev_home.chat.routes import bp, orchestrator
from back_dev_home.chat.knowledge.contracts import (
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)
from back_dev_home.chat.scope.contracts import ScopeUnavailable


REQUEST_ID = "64d35cd4-9e07-4be8-90a3-683f94c29408"


def _answer(content="pong", **overrides):
    return {
        "content": content,
        "sources": [],
        "follow_ups": [],
        "rewrite": None,
        "tool_traces": [],
        "prompt_tokens": 3,
        "completion_tokens": 1,
        **overrides,
    }


@pytest.fixture
def answerer(monkeypatch):
    """Stand in for the RAG on the module-level orchestrator these routes use."""
    calls = []

    def answer(question, messages, scope):
        calls.append({"question": question, "messages": list(messages)})
        if isinstance(answer.result, Exception):
            raise answer.result
        return answer.result

    answer.result = _answer()
    answer.calls = calls
    monkeypatch.setattr(orchestrator, "_answerer", answer)
    return answer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")

    @app.before_request
    def _uid():
        g.user_id = "u1"

    return app.test_client()


def test_availability_reports_the_page_gate(client, monkeypatch):
    """Catches the SPA losing its only signal that chat is not in service."""
    monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", "1")
    assert client.get("/api/chat/availability").get_json()["data"] == {
        "available": False
    }

    monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", "0")
    assert client.get("/api/chat/availability").get_json()["data"] == {
        "available": True
    }


def test_under_development_does_not_disable_the_chat_api(client, monkeypatch):
    """Catches the page gate turning into an authorization gate.

    The notice hides the page; /api/chat/* deliberately keeps answering so the
    feature stays exercisable on a host where the page is hidden.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", "1")

    created = client.post("/api/chat/threads")

    assert created.status_code == 201


def test_create_and_list_thread(client):
    r = client.post("/api/chat/threads")
    assert r.status_code == 201
    tid = r.get_json()["data"]["id"]
    listed = client.get("/api/chat/threads").get_json()["data"]
    assert [t["id"] for t in listed] == [tid]


def test_create_takes_no_body(client):
    """The RAG owns the model and the prompt; the client chooses neither."""
    r = client.post("/api/chat/threads")
    assert r.status_code == 201
    assert set(r.get_json()["data"]) == {
        "id", "user_id", "title", "created_at", "updated_at", "messages",
    }


def test_send_message_persists_reply(client, answerer):
    tid = client.post("/api/chat/threads").get_json()["data"][
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
    assert body["latency_ms"] is not None
    assert body["rewrite"] is None
    assert body["follow_ups"] == []
    roles = [
        m["role"]
        for m in client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    ]
    assert roles == ["user", "assistant"]


def test_send_message_timeout_preserves_user_message(client, answerer):
    answerer.result = KnowledgeTimeout("too slow")
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": REQUEST_ID},
    )
    assert r.status_code == 504
    msgs = client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    assert [m["role"] for m in msgs] == ["user"]  # user msg kept, no assistant


def test_send_message_requires_content(client):
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]
    r = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "  ", "request_id": REQUEST_ID},
    )
    assert r.status_code == 400


@pytest.mark.parametrize("body", [["alarm", REQUEST_ID], {"content": 42}])
def test_send_rejects_malformed_json_shapes(client, body):
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]

    response = client.post(f"/api/chat/threads/{tid}/messages", json=body)

    assert response.status_code == 400


def test_send_requires_request_id(client):
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]
    response = client.post(
        f"/api/chat/threads/{tid}/messages", json={"content": "ping"}
    )
    assert response.status_code == 400


@pytest.mark.parametrize("request_id", ["not-a-uuid", REQUEST_ID.upper(), 42])
def test_send_requires_canonical_uuid(client, request_id):
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]
    response = client.post(
        f"/api/chat/threads/{tid}/messages",
        json={"content": "alarm", "request_id": request_id},
    )
    assert response.status_code == 400


def test_retry_after_failure_does_not_duplicate_user_message(client, answerer):
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]
    answerer.result = KnowledgeTimeout("slow")
    assert (
        client.post(
            f"/api/chat/threads/{tid}/messages",
            json={"content": "alarm", "request_id": REQUEST_ID},
        ).status_code
        == 504
    )

    answerer.result = _answer()
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
    # the retried question travelled once, in `question`, and not in the history
    assert answerer.calls[-1]["question"] == "alarm"
    assert answerer.calls[-1]["messages"] == []


@pytest.fixture
def completed_assistant(client, answerer):
    tid = client.post("/api/chat/threads").get_json()["data"][
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
    thread = store.create_thread("u2")
    store.append_user_message(thread["id"], "alarm", REQUEST_ID)
    assistant = store.complete_turn(
        thread["id"],
        REQUEST_ID,
        {
            "content": "private",
            "runtime": "rag",
            "model": None,
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
    thread = store.create_thread("u1")
    user_message = store.append_user_message(thread["id"], "alarm", REQUEST_ID)
    path = f"/api/chat/messages/{user_message['id']}/feedback"

    def unexpected_write(*_args, **_kwargs):
        pytest.fail("invalid feedback target must be rejected before storage mutation")

    monkeypatch.setattr(store, "put_feedback", unexpected_write)
    monkeypatch.setattr(store, "delete_feedback", unexpected_write)

    assert client.put(path, json={"rating": "up", "reasons": []}).status_code == 400
    assert client.delete(path).status_code == 400


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (KnowledgeDenied("rag denied"), 403),
        (ScopeUnavailable("scope offline"), 503),
        (KnowledgeUnavailable("rag offline"), 503),
        (KnowledgeTimeout("rag slow"), 504),
    ],
)
def test_answer_errors_map_to_typed_http_statuses(client, monkeypatch, error, status):
    from back_dev_home.chat import routes

    def _raise(*args):
        raise error

    monkeypatch.setattr(routes.orchestrator, "send_message", _raise)
    tid = client.post("/api/chat/threads").get_json()["data"][
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
    tid = client.post("/api/chat/threads").get_json()["data"][
        "id"
    ]
    assert client.delete(f"/api/chat/threads/{tid}").status_code == 200
    assert client.get(f"/api/chat/threads/{tid}").status_code == 404
