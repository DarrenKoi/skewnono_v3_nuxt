"""Environment-driven config for the shared scheduler.

Same shape as ``msr_image/config.py``: ``env`` is a parameter with an
``os.environ`` default, so tests pass a dict instead of monkeypatching, and a
malformed value falls back to the default rather than raising. The scheduler is
plumbing -- refusing to boot over one typo'd env var would cost more than the
bad value does.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, "").strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class SchedulerConfig:
    # Orphan-clear window, NOT a runtime budget. A live run re-arms its own TTL
    # (see locks.py), so this only bounds how long a lock survives a process
    # that died without releasing it. All three jobs are daily or weekly, so
    # any value under a day skips zero runs -- keep it small so an orphan from
    # an OOM-killed worker clears in minutes instead of blocking tomorrow too.
    lock_ttl: int = 600
    lock_key_prefix: str = "skewnono:scheduler:lock:"
    log_list_key: str = "skewnono:scheduler:logs"
    log_list_max: int = 500
    timezone: str = "Asia/Seoul"


def load_scheduler_config(env: Mapping[str, str] | None = None) -> SchedulerConfig:
    env = os.environ if env is None else env
    return SchedulerConfig(
        lock_ttl=_int(env, "SKEWNONO_SCHEDULER_LOCK_TTL", 600),
        log_list_max=_int(env, "SKEWNONO_SCHEDULER_LOG_MAX", 500),
    )
