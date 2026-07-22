"""run_once() — everything the host scheduler needs to call.

Portability is the governing constraint: this module must work on any
Flask + APScheduler server, so it asks the host for nothing but a periodic
call. No distributed lock, no app context, no framework logger. Duplicate
execution is safe because every Redis write here is idempotent.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from .normalize import (
    canonical_json,
    to_events,
)
from .window import compute_window


log = logging.getLogger(__name__)

KEY_PREFIX = "skewnono:live_alarm"
REGISTRY_KEY = f"{KEY_PREFIX}:registry"
TTL_SEC = 86_400
PRUNE_SEC = int(os.environ.get("LIVE_ALARM_PRUNE_SEC", "900"))
MAX_PARALLEL_FABS = 8

__all__ = ["run_once", "keys", "REGISTRY_KEY"]


def keys(tool_slug: str, fab_name: str) -> tuple[str, str]:
    base = f"{KEY_PREFIX}:{tool_slug}:{fab_name}"
    return f"{base}:events", f"{base}:meta"


def _last_polled_at(client, meta_key: str) -> int | None:
    raw = client.get(meta_key)
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return int(json.loads(text)["polled_at"])
    except (UnicodeDecodeError, ValueError, TypeError, KeyError):
        # Unreadable meta is indistinguishable from no meta: cold start.
        return None


def _poll_one(client, fetch, tool_slug: str, fab_name: str, now: int) -> None:
    events_key, meta_key = keys(tool_slug, fab_name)

    window, covered_since = compute_window(
        _last_polled_at(client, meta_key),
        events_key_exists=bool(client.exists(events_key)),
        now=now,
    )

    rows = fetch(tool_slug, fab_name, window)      # raises on failure
    events = to_events(rows, now=now)

    pipe = client.pipeline()
    if events:
        # redis-py rejects an empty mapping, and an empty window is normal.
        pipe.zadd(events_key, {canonical_json(e): e["occurred_epoch"] for e in events})
    pipe.zremrangebyscore(events_key, "-inf", now - PRUNE_SEC)
    pipe.expire(events_key, TTL_SEC)
    pipe.set(
        meta_key,
        json.dumps({"polled_at": now, "covered_since": covered_since}),
        ex=TTL_SEC,
    )
    pipe.sadd(REGISTRY_KEY, f"{tool_slug}:{fab_name}")
    pipe.expire(REGISTRY_KEY, TTL_SEC)
    pipe.execute()


def run_once(fetch=None, client=None, fabs=None) -> None:
    """One scheduler tick. Poll every configured fab and write the board.

    The heartbeat is only stamped on success — a failed poll must leave it
    ageing, because a fresh heartbeat over missing data is the one failure
    mode this whole design exists to prevent.

    Partial failure is swallowed so one dark fab cannot blind the rest.
    Total failure raises: the host's run log would otherwise record a
    successful execution while every fab is down.
    """
    if fetch is None or client is None or fabs is None:
        from . import office
        fetch = fetch or office.fetch_alarms
        client = client if client is not None else office.redis_client()
        fabs = fabs or office.configured_fabs()

    now = int(client.time()[0])   # Redis is the single clock authority
    failures: list[str] = []

    def attempt(target: tuple[str, str]) -> None:
        tool_slug, fab_name = target
        try:
            _poll_one(client, fetch, tool_slug, fab_name, now)
        except Exception:
            failures.append(f"{tool_slug}:{fab_name}")
            log.exception("live_alarm poll failed for %s/%s", tool_slug, fab_name)

    targets = list(fabs)
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FABS, max(1, len(targets)))) as pool:
        list(pool.map(attempt, targets))

    if targets and len(failures) == len(targets):
        raise RuntimeError(f"live_alarm: every fab failed ({', '.join(failures)})")
