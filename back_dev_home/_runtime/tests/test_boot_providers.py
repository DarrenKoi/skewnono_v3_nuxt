"""The startup provider table, and boot refusal on unhonorable config."""

import logging
import os

import pytest

from back_dev_home._runtime import boot, office_registry


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SKEWNONO_SITE", raising=False)
    for name in list(os.environ):
        if name.startswith("SKEWNONO_") and name.endswith("_PROVIDER"):
            monkeypatch.delenv(name)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    root = tmp_path / "back_dev_home"
    for rel, filenames in {
        "sem_list": ["mock.py", "office.py"],
        "chat": ["mock.py"],
    }.items():
        providers = root / rel / "providers"
        providers.mkdir(parents=True)
        for filename in filenames:
            (providers / filename).write_text("")
    monkeypatch.setattr(office_registry, "_ROOT", root)
    office_registry.reset_cache()
    yield root
    office_registry.reset_cache()


def test_table_names_every_feature_with_provider_and_reason(
    monkeypatch, wired, caplog
):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    with caplog.at_level(logging.INFO, logger="skewnono.providers"):
        boot.log_provider_table()
    text = caplog.text
    assert "mode=office" in text
    assert "sem_list" in text and "providers/office.py found" in text
    assert "chat" in text and "no providers/office.py" in text


def test_table_logs_at_info_on_its_own_logger():
    """The logger must carry its own handler+level like skewnono.activity —
    app.logger defaults to WARNING, which would make the table invisible in
    exactly the deployment where it matters."""
    logger = logging.getLogger("skewnono.providers")
    assert logger.level == logging.INFO
    assert logger.handlers
    assert logger.propagate is False
