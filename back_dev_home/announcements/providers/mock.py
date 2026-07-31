"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본:        announcements.json (홈) / 사무실 측 운영자 공지 테이블·피드
계약:        docs/api-contracts/announcements.yaml
픽스처:      back_dev_home/announcements/__fixtures__/ (capture_fixtures 가 갱신)

Announcement 는 모의 발생기가 아니라 실제 JSON 파일을 읽는 유일한 피처입니다.
사무실 전환 시 동일한 응답 형태로 사내 공지 소스를 매핑하면 됩니다.

``is_active`` 는 두 provider 가 공유하는 활성 구간 판정입니다. office 어댑터가
여기서 import 하므로, 의미(경계는 optional, 파싱 실패한 경계는 무시, naive 는
KST 해석)가 provider 간에 어긋나면 안 됩니다.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from back_dev_home.announcements.contracts import Announcement


__all__ = ["get_announcements", "is_active"]

logger = logging.getLogger("skewnono.announcements")


# Naive timestamps in announcements.json are interpreted as KST so operators
# can write "2026-05-07T18:00:00" without remembering the offset. Comparing
# naive vs. aware datetimes would otherwise raise TypeError and 500 the route.
_DEFAULT_TZ = timezone(timedelta(hours=9))

_PATH = Path(__file__).parent.parent / "announcements.json"
_cache: dict = {"mtime": 0.0, "items": []}


def _load() -> list[Announcement]:
    if not _PATH.exists():
        return []
    mtime = _PATH.stat().st_mtime
    if mtime != _cache["mtime"]:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else []
        # The file is hand-edited, so a bare string (or any non-object row)
        # must degrade to "that row skipped" — is_active calling .get() on it
        # would be an AttributeError, and routes.py has no try/except, so the
        # SPA would 500 on every page load. Same tolerance as the office
        # adapter's _load, and logged for the same reason: a row that just
        # vanishes from the banner is worse to debug than one that says why.
        items = [row for row in rows if isinstance(row, dict)]
        if len(items) != len(rows):
            logger.warning(
                "announcements.json had %d non-object row(s); skipping them",
                len(rows) - len(items),
            )
        _cache["items"] = items
        _cache["mtime"] = mtime
    return _cache["items"]


def _parse_bound(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_DEFAULT_TZ)
    return dt


def is_active(a: Announcement, now: datetime) -> bool:
    """활성 구간 판정 — office 어댑터가 import 하는 공유 술어(public)."""
    starts = _parse_bound(a.get("starts_at"))
    if starts and now < starts:
        return False
    ends = _parse_bound(a.get("ends_at"))
    if ends and now > ends:
        return False
    return True


def get_announcements() -> list[Announcement]:
    now = datetime.now(timezone.utc)
    return [a for a in _load() if is_active(a, now)]
