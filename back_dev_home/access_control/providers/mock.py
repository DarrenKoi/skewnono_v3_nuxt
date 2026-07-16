"""Mock (Phase 1 home/offline) provider for access-control policy data.

원본:        (사무실 측은 OpenSearch/Redis 등 공용 저장소로 교체 예정)
동작 규칙:
- 차단 규칙: 멤버 ID가 'X'로 시작하면(대소문자 무시) 차단 대상입니다.
  단, 관리자가 등록한 예외 목록에 있으면 통과합니다.
- 예외 목록은 JSON 파일에 write-through로 저장되어 재시작 후에도 유지됩니다.
  파일 mtime이 바뀌면 다시 읽으므로 멀티 워커 환경에서도 grant가 전파됩니다.
- 읽기 실패는 fail-safe(그 요청만 빈 목록으로 판정, 캐시하지 않음)이고,
  그 상태에서의 변경은 거부합니다 — 손상된 캐시로 파일을 덮어써서 기존
  grant를 날리는 사고를 막기 위함입니다. 쓰기 실패는 호출자에게 예외로
  전파되어 관리자가 실패를 알 수 있습니다.
- 차단 시도 기록은 메모리 링 버퍼(최근 50건)로만 유지되는 편의 뷰입니다 —
  관리자가 정확한 사번을 몰라도 원클릭으로 허용할 수 있게 해 줍니다.

All six functions below (``is_blocked``, ``list_exceptions``,
``add_exception``, ``remove_exception``, ``record_denied``,
``list_denied``) are provider-switched through ``access_control/data.py``'s
``_provider()`` and dispatched based on ``SKEWNONO_ACCESS_CONTROL_PROVIDER``
— they all read/write the SAME exception store (and the same in-memory
denied-attempts ring buffer), so an office implementation must implement
all six against the same backing store (Redis) for
``back_dev_home/_auth/middleware.py``'s enforcement to stay correct the
moment the provider is switched. See access_control/data.py and
MIGRATION.md for architecture details. ``reset_for_tests`` and
``_store_path`` stay mock-only (test-support / this provider's own file
location), re-exported unswitched from data.py.
"""

from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

logger = logging.getLogger("skewnono.access_control")

BLOCKED_PREFIX = "X"

_DENIED_CAP = 50

_lock = Lock()
# user_id(uppercased) -> {"user_id": ..., "granted_at": ...}
_cache: OrderedDict[str, dict] | None = None
_cache_mtime: float | None = None
_load_failed = False
# user_id(uppercased) -> last denied timestamp (ISO). Ordered oldest-first.
_denied: OrderedDict[str, str] = OrderedDict()


class StoreUnavailableError(RuntimeError):
    """The exception store cannot be read; mutations are refused so a
    half-loaded view is never persisted over the real file."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _store_path() -> Path:
    override = os.environ.get("SKEWNONO_ACCESS_EXCEPTIONS_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "state" / "access_exceptions.json"


def _load_locked() -> OrderedDict[str, dict]:
    """Return the current exception store, reloading when the file changed.

    A missing file is a normal empty store. An unreadable/corrupt file is
    fail-safe: this call sees an empty store, but nothing is cached (so the
    next call retries) and _load_failed marks mutations as unsafe.
    """
    global _cache, _cache_mtime, _load_failed
    path = _store_path()
    try:
        mtime: float | None = path.stat().st_mtime
    except FileNotFoundError:
        mtime = None
    except OSError:
        logger.warning("access exceptions file unstatable; failing safe: %s", path)
        _load_failed = True
        return OrderedDict()

    if _cache is not None and mtime == _cache_mtime:
        _load_failed = False
        return _cache

    loaded: OrderedDict[str, dict] = OrderedDict()
    if mtime is not None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("access exceptions file unreadable; failing safe: %s", path)
            _load_failed = True
            return loaded
        for row in raw.get("exceptions", []):
            user_id = str(row.get("user_id", "")).strip().upper()
            if user_id:
                loaded[user_id] = {
                    "user_id": user_id,
                    "granted_at": row.get("granted_at"),
                }
    _cache = loaded
    _cache_mtime = mtime
    _load_failed = False
    return _cache


def _save_locked() -> None:
    """Write-through persist. Raises OSError on failure — callers surface it
    instead of reporting success for a grant that would vanish on restart."""
    global _cache_mtime
    path = _store_path()
    payload = {"exceptions": list((_cache or {}).values())}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    _cache_mtime = path.stat().st_mtime


def _mutable_store_locked() -> OrderedDict[str, dict]:
    store = _load_locked()
    if _load_failed:
        raise StoreUnavailableError("access exception store unreadable; refusing to modify")
    return store


def is_blocked(user_id: str) -> bool:
    """Pure rule check: X-prefixed and not on the exception list.

    Admin bypass is the enforcement point's concern (_auth/middleware.py),
    not part of the rule itself.
    """
    normalized = user_id.strip().upper()
    if not normalized.startswith(BLOCKED_PREFIX):
        return False
    with _lock:
        return normalized not in _load_locked()


def list_exceptions() -> list[dict]:
    with _lock:
        return list(_load_locked().values())


def add_exception(user_id: str) -> dict:
    """Grant an X-user access. Raises ValueError for IDs the rule never
    blocks, StoreUnavailableError/OSError when the grant cannot be stored."""
    normalized = user_id.strip().upper()
    if not normalized:
        raise ValueError("member id is required")
    if not normalized.startswith(BLOCKED_PREFIX):
        raise ValueError(f"only ids starting with '{BLOCKED_PREFIX}' need an exception")
    with _lock:
        store = _mutable_store_locked()
        row = store.get(normalized)
        if row is None:
            row = {"user_id": normalized, "granted_at": _now_iso()}
            store[normalized] = row
            try:
                _save_locked()
            except OSError:
                store.pop(normalized, None)
                raise
        _denied.pop(normalized, None)
        return row


def remove_exception(user_id: str) -> bool:
    normalized = user_id.strip().upper()
    with _lock:
        store = _mutable_store_locked()
        row = store.get(normalized)
        if row is None:
            return False
        del store[normalized]
        try:
            _save_locked()
        except OSError:
            store[normalized] = row
            raise
        return True


def record_denied(user_id: str) -> None:
    normalized = user_id.strip().upper()
    if not normalized:
        return
    with _lock:
        _denied[normalized] = _now_iso()
        _denied.move_to_end(normalized)
        while len(_denied) > _DENIED_CAP:
            _denied.popitem(last=False)


def list_denied() -> list[dict]:
    """Most recent attempts first."""
    with _lock:
        return [
            {"user_id": uid, "last_denied_at": ts}
            for uid, ts in reversed(_denied.items())
        ]


def reset_for_tests() -> None:
    """Drop all in-memory state so tests can point at a fresh store file."""
    global _cache, _cache_mtime, _load_failed
    with _lock:
        _cache = None
        _cache_mtime = None
        _load_failed = False
        _denied.clear()
