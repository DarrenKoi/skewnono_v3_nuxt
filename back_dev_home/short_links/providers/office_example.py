"""Tracked office adapter for short links, backed by Redis.

Copy to ``office.py`` to activate (``cp office_example.py office.py``) — this
file holds no in-house address or secret, so the copy is verbatim. The Redis
host/password come from ``back_dev_home/.env`` via ``_runtime/office_redis.py``.

Layout — one expiring string per link:

    skewnono:short_link:<code>   STRING  JSON {code, target, created_at}, TTL

WHY THIS ONE IS A WRITE ADAPTER. Almost every office adapter in this repo READS
a table the office already maintains. Short links have no such source: the rows
are state this app creates, so there is nothing to map and the office side is a
store, not a query. ``_scheduler/runlog.py`` is the existing precedent for an
app-owned Redis write here. The consequence to keep in mind is that the mock's
process-local dict is NOT a stand-in for this: it is emptied by a restart and is
invisible to sibling uWSGI workers, so home behaviour understates how long a
link lives and overstates nothing.

EXPIRY is the deliberate difference from the mock, which never expires because
its store dies with the process anyway. ``TTL_SECONDS`` is refreshed every time
the same screen is re-shared, so a link that stays in circulation stays alive
and only genuinely abandoned ones are collected.

OUTAGE BEHAVIOR follows the same rule as ``access_control``: **never report an
infrastructure failure as a data decision.** Both functions convert a store
failure into the bare ``RuntimeError`` that ``back_dev_home/__init__.py`` maps
to a JSON 503.

* ``create_short_link`` — RAISES. Returning a code we failed to persist would
  hand the user a link that 404s forever, and they would paste it into a report
  before finding out. The frontend's documented fallback is to copy the long URL
  when this errors, which is only correct if the error actually arrives.
* ``resolve_short_link`` — RAISES rather than returning ``None``. ``None`` means
  "this link does not exist", which during an outage tells someone their
  perfectly good link is dead and sends them to re-mint it. 503 says "retry".
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from back_dev_home._runtime.office_redis import (
    STORE_ERRORS,
    load_env_file,
    redis_client,
    unreachable,
)
from back_dev_home.short_links.contracts import ShortLink


__all__ = ["create_short_link", "resolve_short_link"]


KEY_PREFIX = "skewnono:short_link:"

TTL_SECONDS = 365 * 24 * 60 * 60
"""One year, refreshed on every re-share. Analysis links get pasted into reports
and reviewed months later, so a shorter window would break the main use; an
unbounded one would grow the keyspace with links nobody opened again."""

CODE_LEN = 10
"""Kept in step with ``providers/mock.py``'s constant of the same name — the two
must agree or a code minted at home and a code minted at the office have
different shapes for the same screen."""


def _client():
    """Indirection point so tests can inject a fake (same shape as the other
    office adapters here)."""
    load_env_file()
    return redis_client()


def _key(code: str) -> str:
    return f"{KEY_PREFIX}{code}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(target: str) -> str:
    """Byte-identical to ``providers/mock.py::_digest``. Duplicated rather than
    imported so the office adapter has no import edge into the mock — but the
    two are pinned equal by a test, because a drift here would silently change
    every code the office mints."""
    raw = hashlib.sha256(target.encode("utf-8")).digest()
    return base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def _parse(raw: bytes | None, code: str) -> ShortLink | None:
    """Read one stored value, treating an unreadable one as absent.

    A truncated or hand-edited value must not 500 the resolver, and on the mint
    path "unreadable" is what lets the slot be reclaimed rather than blocking
    that code forever.
    """
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("target"), str):
        return None
    return {
        "code": code,
        "target": value["target"],
        "created_at": str(value.get("created_at") or ""),
    }


def create_short_link(target: str) -> ShortLink:
    digest = _digest(target)
    try:
        client = _client()
        for length in range(CODE_LEN, len(digest) + 1, 2):
            code = digest[:length]
            key = _key(code)
            link: ShortLink = {"code": code, "target": target, "created_at": _now()}
            payload = json.dumps(link, ensure_ascii=False)

            # NX so two workers minting DIFFERENT targets that collide cannot
            # both believe they own the code — the loser sees the winner's value
            # below and widens. A plain SET would let the second write silently
            # steal the first engineer's link.
            if client.set(key, payload, ex=TTL_SECONDS, nx=True):
                return link

            existing = _parse(client.get(key), code)
            if existing is None:
                # Expired between the SET NX and this GET, or the value is
                # unreadable. Either way nobody is using the slot.
                client.set(key, payload, ex=TTL_SECONDS)
                return link
            if existing["target"] == target:
                # Same screen re-shared: hand back the code the colleague
                # already has (created_at preserved, matching the mock) and
                # refresh its life rather than minting a second entry.
                client.expire(key, TTL_SECONDS)
                return existing
            # Genuine collision on this width — widen and try again.
    except STORE_ERRORS as exc:
        raise unreachable("short link store unavailable", exc) from exc

    raise RuntimeError("short link code space exhausted for target")


def resolve_short_link(code: str) -> ShortLink | None:
    if not code:
        return None
    try:
        return _parse(_client().get(_key(code)), code)
    except STORE_ERRORS as exc:
        raise unreachable("short link store unavailable", exc) from exc
