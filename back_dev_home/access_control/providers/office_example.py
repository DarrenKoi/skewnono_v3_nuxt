"""Tracked office adapter for access-control policy data, backed by Redis.

Copy to ``office.py`` to activate (``cp office_example.py office.py``) — this
file holds no in-house address or secret, so the copy is verbatim. The Redis
host/password come from ``back_dev_home/.env`` via ``_runtime/office_redis.py``.

Layout — one hash for grants, one sorted set for denied attempts:

    skewnono:access_control:exceptions   HASH  <USER_ID> -> granted_at (ISO Z)
    skewnono:access_control:denied       ZSET  <USER_ID> scored by epoch seconds

DIVERGENCE FROM MIGRATION.md's original hint, which suggested a key per
exception plus a SET index. One hash is strictly better at every call site:
``list_exceptions`` is a single ``HGETALL`` instead of ``SMEMBERS`` + N
``HGET``s; ``is_blocked`` — which runs on every request from an X-member — is a
single ``HEXISTS``; idempotent granting is ``HSETNX``, atomic, with no
read-before-write race; and ``HDEL``'s 0/1 return *is* the bool
``remove_exception`` owes its caller.

The ZSET is likewise a better fit than a list: ``ZADD`` on an existing member
updates its score in place, which is exactly the mock's "a repeat denial
refreshes the timestamp and moves the entry to most-recent, it does not
duplicate" semantics, and ``ZREVRANGE`` gives most-recent-first for free.

OUTAGE BEHAVIOR follows one rule: **never report an infrastructure failure as a
policy decision.** The app factory (``back_dev_home/__init__.py``) already maps
redis ``ConnectionError``/``TimeoutError`` and bare ``RuntimeError`` to a JSON
503, so propagating produces a truthful status rather than an opaque 500:

* ``is_blocked`` — called by ``_auth/middleware.py::_deny_if_blocked`` on every
  request. PROPAGATES. Returning ``False`` would let blocked members in;
  returning ``True`` would tell a legitimately-granted member they are "not
  allowed to use this service" — a lie that sends someone chasing a policy
  problem that does not exist. Propagating is *also* fail-closed, since the
  request is not served either way, so it strictly dominates both. Only
  X-prefixed ids reach Redis at all, so an outage cannot affect anyone else.
* ``list_exceptions`` / ``list_denied`` — PROPAGATE. An admin shown an empty
  exception table during an outage may conclude the grants were lost and start
  re-granting; 503 is the honest answer.
* ``add_exception`` / ``remove_exception`` — raise ``StoreUnavailableError``,
  imported from ``providers.mock`` and never redefined, because ``routes.py``
  catches that exact class for a more specific 503 ("grant NOT saved") than the
  generic handler gives. A bare redis error would sail past its ``except``.
* ``record_denied`` — SWALLOWS. It runs only after ``is_blocked`` already
  returned True, so the store was readable a moment ago, and a failure here must
  not convert a correct 403 into a 503. Recording an attempt is a convenience
  view for the admin page, not enforcement.

This diverges from the mock, whose reads fail safe to an empty store. That is
right for the mock — its failure mode is a corrupt local JSON file, where
carrying on is reasonable — and wrong here, where the failure is a server that
is not answering and there is a status code that says exactly that.

``BLOCKED_PREFIX`` and ``_now_iso`` are imported from ``providers.mock`` rather
than restated: the blocking rule is provider-independent policy, and the
timestamp format (seconds precision, literal ``Z``) must not drift or the
frontend would have to branch on provider to parse it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import redis

from back_dev_home.access_control.providers.mock import (
    BLOCKED_PREFIX,
    StoreUnavailableError,
    _DENIED_CAP,
    _now_iso,
)

__all__ = ["StoreUnavailableError"]

logger = logging.getLogger("skewnono.access_control")

_EXC_KEY = "skewnono:access_control:exceptions"
_DENIED_KEY = "skewnono:access_control:denied"

# Redis errors that mean "the store is unreachable/unusable right now".
# OSError covers socket-level failures redis-py lets through unwrapped.
_STORE_ERRORS = (redis.exceptions.RedisError, OSError)


def _client():
    # Lazy: office-only dependency, keeps the home boot path free of Redis.
    from back_dev_home._runtime.office_redis import redis_client

    return redis_client()


def _text(value) -> str:
    """The shared office client runs ``decode_responses=False`` (its usual
    payloads are parquet DataFrames), so fields come back as bytes."""
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def _normalize(user_id: str) -> str:
    return user_id.strip().upper()


def _iso_from_score(score: float) -> str:
    """Render a ZSET score back into the mock's timestamp format.

    The score is epoch seconds because that is what makes the ZSET order by
    recency; the wire format has to match ``_now_iso`` exactly, so it is
    rebuilt here rather than stored twice.
    """
    moment = datetime.fromtimestamp(float(score), timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def is_blocked(user_id: str) -> bool:
    """Pure rule check: X-prefixed and not on the exception list.

    Admin bypass is the enforcement point's concern (``_auth/middleware.py``),
    not part of the rule itself. Fails closed — see the module docstring.
    """
    normalized = _normalize(user_id)
    if not normalized.startswith(BLOCKED_PREFIX):
        return False  # nearly every id: no Redis round trip at all
    return not _client().hexists(_EXC_KEY, normalized)


def list_exceptions() -> list[dict]:
    """Every granted exception, oldest grant first.

    Ordering is a deliberate divergence from the mock, which returns file
    insertion order: a Redis hash has no order, so rows are sorted by
    ``granted_at`` then ``user_id`` to keep the admin table stable across
    reloads instead of reshuffling.
    """
    raw = _client().hgetall(_EXC_KEY)
    rows = [
        {"user_id": _text(field), "granted_at": _text(value)}
        for field, value in raw.items()
    ]
    rows.sort(key=lambda row: (row["granted_at"], row["user_id"]))
    return rows


def add_exception(user_id: str) -> dict:
    """Grant an X-user access. Idempotent — a repeat grant keeps the original
    ``granted_at`` rather than bumping it.

    Raises ValueError for ids the rule never blocks (granting one is a caller
    error, not a no-op) and StoreUnavailableError when the grant cannot be
    stored.
    """
    normalized = _normalize(user_id)
    if not normalized:
        raise ValueError("member id is required")
    if not normalized.startswith(BLOCKED_PREFIX):
        raise ValueError(
            f"only ids starting with '{BLOCKED_PREFIX}' need an exception"
        )
    granted_at = _now_iso()
    try:
        client = _client()
        # HSETNX makes idempotency atomic: a concurrent second grant cannot
        # overwrite the first one's timestamp.
        if not client.hsetnx(_EXC_KEY, normalized, granted_at):
            existing = client.hget(_EXC_KEY, normalized)
            if existing is not None:
                granted_at = _text(existing)
        # A fresh grant clears the "attempted and was blocked" history, so the
        # admin page stops offering to grant someone who already has access.
        client.zrem(_DENIED_KEY, normalized)
    except _STORE_ERRORS as exc:
        raise StoreUnavailableError(
            "access exception store unavailable; refusing to modify"
        ) from exc
    return {"user_id": normalized, "granted_at": granted_at}


def remove_exception(user_id: str) -> bool:
    """Revoke a grant. Idempotent: True the first time, False afterwards.

    HDEL against a field that is already gone returns 0, which is the False
    the caller wants — not an error.
    """
    normalized = _normalize(user_id)
    try:
        return bool(_client().hdel(_EXC_KEY, normalized))
    except _STORE_ERRORS as exc:
        raise StoreUnavailableError(
            "access exception store unavailable; refusing to modify"
        ) from exc


def record_denied(user_id: str) -> None:
    """Note that a blocked member just attempted access.

    Never raises — see the module docstring. ZADD on an existing member updates
    its score in place, so a repeat denial refreshes the timestamp and moves the
    entry to most-recent without duplicating it.
    """
    normalized = _normalize(user_id)
    if not normalized:
        return
    try:
        client = _client()
        client.zadd(_DENIED_KEY, {normalized: datetime.now(timezone.utc).timestamp()})
        # Trim to the cap, oldest first. Negative rank counts from the end, so
        # -(cap + 1) is "everything below the newest `cap` entries".
        client.zremrangebyrank(_DENIED_KEY, 0, -(_DENIED_CAP + 1))
    except _STORE_ERRORS:
        logger.warning("denied-attempt store unavailable; not recording")


def list_denied() -> list[dict]:
    """Most recent attempts first, one entry per member id."""
    entries = _client().zrevrange(_DENIED_KEY, 0, _DENIED_CAP - 1, withscores=True)
    return [
        {"user_id": _text(member), "last_denied_at": _iso_from_score(score)}
        for member, score in entries
    ]
