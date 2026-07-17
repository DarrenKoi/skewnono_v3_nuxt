import json

from back_dev_home.chat import config


def test_list_models_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("CHAT_MODELS", raising=False)
    models = config.list_models()
    assert isinstance(models, list)
    assert models
    for m in models:
        assert set(m) >= {"id", "label"}


def test_list_models_parses_env_json(monkeypatch):
    monkeypatch.setenv("CHAT_MODELS", json.dumps([{"id": "x/y", "label": "XY"}]))
    assert config.list_models() == [{"id": "x/y", "label": "XY"}]


def test_base_url_default_and_strip(monkeypatch):
    monkeypatch.delenv("CHAT_BASE_URL", raising=False)
    assert config.get_base_url() == "https://openrouter.ai/api/v1"
    monkeypatch.setenv("CHAT_BASE_URL", "http://internal/v1/")
    assert config.get_base_url() == "http://internal/v1"


def test_timeout_default_and_override(monkeypatch):
    monkeypatch.delenv("CHAT_TIMEOUT", raising=False)
    assert config.get_timeout() == 60.0
    monkeypatch.setenv("CHAT_TIMEOUT", "12")
    assert config.get_timeout() == 12.0
