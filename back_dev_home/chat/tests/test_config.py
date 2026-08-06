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


def test_under_development_follows_the_deploy_unless_overridden(monkeypatch):
    """Catches chat looking live to production users, or hidden at the office.

    The default has to track the deploy rather than a checked-in constant: a
    hardcoded True would hide the page at home and at the office too, and a
    hardcoded False is exactly the state this flag exists to prevent.
    """
    monkeypatch.delenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", raising=False)

    monkeypatch.setattr(config, "is_cloud", lambda: True)
    assert config.is_under_development() is True
    monkeypatch.setattr(config, "is_cloud", lambda: False)
    assert config.is_under_development() is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("on", True), ("YES", True),
     ("0", False), ("false", False), ("off", False), ("nonsense", False)],
)
def test_under_development_override_beats_the_deploy_default(monkeypatch, raw, expected):
    """Catches an override that can only turn the notice on, never off.

    Launch day is a config flip on the cloud host, so `0` has to beat a
    cloud default of True — an override honoured in one direction only would
    leave no way to ship without a code change.
    """
    monkeypatch.setattr(config, "is_cloud", lambda: True)
    monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", raw)

    assert config.is_under_development() is expected


def test_knowledge_candidate_pool_default_and_clamp(monkeypatch):
    """Catches a typo'd env var name or a dropped clamp reaching the backend.

    The default (unset) case exercises the fallback; a below-floor value, an
    above-ceiling value, and a normal in-range value each exercise both the
    read of SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES and the min(max(x, 5), 50)
    clamp, so a widened over-fetch (e.g. an unclamped 5000) would fail here.
    """
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", raising=False)
    assert config.get_knowledge_candidate_pool() == 24

    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "1")
    assert config.get_knowledge_candidate_pool() == 5

    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "5000")
    assert config.get_knowledge_candidate_pool() == 50

    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "31")
    assert config.get_knowledge_candidate_pool() == 31


def test_blank_override_falls_through_to_the_deploy_default(monkeypatch):
    """Catches a blank env var being read as an explicit 'no'.

    An empty SKEWNONO_CHAT_UNDER_DEVELOPMENT= line in .env means "unset", not
    "launch". Treating it as an override would silently expose the page in
    production on the strength of a stray line.
    """
    monkeypatch.setattr(config, "is_cloud", lambda: True)

    for blank in ("", "   "):
        monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", blank)
        assert config.is_under_development() is True
