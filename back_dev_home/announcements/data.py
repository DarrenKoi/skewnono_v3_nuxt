import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional, TypedDict


class Announcement(TypedDict, total=False):
    id: str
    level: Literal["info", "warning", "critical"]
    title: str
    body: str
    starts_at: str
    ends_at: str
    dismissible: bool


# Naive timestamps in announcements.json are interpreted as KST so operators
# can write "2026-05-07T18:00:00" without remembering the offset. Comparing
# naive vs. aware datetimes would otherwise raise TypeError and 500 the route.
_DEFAULT_TZ = timezone(timedelta(hours=9))

_PATH = Path(__file__).parent / "announcements.json"
_cache: dict = {"mtime": 0.0, "items": []}


def _load() -> list[Announcement]:
    if not _PATH.exists():
        return []
    mtime = _PATH.stat().st_mtime
    if mtime != _cache["mtime"]:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
        _cache["items"] = raw if isinstance(raw, list) else []
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


def _is_active(a: Announcement, now: datetime) -> bool:
    starts = _parse_bound(a.get("starts_at"))
    if starts and now < starts:
        return False
    ends = _parse_bound(a.get("ends_at"))
    if ends and now > ends:
        return False
    return True


def get_announcements() -> list[Announcement]:
    now = datetime.now(timezone.utc)
    return [a for a in _load() if _is_active(a, now)]
