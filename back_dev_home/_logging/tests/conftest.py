"""Shared fixtures for the logging tests.

Two things bite every test in this package.

Loggers are process-global. ``skewnono.providers`` and ``skewnono.activity``
are module-level objects configured by an install function, so a test that
attaches a handler or lowers a level hands that state to whatever runs next —
these tests must pass alone and inside the full suite alike. ``preserve_logger``
snapshots and restores anything a test touches, including the root logger.

The OpenSearch handler reads its config straight from ``os.environ``, and at
the office ``back_dev_home/.env`` (loaded by the package conftest) carries real
credentials. Strip the whole prefix so "no credentials" tests mean it.
"""

import logging
import os

import pytest


@pytest.fixture(autouse=True)
def _clean_opensearch_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("OPENSEARCH_"):
            monkeypatch.delenv(name)


@pytest.fixture
def preserve_logger():
    """Factory: hand back a logger with its handlers/level/propagate restored."""
    saved = []

    def keep(name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        saved.append((logger, list(logger.handlers), logger.level, logger.propagate))
        return logger

    yield keep

    for logger, handlers, level, propagate in reversed(saved):
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
