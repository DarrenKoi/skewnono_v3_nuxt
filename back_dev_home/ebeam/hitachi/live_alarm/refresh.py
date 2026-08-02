"""On-demand board refresh: a short cache in front of the in-house alarm API.

The page request is the trigger. Freshness is checked first, so the common
case makes no office call at all; when the cache has lapsed, exactly one
request wins a lock and fetches while every other request serves the board
already in Redis.

Three rules hold this together:

* the lock is NON-BLOCKING — a loser never waits, it serves what is there;
* ``fetched_at`` is stamped ONLY on success, so a failing feed ages into
  "stale" rather than reporting a fresh heartbeat over missing data;
* the lock is released only on success, so its TTL doubles as the retry
  backoff and an office API already in trouble is not retried by every poll
  of every viewer.

The events key stays an ACCUMULATING ZSET rather than a last-response cache.
``get_live_alarms`` takes no window argument, so how far back it reaches is
the office's choice; if it reports only currently-active alarms, a
last-response cache could never hold the 10-minute board. Accumulation is
safe because ZSET members are canonical JSON, making a repeated event a no-op.

Nothing here imports ``office_utils`` or knows what the office is: ``fetch``
is injected by the caller. That keeps this module — cache and lock policy
over an injected client — importable and testable at home, and leaves the
office binding in the adapter that is copied to make ``office.py``.
"""

from __future__ import annotations

import json
import logging
from typing import NamedTuple

from redis.exceptions import LockError
from redis.lock import Lock

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    CACHE_TTL_SEC,
    KEY_TTL_SEC,
    LOCK_TTL_SEC,
    PRUNE_SEC,
)
from back_dev_home.ebeam.hitachi.live_alarm.normalize import canonical_json, to_events


log = logging.getLogger(__name__)

KEY_PREFIX = "skewnono:live_alarm"

__all__ = ["BoardKeys", "keys", "read_meta", "ensure_fresh"]


class BoardKeys(NamedTuple):
    """Named so callers stop writing ``events_key, _, _ = keys(fac_id)``."""

    events: str
    meta: str
    lock: str


def keys(fac_id: str) -> BoardKeys:
    """events, meta, lock — all scoped to the FACILITY, not the fab.

    fac_id is the granularity the office call is parameterized by, so M16A,
    M16B and M16C share one entry and issue one upstream call between them.
    """
    base = f"{KEY_PREFIX}:{fac_id}"
    return BoardKeys(f"{base}:events", f"{base}:meta", f"{base}:lock")


def read_meta(client, fac_id: str) -> dict | None:
    raw = client.get(keys(fac_id).meta)
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        payload = json.loads(text)
    except (UnicodeDecodeError, ValueError, TypeError):
        # Unreadable meta is indistinguishable from no meta: treat as cold.
        return None
    if not isinstance(payload, dict) or "fetched_at" not in payload:
        return None
    return payload


def _write_board(client, fac_id: str, events: list[dict], now: int) -> None:
    board_keys = keys(fac_id)
    pipe = client.pipeline()
    if events:
        # redis-py rejects an empty mapping, and a quiet facility is normal.
        pipe.zadd(
            board_keys.events,
            {canonical_json(e): e["occurred_epoch"] for e in events},
        )
    pipe.zremrangebyscore(board_keys.events, "-inf", now - PRUNE_SEC)
    pipe.expire(board_keys.events, KEY_TTL_SEC)
    pipe.set(board_keys.meta, json.dumps({"fetched_at": now}), ex=KEY_TTL_SEC)
    pipe.execute()


def ensure_fresh(client, fac_id: str, *, now: int, fetch) -> dict | None:
    """Refresh this facility's board if the cache has lapsed. Never blocks.

    Returns the meta the caller should report — ``{"fetched_at": now}`` when
    this call refreshed, otherwise whatever was already stored (``None`` if
    nothing ever succeeded). Returned rather than re-read so the caller does
    not need a second round trip to observe the write this call just made.
    """
    meta = read_meta(client, fac_id)
    if meta and now - int(meta["fetched_at"]) < CACHE_TTL_SEC:
        return meta

    # redis-py's own lock: SET NX PX to acquire, and an owner-checked
    # compare-and-delete to release, so a fetch that outlived its TTL cannot
    # delete the successor's lock. Same choice _scheduler/locks.py made, and
    # for the same reason — the release script is the driver's, not ours.
    lock = Lock(client, keys(fac_id).lock, timeout=LOCK_TTL_SEC, thread_local=False)
    if not lock.acquire(blocking=False):
        return meta   # another request is fetching; serve what is already here

    try:
        rows = fetch(fac_id)
        _write_board(client, fac_id, to_events(rows, now=now), now)
    except Exception:
        log.exception("live_alarm refresh failed for fac_id=%s", fac_id)
        # The lock is deliberately NOT released: it expires in LOCK_TTL_SEC
        # and is the retry backoff.
        return meta

    try:
        lock.release()
    except LockError:
        # Our lock lapsed during a fetch slower than LOCK_TTL_SEC, and may
        # already belong to a successor. The board WAS written, so this must
        # not fail the request — hence an explicit guard rather than the
        # `raise_on_release_error` flag, which redis-py honours only in the
        # context manager, and `with lock:` would release in a finally and
        # destroy the don't-release-on-failure backoff above.
        log.warning(
            "live_alarm lock for fac_id=%s expired before release "
            "(fetch slower than %ss)", fac_id, LOCK_TTL_SEC,
        )
    return {"fetched_at": now}
