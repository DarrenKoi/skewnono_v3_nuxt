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
"""

from __future__ import annotations

import json
import logging
import secrets

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    CACHE_TTL_SEC,
    LOCK_TTL_SEC,
    PRUNE_SEC,
)
from back_dev_home.ebeam.hitachi.live_alarm.normalize import canonical_json, to_events


log = logging.getLogger(__name__)

KEY_PREFIX = "skewnono:live_alarm"
TTL_SEC = 86_400

__all__ = ["keys", "read_meta", "ensure_fresh"]

# Compare-and-delete. A fetch that outlived its own lock TTL must not delete
# the SUCCESSOR's lock, which is what an unconditional DEL would do.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def keys(fac_id: str) -> tuple[str, str, str]:
    """events, meta, lock — all scoped to the FACILITY, not the fab.

    fac_id is the granularity the office call is parameterized by, so M16A,
    M16B and M16C share one entry and issue one upstream call between them.
    """
    base = f"{KEY_PREFIX}:{fac_id}"
    return f"{base}:events", f"{base}:meta", f"{base}:lock"


def read_meta(client, fac_id: str) -> dict | None:
    _, meta_key, _ = keys(fac_id)
    raw = client.get(meta_key)
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


def _office_fetch():
    """Bind the office callable, or explain why it is missing.

    Imported inside the function because office_utils is gitignored and does
    not exist at home; a module-scope import would break every developer
    machine's import of this module.
    """
    try:
        from office_utils.live_alarm import get_live_alarms
    except ImportError as exc:
        raise RuntimeError(
            "office_utils.live_alarm is not importable — live_alarm's office "
            "provider needs the office-only office_utils package on sys.path. "
            "Copy it onto this host, or run with "
            "SKEWNONO_LIVE_ALARM_PROVIDER=mock."
        ) from exc

    def fetch(fac_id: str) -> list[dict]:
        frame = get_live_alarms(fac_id)
        # DataFrame -> dict rows (CLAUDE.md's dataframe-dict convention).
        # NaN survives to_dict; normalize._text is what guards it.
        if hasattr(frame, "to_dict"):
            return frame.to_dict(orient="records")
        return list(frame)

    return fetch


def _write_board(client, fac_id: str, events: list[dict], now: int) -> None:
    events_key, meta_key, _ = keys(fac_id)
    pipe = client.pipeline()
    if events:
        # redis-py rejects an empty mapping, and a quiet facility is normal.
        pipe.zadd(events_key, {canonical_json(e): e["occurred_epoch"] for e in events})
    pipe.zremrangebyscore(events_key, "-inf", now - PRUNE_SEC)
    pipe.expire(events_key, TTL_SEC)
    pipe.set(meta_key, json.dumps({"fetched_at": now}), ex=TTL_SEC)
    pipe.execute()


def ensure_fresh(client, fac_id: str, *, now: int, fetch=None) -> None:
    """Refresh this facility's board if the cache has lapsed. Never blocks."""
    meta = read_meta(client, fac_id)
    if meta and now - int(meta["fetched_at"]) < CACHE_TTL_SEC:
        return

    # Bound BEFORE the lock is taken. A missing office_utils is a deployment
    # fault that must surface as a 503 — not be swallowed as a transient
    # failure, and not hold a lock for LOCK_TTL_SEC on the way out.
    fetcher = fetch or _office_fetch()

    _, _, lock_key = keys(fac_id)
    token = secrets.token_hex(8)
    if not client.set(lock_key, token, nx=True, ex=LOCK_TTL_SEC):
        return   # another request is fetching; serve the board already here

    try:
        rows = fetcher(fac_id)
        _write_board(client, fac_id, to_events(rows, now=now), now)
    except Exception:
        log.exception("live_alarm refresh failed for fac_id=%s", fac_id)
        # The lock is deliberately NOT released: it expires in LOCK_TTL_SEC
        # and is the retry backoff.
        return

    client.eval(_RELEASE_LUA, 1, lock_key, token)
