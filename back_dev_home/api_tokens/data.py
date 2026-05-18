"""In-memory API token store for the Phase 1 home/offline mock.

The office swap can replace this module with an OpenSearch- or DB-backed
implementation; routes and middleware import only the public functions
below.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    _tokens[row.id] = row
    _by_hash[row.hash] = row.id
    return _public_view(row), plaintext


def list_tokens(owner_user_id: str) -> list[dict]:
    return [
        _public_view(row)
        for row in _tokens.values()
        if row.owner_user_id == owner_user_id
    ]


def revoke_token(owner_user_id: str, token_id: str) -> bool:
    row = _tokens.get(token_id)
    if row is None or row.owner_user_id != owner_user_id:
        return False
    _by_hash.pop(row.hash, None)
    _tokens.pop(token_id, None)
    return True


def find_by_plaintext(plaintext: str) -> Optional[_TokenRow]:
    if not plaintext.startswith(_PREFIX):
        return None
    token_id = _by_hash.get(_hash(plaintext))
    if token_id is None:
        return None
    return _tokens.get(token_id)


def touch_last_used(token_id: str) -> None:
    # Debounced to once per minute per token. The mock cost is trivial,
    # but the office swap will write through to OpenSearch/DB on every
    # call, so the contract here documents the expected write cadence.
    row = _tokens.get(token_id)
    if row is None:
        return
    now = datetime.now(timezone.utc)
    if row.last_used_at:
        last = datetime.fromisoformat(row.last_used_at)
        if now - last < _TOUCH_DEBOUNCE:
            return
    row.last_used_at = now.isoformat(timespec="seconds")
