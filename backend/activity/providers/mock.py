"""Network-free activity aggregation for home and automated tests.

The mock stores the same request-scoped semantics the OpenSearch office reader
will aggregate: entry requests count active users, feature requests also count
FAB page usage, and each request can belong to multiple FAB buckets. Feature
recency (``last_opened``) and the popularity windows (``daily_features``)
are a separate unit driven
entirely by ``page_view`` events — a page open is not a request, so it never
touches the daily series or ``daily_fabs``. ``last_seen`` is the deliberate
exception: it answers "when did we last see this person", a presence question
rather than a request-volume one, so a page open DOES advance it. Some pages
(mag-pixel) make no API calls at all, and a user who only opens those must not
read as never-seen while ranking in the page list. Timestamps stay UTC
but day buckets follow ``Asia/Seoul``, matching the office reader's
``time_zone`` aggregations — a UTC calendar here would disagree with
production about "today" for nine hours a day.

``get_family_page_usage`` stands in for the office's terms aggregation over
page-view rows grouped by beacon URL (/api/page-view/<family>): per family,
the people who opened one of its pages and the opens per feature. There is no
family field in the index; here the family arrives with each page view (the
beacon route hands the middleware the family from its URL), is kept only for
page views, and every family is listed whether or not anyone came. Seeded page opens are filed
under a family per demo user (``_DEMO_FAMILY``); VeritySEM and Provision stay
at zero because no page of theirs exists yet — a mock that showed traffic
there would be inventing a product.

``get_daily_visitors`` reads the same request rows as the summary counts: a
person is a visitor on a day they made at least one request, and page opens
do not count. Each of its ``VISITOR_DAYS`` rows also carries the rolling WAU
and MAU ending that day, so today's row always equals ``get_summary()``'s
``dau``/``wau``/``mau``. The arithmetic is ``shared.daily_visitor_rows``, which
the office reader calls too — the two adapters differ only in where a
person's active days come from.

Anonymous callers share one ID, so their events are never stored. Reads also
exclude legacy anonymous state, matching the office reader's source/ID filter
(user-confirmed 2026-10-02). Operational request logs are retained separately.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import NamedTuple

from ..._auth.admin import is_admin
from ..._auth.provider import ANONYMOUS
from ..._core.timefmt import iso_z as _iso
from ..contracts import (
    DailyCount,
    FabUsageResponse,
    FabUsageRow,
    FamilyUsageResponse,
    FamilyUsageRow,
    FeatureCount,
    FeatureUse,
    MeResponse,
    MeThisMonth,
    SummaryResponse,
    UserHistoryResponse,
    UserListResponse,
    UserListRow,
    VisitorsResponse,
)
from .shared import (
    FAMILY_BY_BEACON_PATH,
    KST,
    RECENT_FEATURES_CAP,
    SPARKLINE_DAYS,
    TOP_FEATURES_CAP,
    VISIT_DAYS,
    VISITOR_DAYS,
    VISITOR_LOOKBACK_DAYS,
    daily_visitor_rows,
    family_usage_rows,
)


@dataclass
class _UserState:
    user_id: str
    # feature -> when it was last opened. Keyed by feature rather than
    # appended to a list because the question is "which five features", not
    # "which five opens": someone who refreshes Storage all morning would
    # otherwise fill every row with Storage. Bounded by the feature
    # vocabulary (~30 slugs), so it needs no day-based pruning.
    last_opened: dict[str, datetime] = field(default_factory=dict)
    daily: dict[date, int] = field(default_factory=dict)
    daily_features: dict[date, dict[str, int]] = field(default_factory=dict)
    visits: dict[date, int] = field(default_factory=dict)
    # Requests per feature per day, counted ONCE per request. Not derivable
    # from daily_fab_features, which counts a request once per FAB it names —
    # correct for the FAB card, double-counting for a per-day total. The
    # office reader counts each document once, so deriving it here would put
    # home and office on different numbers for the same field.
    daily_feature_requests: dict[date, dict[str, int]] = field(
        default_factory=dict
    )
    # Page opens per feature per FAMILY per day. Separate from daily_features
    # because a page open may belong to no family at all (the hub's children,
    # chat, mag-pixel) and still counts in the global ranking; folding the
    # family into that dict's key would drop those from it.
    daily_family_features: dict[date, dict[str, dict[str, int]]] = field(
        default_factory=dict
    )
    daily_fabs: dict[date, set[str]] = field(default_factory=dict)
    daily_fab_features: dict[date, dict[str, dict[str, int]]] = field(
        default_factory=dict
    )
    first_seen: datetime | None = None
    last_seen: datetime | None = None


_users: dict[str, _UserState] = {}
_lock = RLock()


def _identified_users(users: dict[str, _UserState]) -> Iterable[_UserState]:
    return (state for user_id, state in users.items() if user_id != ANONYMOUS)


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


def _recent_features(
    last_opened: dict[str, datetime],
    cap: int = RECENT_FEATURES_CAP,
) -> list[FeatureUse]:
    ranked = sorted(
        last_opened.items(),
        key=lambda item: (-item[1].timestamp(), item[0]),
    )[:cap]
    return [{"feature": feature, "at": _iso(at)} for feature, at in ranked]


def _day_count(
    day: date,
    daily: dict[date, int],
    day_features: dict[date, dict[str, int]],
) -> DailyCount:
    """One day of the series: the bar, its breakdown, and the rest.

    ``other_count`` is computed from the FULL feature tally, before
    ``_top_features`` truncates it, so a day with more features than the cap
    still reports the entry traffic honestly rather than folding the dropped
    features into it.
    """
    features = day_features.get(day, {})
    total = daily.get(day, 0)
    return {
        "date": day.isoformat(),
        "count": total,
        "features": _top_features(features),
        "other_count": total - sum(features.values()),
    }


def _daily_series(
    daily: dict[date, int],
    day_features: dict[date, dict[str, int]],
    today: date,
    days: int,
) -> list[DailyCount]:
    return [
        _day_count(today - timedelta(days=offset), daily, day_features)
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

    One retention for every bucket: the widest window any reader has. Today
    that is the 90-day visit calendar, with the 방문자 추이 chart (60 days plus
    the 30 its first MAU looks behind) a day short of it. Readers filter by
    their own window, so a bucket kept a little longer than its reader needs
    is invisible.
    """
    cutoff = today - timedelta(days=max(VISIT_DAYS, VISITOR_LOOKBACK_DAYS) - 1)
    for bucket in (
        state.visits,
        state.daily,
        state.daily_features,
        state.daily_fabs,
        state.daily_fab_features,
        state.daily_feature_requests,
        state.daily_family_features,
    ):
        for day in [day for day in bucket if day < cutoff]:
            del bucket[day]


