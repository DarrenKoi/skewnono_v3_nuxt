import logging

import back_dev_home
from back_dev_home import create_app
from back_dev_home.chat import rag
from back_dev_home.chat.orchestration import orchestrator


REQUEST_ID = "64d35cd4-9e07-4be8-90a3-683f94c29408"


def test_chat_routes_registered():
    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/chat/threads" in rules
    assert "/api/chat/availability" in rules


def test_create_app_loads_dotenv():
    # create_app must import load_dotenv at module scope and call it at startup.
    assert callable(back_dev_home.load_dotenv)
    # smoke: building the app twice must not raise
    create_app()
    create_app()


def _run_turn_inline(monkeypatch):
    """Run the worker on the request thread so a boot test can assert on it.

    The turn is a background worker in production; these tests are about which
    adapter answers, not about when.
    """
    monkeypatch.setattr(orchestrator, "_spawn", lambda run: run())


def _settled(client, thread_id):
    messages = client.get(f"/api/chat/threads/{thread_id}").get_json()["data"][
        "messages"
    ]
    return next(message for message in messages if message["role"] == "assistant")


def test_boot_without_a_rag_checkout_serves_the_mock(monkeypatch, tmp_path):
    """The home case: no checkout, no env to set, a working chat anyway."""
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setattr(rag, "rag_ready", lambda: False)
    _run_turn_inline(monkeypatch)

    client = create_app().test_client()
    thread_id = client.post("/api/chat/threads").get_json()["data"]["id"]
    response = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"content": "alignment 오차 보정 방법", "request_id": REQUEST_ID},
    )

    assert response.status_code == 202
    settled = _settled(client, thread_id)
    assert settled["status"] == "done"
    assert settled["runtime"] == "rag"


def test_a_present_but_unusable_checkout_fails_per_request_not_at_boot(
    monkeypatch, tmp_path
):
    """Readiness is a filesystem check; a broken RAG is a failed turn, never a dead app.

    It used to be a 503 on the POST. The failure is the same one; it is now
    recorded on the turn, because the request that would have carried it is
    already over by the time the RAG is asked.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setattr(rag, "rag_ready", lambda: True)
    _run_turn_inline(monkeypatch)

    client = create_app().test_client()  # must not raise
    thread_id = client.post("/api/chat/threads").get_json()["data"]["id"]
    response = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"content": "alignment 오차 보정 방법", "request_id": REQUEST_ID},
    )

    assert response.status_code == 202
    settled = _settled(client, thread_id)
    assert settled["status"] == "failed"
    assert settled["error_code"] == "runtime_unavailable"
    assert settled["content"] == ""


def test_the_boot_log_names_which_source_chat_resolved_to(monkeypatch, caplog):
    """`python index.py` must say mock or office without anyone guessing."""
    from back_dev_home._runtime import boot

    monkeypatch.setattr(rag, "rag_ready", lambda: False)
    with caplog.at_level(logging.INFO, logger="skewnono.providers"):
        boot.log_provider_table()

    assert "chat/answer  mock    no RAG checkout" in caplog.text
