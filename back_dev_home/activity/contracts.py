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