def record_request(
    user_id: str,
    feature: str,
    activity_kind: str,
    fab_name_list: list[str],
    path: str | None = None,
) -> None:
    """Record one already-classified human entry, feature or page-view event.

    Two units live in this store on purpose and must not be mixed:

    * request rows (entry/feature) drive the daily series, this_month,
      active-user counts and the FAB page rankings;
    * page_view rows drive the feature rankings only — plus ``last_seen``,
      which is a presence signal rather than a counter (see module docstring).

    ``path`` is the request path of the row. For a page view it names the tool
    family — a page open is posted to /api/page-view/<family> — and that is
    the only thing it is read for, exactly as the office reader groups on the
    log row's ``path``. A page view on the plain beacon URL has no family.

    Mixing them would silently redefine this_month.requests. See
    docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md.
    """

    if user_id == ANONYMOUS or activity_kind not in {"entry", "feature", "page_view"}:
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
            state.visits[today] = state.visits.get(today, 0) + 1
            # Rankings and visits. A page open is not a request, so it must not
            # touch state.daily / daily_fabs / daily_fab_features.
            # last_seen is the exception: presence, not volume.
            state.last_seen = now
            state.last_opened[feature] = now
            daily_features = state.daily_features.setdefault(today, {})
            daily_features[feature] = daily_features.get(feature, 0) + 1
            family = FAMILY_BY_BEACON_PATH.get(path)
            if family:
                family_features = state.daily_family_features.setdefault(
                    today, {}
                ).setdefault(family, {})
                family_features[feature] = family_features.get(feature, 0) + 1
            _prune_old_days(state, today)
            return

        state.daily[today] = state.daily.get(today, 0) + 1
        state.daily_fabs.setdefault(today, set()).update(fabs)
        state.last_seen = now
        _prune_old_days(state, today)

        if activity_kind != "feature":
            return

        day_features = state.daily_feature_requests.setdefault(today, {})
        day_features[feature] = day_features.get(feature, 0) + 1

        daily_fab_features = state.daily_fab_features.setdefault(today, {})
        for fab in fabs:
            fab_features = daily_fab_features.setdefault(fab, {})
            fab_features[feature] = fab_features.get(feature, 0) + 1


