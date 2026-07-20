"""Load back_dev_home/.env for every backend test run.

The Flask app factory calls load_dotenv at startup, but pytest imports
feature modules directly without creating an app. Office-mode contract
tests (SKEWNONO_<FEATURE>_PROVIDER=office) need the REDIS_* / connection
vars from .env, so mirror the app factory's loading here.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
