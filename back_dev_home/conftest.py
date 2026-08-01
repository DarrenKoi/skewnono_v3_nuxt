"""Load back_dev_home/.env for every backend test run.

The Flask app factory calls load_dotenv at startup, but pytest imports
feature modules directly without creating an app. Office-mode contract
tests (SKEWNONO_<FEATURE>_PROVIDER=office) need the REDIS_* / connection
vars from .env, so mirror the app factory's loading here.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Tests build apps with bare create_app() and only set app.testing
# afterwards, so start_scheduler's `if app.testing` guard runs too late --
# the scheduler thread already exists by then. Without this, a suite run
# between 01:00 and 08:00 (the jobs' quiet window) fires REAL jobs: a real
# purge_image_cache() deleting cached images, a real write_weekly_snapshot()
# writing to var/weekly_trend/. Set before any test imports back_dev_home,
# so start_scheduler's env read (at call time) always sees it disabled.
import os

os.environ["SKEWNONO_SCHEDULER_ENABLED"] = "0"
