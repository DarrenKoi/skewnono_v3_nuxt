"""Transfer limits. The FTP account/encoding knobs are msr_image's, reused as-is.

Every default here is a proposal (OFFICE-VERIFY): real log and recipe sizes,
and the largest LIST a tool returns, have not been measured at the office.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Limits:
    max_bytes: int = 100 * 1024 * 1024
    # Cloud wsgi.ini harakiri is 720 s, so 120 s leaves the worker alive.
    deadline: float = 120.0
    # Phase 2 proxy transport: the proxy host's harakiri is 60 s
    # (flask_modules api/wsgi.ini; scheduler1's own value is OFFICE-VERIFY).
    proxy_deadline: float = 45.0
    max_entries: int = 20000
    max_list_bytes: int = 4 * 1024 * 1024
    max_upload_bytes: int = 100 * 1024 * 1024


def _positive(env: Mapping[str, str], key: str, default, cast):
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        value = 0
    if value <= 0:
        _LOG.warning("%s=%r is not a positive number; using %s", key, raw, default)
        return default
    return value


def write_enabled(env: Mapping[str, str] | None = None) -> bool:
    """``SKEWNONO_TOOL_FILES_WRITE``: upload and delete stay off unless set truthy."""
    env = os.environ if env is None else env
    return env.get("SKEWNONO_TOOL_FILES_WRITE", "").strip().lower() in {"1", "true", "yes", "on"}


def load_limits(env: Mapping[str, str] | None = None) -> Limits:
    env = os.environ if env is None else env
    base = Limits()
    return Limits(
        max_bytes=_positive(env, "SKEWNONO_TOOL_FILES_MAX_BYTES", base.max_bytes, int),
        deadline=_positive(env, "SKEWNONO_TOOL_FILES_DEADLINE", base.deadline, float),
        proxy_deadline=_positive(
            env, "SKEWNONO_TOOL_FILES_PROXY_DEADLINE", base.proxy_deadline, float
        ),
        max_entries=_positive(env, "SKEWNONO_TOOL_FILES_MAX_ENTRIES", base.max_entries, int),
        max_list_bytes=_positive(
            env, "SKEWNONO_TOOL_FILES_MAX_LIST_BYTES", base.max_list_bytes, int
        ),
        max_upload_bytes=_positive(
            env, "SKEWNONO_TOOL_FILES_MAX_UPLOAD_BYTES", base.max_upload_bytes, int
        ),
    )
