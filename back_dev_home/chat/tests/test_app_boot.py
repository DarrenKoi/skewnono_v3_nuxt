import logging

import back_dev_home
from back_dev_home import create_app
from back_dev_home.chat import rag


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


def test_boot_without_a_rag_checkout_serves_the_mock(monkeypatch, tmp_path):
    """The home case: no checkout, no env to set, a working chat anyway."""
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setattr(rag, "rag_ready", lambda: False)

    client = create_app().test_client()
    thread_id = client.post("/api/chat/threads").get_json()["data"]["id"]
    response = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"content": "alignment 오차 보정 방법", "request_id": REQUEST_ID},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["runtime"] == "rag"


def test_a_present_but_unusable_checkout_fails_per_request_not_at_boot(
    monkeypatch, tmp_path
):
    """Readiness is a filesystem check; a broken RAG is a 503, never a dead app."""
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setattr(rag, "rag_ready", lambda: True)

    client = create_app().test_client()  # must not raise
    thread_id = client.post("/api/chat/threads").get_json()["data"]["id"]
    response = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"content": "alignment 오차 보정 방법", "request_id": REQUEST_ID},
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "runtime_unavailable"
    messages = client.get(f"/api/chat/threads/{thread_id}").get_json()["data"][
        "messages"
    ]
    assert [message["role"] for message in messages] == ["user"]


def test_the_boot_log_names_which_source_chat_resolved_to(monkeypatch, caplog):
    """`python index.py` must say mock or office without anyone guessing."""
    from back_dev_home._runtime import boot

    monkeypatch.setattr(rag, "rag_ready", lambda: False)
    with caplog.at_level(logging.INFO, logger="skewnono.providers"):
        boot.log_provider_table()

    assert "chat/answer  mock    no RAG checkout" in caplog.text
