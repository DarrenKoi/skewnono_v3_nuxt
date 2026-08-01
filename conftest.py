"""Root conftest — applies to every collection root in ``testpaths``.

Tests build apps with bare create_app() and only set app.testing
afterwards, so start_scheduler's `if app.testing` guard runs too late --
the scheduler thread already exists by then. Without this, a suite run
between 01:00 and 08:00 (the jobs' quiet window) fires REAL jobs: a real
purge_image_cache() deleting cached images, a real write_weekly_snapshot()
writing to var/weekly_trend/. Set before any test imports back_dev_home,
so start_scheduler's env read (at call time) always sees it disabled.

This lives at the ROOT rather than in back_dev_home/conftest.py because
``testpaths = ["tests", "back_dev_home"]``: a focused run like
``pytest tests/test_rate_limit.py`` never loads back_dev_home's conftest, and
that fixture calls create_app().test_client() -- so the kill switch has to
cover both roots.
"""

import os

os.environ["SKEWNONO_SCHEDULER_ENABLED"] = "0"
