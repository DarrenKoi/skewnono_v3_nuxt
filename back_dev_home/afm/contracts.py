"""Stable response contracts for afm endpoints."""

from __future__ import annotations

from typing import Any, TypedDict


__all__ = [
    "AfmMeasurementRow",
    "AfmToolRow",
    "AfmFileDetail",
    "AfmProfilePoint",
    "AfmUserActivity",
    "AfmDailyStat",
    "AfmAnalyticsSummary",
    "AfmUserAnalytics",
]


class AfmMeasurementRow(TypedDict):
    unique_key: str
    filename: str
    date: str
    formatted_date: str
    recipe_name: str
    lot_id: str
    slot_number: str
    time: str
    measured_info: str
    tool_name: str
    tool_id: str
    fab: str
    profile_dir_list: list[str]
    data_dir_list: list[str]
    tiff_dir_list: list[str]
    align_dir_list: list[str]
    tip_dir_list: list[str]
    capture_dir_list: list[str]
    has_profile: bool
    has_data: bool
    has_image: bool
    has_align: bool
    has_tip: bool
    hasProfile: bool
    hasData: bool
    hasImage: bool
    hasAlign: bool
    hasTip: bool
    point_count: int


class AfmToolRow(TypedDict):
    id: str
    name: str
    label: str
    fab: str


class AfmFileDetail(TypedDict):
    filename: str
    tool: str
    pickle_filename: str
    information: dict[str, str]
    summary: list[dict[str, Any]]


class AfmProfilePoint(TypedDict):
    x: float
    y: float
    z: float


class AfmUserActivity(TypedDict):
    timestamp: str
    user: str
    action: str
    tool: str
    filename: str
    summary_count: int
    detail_count: int


class AfmDailyStat(TypedDict):
    date: str
    unique_users: int
    total_sessions: int
    total_actions: int
    avg_actions_per_session: float


class AfmAnalyticsSummary(TypedDict):
    period_days: int
    total_unique_users: int
    avg_daily_users: float
    avg_daily_sessions: float


class AfmUserAnalytics(TypedDict):
    daily_stats: list[AfmDailyStat]
    summary: AfmAnalyticsSummary
