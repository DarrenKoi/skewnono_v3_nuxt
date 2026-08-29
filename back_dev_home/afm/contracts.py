"""Stable response contracts for afm endpoints."""

from __future__ import annotations

from typing import Any, TypedDict


__all__ = [
    "AfmMeasurementRow",
    "AfmToolRow",
    "AfmFileDetail",
    "AfmProfilePoint",
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
    # Frontend-required: available_points feeds the point picker; data carries
    # the per-site measurement rows the profile view reads.
    available_points: list[str]
    data: list[dict[str, Any]]


class AfmProfilePoint(TypedDict):
    x: float
    y: float
    z: float
