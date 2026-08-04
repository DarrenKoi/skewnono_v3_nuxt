"""Stable response contracts for activity endpoints."""

from __future__ import annotations

from typing import TypedDict


__all__ = [
    "FeatureCount",
    "DailyCount",
    "MeThisMonth",
    "MeResponse",
    "SummaryResponse",
    "UserListRow",
    "UserListResponse",
    "NamedUserListRow",
    "NamedUserListResponse",
    "UserHistoryResponse",
    "FabPageCount",
    "FabUsageRow",
    "FabUsageResponse",
]


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


class NamedUserListRow(UserListRow):
    """A listed user after the route joined the member directory onto it.

    Split from ``UserListRow`` on purpose. The activity providers read the
    logging store, which knows employee numbers and no names at all, so making
    them promise ``emp_nm`` would be a promise neither adapter could keep. The
    name is added in ``routes.py`` from ``_auth.directory``, and this is the
    shape that reaches the SPA.

    ``emp_nm`` is None whenever the directory could not answer — no row for
    that empno, Redis unreachable, a malformed document. The frontend falls
    back to showing the employee number alone.
    """

    emp_nm: str | None


class NamedUserListResponse(TypedDict):
    generated_at: str
    users: list[NamedUserListRow]


class UserHistoryResponse(TypedDict):
    user_id: str
    this_month: MeThisMonth
    top_features: list[FeatureCount]
    daily: list[DailyCount]
    first_seen: str | None
    last_seen: str | None


class FabPageCount(TypedDict):
    feature: str
    count: int


class FabUsageRow(TypedDict):
    fab: str
    total: int
    pages: list[FabPageCount]


class FabUsageResponse(TypedDict):
    generated_at: str
    fabs_7d: list[FabUsageRow]
    fabs_30d: list[FabUsageRow]
