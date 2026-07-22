"""The startup provider table and its logger."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from back_dev_home._logging.providers import install_provider_logging, logger
from back_dev_home._runtime import boot


_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def captured():
    """Capture on the logger itself.

    caplog attaches to the ROOT logger, and skewnono.providers deliberately
    sets propagate=False so its table cannot be swallowed by whatever the root
    level happens to be — which also means caplog never sees these records.
    """
    install_provider_logging()
    records: list[str] = []

    class _Sink(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    sink = _Sink()
    logger.addHandler(sink)
    yield records
    logger.removeHandler(sink)


def test_table_names_every_feature_with_provider_and_reason(
    monkeypatch, wired, captured
):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    boot.log_provider_table()
    text = "\n".join(captured)

    assert "mode=office" in text
    assert "sem_list" in text and "providers/office.py found" in text
    assert "chat" in text and "no providers/office.py" in text


def test_table_counts_only_the_features_actually_on_office(
    monkeypatch, wired, captured
):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    boot.log_provider_table()
    assert "2/4 features on office" in captured[0]


def test_install_is_idempotent_and_configures_the_logger():
    """The logger must carry its own handler and level like skewnono.activity —
    app.logger defaults to WARNING, which would make the table invisible in
    exactly the deployment where it matters."""
    install_provider_logging()
    before = len(logger.handlers)
    install_provider_logging()

    assert len(logger.handlers) == before  # no duplicate handler, no dupe lines
    assert logger.level == logging.INFO
    assert logger.propagate is False


def test_importing_the_logger_does_not_configure_it():
    """Setup belongs in a function the app factory calls, not an import side
    effect: hardware's office adapter imports this logger, and that import
    must not mutate global logging state.

    Run in a subprocess because this process has already configured it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from back_dev_home._logging.providers import logger;"
            "print(len(logger.handlers), logger.level)",
        ],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0 0"
