"""Stable response contracts for activity endpoints."""

from __future__ import annotations

from typing import TypedDict


__all__ = [
    "FeatureCount",
    "FeatureUse",
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


class FeatureUse(TypedDict):
    """One feature and when this person last opened it.

    Separate from ``FeatureCount`` on purpose: that one answers "how often",
    this one answers "how recently", and a shape carrying both would invite a
    reader to rank by the field the query did not order on.
    """

    feature: str
    at: str


class DailyCount(TypedDict):
    """One day of the 30일 활동 series, plus what was called that day.

    ``count`` is every request row (entry + feature kinds). ``features``
    breaks down the feature-kind ones only and is capped, so the parts do NOT
    sum to ``count`` — which is why ``other_count`` is sent rather than left
    to the caller to subtract: entry traffic belongs to no single feature,
    and on a day with more features than the cap a subtraction would fold the
    dropped ones into it silently.
    """

    date: str
    count: int
    features: list[FeatureCount]
    other_count: int


class MeThisMonth(TypedDict):
    requests: int
    days_active: int


class MeResponse(TypedDict):
    user_id: str
    is_admin: bool
    this_month: MeThisMonth
    recent_features: list[FeatureUse]
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
    #: The feature opened most recently, or None for someone whose only rows
    #: are requests (a page whose beacon never fired, or traffic older than
    #: the page-view rollout).
    recent_feature: str | None


class UserListResponse(TypedDict):
    generated_at: str
    users: list[UserListRow]


class NamedUserListRow(UserListRow):
    """A listed user after the route joined the member directory onto it.

    Split from ``UserListRow`` on purpose. The activity providers read the
    logging store, which knows employee numbers and no names or teams at all,
    so making them promise these would be a promise neither adapter could
    keep. They are added in ``routes.py`` from ``_auth.directory``, and this
    is the shape that reaches the SPA.

    Both are None whenever the directory could not answer — no row for that
    empno, Redis unreachable, a malformed document — and either can be None on
    its own, because a member row may be partial. The frontend falls back to
    the employee number alone for the name, and to a dash for the team.

    The directory also carries ``organ_cd`` and ``upper_organ_nm``; they stay
    out of this shape because nothing renders them, and an API field with no
    reader is a field that quietly rots.
    """

    emp_nm: str | None
    dept_nm: str | None


class NamedUserListResponse(TypedDict):
    generated_at: str
    users: list[NamedUserListRow]


class UserHistoryResponse(TypedDict):
    user_id: str
    this_month: MeThisMonth
    recent_features: list[FeatureUse]
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
