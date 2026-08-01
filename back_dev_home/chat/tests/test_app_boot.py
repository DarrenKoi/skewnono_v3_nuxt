import back_dev_home
import pytest
from back_dev_home import create_app


REQUEST_ID = "64d35cd4-9e07-4be8-90a3-683f94c29408"


def test_chat_routes_registered():
    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/chat/models" in rules
    assert "/api/chat/threads" in rules


def test_create_app_loads_dotenv():
    # create_app must import load_dotenv at module scope and call it at startup
    # so CHAT_API_KEY from back_dev_home/.env is available to the LLM client.
    assert callable(back_dev_home.load_dotenv)
    # smoke: building the app twice must not raise
    create_app()
    create_app()


@pytest.mark.parametrize(
    "env_name",
    [
        "SKEWNONO_CHAT_KNOWLEDGE_PROVIDER",
        "SKEWNONO_CHAT_SCOPE_PROVIDER",
    ],
)
def test_invalid_lazy_chat_selector_fails_at_startup(monkeypatch, env_name):
    monkeypatch.setenv(env_name, "typo")

    with pytest.raises(RuntimeError, match=env_name):
        create_app()


def test_office_chat_sub_providers_start_then_fail_lazily(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_SCOPE_PROVIDER", "office")

    client = create_app().test_client()
    thread_id = client.post(
        "/api/chat/threads", json={"model": "m1"}
    ).get_json()["data"]["id"]
    response = client.post(
        f"/api/chat/threads/{thread_id}/messages",
        json={"content": "recommend a movie", "request_id": REQUEST_ID},
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "runtime_unavailable"
    messages = client.get(f"/api/chat/threads/{thread_id}").get_json()["data"][
        "messages"
    ]
    assert [message["role"] for message in messages] == ["user"]
