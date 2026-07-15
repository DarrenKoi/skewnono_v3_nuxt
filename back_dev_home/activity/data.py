"""SWAP SURFACE — usage statistics data layer.

원본:        (사무실 측 Redis 카운터 + OpenSearch usage_events 인덱스)
계약:        docs/api-contracts/activity.yaml + docs/api-contracts/usage-events.yaml
픽스처:      없음 — 라이브 카운터라 픽스처 캡처는 무의미합니다.

동작 규칙:
- 홈 (is_cloud()=False): 모든 호출이 메모리 내 `_users` 딕셔너리만 사용합니다.
  record_request() 가 라이브 요청을 받아 집계하고, get_* 함수들이 같은 딕셔너리를
  순회해서 응답을 만듭니다. Redis / OpenSearch 는 호출하지 않습니다.
- 사무실 (is_cloud()=True): record_request() 가 Redis 에 HINCRBY/SADD 를 쏘고
  OpenSearch usage_events 에 도큐먼트 한 건을 인덱싱합니다. get_summary /
  get_user_history 는 라이브 카운터를 읽고, 실패 시 메모리 폴백을 사용합니다
  (health/data.py 와 동일한 try/except 패턴).

이 파일은 게임화 (tier / score / streak) 로직을 더 이상 다루지 않습니다.
이전 버전과 호환되어야 하는 외부 임포트는 없습니다 (라우트는 이 파일과 함께
교체됨).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import TypedDict

from .._auth.admin import is_admin
from .._runtime.env import is_cloud


__all__ = [
    "FeatureCount",
    "DailyCount",
    "MeThisMonth",
    "MeResponse",
    "SummaryResponse",
    "UserListRow",
    "UserListResponse",
    "UserHistoryResponse",
    "SemModelCount",
    "SemModelUsageResponse",
    "record_request",
    "get_me",
    "get_summary",
    "get_sem_model_usage",
    "get_users_list",
    "get_user_history",
    "is_admin",
    "seed_demo_users",
]


# Skip the usage API itself and the admin log viewer so the dashboard doesn't
# inflate its own counters.
_SKIP_PATH_PREFIXES = ("/api/activity/", "/api/admin/logs")
# Sparkline window for personal / per-user views.
_SPARKLINE_DAYS = 30
# Cap top-features lists in the response payload.
_TOP_FEATURES_CAP = 10


class FeatureCount(TypedDict):
    feature: str
    count: int


class DailyCount(TypedDict):
    date: str
    count: int


class MeThisMonth(TypedDict):
    requests: int
    days_active: int


class MeResponse(TypedDict):
    user_id: str
    is_admin: bool
    this_month: MeThisMonth
    top_features: list[FeatureCount]
    daily: list[DailyCount]
    first_seen: str | None
    last_seen: str | None


class SummaryResponse(TypedDict):
    generated_at: str
    dau: int
    wau: int
    mau: int
    top_features_7d: list[FeatureCount]
    top_features_30d: list[FeatureCount]


class UserListRow(TypedDict):
    user_id: str
    requests_30d: int
    days_active_30d: int
    last_seen: str | None
    favorite_feature: str | None


class UserListResponse(TypedDict):
    generated_at: str
    users: list[UserListRow]


class UserHistoryResponse(TypedDict):
    user_id: str
    this_month: MeThisMonth
    top_features: list[FeatureCount]
    daily: list[DailyCount]
    first_seen: str | None
    last_seen: str | None


class SemModelCount(TypedDict):
    model: str
    vendor: str
    tool_count: int
    count: int


class SemModelUsageResponse(TypedDict):
    generated_at: str
    models_7d: list[SemModelCount]
    models_30d: list[SemModelCount]


@dataclass
class _UserState:
    user_id: str
    total: int = 0
    by_feature: dict[str, int] = field(default_factory=dict)
    daily: dict[date, int] = field(default_factory=dict)
    first_seen: datetime | None = None
    last_seen: datetime | None = None


_users: dict[str, _UserState] = {}
_lock = RLock()


# ------- helpers ------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _top_features(counts: dict[str, int], cap: int = _TOP_FEATURES_CAP) -> list[FeatureCount]:
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:cap]
    return [{"feature": feat, "count": n} for feat, n in ranked]


def _daily_series(daily: dict[date, int], today: date, days: int) -> list[DailyCount]:
    out: list[DailyCount] = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        out.append({"date": d.isoformat(), "count": daily.get(d, 0)})
    return out


def _this_month_stats(daily: dict[date, int], today: date) -> MeThisMonth:
    first = today.replace(day=1)
    requests = 0
    days_active = 0
    for d, n in daily.items():
        if d >= first and d <= today and n > 0:
            requests += n
            days_active += 1
    return {"requests": requests, "days_active": days_active}


def _scale_features(by_feature: dict[str, int], window_sum: int, total: int, into: dict[str, int]) -> None:
    """Approximate per-window feature counts by scaling the lifetime by_feature
    map by the user's share-of-activity in the window. The in-memory mock
    only carries lifetime feature totals, so true per-day slicing requires
    Redis HINCRBY counters (the office implementation).
    """
    if window_sum <= 0 or total <= 0:
        return
    scale = window_sum / total
    for feat, n in by_feature.items():
        into[feat] = into.get(feat, 0) + int(round(n * scale))


# ------- record_request -----------------------------------------------------


def is_recordable(user_id: str | None, path: str, status: int) -> bool:
    """Single source of truth for usage-event gating.

    Used by both the middleware (to decide whether to call record_request at
    all) and as a defensive re-check inside record_request itself.
    """
    if not user_id or user_id == "-":
        return False
    if not path.startswith("/api/"):
        return False
    if any(path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
        return False
    if status >= 400:
        return False
    return True


def record_request(
    user_id: str,
    method: str,
    path: str,
    status: int,
    feature: str,
) -> None:
    """Tap point invoked from _logging/activity.py after each request.

    Caller is expected to have already checked `is_recordable(...)`. Feature
    slug is passed in so the middleware and the writer share one computation.
    """
    now = _now()
    today = now.date()

    with _lock:
        state = _users.get(user_id)
        if state is None:
            state = _UserState(user_id=user_id, first_seen=now)
            _users[user_id] = state
        state.total += 1
        state.by_feature[feature] = state.by_feature.get(feature, 0) + 1
        state.daily[today] = state.daily.get(today, 0) + 1
        state.last_seen = now

    if is_cloud():
        try:
            from ._office_writer import record_request_to_backends
            record_request_to_backends(
                user_id=user_id,
                method=method,
                path=path,
                status=status,
                feature=feature,
                now=now,
            )
        except Exception:
            # Never let analytics break a real request.
            pass


# ------- read APIs ----------------------------------------------------------


def _history_fields(state: _UserState | None, today: date) -> dict:
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


def _summary_from_mock(today: date) -> SummaryResponse:
    week_start = today - timedelta(days=6)
    month_first = today.replace(day=1)
    last30_start = today - timedelta(days=29)
    dau = wau = mau = 0
    feat_7d: dict[str, int] = {}
    feat_30d: dict[str, int] = {}
    with _lock:
        for state in _users.values():
            sum_7d = 0
            sum_30d = 0
            today_count = 0
            active_month = False
            for d, n in state.daily.items():
                if n <= 0:
                    continue
                if d == today:
                    today_count = n
                if d >= week_start:
                    sum_7d += n
                if d >= last30_start:
                    sum_30d += n
                if d >= month_first:
                    active_month = True
            if today_count > 0:
                dau += 1
            if sum_7d > 0:
                wau += 1
            if active_month:
                mau += 1
            _scale_features(state.by_feature, sum_7d, state.total, feat_7d)
            _scale_features(state.by_feature, sum_30d, state.total, feat_30d)
    return {
        "generated_at": _iso(_now()) or "",
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "top_features_7d": _top_features(feat_7d),
        "top_features_30d": _top_features(feat_30d),
    }


def get_summary() -> SummaryResponse:
    today = _today()
    if is_cloud():
        try:
            from ._office_reader import summary_from_backends
            return summary_from_backends(today)
        except Exception:
            pass
    return _summary_from_mock(today)


def _users_list_from_mock(today: date) -> UserListResponse:
    cutoff = today - timedelta(days=29)
    rows: list[UserListRow] = []
    with _lock:
        for state in _users.values():
            requests_30d = 0
            days_active_30d = 0
            for d, n in state.daily.items():
                if d >= cutoff and n > 0:
                    requests_30d += n
                    days_active_30d += 1
            if requests_30d == 0:
                continue
            favorite = max(state.by_feature.items(), key=lambda kv: kv[1])[0] if state.by_feature else None
            rows.append({
                "user_id": state.user_id,
                "requests_30d": requests_30d,
                "days_active_30d": days_active_30d,
                "last_seen": _iso(state.last_seen),
                "favorite_feature": favorite,
            })
    rows.sort(key=lambda r: (-r["requests_30d"], r["user_id"]))
    return {"generated_at": _iso(_now()) or "", "users": rows}


def get_users_list() -> UserListResponse:
    today = _today()
    if is_cloud():
        try:
            from ._office_reader import users_list_from_backends
            return users_list_from_backends(today)
        except Exception:
            pass
    return _users_list_from_mock(today)


def _sem_model_usage_from_mock() -> SemModelUsageResponse:
    # Model universe comes from the actual sem_list mock fleet so the
    # breakdown always matches what the 장비 상태 pages show.
    from back_dev_home.sem_list.data import get_sem_list

    fleet: dict[str, dict[str, object]] = {}
    for row in get_sem_list():
        entry = fleet.setdefault(
            row["eqp_model_cd"], {"vendor": row["vendor_nm"], "tools": 0}
        )
        entry["tools"] = int(entry["tools"]) + 1  # type: ignore[arg-type]

    # Fixed seed: the ranking stays stable across refreshes. Traffic scales
    # with fleet size but is skewed by a per-model popularity factor so the
    # list isn't just a fleet-size mirror.
    rng = random.Random(0x53454D4C)
    models_7d: list[SemModelCount] = []
    models_30d: list[SemModelCount] = []
    for model in sorted(fleet):
        info = fleet[model]
        tools = int(info["tools"])  # type: ignore[arg-type]
        monthly = max(tools, int(tools * rng.uniform(2.5, 9.0)))
        weekly = max(1, int(monthly * rng.uniform(0.18, 0.32)))
        base = {"model": model, "vendor": str(info["vendor"]), "tool_count": tools}
        models_30d.append({**base, "count": monthly})  # type: ignore[typeddict-item]
        models_7d.append({**base, "count": weekly})  # type: ignore[typeddict-item]
    models_30d.sort(key=lambda r: (-r["count"], r["model"]))
    models_7d.sort(key=lambda r: (-r["count"], r["model"]))
    return {
        "generated_at": _iso(_now()) or "",
        "models_7d": models_7d,
        "models_30d": models_30d,
    }


def get_sem_model_usage() -> SemModelUsageResponse:
    if is_cloud():
        try:
            from ._office_reader import sem_model_usage_from_backends
            return sem_model_usage_from_backends()
        except Exception:
            pass
    return _sem_model_usage_from_mock()


# ------- demo seed ----------------------------------------------------------


def seed_demo_users() -> None:
    """Populate a few mock peers so the dashboard has shape in home/dev mode.

    Idempotent: only seeds users that don't already exist. Real activity from
    record_request() coexists with these (the viewer's own user_id will
    typically be `local-dev`, not in this list).
    """
    today = _today()
    # Page-level slugs from _logging/feature_map.py. The mix is shaped so the
    # global Top 10 reads like real traffic: everyone lands on SEM List first
    # (the basic tool-list request), engineers live in Recipe 검색/TAT, and
    # niche pages (Skewvoir, AFM, 디바이스 통계) trail behind.
    demo: list[tuple[str, dict[str, int], int, int]] = [
        ("kim.minju",   {"sem_list": 220, "recipe_search": 160, "meas_hist": 45, "fail_issue": 30},         14, 35),
        ("park.jinho",  {"recipe_search": 190, "sem_list": 120, "recipe_tat": 65, "storage": 25},           12, 28),
        ("lee.soyoung", {"sem_list": 140, "storage": 80, "fail_issue": 55, "hardware": 20},                  9, 22),
        ("choi.eunwoo", {"recipe_tat": 70, "sem_list": 60, "recipe_search": 40, "device_statistics": 25},    6, 18),
        ("jung.hari",   {"skewvoir": 90, "sem_list": 30, "afm": 25, "meas_hist": 15},                        4, 14),
    ]
    now = _now()
    with _lock:
        for user_id, features, days_back, peak in demo:
            if user_id in _users:
                continue
            state = _UserState(user_id=user_id)
            state.total = sum(features.values())
            state.by_feature = dict(features)
            # Triangle distribution peaking midweek so the sparkline has shape.
            middle = days_back / 2
            for offset in range(days_back):
                d = today - timedelta(days=offset)
                state.daily[d] = max(1, peak - int(abs(offset - middle) * 2))
            state.first_seen = now - timedelta(days=days_back)
            state.last_seen = now - timedelta(hours=(days_back - 1) * 3 + 1)
            _users[user_id] = state
