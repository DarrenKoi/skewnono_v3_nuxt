import pytest

from back_dev_home.chat import config


def test_answer_timeout_is_clamped(monkeypatch):
    """The cap is the RAG's own hard ceiling, not a number of our choosing.

    They stop a turn at 300s outright (RAG 측 확인 2026-09-01), so a
    deployment asking for more would have chat waiting on time that will
    never arrive.
    """
    monkeypatch.delenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", raising=False)
    assert config.get_answer_timeout() == 240.0
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", "9999")
    assert config.get_answer_timeout() == 300.0
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", "0")
    assert config.get_answer_timeout() == 1.0


def test_the_page_is_in_service_by_default(monkeypatch):
    """Catches the pre-launch cloud default creeping back in.

    Chat launched 2026-09-01, so an unset flag means "show the page" on every
    phase including the production cloud — the notice is now opt-IN.
    """
    monkeypatch.delenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", raising=False)

    assert config.is_under_development() is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("on", True), ("YES", True),
     ("0", False), ("false", False), ("off", False), ("nonsense", False)],
)
def test_under_development_override_beats_the_default(monkeypatch, raw, expected):
    """Catches an override that only works in one direction.

    Post-launch the load-bearing direction is `1`: taking the page down on
    the cloud must not need a deploy. `0` is kept honoured so an old cloud
    `.env` line from before the launch still means what it said.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", raw)

    assert config.is_under_development() is expected


def test_blank_override_falls_through_to_the_default(monkeypatch):
    """Catches a blank env var being read as an explicit answer.

    An empty SKEWNONO_CHAT_UNDER_DEVELOPMENT= line in .env means "unset", not
    "1" — a stray line must not take the page down.
    """
    for blank in ("", "   "):
        monkeypatch.setenv("SKEWNONO_CHAT_UNDER_DEVELOPMENT", blank)
        assert config.is_under_development() is False


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
