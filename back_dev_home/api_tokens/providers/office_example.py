"""Tracked office adapter for the Redis-backed API token store.

Copy to ``office.py`` to activate (``cp office_example.py office.py``) — this
file holds no in-house address or secret, so the copy is verbatim, same as
``activity`` and ``admin_logs``. The Redis host/password come from
``back_dev_home/.env`` via the shared plumbing in ``_runtime/office_redis.py``.

WHY THIS EXISTS AT ALL: ``providers/mock.py`` keeps its tokens in two module
dicts, which is correct at home and for a single worker. Under ``gunicorn -w N``
it is not — the worker that serves ``POST /api/account/api-tokens`` and the
worker that later authenticates ``Authorization: Bearer skn_...`` are different
processes, so ``find_by_plaintext`` misses a token that exists perfectly well
next door and bearer auth fails at random. Every worker shares this Redis.

Layout — one hash per token, one owner index, one hash→id reverse index:

    skewnono:api_tokens:token:<token_id>   HASH  id owner_user_id label
                                                 hash created_at last_used_at
    skewnono:api_tokens:owner:<owner_id>   SET   token ids owned by this member
    skewnono:api_tokens:hash:<sha256>      STR   token_id

The reverse index is what keeps :func:`find_by_plaintext` — called on the hot
path of *every* bearer request — off a full keyspace scan; it mirrors the mock's
``_by_hash`` dict. Only the SHA-256 is ever written; the plaintext exists in
process memory just long enough to be returned once.

NO TTL, deliberately. ``msr_image/redis_jobs.py`` (the other writer against this
Redis) expires every key it writes, because a job is transient. A token is a
durable credential — an expiring key here would log a member out with no trace.

Naming/format decisions are inherited from ``providers/mock.py`` rather than
restated: ``_PREFIX``, ``_hash``, ``_now``, ``_TOUCH_DEBOUNCE``, ``_public_view``
and the ``_TokenRow`` dataclass are imported from it. That is not incidental —
the token prefix and hash algorithm must not drift between providers, and
reusing ``_TokenRow`` is what guarantees the attribute access
``back_dev_home/_auth/middleware.py`` does (``row.owner_user_id``, ``row.id``)
keeps working. See api_tokens/MIGRATION.md's "Auth path" section.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from back_dev_home.api_tokens.providers.mock import (
    _PREFIX,
    _TOUCH_DEBOUNCE,
    _TokenRow,
    _hash,
    _now,
    _public_view,
)

_TOKEN_PREFIX = "skewnono:api_tokens:token"
_OWNER_PREFIX = "skewnono:api_tokens:owner"
_HASH_PREFIX = "skewnono:api_tokens:hash"

# Redis hash fields are strings, so a missing last_used_at needs an explicit
# encoding. Storing None directly would round-trip as the string "None".
_NO_LAST_USED = ""


def _client():
    # Lazy: office-only dependency, keeps the home boot path free of Redis.
    from back_dev_home._runtime.office_redis import redis_client

    return redis_client()


def _text(value) -> str:
    """The shared office client runs ``decode_responses=False`` (its usual
    payloads are parquet DataFrames), so fields come back as bytes."""
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def _token_key(token_id: str) -> str:
    return f"{_TOKEN_PREFIX}:{token_id}"


def _owner_key(owner_user_id: str) -> str:
    return f"{_OWNER_PREFIX}:{owner_user_id}"


def _hash_key(token_hash: str) -> str:
    return f"{_HASH_PREFIX}:{token_hash}"


def _read_row(client, token_id: str) -> Optional[_TokenRow]:
    """Rebuild a ``_TokenRow`` from its hash, or None if it is not there.

    A row missing ``id`` is not one we wrote — the owner index outliving its
    row, or a partially-written key. Report it absent rather than returning a
    half-populated row that would authenticate as owner "".
    """
    raw = client.hgetall(_token_key(token_id))
    fields = {_text(k): _text(v) for k, v in raw.items()}
    if "id" not in fields:
        return None
    last_used = fields.get("last_used_at", _NO_LAST_USED)
    return _TokenRow(
        id=fields["id"],
        owner_user_id=fields.get("owner_user_id", ""),
        label=fields.get("label", ""),
        hash=fields.get("hash", ""),
        created_at=fields.get("created_at", ""),
        last_used_at=last_used or None,
    )


def create_token(owner_user_id: str, label: str) -> tuple[dict, str]:
    """Create a token for the owner. Returns (public view, plaintext).

    The plaintext is the caller's only chance to see the raw secret — only its
    SHA-256 reaches Redis.
    """
    client = _client()
    plaintext = _PREFIX + secrets.token_urlsafe(32)
    row = _TokenRow(
        id=uuid.uuid4().hex[:12],
        owner_user_id=owner_user_id,
        label=label.strip() or "untitled",
        hash=_hash(plaintext),
        created_at=_now(),
        last_used_at=None,
    )
    client.hset(
        _token_key(row.id),
        mapping={
            "id": row.id,
            "owner_user_id": row.owner_user_id,
            "label": row.label,
            "hash": row.hash,
            "created_at": row.created_at,
            "last_used_at": _NO_LAST_USED,
        },
    )
    client.sadd(_owner_key(owner_user_id), row.id)
    client.set(_hash_key(row.hash), row.id)
    return _public_view(row), plaintext


def list_tokens(owner_user_id: str) -> list[dict]:
    """Every token this owner holds, oldest first.

    Ordering is a deliberate divergence from the mock, which returns its dict's
    insertion order: a Redis SET has no order at all, so rows are sorted by
    ``created_at`` (then id, to break same-second ties) to keep the response
    stable across calls instead of shuffling on every request.
    """
    client = _client()
    rows = [
        row
        for row in (
            _read_row(client, _text(raw_id))
            for raw_id in client.smembers(_owner_key(owner_user_id))
        )
        if row is not None
    ]
    rows.sort(key=lambda row: (row.created_at, row.id))
    return [_public_view(row) for row in rows]


def revoke_token(owner_user_id: str, token_id: str) -> bool:
    """Delete the token and both of its indexes. Idempotent.

    Returns False when the row does not exist **or** belongs to someone else —
    the caller is told nothing about which, exactly as the mock does. A second
    revoke of the same id finds no row and returns False rather than raising,
    which is what real client retries depend on.
    """
    client = _client()
    row = _read_row(client, token_id)
    if row is None or row.owner_user_id != owner_user_id:
        return False
    client.delete(_hash_key(row.hash))
    client.srem(_owner_key(owner_user_id), token_id)
    client.delete(_token_key(token_id))
    return True


def find_by_plaintext(plaintext: str) -> Optional[_TokenRow]:
    """Resolve a bearer secret to its row, or None.

    The wrong-prefix check short-circuits before any Redis call: this runs on
    every ``/api/*`` request carrying an Authorization header, and a malformed
    one should not cost a round trip.
    """
    if not plaintext.startswith(_PREFIX):
        return None
    client = _client()
    raw_id = client.get(_hash_key(_hash(plaintext)))
    if raw_id is None:
        return None
    # The row can still be gone while the index lingers; _read_row reports that
    # as absent, which the middleware turns into 401 invalid_token.
    return _read_row(client, _text(raw_id))


def touch_last_used(token_id: str) -> None:
    """Record that a bearer token just authenticated a request.

    Called once per authenticated bearer request, so the write is debounced to
    once per ``_TOUCH_DEBOUNCE`` per token (the mock's own cadence) — without
    it this would be a Redis write on every single API call a token makes.
    """
    client = _client()
    raw_last = client.hget(_token_key(token_id), "last_used_at")
    if raw_last is None:
        return  # no such token (or no such field) — nothing to record
    now = datetime.now(timezone.utc)
    last_used = _text(raw_last)
    if last_used:
        try:
            if now - datetime.fromisoformat(last_used) < _TOUCH_DEBOUNCE:
                return
        except ValueError:
            pass  # unparseable timestamp: overwrite it rather than wedge here
    client.hset(
        _token_key(token_id),
        "last_used_at",
        now.isoformat(timespec="seconds"),
    )
