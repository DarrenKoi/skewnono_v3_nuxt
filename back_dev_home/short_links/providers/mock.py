"""Mock (Phase 1 home/offline) provider for short_links — an in-memory store.

SWAP SURFACE — 사무실에서 동일 시그니처로 재구현 대상.

원본:        프로세스 메모리(홈) / Redis 문자열 키(사무실)
계약:        back_dev_home/short_links/contracts.py

Unlike most features here, short_links has no office DB to READ: the rows are
state this app owns and creates, so the office adapter is a WRITE path
(``_scheduler/runlog.py`` is the existing precedent for that in this codebase).
That difference is the whole of MIGRATION.md.

The dict is guarded by a module-level ``threading.Lock`` (same pattern as
``api_tokens/providers/mock.py``): the home dev server runs every request on a
fresh thread, and mint is a read-modify-write over the collision probe. It is a
single-process guarantee only — the multi-worker office deployment is exactly
why the office adapter is Redis and not this. A home restart empties the store,
which is acceptable at home and NOT acceptable at the office; see MIGRATION.md.

``reset_for_tests`` is mock-only test support for the module-global dict; it is
not dispatched through data.py and an office adapter has no reason to implement
it — same arrangement as ``api_tokens/providers/mock.py``.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from threading import Lock

from back_dev_home.short_links.contracts import ShortLink


__all__ = ["create_short_link", "resolve_short_link", "reset_for_tests"]


CODE_LEN = 10
"""Base32 characters taken from the digest — 50 bits. At the tens-of-thousands
of links this app will ever hold, a natural collision is ~1e-10; the probe in
``create_short_link`` makes even that outcome impossible rather than silent."""

_lock = Lock()
_links: dict[str, ShortLink] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(target: str) -> str:
    """Base32 of the target's SHA-256, lowercased.

    Base32 rather than hex or base64url because a code is something a person
    may read off a screenshot and retype: its alphabet omits 0/1/8/9, so there
    is no O/0 or l/1 pair to misread, and it has no case or punctuation to lose
    in a messenger that helpfully "corrects" text.
    """
    raw = hashlib.sha256(target.encode("utf-8")).digest()
    return base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def create_short_link(target: str) -> ShortLink:
    digest = _digest(target)
    with _lock:
        # Deterministic prefix first, so re-sharing the same screen returns the
        # code the colleague already has rather than forking the store. Widen
        # only on a genuine collision: two DIFFERENT targets sharing a code
        # would silently land one engineer on another's screen, which is a worse
        # failure than any error message.
        for length in range(CODE_LEN, len(digest) + 1, 2):
            code = digest[:length]
            existing = _links.get(code)
            if existing is None:
                link: ShortLink = {
                    "code": code,
                    "target": target,
                    "created_at": _now(),
                }
                _links[code] = link
                return link
            if existing["target"] == target:
                return existing
        # Unreachable short of a full SHA-256 prefix collision; raising beats
        # returning a code that points somewhere else.
        raise RuntimeError("short link code space exhausted for target")


def resolve_short_link(code: str) -> ShortLink | None:
    if not code:
        return None
    with _lock:
        return _links.get(code)


def reset_for_tests() -> None:
    with _lock:
        _links.clear()