def _history_fields(
    state: _UserState | None,
    today: date,
) -> dict:
    # An unknown user gets the zero response of the same shape, and every
    # helper below already produces it from empty state — so the blank is one
    # empty _UserState rather than a hand-written second copy that has to be
    # edited in step whenever a field is added.
    state = state or _UserState(user_id="")
    visit_days = [today - timedelta(days=offset) for offset in range(VISIT_DAYS - 1, -1, -1)]
    return {
        "this_month": _this_month_stats(state.daily, today),
        "recent_features": _recent_features(state.last_opened),
        "daily": _daily_series(
            state.daily,
            state.daily_feature_requests,
            today,
            SPARKLINE_DAYS,
        ),
        "visits": [
            {"date": day.isoformat(), "count": state.visits.get(day, 0)}
            for day in visit_days
        ],
        "first_seen": _iso_or_none(state.first_seen),
        "last_seen": _iso_or_none(state.last_seen),
    }


def get_me(user_id: str) -> MeResponse:
    today = _today()
    with _lock:
        fields = _history_fields(
            _users.get(user_id) if user_id != ANONYMOUS else None, today
        )
    return {"user_id": user_id, "is_admin": is_admin(user_id), **fields}


def get_user_history(user_id: str) -> UserHistoryResponse | None:
    if user_id == ANONYMOUS:
        return None
    today = _today()
    with _lock:
        state = _users.get(user_id)
        if state is None:
            return None
        return {"user_id": user_id, **_history_fields(state, today)}


def _active_days() -> list[list[date]]:
    """Each person's active KST days. Call with ``_lock`` held."""
    return [
        [day for day, count in state.daily.items() if count > 0]
        for state in _identified_users(_users)
    ]


def get_summary() -> SummaryResponse:
    today = _today()
    week_start = today - timedelta(days=6)
    last30_start = today - timedelta(days=29)
    feature_7d: dict[str, int] = {}
    feature_30d: dict[str, int] = {}

    with _lock:
        active_days = _active_days()
        for state in _identified_users(_users):
            for day, counts in state.daily_features.items():
                if week_start <= day <= today:
                    _merge_counts(feature_7d, counts)
                if last30_start <= day <= today:
                    _merge_counts(feature_30d, counts)

    # Today's row of the visitors series IS the three summary counts, so they
    # are taken from it rather than counted a second way that has to be kept
    # equal by hand.
    now_row = daily_visitor_rows(active_days, today)[-1]
    return {
        "generated_at": _iso(_now()),
        "dau": now_row["visitors"],
        "wau": now_row["wau"],
        "mau": now_row["mau"],
        "top_features_7d": _top_features(feature_7d),
        "top_features_30d": _top_features(feature_30d),
    }


