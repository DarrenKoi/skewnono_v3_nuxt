import json

import pytest

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
    assert config.list_models() == [{
        "id": "x/y",
        "label": "XY",
        "supports_tools": False,
        "supports_vision": False,
    }]


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


def test_models_default_missing_capabilities_to_false(monkeypatch):
    monkeypatch.setenv("CHAT_MODELS", '[{"id":"m1","label":"Model 1"}]')
    assert config.list_models() == [{
        "id": "m1",
        "label": "Model 1",
        "supports_tools": False,
        "supports_vision": False,
    }]


def test_runtime_and_provider_defaults(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_RUNTIME", raising=False)
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", raising=False)
    monkeypatch.delenv("SKEWNONO_CHAT_SCOPE_PROVIDER", raising=False)
    assert config.get_runtime_name() == "direct"
    assert config.get_knowledge_provider_name() == "mock"
    assert config.get_scope_provider_name() == "mock"


def test_invalid_runtime_is_rejected(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_RUNTIME", "unknown")
    with pytest.raises(ValueError, match="SKEWNONO_CHAT_RUNTIME"):
        config.get_runtime_name()


def test_agent_bounds_are_clamped(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_MAX_TOOL_CALLS", "999")
    assert config.get_max_tool_calls() == 12


def test_max_concurrent_agent_runs_is_strictly_bounded(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS", raising=False)
    assert config.get_max_concurrent_agent_runs() == 4

    monkeypatch.setenv("SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS", "3")
    assert config.get_max_concurrent_agent_runs() == 3

    for invalid in ("0", "33", "not-an-integer"):
        monkeypatch.setenv("SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS", invalid)
        with pytest.raises(ValueError, match="SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS"):
            config.get_max_concurrent_agent_runs()


def test_evidence_bounds_have_application_defaults_and_hard_maxima(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_MAX_SNIPPET_CHARS", raising=False)
    monkeypatch.delenv("SKEWNONO_CHAT_MAX_EVIDENCE_CHARS", raising=False)
    assert config.get_max_snippet_chars() == 1200
    assert config.get_max_evidence_chars() == 12000

    monkeypatch.setenv("SKEWNONO_CHAT_MAX_SNIPPET_CHARS", "999999")
    monkeypatch.setenv("SKEWNONO_CHAT_MAX_EVIDENCE_CHARS", "999999")
    assert config.get_max_snippet_chars() == 4000
    assert config.get_max_evidence_chars() == 40000
