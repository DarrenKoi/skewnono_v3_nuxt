"""Stable response contracts for fail_issue endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi.recipe_tat.providers.mock import ToolType


__all__ = [
    "FAIL_INDEX_MIN_EXPECTED",
    "CONFIDENCE_Z",
    "AlignOutcome",
    "MsrCheck",
    "FailRow",
    "SummaryPayload",
    "DailyTrendPoint",
    "AlignRankingRow",
    "MeasRankingRow",
    "DeviceRow",
]


# 지수를 만들 수 있는 최소 기대 실패 건수. 기대가 1건 미만이면 비율의 분모가
# 사실상 없습니다.
#
# recipe_tat 의 TAT_INDEX_MIN_SAMPLE(=12, 실행 횟수) 과 달리 **OFFICE-VERIFY 가
# 아닙니다.** 튜닝 대상이 아니라 정의의 경계이기 때문입니다. 잡음 판정은 이
# 상수가 아니라 신뢰구간이 합니다 — 설계 3.2절.
FAIL_INDEX_MIN_EXPECTED = 1.0

# Byar 구간의 신뢰수준. 95 % 관례값이며 튜닝 대상이 아닙니다. payload 에
# 에코하는 이유는 프론트엔드가 구간의 의미를 추측하지 않게 하기 위해서입니다.
CONFIDENCE_Z = 1.96

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
    fail_ratio: float  # PERCENT, 0..100 — same scale as MeasHistRow.fail_ratio


class SummaryPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
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
    # Fabs whose measurements entered this aggregate, sorted asc. The detail
    # link uses this to route to the owning fab's registry (multi-fab spec §6.1).
    fab_names: list[str]


class MeasRankingRow(TypedDict):
    rank: int
    class_name: str
    recipe_name: str
    full_name: str
    exec_count: int
    meas_fail_count: int
    meas_fail_rate: float   # fraction, 0..1 — failing rows / all rows
    avg_fail_ratio: float   # PERCENT, 0..100 — mean of the per-row fail_ratio
    sample_eqp_ids: list[str]
    # Fabs whose measurements entered this aggregate, sorted asc. The detail
    # link uses this to route to the owning fab's registry (multi-fab spec §6.1).
    fab_names: list[str]


class DeviceRow(TypedDict):
    lot_cd: str
    exec_count: int
    align_fail_count: int
    meas_fail_count: int
    prod_catg_cd: str | None
    tech_nm: str | None
