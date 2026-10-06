"""Stable response contracts for afm endpoints."""

from __future__ import annotations

from typing import Any, TypedDict


__all__ = [
    "AfmMeasurementRow",
    "AfmToolRow",
    "AfmFileDetail",
    "AfmProfilePoint",
    "AfmProfileMeta",
    "AfmOriginalFile",
]


class AfmMeasurementRow(TypedDict):
    # One row of Redis `afm_d2_measurements` (docs/datatables/afm/afm_redis.txt).
    # The office stores an empty value as null, so the three cells it documents
    # as nullable are typed that way; every other text cell is "" when missing.
    # `unique_key` is the name's first six `#` fields (four on MAPC01).
    unique_key: str
    filename: str
    date: str
    formatted_date: str | None
    recipe_name: str
    lot_id: str
    slot_number: str
    time: str | None
    measured_info: str
    tool_name: str
    tool_id: str
    fab: str
    # File names (the basename of each stored MinIO key), [] when there are none.
    profile_dir_list: list[str]
    data_dir_list: list[str]
    tiff_dir_list: list[str]
    align_dir_list: list[str]
    tip_dir_list: list[str]
    capture_dir_list: list[str]
    raw_dir_list: list[str]
    has_profile: bool
    has_data: bool
    has_image: bool
    has_align: bool
    has_tip: bool
    point_count: int | None


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


class AfmProfileMeta(TypedDict):
    # What one profile file declares about itself. Units are never unified —
    # each is one of um / nm / pm / Pixel and differs from file to file — so
    # they travel with the points. `data_size` ("1024 x 1") tells a 1D line from
    # a 2D grid.
    x_unit: str
    y_unit: str
    z_unit: str
    data_size: str
    surface_size: str


class AfmOriginalFile(TypedDict):
    # One stored object handed to the caller byte for byte — the only AFM
    # contract that carries bytes. `filename` is the basename of the stored key,
    # not a name we compose, so a download keeps the identity it has in storage.
    filename: str
    content_type: str
    data: bytes
