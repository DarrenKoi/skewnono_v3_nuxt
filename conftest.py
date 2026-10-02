"""Root conftest — applies to every collection root in ``testpaths``.

Tests build apps with bare create_app() and only set app.testing
afterwards, so start_scheduler's `if app.testing` guard runs too late --
the scheduler thread already exists by then. Without this, a suite run
between 01:00 and 08:00 (the jobs' quiet window) fires REAL jobs: a real
purge_image_cache() deleting cached images, a real write_weekly_snapshot()
writing to var/weekly_trend/. Set before any test imports backend,
so start_scheduler's env read (at call time) always sees it disabled.

This lives at the ROOT rather than in backend/conftest.py because
``testpaths = ["tests", "backend"]``: a focused run like
``pytest tests/test_rate_limit.py`` never loads backend's conftest, and
that fixture calls create_app().test_client() -- so the kill switch has to
cover both roots.
"""

import os

import pytest

os.environ["SKEWNONO_SCHEDULER_ENABLED"] = "0"


@pytest.fixture(autouse=True)
def _afm_mock_reads_one_fixed_day(monkeypatch):
    """The AFM mock's file list ends today, and a file's contents are seeded
    by its name -- so which recipe, block count or oddity the list holds
    changes with the calendar. Tests that pick rows out of it (three files
    across both roots) would pass or fail by date; pinning the day gives them
    one fixed set. A test about the rolling window sets its own day.
    """
    from backend.afm.providers import mock

    monkeypatch.setattr(mock, "_today", lambda: mock.BASE_TIME.date())
