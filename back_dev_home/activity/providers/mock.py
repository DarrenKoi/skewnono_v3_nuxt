"""Network-free activity aggregation for home and automated tests.

The mock stores the same request-scoped semantics the OpenSearch office reader
will aggregate: entry requests count active users, feature requests also count
FAB page usage, and each request can belong to multiple FAB buckets. Feature
rankings (``by_feature`` / ``daily_features``) are a separate unit driven
entirely by ``page_view`` events — a page open is not a request, so it never
touches the daily series or ``daily_fabs``. ``last_seen`` is the deliberate
exception: it answers "when did we last see this person", a presence question
rather than a request-volume one, so a page open DOES advance it. Some pages
(mag-pixel) make no API calls at all, and a user who only opens those must not
read as never-seen while ranking in the page list. Timestamps stay UTC
but day buckets follow ``Asia/Seoul``, matching the office reader's
``time_zone`` aggregations — a UTC calendar here would disagree with
production about "today" for nine hours a day.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from threading import RLock

from ..._auth.admin import is_admin
from ..._core.timefmt import iso_z as _iso
from ..contracts import (
    DailyCount,
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
from .shared import KST, SPARKLINE_DAYS, TOP_FEATURES_CAP


@dataclass
class _UserState:
    user_id: str
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


def _iso_or_none(value: datetime | None) -> str | None:
    # first_seen/last_seen are genuinely nullable; generated_at is not, so the
    # two get different signatures rather than one that lies about both.
    return None if value is None else _iso(value)


def _top_features(
    counts: dict[str, int],
    cap: int = TOP_FEATURES_CAP,
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


def _prune_old_days(state: _UserState, today: date) -> None:
    """Drop day buckets no read window can reach, so state stays bounded.

    The widest windows are the 30-day series and ``this_month``, which on the
    31st of a month reaches one day further back than the sparkline does.
    """
    cutoff = min(
        today - timedelta(days=SPARKLINE_DAYS - 1),
        today.replace(day=1),
    )
    for bucket in (
        state.daily,
        state.daily_features,
        state.daily_fabs,
        state.daily_fab_features,
    ):
        for day in [day for day in bucket if day < cutoff]:
            del bucket[day]


def record_request(
    user_id: str,
    feature: str,
    activity_kind: str,
    fab_name_list: list[str],
) -> None:
    """Record one already-classified human entry, feature or page-view event.

    Two units live in this store on purpose and must not be mixed:

    * request rows (entry/feature) drive the daily series, this_month,
      active-user counts and the FAB page rankings;
    * page_view rows drive the feature rankings only — plus ``last_seen``,
      which is a presence signal rather than a counter (see module docstring).

    Mixing them would silently redefine this_month.requests. See
    docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md.
    """

    if activity_kind not in {"entry", "feature", "page_view"}:
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

        if activity_kind == "page_view":
            # Rankings only. A page open is not a request, so it must not
            # touch state.daily / daily_fabs / daily_fab_features.
            # last_seen is the exception: presence, not volume.
            state.last_seen = now
            state.by_feature[feature] = state.by_feature.get(feature, 0) + 1
            daily_features = state.daily_features.setdefault(today, {})
            daily_features[feature] = daily_features.get(feature, 0) + 1
            _prune_old_days(state, today)
            return

        state.daily[today] = state.daily.get(today, 0) + 1
        state.daily_fabs.setdefault(today, set()).update(fabs)
        state.last_seen = now
        _prune_old_days(state, today)

        if activity_kind != "feature":
            return

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
            "daily": _daily_series({}, today, SPARKLINE_DAYS),
            "first_seen": None,
            "last_seen": None,
        }
    return {
        "this_month": _this_month_stats(state.daily, today),
        "top_features": _top_features(state.by_feature),
        "daily": _daily_series(state.daily, today, SPARKLINE_DAYS),
        "first_seen": _iso_or_none(state.first_seen),
        "last_seen": _iso_or_none(state.last_seen),
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
        "generated_at": _iso(_now()),
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
                    "last_seen": _iso_or_none(state.last_seen),
                    "favorite_feature": favorite,
                }
            )

    rows.sort(key=lambda row: (-row["requests_30d"], row["user_id"]))
    return {"generated_at": _iso(_now()), "users": rows}


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
    users: dict[str, _UserState],
    today: date,
    cutoff: date,
) -> list[FabUsageRow]:
    active_users: dict[str, set[str]] = {}
    page_counts: dict[str, dict[str, int]] = {}

    for state in users.values():
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
        rows_7d = _fab_window(_users, today, today - timedelta(days=6))
        rows_30d = _fab_window(_users, today, today - timedelta(days=29))
    return {
        "generated_at": _iso(_now()),
        "fabs_7d": rows_7d,
        "fabs_30d": rows_30d,
    }


# (user_id, fab, request feature totals, page-view totals, days of activity
# ending today). ``sem_list`` stands in for entry traffic — see _seed_feature.
#
# Page-view totals are listed separately, not derived from the request totals:
# the two have no fixed ratio in reality (mag-pixel makes no requests at all,
# live-alarm makes hundreds per open), and a derived number would teach a
# relationship the office data does not have.
_DEMO_USERS: list[tuple[str, str, dict[str, int], dict[str, int], int]] = [
    (
        "kim.minju",
        "M14",
        {"sem_list": 220, "recipe_search": 160, "meas_hist": 45, "fail_issue": 30},
        {"recipe_search": 34, "meas_hist": 12, "fail_issue": 9, "mag_pixel": 4},
        14,
    ),
    (
        "park.jinho",
        "M16B",
        {"recipe_search": 190, "sem_list": 120, "recipe_tat": 65, "storage": 25},
        {"recipe_search": 28, "recipe_tat": 15, "storage": 11, "live_alarm": 6},
        12,
    ),
    (
        "lee.soyoung",
        "M11",
        {"sem_list": 140, "storage": 80, "fail_issue": 55, "hardware": 20},
        {"storage": 22, "fail_issue": 14, "hardware": 8, "live_alarm": 5},
        9,
    ),
    (
        "choi.eunwoo",
        "R3",
        {"recipe_tat": 70, "sem_list": 60, "recipe_search": 40, "device_statistics": 25},
        {"recipe_tat": 12, "recipe_search": 9, "device_statistics": 7, "chat": 3},
        6,
    ),
    (
        "jung.hari",
        "M15",
        {"skewvoir": 90, "sem_list": 30, "afm": 25, "meas_hist": 15},
        {"skewvoir": 19, "afm": 6, "meas_hist": 5, "mag_pixel": 3},
        4,
    ),
]


def _seed_feature(
    state: _UserState,
    fab: str,
    feature: str,
    total: int,
    days_back: int,
    today: date,
) -> None:
    """Spread ``total`` requests evenly over the last ``days_back`` days.

    ``sem_list`` stands in for entry traffic: it counts toward daily totals
    and FAB active users but never toward the FAB-page rankings, mirroring
    record_request's entry/feature split. Feature rankings themselves
    (``by_feature`` / ``daily_features``) are seeded separately by
    ``_seed_page_views`` — requests no longer feed the rankings.
    """
    is_entry = feature == "sem_list"
    for offset in range(days_back):
        count = total // days_back
        if offset < total % days_back:
            count += 1
        if count == 0:
            continue
        day = today - timedelta(days=offset)
        state.daily[day] = state.daily.get(day, 0) + count
        state.daily_fabs.setdefault(day, set()).add(fab)
        if is_entry:
            continue
        fab_features = state.daily_fab_features.setdefault(
            day,
            {},
        ).setdefault(fab, {})
        fab_features[feature] = fab_features.get(feature, 0) + count


def _seed_page_views(
    state: _UserState,
    feature: str,
    total: int,
    days_back: int,
    today: date,
) -> None:
    """Spread ``total`` page opens evenly over the last ``days_back`` days.

    Deliberately does NOT touch state.daily or daily_fab_features: page views
    feed the rankings only, exactly as record_request splits them.
    """
    if days_back <= 0 or total <= 0:
        return
    per_day, remainder = divmod(total, days_back)
    for offset in range(days_back):
        count = per_day + (1 if offset < remainder else 0)
        if count == 0:
            continue
        day = today - timedelta(days=offset)
        state.by_feature[feature] = state.by_feature.get(feature, 0) + count
        daily = state.daily_features.setdefault(day, {})
        daily[feature] = daily.get(feature, 0) + count


def seed_demo_users() -> None:
    """Populate deterministic mock peers without ranking entry traffic."""

    today = _today()
    now = _now()

    with _lock:
        for user_id, fab, features, page_views, days_back in _DEMO_USERS:
            if user_id in _users:
                continue
            state = _UserState(
                user_id=user_id,
                first_seen=now - timedelta(days=days_back),
                last_seen=now - timedelta(hours=1),
            )
            for feature, total in features.items():
                _seed_feature(state, fab, feature, total, days_back, today)
            for feature, total in page_views.items():
                _seed_page_views(state, feature, total, days_back, today)
            _users[user_id] = state
