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
    "EquipmentRow",
    "FleetReference",
    "EquipmentsPayload",
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


class EquipmentRow(TypedDict):
    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    exec_count: int
    # align --------------------------------------------------------------
    align_fail_count: int
    align_fail_rate: float          # fraction, 0..1
    # 이 장비의 레시피 구성이면 나왔어야 할 실패 건수. 표의 툴팁이 이 값을
    # 그대로 보여줍니다 — 배지가 켜진 근거를 사용자가 확인할 수 없으면
    # 배지를 믿지 않거나, 더 나쁘게는 근거 없이 믿습니다.
    align_expected: float
    align_index: float | None       # actual / expected. 표시 하한 미만이면 None
    align_index_low: float | None   # Byar 95 % 하한
    align_index_high: float | None
    # meas ---------------------------------------------------------------
    meas_fail_count: int
    meas_fail_rate: float
    meas_expected: float
    meas_index: float | None
    meas_index_low: float | None
    meas_index_high: float | None
    # 구성 ---------------------------------------------------------------
    recipe_count: int
    top_recipe: str | None
    # 실행 **횟수** 비중입니다(recipe_tat 은 TAT 비중). 실패 화면에서 "이
    # 장비는 사실상 한 레시피만 돈다"의 근거는 시간이 아니라 횟수입니다.
    top_recipe_share: float


class FleetReference(TypedDict):
    tool_count: int
    total_executions: int
    align_fail_count: int
    meas_fail_count: int
    align_fail_rate: float
    meas_fail_rate: float
    median_exec_count: float
    median_recipe_count: float
    min_expected_fails: float
    confidence_z: float
    # 사무실에서 FAIL_INDEX_CEIL 을 정하기 위한 분포 참고용입니다.
    # **배지 판정에는 쓰이지 않습니다** — 잡음 판정은 신뢰구간이 합니다.
    # 키: "align_fail_rate" | "align_index" | "meas_fail_rate" | "meas_index"
    #     | "recipe_count" | "exec_count"
    # 값: {"p10","p25","p50","p75","p90"}. 지수는 None 인 장비를 제외하고
    # 계산하며, 대상 장비가 없으면 빈 dict.
    percentiles: dict[str, dict[str, float]]


class EquipmentsPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    fleet: FleetReference
    equipments: list[EquipmentRow]
