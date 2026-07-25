"""The provider-table logger's own setup.

``_runtime/tests/test_boot_providers.py`` covers what the table *says* and that
installing it twice adds no second handler. What it cannot cover is the setup
itself: by the time it runs, this process has already configured the logger, so
"install() from an unconfigured logger" and "the record survives a hostile root
level" are only observable here.
"""

import logging
import re
import sys

from back_dev_home._logging.providers import install_provider_logging, logger


def _unconfigure(preserve_logger):
    """Return the providers logger in its just-imported state."""
    providers = preserve_logger("skewnono.providers")
    providers.handlers[:] = []
    providers.setLevel(logging.NOTSET)
    providers.propagate = True
    return providers


def test_install_configures_the_logger_from_scratch(preserve_logger):
    """One handler, INFO, no propagation — asserted from zero handlers rather
    than from "no more than before", which is all the boot test can see."""
    providers = _unconfigure(preserve_logger)

    install_provider_logging()

    assert len(providers.handlers) == 1
    assert providers.level == logging.INFO
    assert providers.propagate is False


def test_install_never_touches_the_root_logger(preserve_logger):
    """The app factory calls this before any other logging setup. Adding a root
    handler here would double every line uwsgi already captures, and raising the
    root level would turn the whole app chatty as a side effect of printing a
    four-line table."""
    root = preserve_logger("")
    _unconfigure(preserve_logger)
    handlers_before, level_before = list(root.handlers), root.level

    install_provider_logging()

    assert list(root.handlers) == handlers_before
    assert root.level == level_before


def test_the_table_survives_a_hostile_root_level(preserve_logger):
    """Why the logger carries its own level at all: under uwsgi the root logger
    sits at WARNING, and the table is INFO. propagate=False plus an own level
    means the roster prints regardless of what configured the root."""
    _unconfigure(preserve_logger)
    root = preserve_logger("")
    root.setLevel(logging.CRITICAL)
    install_provider_logging()
    seen: list[str] = []
    logger.addHandler(_sink(seen))

    logger.info("data providers: site=%s", "office")

    assert seen == ["data providers: site=office"]


def test_records_carry_a_timestamp_and_a_level(preserve_logger):
    """The table is read out of a plain uwsgi log days after boot. Without the
    level, a STALE warning reads like another roster row; without the
    timestamp, there is no way to tell which restart printed it."""
    providers = _unconfigure(preserve_logger)
    install_provider_logging()
    handler = providers.handlers[0]

    text = handler.format(
        logging.LogRecord(
            name="skewnono.providers",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="  STALE office.py: %s",
            args=("sem_list",),
            exc_info=None,
        )
    )

    assert re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", text), text
    assert "WARNING" in text
    assert "STALE office.py: sem_list" in text


def test_records_go_to_stderr(preserve_logger):
    """uwsgi's log is stderr. A handler on stdout would interleave the roster
    with whatever the app prints, and under some server configs vanish."""
    providers = _unconfigure(preserve_logger)

    install_provider_logging()

    assert providers.handlers[0].stream is sys.stderr


def _sink(records: list[str]) -> logging.Handler:
    class _Sink(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    return _Sink()
