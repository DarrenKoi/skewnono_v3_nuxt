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
    para_all: int
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    para_16_percent: float
    para_13_percent: float
    para_9_percent: float
    para_5_percent: float


class SummaryRow(TypedDict):
    lot_cd: str
    fac_id: str
    para_all: int
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    para_16_percent: float
    para_13_percent: float
    para_9_percent: float
    para_5_percent: float
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
    fab: str
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
    fab: str
    version: int
    edited_by: str
    edited_at: str
    cells: list[RuleCell]
    thresholds: Thresholds
