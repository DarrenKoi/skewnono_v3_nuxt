"""Stable response contracts for fail_issue endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi.recipe_tat.providers.mock import ToolType


__all__ = [
    "AlignOutcome",
    "MsrCheck",
    "FailRow",
    "SummaryPayload",
    "DailyTrendPoint",
    "AlignRankingRow",
    "MeasRankingRow",
    "DeviceRow",
]


AlignOutcome = Literal["Pass", "Fail", "NA"]
MsrCheck = Literal["Yes", "No"]


class FailRow(TypedDict):
    # Subset of MeasHistRow needed by fail aggregators, plus enriched fail
    # fields. Keeping this typed lets the aggregators below stay readable.
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
    timestamp: str
    align_fail: AlignOutcome
    msr_check: MsrCheck
    total_images: int
    fail_images: int
    fail_ratio: float


class SummaryPayload(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    start_date: str | None
    end_date: str | None
    anchor_date: str
    total_executions: int
    align_fail_count: int
    align_fail_rate: float
    align_na_count: int
    meas_fail_count: int
    meas_fail_rate: float
    meas_fail_threshold: float
    distinct_equipment: int
    distinct_recipes: int
    distinct_lots: int


class DailyTrendPoint(TypedDict):
    date: str
    exec_count: int
    align_fail_count: int
    meas_fail_count: int


class AlignRankingRow(TypedDict):
    # Ranked by align_fail_count desc, grouped by recipe so the Align Fail
    # table uses the same recipe-first triage axis as Meas Fail.
    rank: int
    class_name: str
    recipe_name: str
    full_name: str
    exec_count: int
    align_fail_count: int
    align_fail_rate: float
    sample_eqp_ids: list[str]


class MeasRankingRow(TypedDict):
    rank: int
    class_name: str
    recipe_name: str
    full_name: str
    exec_count: int
    meas_fail_count: int
    meas_fail_rate: float
    avg_fail_ratio: float
    sample_eqp_ids: list[str]


class DeviceRow(TypedDict):
    lot_cd: str
    exec_count: int
    align_fail_count: int
    meas_fail_count: int
    prod_catg_cd: str | None
    tech_nm: str | None
