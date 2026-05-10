"""In-memory activity store powering the gamification page.

Why a plain module-level dict (and not @lru_cache like neighbors): activity is
*mutated* on every request. lru_cache memoizes — exactly the wrong shape. The
closest precedent in this repo is announcements/data._cache, which is also a
mutable module dict. State resets on process restart; that's acceptable for the
home phase and matches the cloud's "single sync worker" assumption.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import Deque, Literal, TypedDict


__all__ = [
    "Tier",
    "TierInfo",
    "ActivityEvent",
    "MeResponse",
    "LeaderboardResponse",
    "record_request",
    "get_me",
    "get_leaderboard",
    "seed_demo_users",
]


Tier = Literal["bronze", "silver", "gold", "platinum", "diamond"]


class TierInfo(TypedDict):
    key: Tier
    label: str
    icon: str
    min_score: int
    next_score: int | None  # None for the top tier


# Threshold tuples are ordered; pick the highest tier whose min_score <= score.
_TIERS: list[TierInfo] = [
    {"key": "bronze",   "label": "Bronze",   "icon": "medal",  "min_score": 0,    "next_score": 50},
    {"key": "silver",   "label": "Silver",   "icon": "medal",  "min_score": 50,   "next_score": 200},
    {"key": "gold",     "label": "Gold",     "icon": "trophy", "min_score": 200,  "next_score": 500},
    {"key": "platinum", "label": "Platinum", "icon": "gem",    "min_score": 500,  "next_score": 1500},
    {"key": "diamond",  "label": "Diamond",  "icon": "crown",  "min_score": 1500, "next_score": None},
]

# Skip self-referential paths so the activity page itself doesn't inflate scores.
_SKIP_PATH_PREFIXES = ("/api/activity/",)
# Cap recent-events buffer so memory stays bounded under heavy use.
_RECENT_EVENTS_CAP = 50
# Streak window: only consider the last 60 days when looking for gaps.
_STREAK_WINDOW_DAYS = 60


class ActivityEvent(TypedDict):
    timestamp: str
    method: str
    path: str
    status: int
    feature: str


class _MeStats(TypedDict):
    score: int
    rank: int
    total_users: int
    streak_days: int
    days_active: int
    favorite_feature: str | None
    by_feature: dict[str, int]
    first_seen: str | None
    last_seen: str | None


class _TierProgress(TypedDict):
    current: TierInfo
    next: TierInfo | None
    score_into_tier: int
    score_to_next: int | None
    pct: int  # 0..100, percent through current tier; 100 if at top tier


class MeResponse(TypedDict):
    user_id: str
    stats: _MeStats
    tier: _TierProgress
    recent: list[ActivityEvent]


class _LeaderRow(TypedDict):
    rank: int
    user_id: str
    score: int
    tier: Tier
    streak_days: int
    is_me: bool


class LeaderboardResponse(TypedDict):
    generated_at: str
    me: _LeaderRow | None
    top: list[_LeaderRow]


@dataclass
class _UserState:
    user_id: str
    total: int = 0
    by_feature: dict[str, int] = field(default_factory=dict)
    active_days: set[date] = field(default_factory=set)
    recent: Deque[ActivityEvent] = field(default_factory=lambda: deque(maxlen=_RECENT_EVENTS_CAP))
    first_seen: datetime | None = None
    last_seen: datetime | None = None


_users: dict[str, _UserState] = {}
_lock = RLock()


def _feature_of(path: str) -> str:
    # /api/afm/recipes/123 -> "afm"; /api/health/services -> "health"; root -> "(root)".
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "api":
        return parts[1]
    if not parts:
        return "(root)"
    return parts[0]


def _tier_for(score: int) -> TierInfo:
    current = _TIERS[0]
    for tier in _TIERS:
        if score >= tier["min_score"]:
            current = tier
        else:
            break
    return current


def _tier_progress(score: int) -> _TierProgress:
    current = _tier_for(score)
    next_tier: TierInfo | None = None
    for idx, tier in enumerate(_TIERS):
        if tier is current and idx + 1 < len(_TIERS):
            next_tier = _TIERS[idx + 1]
            break
    if next_tier is None or current["next_score"] is None:
        return {"current": current, "next": None, "score_into_tier": score - current["min_score"], "score_to_next": None, "pct": 100}
    span = current["next_score"] - current["min_score"]
    into = score - current["min_score"]
    pct = max(0, min(100, round(into * 100 / span))) if span > 0 else 0
    return {
        "current": current,
        "next": next_tier,
        "score_into_tier": into,
        "score_to_next": current["next_score"] - score,
        "pct": pct,
    }


def _streak_for(active_days: set[date], today: date) -> int:
    if not active_days:
        return 0
    # Count back from today (or yesterday if no activity today) until a gap.
    cursor = today if today in active_days else today - timedelta(days=1)
    streak = 0
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)
        if streak >= _STREAK_WINDOW_DAYS:
            break
    return streak


def record_request(user_id: str | None, method: str, path: str, status: int) -> None:
    """Tap point invoked from _logging/activity.py after each request.

    Skips: missing/unauthed users, the activity API itself, non-API paths
    (SPA assets, /login), and 4xx/5xx errors (don't reward failed calls).
    """
    if not user_id or user_id == "-":
        return
    if not path.startswith("/api/"):
        return
    if any(path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
        return
    if status >= 400:
        return

    now = datetime.now(timezone.utc)
    feature = _feature_of(path)
    event: ActivityEvent = {
        "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "method": method,
        "path": path,
        "status": status,
        "feature": feature,
    }
    with _lock:
        state = _users.get(user_id)
        if state is None:
            state = _UserState(user_id=user_id, first_seen=now)
            _users[user_id] = state
        state.total += 1
        state.by_feature[feature] = state.by_feature.get(feature, 0) + 1
        state.active_days.add(now.date())
        state.last_seen = now
        state.recent.append(event)


def _build_leaderboard_rows(viewer: str | None, today: date) -> list[_LeaderRow]:
    ranked = sorted(_users.values(), key=lambda s: (-s.total, s.user_id))
    rows: list[_LeaderRow] = []
    for idx, state in enumerate(ranked, start=1):
        rows.append({
            "rank": idx,
            "user_id": state.user_id,
            "score": state.total,
            "tier": _tier_for(state.total)["key"],
            "streak_days": _streak_for(state.active_days, today),
            "is_me": viewer is not None and state.user_id == viewer,
        })
    return rows


def get_me(user_id: str) -> MeResponse:
    today = datetime.now(timezone.utc).date()
    with _lock:
        state = _users.get(user_id)
        rows = _build_leaderboard_rows(user_id, today)
    total_users = len(rows)
    if state is None:
        # User has no recorded API activity yet — return a zero state.
        return {
            "user_id": user_id,
            "stats": {
                "score": 0,
                "rank": total_users + 1 if total_users else 1,
                "total_users": max(total_users, 1),
                "streak_days": 0,
                "days_active": 0,
                "favorite_feature": None,
                "by_feature": {},
                "first_seen": None,
                "last_seen": None,
            },
            "tier": _tier_progress(0),
            "recent": [],
        }
    rank = next((row["rank"] for row in rows if row["user_id"] == user_id), total_users)
    favorite = max(state.by_feature.items(), key=lambda kv: kv[1])[0] if state.by_feature else None
    return {
        "user_id": user_id,
        "stats": {
            "score": state.total,
            "rank": rank,
            "total_users": total_users,
            "streak_days": _streak_for(state.active_days, today),
            "days_active": len(state.active_days),
            "favorite_feature": favorite,
            "by_feature": dict(sorted(state.by_feature.items(), key=lambda kv: -kv[1])),
            "first_seen": state.first_seen.isoformat(timespec="seconds").replace("+00:00", "Z") if state.first_seen else None,
            "last_seen": state.last_seen.isoformat(timespec="seconds").replace("+00:00", "Z") if state.last_seen else None,
        },
        "tier": _tier_progress(state.total),
        "recent": list(reversed(state.recent)),
    }


def get_leaderboard(viewer: str | None, top_n: int = 10) -> LeaderboardResponse:
    today = datetime.now(timezone.utc).date()
    with _lock:
        rows = _build_leaderboard_rows(viewer, today)
    top = rows[:top_n]
    me_row: _LeaderRow | None = None
    if viewer is not None:
        in_top = any(row["is_me"] for row in top)
        if not in_top:
            me_row = next((row for row in rows if row["user_id"] == viewer), None)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "me": me_row,
        "top": top,
    }


def seed_demo_users() -> None:
    """Populate a few mock peers so the leaderboard has shape in home/dev mode.

    Idempotent: only seeds users that don't already exist. Real activity from
    record_request() will outpace these once the user actually clicks around.
    """
    base = datetime.now(timezone.utc) - timedelta(days=14)
    demo: list[tuple[str, int, list[str], int]] = [
        # (user_id, total, features, days_active_back)
        ("kim.minju",   428, ["afm", "ebeam", "health"], 12),
        ("park.jinho",  312, ["ebeam", "afm"],            9),
        ("lee.soyoung", 187, ["afm", "health"],           7),
        ("choi.eunwoo", 96,  ["ebeam"],                   5),
        ("jung.hari",   54,  ["afm"],                     3),
    ]
    with _lock:
        for user_id, total, features, days_back in demo:
            if user_id in _users:
                continue
            state = _UserState(user_id=user_id, first_seen=base)
            state.total = total
            # Spread feature counts roughly proportional to position.
            for idx, feat in enumerate(features):
                state.by_feature[feat] = total // len(features) + (1 if idx == 0 else 0)
            today = datetime.now(timezone.utc).date()
            for d in range(days_back):
                state.active_days.add(today - timedelta(days=d))
            state.last_seen = datetime.now(timezone.utc) - timedelta(hours=2)
            _users[user_id] = state
