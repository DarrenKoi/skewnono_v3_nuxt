import pytest

from back_dev_home.chat import config


def test_answer_timeout_is_clamped(monkeypatch):
    """The whole-turn ceiling: a typo must not remove the ceiling."""
    monkeypatch.delenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", raising=False)
    assert config.get_answer_timeout() == 180.0
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", "9999")
    assert config.get_answer_timeout() == 360.0
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", "0")
    assert config.get_answer_timeout() == 1.0


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


def test_figure_prefix_defaults_to_the_office_layout(monkeypatch):
    """RAG 측 확인 2026-08-31: {namespace}/skewnono_rag/hitachi_manuals/figures/{id}.webp."""
    monkeypatch.delenv("SKEWNONO_CHAT_FIGURE_PREFIX", raising=False)

    assert config.get_figure_prefix() == "skewnono_rag/hitachi_manuals/figures/"


@pytest.mark.parametrize(
    "raw",
    ["other_sem/manual_figures", "/other_sem/manual_figures/", " other_sem/manual_figures// "],
)
def test_figure_prefix_is_normalized_to_one_trailing_slash(monkeypatch, raw):
    """Catches ``figure_key()`` producing ``//`` or a namespace-rooted key."""
    monkeypatch.setenv("SKEWNONO_CHAT_FIGURE_PREFIX", raw)

    assert config.get_figure_prefix() == "other_sem/manual_figures/"


def test_figure_bucket_is_unset_by_default(monkeypatch):
    """Unset means the MinIO client's own default bucket (``user`` at the office)."""
    monkeypatch.delenv("SKEWNONO_CHAT_FIGURE_BUCKET", raising=False)

    assert config.get_figure_bucket() is None


def test_answer_history_limit_defaults_and_clamps(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_ANSWER_MAX_HISTORY", raising=False)
    assert config.get_answer_history_limit() == 5  # RAG 의 MAX_HISTORY 와 동일

    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_MAX_HISTORY", "500")
    assert config.get_answer_history_limit() == 100

    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_MAX_HISTORY", "0")
    assert config.get_answer_history_limit() == 1
