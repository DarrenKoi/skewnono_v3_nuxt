"""Stable response contracts for cdsem device_statistics endpoints.

Moved out of the former data.py / statistics.py / recipe_params.py / rules.py
top-level modules unchanged (field-for-field) so both data.py's thin switch
and providers/mock.py can share one typed source of truth.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypedDict


__all__ = [
    "R3DeviceGrpRow",
    "DeviceDescRow",
    "MeasActivityRow",
    "ParaBlock",
    "RecipeInfoRow",
    "step_key",
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
    "FamilyToolType",
    "FamilyStepRow",
    "FamilyParamRow",
    "FamilyRecipeStatusRow",
    "FamilyActivityRow",
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


class ParaBlock(TypedDict):
    """point 수 **구간**별 파라미터 개수 — ``RecipeInfoRow`` 와 ``SummaryRow`` 가
    이 11개 필드를 그대로 공유합니다. para_buckets.py 가 경계를 정합니다.
    다섯 구간이 전체를 덮으므로 para_all 은 파라미터 총 개수이고, 다섯
    퍼센트의 합은 항상 100 입니다."""

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


class RecipeInfoRow(ParaBlock):
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


def step_key(row: Mapping[str, Any]) -> tuple[int, int]:
    """``RecipeInfoRow`` 한 건의 정체성 — **한 lot 안에서** 유일합니다.

    실물 문서 1건이 (prod_id, oper_seq, samp_seq) 스텝이므로
    (docs/datatables/hitachi/planstep_r3.txt), lot 을 고정하면 (oper_seq, samp_seq) 가 곧
    행의 정체성입니다. lot 을 가로지르는 목록에서는 부르는 쪽이 lot_cd 를 앞에
    붙입니다 — lot 은 정체성의 일부가 아니라 그것을 담는 범위입니다.

    ``recipe_id`` 는 여기에 **없습니다.** 여러 스텝이 같은 측정 recipe 를 쓰므로
    그것은 cdsem_idp_ver 로 건너가는 조인 키이지 행의 정체성이 아닙니다. 이 구분이
    무너지면 목록이 카드를 접어 스텝이 조용히 사라집니다 — 프론트엔드의 짝은
    ``frontend/app/utils/recipeStepSort.ts`` 의 ``recipeStepKey`` 입니다.

    ``RecipeInfoRow`` 와 mock 의 ``RecipeIdentity`` 둘 다 받도록 Mapping 을
    받습니다. 두 TypedDict 는 서로 하위 타입이 아니지만 이 두 key 는 공통입니다.
    """
    return row["oper_seq"], row["samp_seq"]


class SummaryRow(ParaBlock):
    lot_cd: str
    fac_id: str
    ctn_desc: str
    # **device 행 단위**의 recipe 수입니다 — 이 device 의 버킷에 든 distinct recipe.
    # device 끼리 recipe 를 공유하므로 행을 더한 합은 전체 distinct 수가 아닙니다
    # (R3 all: 합 17,974 / distinct 14,123, office 확인 2026-11-05). 화면 합계로 본
    # 18,794 는 하루 전 값이라 기준으로 쓰지 않습니다.
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
    # 이 파라미터가 속한 image definition 묶음 (idp_image_info.Region —
    # user-confirmed 2026-08-18). 같은 region = 한 SEQ 그룹이고, 화면에
    # "1/8, 2/8, 3/8" 으로 보이는 그 묶음입니다(분모는 Last_SEQ).
    #
    # 그룹 안에서 mother 인 하나가 image 의 주인이고 나머지는 son 입니다. 그룹
    # 전체가 **한 번의 측정**이므로 프론트엔드의 계측 룰 판정은 son 을 자기 이름의
    # 타입 cap 이 아니라 mother 의 cap 으로 잽니다 (ruleEngine.groupCaps). 이 값이
    # 없으면 WAFER(13) mother 의 son 인 CELL_SP·LWR 이 이름이 OTHER 라는 이유로
    # _other(9)에 걸려, recipe 를 고쳐서 없앨 수 없는 위반이 무더기로 잡힙니다.
    #
    # None 은 "이 문서에서 Region 을 읽지 못했다" 입니다 — 묶을 근거가 없으므로
    # 프론트엔드가 파라미터마다 자기 cap 으로 판정합니다(2026-08-18 이전 동작).
    region: int | None


class RecipeParamsRow(TypedDict):
    lot_cd: str
    recipe_id: str
    fac_id: str
    ctn_desc: str
    prod_catg_cd: str
    recipe_class: Literal["Main", "Sample"]
    # desc_format.parse_device_desc 의 축. family=None 은 device description 이
    # 표준 포맷(``[phase / memory] …``)이 아니라는 뜻이고 룰 미정(Gray)으로 판정됩니다.
    family: Literal["Core", "Pool", "Other"] | None
    phase: Literal["EV", "tEV", "DTV", "TTV", "TV", "PV"] | None
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
    family: Literal["Core", "Pool", "Other"]
    phase_in: list[str]
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


# ── Rule 없는 장비 계열(HV-SEM / VeritySEM / Provision) ─────────────────────
# 사무실 요청서 docs/office-migration/to-office-device-statistics-families-261102.md
# 의 표 A~D 를 그대로 옮긴 것입니다. 사무실 어댑터는 이 모양으로 정규화하고, mock
# (providers/family_tables.py)이 같은 모양을 냅니다. 화면·라우트는 아직 없습니다.
#
# 조인 키는 recipe_id 하나가 아니라 **(tool_type, recipe_id)** 입니다 — 계열이
# 다르면 같은 이름이 다른 recipe 일 수 있습니다.

FamilyToolType = Literal["hv-sem", "veritysem", "provision"]


class FamilyStepRow(TypedDict):
    """표 A — 한 계열·한 device 의 한 step.

    정체성은 R3 에서 (tool_type, prod_id, oper_seq, samp_seq, oper_desc) 입니다.
    (prod_id, oper_seq, samp_seq) 만으로는 겹치는 행이 있고, 겹친 행은 전부
    oper_desc 가 다른 별개 step 입니다 (hv 3 / verity 30 / provision 27,
    office 확인 2026-11-04). recipe_id 는 정체성이 아닙니다."""

    tool_type: FamilyToolType
    fac_id: str
    prod_id: str           # R3 원천 값("REXA_BASE" / "RH0V_CAP_BASE"). M fab 은 ""
    lot_cd: str            # family_rules.lot_cd_from_prod_id(prod_id) — 카탈로그 키
    oper_id: str
    oper_desc: str
    oper_seq: int | None   # M fab 은 None — Home 이 공정 접두사로 합성합니다
    samp_seq: int | None
    recipe_id: str
    eqp_id: str
    skip_yn: str           # R3 는 "Y" / "N" / "D" (빈 값 0건, office 확인 2026-11-04). M fab 은 ""
    chg_tm: str            # offset 없는 KST wall-clock. M fab 은 ""


class FamilyParamRow(TypedDict):
    """표 B — 한 recipe·한 fab 의 한 파라미터. param_seq 가 측정 순서입니다.

    정체성은 (tool_type, recipe_id, fac_id, fab_name, param_seq) 입니다. fac_id 만으로
    묶으면 같은 (full_name, fac_id, modified) 문서가 5,614 그룹(11,228 문서) 생기고,
    fab_name 까지 넣으면 8 그룹만 남습니다 (U4, office 확인 2026-11-05). 같은 (recipe, version)
    인데 파라미터가 다른 경우가 40건이고 그중 33건이 fab 마다 하나로 정해져, fab 축을
    둡니다 (S2 A, office 확인 2026-11-04). fab 으로도 정해지지 않는 나머지는 가장
    최근 문서를 씁니다 (S3 A) — "최근" 은 ``version`` 이 아니라 ``modified`` 기준입니다
    (T4, office 확인 2026-11-04). fab 은 idp 문서의 ``fac_id`` field 입니다 (T3). idp 의 eqp_id 는 배열이고 94.5% 가 IP 주소라 장비로
    대표를 고르지 않습니다. 빈 param_name 은 빼지 않습니다 (R3 A)."""

    tool_type: FamilyToolType
    recipe_id: str
    fac_id: str            # idp 문서의 fac_id (문자열 하나, U2)
    fab_name: str          # idp 문서의 fab_name (M16A 처럼 fac_id 보다 세분)
    param_seq: int
    param_name: str
    param_type: str        # "" = 원천에 종류가 없음 (Q4)
    point_count: int
    mother: bool | None    # None = 그 계열에 mother 개념이 없거나 읽지 못함
    region: int | None


class FamilyRecipeStatusRow(TypedDict):
    """표 C — 표 A 의 distinct (tool_type, recipe_id) 마다 정확히 한 행."""

    tool_type: FamilyToolType
    recipe_id: str
    status: Literal["ok", "empty", "not_found", "failed"]
    source_kind: Literal["idp", "measurement"]
    source_ref: str        # ok/empty 면 필수, 그 외 ""
    source_tm: str         # ok/empty 면 필수, 그 외 ""
    note: str              # failed 면 필수, 그 외 ""


class FamilyActivityRow(TypedDict):
    """표 D — 한 계열·한 fab·한 device 의 최근 측정 건수.

    fac_id 는 ebeam_tas_lot_hist 의 fab_id 라 표 A 의 det_fac_id 와 다를 수 있습니다 —
    R4 device R7QA / R7QC 는 표 A 에서 "R4", 여기서는 "R3" 입니다 (office 확인
    2026-11-04). 표 A 와는 (tool_type, lot_cd) 로 잇고 fac_id 를 조인 키에 넣지 않습니다."""

    tool_type: FamilyToolType
    fac_id: str
    lot_cd: str
    meas_count: int
    window_days: int
    as_of: str
