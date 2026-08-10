"""Stable response contracts for cdsem device_statistics endpoints.

Moved out of the former data.py / statistics.py / recipe_params.py / rules.py
top-level modules unchanged (field-for-field) so both data.py's thin switch
and providers/mock.py can share one typed source of truth.
"""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = [
    "R3DeviceGrpRow",
    "DeviceDescRow",
    "MeasActivityRow",
    "RecipeInfoRow",
    "SummaryRow",
    "TrendBucket",
    "ParameterRow",
    "RecipeParamsRow",
    "NameOverride",
    "SelectorBase",
    "Selector",
    "RuleCell",
    "Thresholds",
    "RuleVersion",
]


class R3DeviceGrpRow(TypedDict):
    id: str
    fac_id: str
    plan_catg_type: str
    prod_catg_cd: str
    tech_cd: str
    den_type: str
    prod_grp_typ: str
    gen_typ: str
    lot_cd: str
    plan_grade_cd: str
    lake_load_tm: str
    ctn_desc: str


class DeviceDescRow(TypedDict):
    id: str
    fac_id: str
    lot_cd: str
    ctn_desc: str
    chg_tm: str
    tech_nm: str
    rnd_connector: str


class MeasActivityRow(TypedDict):
    """한 fab 의 최근 측정 활동 순위 한 건 — meas_count 내림차순으로 정렬되어
    내려갑니다. 원천은 ebeam_tas_lot_hist 의 최근 90일 lot_cd 별 문서 수입니다."""

    lot_cd: str
    meas_count: int


class RecipeInfoRow(TypedDict):
    lot_cd: str
    fac_id: str
    oper_id: str
    oper_desc: str
    oper_seq: int
    samp_seq: int
    eqp_id: str
    recipe_id: str
    skip_yn: str
    chg_tm: str
    ctn_desc: str
    # point 수 **구간**별 파라미터 개수 — para_buckets.py 가 경계를 정합니다.
    # 다섯 구간이 전체를 덮으므로 para_all 은 파라미터 총 개수이고, 다섯
    # 퍼센트의 합은 항상 100 입니다.
    para_all: int
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    para_over_16: int
    para_16_percent: float
    para_13_percent: float
    para_9_percent: float
    para_5_percent: float
    para_over_16_percent: float


class SummaryRow(TypedDict):
    lot_cd: str
    fac_id: str
    # point 수 **구간**별 파라미터 개수 — para_buckets.py 가 경계를 정합니다.
    # 다섯 구간이 전체를 덮으므로 para_all 은 파라미터 총 개수이고, 다섯
    # 퍼센트의 합은 항상 100 입니다.
    para_all: int
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    para_over_16: int
    para_16_percent: float
    para_13_percent: float
    para_9_percent: float
    para_5_percent: float
    para_over_16_percent: float
    ctn_desc: str
    total_recipe: int
    avail_recipe: int
    avail_recipe_percent: float


class _TrendBucketSummary(TypedDict):
    """The four `*_summary` keys returned in BOTH trend route modes."""

    all_summary: list[SummaryRow]
    only_normal_summary: list[SummaryRow]
    mother_normal_summary: list[SummaryRow]
    only_sample_summary: list[SummaryRow]


class TrendBucket(_TrendBucketSummary, total=False):
    """One weekly-trend date entry, as returned by get_weekly_trend_data().

    The four `*_summary` keys (inherited, required) are always present:
    `recipe-trend` calls with `include_recipes=False` and gets only those;
    `recipe-statistics` calls with the default `include_recipes=True` and gets
    all eight. The four `*_rcp_info` keys are recipe-detail-only, hence
    optional here — but an empty `{}` can no longer pass the gate. (Base-class
    + total False is used instead of NotRequired because this module enables
    `from __future__ import annotations`.)
    """

    all_rcp_info: list[RecipeInfoRow]
    only_normal_rcp_info: list[RecipeInfoRow]
    mother_normal_rcp_info: list[RecipeInfoRow]
    only_sample_rcp_info: list[RecipeInfoRow]


class ParameterRow(TypedDict):
    name: str
    point_count: int
    # 이 파라미터 자신이 mother 인가 (idp_image_info.Mother_Para — 진짜 bool,
    # office 확인 2026-07-28). son 은 mother 와 같은 image 에서 자기 cd_value 를
    # 얻으므로 측정 시간(TAT)을 움직이는 것은 mother 수입니다.
    #
    # 프론트엔드는 mother_normal 버킷에서 이 플래그로 파라미터를 걸러 계측 룰을
    # 검증하고 outlier 기준선을 잡습니다 (utils/lotHealth.scopeRecipesToBucket).
    mother: bool


class RecipeParamsRow(TypedDict):
    lot_cd: str
    recipe_id: str
    fac_id: str
    ctn_desc: str
    prod_catg_cd: str
    recipe_class: Literal["Main", "Sample"]
    family: Literal["Core", "Pool", "VG_RTC_Cubic"]
    phase: Literal["t-EV", "EV", "TV", "PV"] | None
    memory_class_auto: Literal["DRAM", "NAND", "unknown"]
    parameters: list[ParameterRow]


class NameOverride(TypedDict):
    patterns: list[str]
    match: Literal["contains", "affix"]
    cap: int | None  # None = exempt (unlimited)


class SelectorBase(TypedDict):
    # Always present. Split out so total=False below applies only to the
    # optional keying axes — fab/recipe_class stay structurally required
    # (ruleEngine.selectorMatches compares both and a missing fab never matches).
    fac_id: str
    recipe_class: Literal["Main", "Sample"]


class Selector(SelectorBase, total=False):
    family: Literal["Core", "Pool", "VG_RTC_Cubic"]
    phase_in: list[str]
    yield_check: Literal["before", "after"]
    memory_class: Literal["DRAM", "NAND"]


class RuleCell(TypedDict):
    id: str
    selector: Selector
    caps: dict[str, int]  # WAFER/LEVEL/EDGE/EDGE_EX/_other (missing type = n/a)
    name_overrides: list[NameOverride]


class Thresholds(TypedDict):
    yellow_at: float
    red_at: float


class RuleVersion(TypedDict):
    fac_id: str
    version: int
    edited_by: str
    edited_at: str
    cells: list[RuleCell]
    thresholds: Thresholds
