"""Network-free activity aggregation for home and automated tests.

The mock stores the same request-scoped semantics the OpenSearch office reader
will aggregate: entry requests count active users, feature requests also count
page usage, and each request can belong to multiple FAB buckets. Timestamps
stay UTC but day buckets follow ``Asia/Seoul``, matching the office reader's
``time_zone`` aggregations — a UTC calendar here would disagree with
production about "today" for nine hours a day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from threading import RLock

from ..._auth.admin import is_admin
from .opensearch_reader import KST
from back_dev_home.activity.contracts import (
    DailyCount,
    FabPageCount,
    FabUsageResponse,
    FabUsageRow,
    FeatureCount,
    MeResponse,
    MeThisMonth,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
    UserListRow,
)

__all__ = [
    "FeatureCount",
    "DailyCount",
    "MeThisMonth",
    "MeResponse",
    "SummaryResponse",
    "UserListRow",
    "UserListResponse",
    "UserHistoryResponse",
    "FabPageCount",
    "FabUsageRow",
    "FabUsageResponse",
    "record_request",
    "get_me",
    "get_summary",
    "get_fab_page_usage",
    "get_users_list",
    "get_user_history",
    "is_admin",
    "seed_demo_users",
]

_SPARKLINE_DAYS = 30
_TOP_FEATURES_CAP = 10


@dataclass
class _UserState:
    user_id: str
    total: int = 0
    by_feature: dict[str, int] = field(default_factory=dict)
    daily: dict[date, int] = field(default_factory=dict)
    daily_features: dict[date, dict[str, int]] = field(default_factory=dict)
    daily_fabs: dict[date, set[str]] = field(default_factory=dict)
    daily_fab_features: dict[date, dict[str, dict[str, int]]] = field(
        default_factory=dict
    )
    first_seen: datetime | None = None
    last_seen: datetime | None = None


_users: dict[str, _UserState] = {}
_lock = RLock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _kst_date(value: datetime) -> date:
    return value.astimezone(KST).date()


def _today() -> date:
    return _kst_date(_now())


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _top_features(
    counts: dict[str, int],
    cap: int = _TOP_FEATURES_CAP,
) -> list[FeatureCount]:
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:cap]
    return [{"feature": feature, "count": count} for feature, count in ranked]


def _daily_series(
    daily: dict[date, int],
    today: date,
    days: int,
) -> list[DailyCount]:
    return [
        {
            "date": (day := today - timedelta(days=offset)).isoformat(),
            "count": daily.get(day, 0),
        }
        for offset in range(days - 1, -1, -1)
    ]


def _this_month_stats(
    daily: dict[date, int],
    today: date,
) -> MeThisMonth:
    first = today.replace(day=1)
    active = {
        day: count
        for day, count in daily.items()
        if first <= day <= today and count > 0
    }
    return {
        "requests": sum(active.values()),
        "days_active": len(active),
    }


def _merge_counts(
    target: dict[str, int],
    source: dict[str, int],
) -> None:
    for key, count in source.items():
        target[key] = target.get(key, 0) + count


def record_request(
    user_id: str,
    method: str,
    path: str,
    status: int,
    feature: str,
    activity_kind: str,
    fab_name_list: list[str],
) -> None:
    """Record one already-classified human entry or feature request."""

    if activity_kind not in {"entry", "feature"}:
        return

    now = _now()
    today = _kst_date(now)
    fabs = fab_name_list or ["미지정"]

    with _lock:
        state = _users.get(user_id)
        if state is None:
            state = _UserState(
                user_id=user_id,
                first_seen=now,
            )
            _users[user_id] = state

        state.total += 1
        state.daily[today] = state.daily.get(today, 0) + 1
        state.daily_fabs.setdefault(today, set()).update(fabs)
        state.last_seen = now

        if activity_kind != "feature":
            return

        state.by_feature[feature] = state.by_feature.get(feature, 0) + 1
        daily_features = state.daily_features.setdefault(today, {})
        daily_features[feature] = daily_features.get(feature, 0) + 1
        daily_fab_features = state.daily_fab_features.setdefault(today, {})
        for fab in fabs:
            fab_features = daily_fab_features.setdefault(fab, {})
            fab_features[feature] = fab_features.get(feature, 0) + 1


def _history_fields(
    state: _UserState | None,
    today: date,
) -> dict:
    if state is None:
        return {
            "this_month": {"requests": 0, "days_active": 0},
            "top_features": [],
            "daily": _daily_series({}, today, _SPARKLINE_DAYS),
            "first_seen": None,
            "last_seen": None,
        }
    return {
        "this_month": _this_month_stats(state.daily, today),
        "top_features": _top_features(state.by_feature),
        "daily": _daily_series(state.daily, today, _SPARKLINE_DAYS),
        "first_seen": _iso(state.first_seen),
        "last_seen": _iso(state.last_seen),
    }


def get_me(user_id: str) -> MeResponse:
    today = _today()
    with _lock:
        fields = _history_fields(_users.get(user_id), today)
    return {"user_id": user_id, "is_admin": is_admin(user_id), **fields}


def get_user_history(user_id: str) -> UserHistoryResponse | None:
    today = _today()
    with _lock:
        state = _users.get(user_id)
        if state is None:
            return None
        return {"user_id": user_id, **_history_fields(state, today)}


def get_summary() -> SummaryResponse:
    today = _today()
    week_start = today - timedelta(days=6)
    last30_start = today - timedelta(days=29)
    dau = 0
    wau = 0
    mau = 0
    feature_7d: dict[str, int] = {}
    feature_30d: dict[str, int] = {}

    with _lock:
        for state in _users.values():
            if state.daily.get(today, 0) > 0:
                dau += 1
            if any(
                week_start <= day <= today and count > 0
                for day, count in state.daily.items()
            ):
                wau += 1
            if any(
                last30_start <= day <= today and count > 0
                for day, count in state.daily.items()
            ):
                mau += 1
            for day, counts in state.daily_features.items():
                if week_start <= day <= today:
                    _merge_counts(feature_7d, counts)
                if last30_start <= day <= today:
                    _merge_counts(feature_30d, counts)

    return {
        "generated_at": _iso(_now()) or "",
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "top_features_7d": _top_features(feature_7d),
        "top_features_30d": _top_features(feature_30d),
    }


def get_users_list() -> UserListResponse:
    today = _today()
    cutoff = today - timedelta(days=29)
    rows: list[UserListRow] = []

    with _lock:
        for state in _users.values():
            active = {
                day: count
                for day, count in state.daily.items()
                if cutoff <= day <= today and count > 0
            }
            if not active:
                continue
            favorite = (
                sorted(
                    state.by_feature.items(),
                    key=lambda item: (-item[1], item[0]),
                )[0][0]
                if state.by_feature
                else None
            )
            rows.append(
                {
                    "user_id": state.user_id,
                    "requests_30d": sum(active.values()),
                    "days_active_30d": len(active),
                    "last_seen": _iso(state.last_seen),
                    "favorite_feature": favorite,
                }
            )

    rows.sort(key=lambda row: (-row["requests_30d"], row["user_id"]))
    return {"generated_at": _iso(_now()) or "", "users": rows}


def _fab_rows(
    active_users: dict[str, set[str]],
    page_counts: dict[str, dict[str, int]],
) -> list[FabUsageRow]:
    rows = [
        {
            "fab": fab,
            "total": len(users),
            "pages": _top_features(page_counts.get(fab, {})),
        }
        for fab, users in active_users.items()
        if users
    ]
    rows.sort(key=lambda row: (-row["total"], row["fab"]))
    return rows


def _fab_window(
    today: date,
    cutoff: date,
) -> list[FabUsageRow]:
    active_users: dict[str, set[str]] = {}
    page_counts: dict[str, dict[str, int]] = {}

    for state in _users.values():
        for day, fabs in state.daily_fabs.items():
            if not cutoff <= day <= today:
                continue
            for fab in fabs:
                active_users.setdefault(fab, set()).add(state.user_id)
        for day, fab_features in state.daily_fab_features.items():
            if not cutoff <= day <= today:
                continue
            for fab, counts in fab_features.items():
                _merge_counts(page_counts.setdefault(fab, {}), counts)

    return _fab_rows(active_users, page_counts)


def get_fab_page_usage() -> FabUsageResponse:
    today = _today()
    with _lock:
        rows_7d = _fab_window(today, today - timedelta(days=6))
        rows_30d = _fab_window(today, today - timedelta(days=29))
    return {
        "generated_at": _iso(_now()) or "",
        "fabs_7d": rows_7d,
        "fabs_30d": rows_30d,
    }


def seed_demo_users() -> None:
    """Populate deterministic mock peers without ranking entry traffic."""

    today = _today()
    demo: list[tuple[str, str, dict[str, int], int]] = [
        (
            "kim.minju",
            "M14",
            {
                "sem_list": 220,
                "recipe_search": 160,
                "meas_hist": 45,
                "fail_issue": 30,
            },
            14,
        ),
        (
            "park.jinho",
            "M16B",
            {
                "recipe_search": 190,
                "sem_list": 120,
                "recipe_tat": 65,
                "storage": 25,
            },
            12,
        ),
        (
            "lee.soyoung",
            "M11",
            {
                "sem_list": 140,
                "storage": 80,
                "fail_issue": 55,
                "hardware": 20,
            },
            9,
        ),
        (
            "choi.eunwoo",
            "R3",
            {
                "recipe_tat": 70,
                "sem_list": 60,
                "recipe_search": 40,
                "device_statistics": 25,
            },
            6,
        ),
        (
            "jung.hari",
            "M15",
            {
                "skewvoir": 90,
                "sem_list": 30,
                "afm": 25,
                "meas_hist": 15,
            },
            4,
        ),
    ]
    now = _now()

    with _lock:
        for user_id, fab, features, days_back in demo:
            if user_id in _users:
                continue
            state = _UserState(
                user_id=user_id,
                first_seen=now - timedelta(days=days_back),
                last_seen=now - timedelta(hours=1),
            )
            for feature, total in features.items():
                if feature != "sem_list":
                    state.by_feature[feature] = total
                for offset in range(days_back):
                    count = total // days_back
                    if offset < total % days_back:
                        count += 1
                    if count == 0:
                        continue
                    day = today - timedelta(days=offset)
                    state.total += count
                    state.daily[day] = state.daily.get(day, 0) + count
                    state.daily_fabs.setdefault(day, set()).add(fab)
                    if feature == "sem_list":
                        continue
                    day_features = state.daily_features.setdefault(day, {})
                    day_features[feature] = (
                        day_features.get(feature, 0) + count
                    )
                    fab_features = state.daily_fab_features.setdefault(
                        day,
                        {},
                    ).setdefault(fab, {})
                    fab_features[feature] = (
                        fab_features.get(feature, 0) + count
                    )
            _users[user_id] = state
