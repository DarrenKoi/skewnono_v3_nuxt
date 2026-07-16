"""Stable response contracts for recipe_tat endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = [
    "ToolType",
    "MeasHistRow",
    "RankingRow",
    "SummaryPayload",
    "DailyTrendPoint",
    "DeviceRow",
]


ToolType = Literal["cd-sem", "hv-sem"]


class MeasHistRow(TypedDict):
    id: str
    fac_id: str
    fab_name: str
    vendor_nm: str
    eqp_id: str
    eqp_model_cd: str
    tool_type: ToolType
    lot_cd: str
    lot_id: str
    class_name: str
    recipe_name: str
    full_name: str
    timestamp: str       # ISO-8601 UTC
    start_time: str
    end_time: str
    meastime: int         # seconds


class RankingRow(TypedDict):
    rank: int
    class_name: str
    recipe_name: str
    full_name: str
    meas_counts: int
    total_meastime: int
    avg_meastime: float
    sample_lot_cds: list[str]
    sample_eqp_ids: list[str]


class SummaryPayload(TypedDict):
    tool_type: ToolType
    fab_id: str | None
    start_date: str | None
    end_date: str | None
    # `anchor_date` reports the latest UTC date for which the underlying
    # data has rows — pinned to ANCHOR_TIME at module import. The frontend
    # uses it as the date-picker's ceiling so preset clicks ("Last 7 days")
    # never overshoot the available data.
    anchor_date: str
    total_tat_seconds: int
    total_recipes: int
    total_executions: int
    avg_meastime: float


class DailyTrendPoint(TypedDict):
    date: str
    total_meastime: int
    exec_count: int


class DeviceRow(TypedDict):
    lot_cd: str
    exec_count: int
    total_meastime: int
    # 빠른 필터 metadata. Recipe-TAT's MeasHistRow doesn't carry product
    # category info — these come from device_statistics (R3 → prod_catg_cd,
    # M-fab → tech_nm). Exactly one is populated per lot in practice; the
    # other is null.
    prod_catg_cd: str | None
    tech_nm: str | None
