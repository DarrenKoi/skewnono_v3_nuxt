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
    "TAT_INDEX_MIN_SAMPLE",
    "EquipmentRow",
    "FleetReference",
    "EquipmentsPayload",
    "EquipmentTrendSeries",
    "EquipmentRecipeCell",
    "EquipmentRecipeRow",
    "EquipmentComparePayload",
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
    # Fabs whose measurements entered this aggregate, sorted asc. The detail
    # link uses this to route to the owning fab's registry (multi-fab spec §6.1).
    fab_names: list[str]


class SummaryPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
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


# 이 미만의 실행 수를 가진 장비는 tat_index 가 None 입니다. 3건짜리 장비의
# 지수는 신호가 아니라 잡음이고, 잡음에 경고 배지를 다는 순간 화면 전체의
# 신뢰가 무너집니다.
# OFFICE-VERIFY — 실 플릿의 장비당 실행 수 분포를 보고 조정합니다.
TAT_INDEX_MIN_SAMPLE = 12


class EquipmentRow(TypedDict):
    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    # 표시용입니다. 신호 판정에는 쓰지 않습니다 — 가동률은 "얼마나 바빴는가"
    # 이지 "몇 번 돌았는가"가 아니라서, 긴 레시피를 도는 장비가 실행 수만
    # 보면 저사용으로 오진됩니다.
    exec_count: int
    total_meastime: int
    avg_meastime: float
    recipe_count: int
    top_recipe: str | None
    top_recipe_share: float
    # 실제 총 TAT / 이 장비의 레시피 구성이라면 걸렸어야 할 TAT.
    # 1.25 = 같은 일을 25 % 더 오래 함. 표본 미달이면 None.
    tat_index: float | None
    # 절대값: total_meastime / 조회 기간 총 초. **MES 가동률이 아닙니다** —
    # meastime 합이라 로딩·대기·PM이 빠져 있어 실제 가동률보다 낮게 읽힙니다.
    occupancy: float
    # 상대값: total_meastime / 플릿 중앙값
    usage_ratio: float


class FleetReference(TypedDict):
    tool_count: int
    total_executions: int
    total_meastime: int
    window_seconds: int
    median_total_meastime: float
    median_recipe_count: float
    min_sample: int
    # 배지 임계값을 사무실에서 조정하기 위한 분포 요약.
    # 키: "usage_ratio" | "tat_index" | "occupancy" | "recipe_count"
    # 값: {"p10","p25","p50","p75","p90"}. tat_index 는 None 인 장비를 제외하고
    # 계산하며, 대상 장비가 없으면 빈 dict.
    percentiles: dict[str, dict[str, float]]


class EquipmentsPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    fleet: FleetReference
    equipments: list[EquipmentRow]


class EquipmentTrendSeries(TypedDict):
    eqp_id: str
    points: list[DailyTrendPoint]


class EquipmentRecipeCell(TypedDict):
    eqp_id: str
    meas_counts: int
    total_meastime: int
    avg_meastime: float


class EquipmentRecipeRow(TypedDict):
    class_name: str
    recipe_name: str
    full_name: str
    # 선택된 장비 전체의 합. 표 정렬 기준입니다.
    total_meastime: int
    # 선택된 장비 수만큼, 요청 순서 그대로. 그 장비가 이 레시피를 돌지
    # 않았으면 0으로 채웁니다 — 열이 밀리면 비교표가 거짓말을 합니다.
    cells: list[EquipmentRecipeCell]


class EquipmentComparePayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    # 실제로 사용된 목록(상한 적용 후). 절단을 조용히 하지 않기 위한 에코입니다.
    eqp_ids: list[str]
    trends: list[EquipmentTrendSeries]
    recipes: list[EquipmentRecipeRow]