def get_daily_visitors() -> VisitorsResponse:
    """DAU with rolling WAU and MAU, one row per KST day."""
    today = _today()
    with _lock:
        # Copied out under the lock; the counting needs no lock at all.
        active_days = _active_days()
    return {
        "generated_at": _iso(_now()),
        "days": daily_visitor_rows(active_days, today),
    }


def get_users_list() -> UserListResponse:
    today = _today()
    cutoff = today - timedelta(days=29)
    rows: list[UserListRow] = []

    with _lock:
        for state in _identified_users(_users):
            active = {
                day: count
                for day, count in state.daily.items()
                if cutoff <= day <= today and count > 0
            }
            if not active:
                continue
            # Windowed to match the office reader, whose users-list
            # composite sits inside a 30-day range filter: a page opened 40
            # days ago is not this person's current feature there, and must
            # not be here either. /me is unwindowed on both sides.
            recent = _recent_features(
                {
                    feature: at
                    for feature, at in state.last_opened.items()
                    if _kst_date(at) >= cutoff
                },
                cap=1,
            )
            rows.append(
                {
                    "user_id": state.user_id,
                    "requests_30d": sum(active.values()),
                    "days_active_30d": len(active),
                    "last_seen": _iso_or_none(state.last_seen),
                    "recent_feature": recent[0]["feature"] if recent else None,
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

    for state in _identified_users(users):
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


def _family_window(
    users: dict[str, _UserState],
    today: date,
    cutoff: date,
) -> list[FamilyUsageRow]:
    openers: dict[str, set[str]] = {}
    pages: dict[str, dict[str, int]] = {}

    for state in _identified_users(users):
        for day, families in state.daily_family_features.items():
            if not cutoff <= day <= today:
                continue
            for family, counts in families.items():
                openers.setdefault(family, set()).add(state.user_id)
                _merge_counts(pages.setdefault(family, {}), counts)

    return family_usage_rows(
        {family: len(people) for family, people in openers.items()},
        {family: _top_features(counts) for family, counts in pages.items()},
    )


def get_family_page_usage() -> FamilyUsageResponse:
    today = _today()
    with _lock:
        rows_7d = _family_window(_users, today, today - timedelta(days=6))
        rows_30d = _family_window(_users, today, today - timedelta(days=29))
    return {
        "generated_at": _iso(_now()),
        "families_7d": rows_7d,
        "families_30d": rows_30d,
    }


class _DemoUser(NamedTuple):
    """One seeded person. ``sem_list`` in ``requests`` stands in for entry
    traffic — see _seed_feature."""

    user_id: str
    fab: str
    requests: dict[str, int]
    page_views: dict[str, int]
    #: Days of activity, ending today.
    days: int
    #: Which family's pages this person opens. OFFICE-VERIFY: fabricated —
    #: which families people use, and how many work across more than one, is
    #: unknown until it has been collected at the office.
    family: str = "cdsem"
    #: Share of days they do not show up at all. About one in six by default;
    #: the occasional visitors below skip most days.
    skip_rate: float = 0.16


# ``local-dev`` is home's own identity, so it is the one row /activity renders
# as "me". It gets the full 90-day visit window so the calendar has something
# to draw. The peers' histories are staggered — 60, 40, 21, 6 and 4 days — so
# the user table still shows a range AND the admin 방문자 추이 chart has more
# than one person to count on its 1개월/2개월 tabs; with every peer inside two
# weeks it drew a flat 1 for the six weeks before that.
#
# The last three are occasional visitors (their ``skip_rate`` has them come
# roughly weekly, fortnightly and monthly). Without them every
# peer came nearly every day, so WAU equalled MAU on all sixty days: two lines
# drawn on top of each other and a stickiness of 100%, which no real product
# has. OFFICE-VERIFY: the head-count, its slow climb and the share of
# occasional visitors are all fabricated — the real numbers have not been
# read off the office index.
#
# Page-view totals are listed separately, not derived from the request totals:
# the two have no fixed ratio in reality (mag-pixel makes no requests at all,
# live-alarm makes hundreds per open), and a derived number would teach a
# relationship the office data does not have.
_DEMO_USERS: list[_DemoUser] = [
    _DemoUser(
        "kim.minju",
        "M14",
        {"sem_list": 220, "recipe_search": 160, "meas_hist": 45, "fail_issue": 30},
        {"recipe_search": 34, "meas_hist": 12, "fail_issue": 9, "mag_pixel": 4},
        VISITOR_DAYS,
    ),
    _DemoUser(
        "park.jinho",
        "M16B",
        {"recipe_search": 190, "sem_list": 120, "recipe_tat": 65, "storage": 25},
        {"recipe_search": 28, "recipe_tat": 15, "storage": 11, "live_alarm": 6},
        40,
        family="hvsem",
    ),
    _DemoUser(
        "lee.soyoung",
        "M11",
        {"sem_list": 140, "storage": 80, "fail_issue": 55, "hardware": 20},
        {"storage": 22, "fail_issue": 14, "hardware": 8, "live_alarm": 5},
        21,
        family="hvsem",
    ),
    _DemoUser(
        "choi.eunwoo",
        "R3",
        {
            "recipe_tat": 70,
            "sem_list": 60,
            "recipe_search": 40,
            "device_statistics": 25,
        },
        {"recipe_tat": 12, "recipe_search": 9, "device_statistics": 7, "chat": 3},
        6,
    ),
    _DemoUser(
        "jung.hari",
        "M15",
        {"skewvoir": 90, "sem_list": 30, "afm": 25, "meas_hist": 15},
        {"skewvoir": 19, "afm": 6, "meas_hist": 5, "mag_pixel": 3},
        4,
    ),
    _DemoUser(
        "local-dev",
        "M16B",
        {"sem_list": 620, "recipe_search": 430, "storage": 260, "meas_hist": 140},
        {
            "recipe_search": 150,
            "storage": 110,
            "live_alarm": 70,
            "meas_hist": 45,
            "mag_pixel": 25,
        },
        VISIT_DAYS,
    ),
    _DemoUser(
        "han.jiwoo",
        "M14",
        {"sem_list": 26, "recipe_search": 18},
        {"recipe_search": 9, "meas_hist": 3},
        VISITOR_DAYS,
        skip_rate=0.8,
    ),
    _DemoUser(
        "seo.dohyun",
        "M16B",
        {"sem_list": 15, "storage": 9},
        {"storage": 6},
        VISITOR_DAYS,
        family="hvsem",
        skip_rate=0.9,
    ),
    _DemoUser(
        "yoon.chaewon",
        "R3",
        {"sem_list": 9, "device_statistics": 6},
        {"device_statistics": 4},
        45,
        skip_rate=0.95,
    ),
]

# Pages whose family does not depend on who opens them. `afm` is its own
# family; chat and mag-pixel are shared pages that belong to none; and
# device_statistics exists under CD-SEM only.
_PAGE_FAMILY: dict[str, str | None] = {
    "afm": "afm",
    "chat": None,
    "mag_pixel": None,
    "device_statistics": "cdsem",
}


def _day_weights(user: _DemoUser, today: date) -> list[float]:
    """Relative activity per day, index = days before today. Deterministic.

    An even spread renders a flat calendar and teaches that everyone works
    every day at the same rate. Weekends run lighter and a share of days
    (``skip_rate``) is skipped outright. OFFICE-VERIFY: the weekend ratio and
    the skip rates are guesses — fab metrology runs shifts, so real weekends
    may not be this quiet.
    """
    rng = random.Random(user.user_id)
    weights = []
    for offset in range(user.days):
        # Both draws happen every day so the stream never shifts with the branch.
        skipped = rng.random() < user.skip_rate
        spread = rng.uniform(0.2, 1.8)
        weekend = (today - timedelta(days=offset)).weekday() >= 5
        weights.append(0.0 if skipped else spread * (0.3 if weekend else 1.0))
    if not any(weights):
        weights[0] = 1.0
    return weights


def _spread(total: int, weights: list[float]) -> list[int]:
    """Split ``total`` in proportion to ``weights``, keeping the exact sum."""
    scale = sum(weights)
    raw = [total * weight / scale for weight in weights]
    counts = [int(value) for value in raw]
    by_remainder = sorted(
        range(len(raw)), key=lambda i: raw[i] - counts[i], reverse=True
    )
    for i in by_remainder[: total - sum(counts)]:
        counts[i] += 1
    return counts


def _seed_feature(
    state: _UserState,
    fab: str,
    feature: str,
    total: int,
    weights: list[float],
    today: date,
) -> None:
    """Spread ``total`` requests over the days ``weights`` covers.

    ``sem_list`` stands in for entry traffic: it counts toward daily totals
    and FAB active users but never toward the FAB-page rankings or the
    per-day breakdown, mirroring record_request's entry/feature split. The
    popularity windows are seeded by ``_seed_page_views`` and feature recency
    by ``seed_demo_users`` itself — requests no longer feed either.
    """
    is_entry = feature == "sem_list"
    for offset, count in enumerate(_spread(total, weights)):
        if count == 0:
            continue
        day = today - timedelta(days=offset)
        state.daily[day] = state.daily.get(day, 0) + count
        state.daily_fabs.setdefault(day, set()).add(fab)
        if is_entry:
            continue
        day_features = state.daily_feature_requests.setdefault(day, {})
        day_features[feature] = day_features.get(feature, 0) + count
        fab_features = state.daily_fab_features.setdefault(
            day,
            {},
        ).setdefault(fab, {})
        fab_features[feature] = fab_features.get(feature, 0) + count


def _seed_page_views(
    state: _UserState,
    feature: str,
    total: int,
    weights: list[float],
    today: date,
    family: str | None,
) -> None:
    """Spread ``total`` page opens over the days ``weights`` covers.

    Deliberately does NOT touch state.daily or daily_fab_features: page views
    feed the rankings only, exactly as record_request splits them.
    ``last_opened`` is set by the caller, which knows the whole feature order
    and can stagger it into a believable history.
    """
    if not weights or total <= 0:
        return
    for offset, count in enumerate(_spread(total, weights)):
        if count == 0:
            continue
        day = today - timedelta(days=offset)
        daily = state.daily_features.setdefault(day, {})
        daily[feature] = daily.get(feature, 0) + count
        state.visits[day] = state.visits.get(day, 0) + count
        if family:
            by_family = state.daily_family_features.setdefault(
                day, {}
            ).setdefault(family, {})
            by_family[feature] = by_family.get(feature, 0) + count


def seed_demo_users() -> None:
    """Populate deterministic mock peers without ranking entry traffic."""

    today = _today()
    now = _now()

    with _lock:
        for user in _DEMO_USERS:
            if user.user_id in _users:
                continue
            state = _UserState(
                user_id=user.user_id,
                first_seen=now - timedelta(days=user.days),
                last_seen=now - timedelta(hours=1),
            )
            # One pattern per user, shared by requests and page opens, so a
            # day off is a day off in both series.
            weights = _day_weights(user, today)
            for feature, total in user.requests.items():
                _seed_feature(state, user.fab, feature, total, weights, today)
            for feature, total in user.page_views.items():
                _seed_page_views(
                    state,
                    feature,
                    total,
                    weights,
                    today,
                    _PAGE_FAMILY.get(feature, user.family),
                )
            # Staggered an hour apart in declaration order so every demo user
            # has a readable 최근 쓴 기능 list. Seeding them all at `now` would
            # tie, and the tiebreak is alphabetical — an order that says
            # nothing about how the person actually works.
            for index, feature in enumerate(user.page_views):
                state.last_opened[feature] = now - timedelta(hours=index + 1)
            # A 90-day seed would otherwise leave request detail older than any
            # read window in memory until this user's first live request.
            _prune_old_days(state, today)
            _users[user.user_id] = state
