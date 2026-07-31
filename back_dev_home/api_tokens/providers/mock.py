"""Mock (Phase 1 home/offline) provider for api_tokens.

In-memory API token store. All five functions — create_token, list_tokens,
revoke_token, find_by_plaintext, touch_last_used — are provider-switched
through data.py's _provider() and dispatched based on SKEWNONO_API_TOKENS_PROVIDER.
An office implementation must implement all five against the same backing store
(Redis, OpenSearch, or database), since tokens created by office create_token
must be resolvable by office find_by_plaintext for bearer authentication to work.
``reset_for_tests`` is a SIXTH function but stays mock-only (test support for
this provider's module-global dicts); it is not dispatched through data.py and
an office adapter has no reason to implement it — same arrangement as
``access_control/providers/mock.py``.
See api_tokens/data.py and MIGRATION.md for architecture details.

The two dicts are guarded by a module-level ``threading.Lock`` (same pattern as
``access_control/providers/mock.py``): the home dev server runs every request on
a fresh thread, create/revoke each touch BOTH dicts and must not be seen
half-applied, touch_last_used is a read-modify-write, and list_tokens would
raise if it iterated during a concurrent write. The lock protects the dicts, not
the ``_TokenRow`` objects themselves — find_by_plaintext hands the live row back
to the caller — and it is a single-process guarantee only, so the multi-worker
office defect documented in MIGRATION.md stands unchanged.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional

_PREFIX = "skn_"
_TOUCH_DEBOUNCE = timedelta(seconds=60)


@dataclass
class _TokenRow:
    id: str
    owner_user_id: str
    label: str
    hash: str
    created_at: str
    last_used_at: Optional[str] = None


_lock = Lock()
_tokens: dict[str, _TokenRow] = {}
_by_hash: dict[str, str] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _public_view(row: _TokenRow) -> dict:
    return {
        "id": row.id,
        "label": row.label,
        "created_at": row.created_at,
        "last_used_at": row.last_used_at,
    }


def create_token(owner_user_id: str, label: str) -> tuple[dict, str]:
    """Create a token for the owner. Returns (public view, plaintext).

    The plaintext is the only chance the caller has to see the raw token —
    only its SHA-256 is stored.
    """
    plaintext = _PREFIX + secrets.token_urlsafe(32)
    row = _TokenRow(
        id=uuid.uuid4().hex[:12],
        owner_user_id=owner_user_id,
        label=label.strip() or "untitled",
        hash=_hash(plaintext),
        created_at=_now(),
        last_used_at=None,
    )
    with _lock:
        _tokens[row.id] = row
        _by_hash[row.hash] = row.id
        return _public_view(row), plaintext


def list_tokens(owner_user_id: str) -> list[dict]:
    # Locked so the iteration never races a concurrent create/revoke
    # (mutating a dict mid-iteration raises RuntimeError).
    with _lock:
        return [
            _public_view(row)
            for row in _tokens.values()
            if row.owner_user_id == owner_user_id
        ]


def revoke_token(owner_user_id: str, token_id: str) -> bool:
    with _lock:
        row = _tokens.get(token_id)
        if row is None or row.owner_user_id != owner_user_id:
            return False
        _by_hash.pop(row.hash, None)
        _tokens.pop(token_id, None)
    return True


def find_by_plaintext(plaintext: str) -> Optional[_TokenRow]:
    if not plaintext.startswith(_PREFIX):
        return None
    with _lock:
        token_id = _by_hash.get(_hash(plaintext))
        if token_id is None:
            return None
        return _tokens.get(token_id)


def touch_last_used(token_id: str) -> None:
    # Debounced to once per minute per token. The mock cost is trivial,
    # but the office swap will write through to OpenSearch/DB on every
    # call, so the contract here documents the expected write cadence.
    with _lock:
        row = _tokens.get(token_id)
        if row is None:
            return
        now = datetime.now(timezone.utc)
        if row.last_used_at:
            last = datetime.fromisoformat(row.last_used_at)
            if now - last < _TOUCH_DEBOUNCE:
                return
        row.last_used_at = now.isoformat(timespec="seconds")


def reset_for_tests() -> None:
    """Drop all in-memory tokens so route tests start from a clean store.

    Mock-only: not dispatched through data.py, so office never implements it.
    Like every function here it takes ``_lock`` itself — the lock is not
    reentrant, so nothing under a lock may call one of these.
    """
    with _lock:
        _tokens.clear()
        _by_hash.clear()
