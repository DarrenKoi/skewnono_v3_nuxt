import back_dev_home
from back_dev_home import create_app


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
