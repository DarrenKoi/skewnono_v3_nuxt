"""recipe-params data surface (D22). device(lot_cd) 1개 = recipe 100~200개,
recipe 1개 = 파라미터 다수, 파라미터마다 측정 point 수가 다릅니다. 프론트
ruleEngine.ts 의 RecipeInput 형태와 1:1 로 맞춥니다 (lot_cd, recipe_id,
fac_id, ctn_desc, prod_catg_cd, recipe_class, family, phase,
memory_class_auto, parameters[{name, point_count}]).

설계:  docs/issues/ground_rules/grilling-log.md (D22), rule-editor-structure.md §8-bis(B)
소비:  front-dev-home/app/utils/ruleEngine.ts (evaluateLot) · outlierDetect.ts (detectDeviceOutliers)

Phase 1 mock: lot 당 결정론적 seed 로 recipe·parameter 생성. 일부 recipe 에
의도적으로 (a) point-count outlier 와 (b) cap 위반 파라미터를 심어 두 소비처
(outlier 뷰 · R3 compliance)가 모두 실데이터로 검증되게 합니다.

사무실 파생 규칙 (user-confirmed 2026-07-31) — 이 mock 이 난수로 고르는 분류
컬럼들은 실물에서 **파생**됩니다. 규칙 전문은
docs/datatables/recipe_params.txt 의 "사무실 파생 규칙" 절이고, 요지는:

- recipe_class -> **recipe 이름이 "_S"/"SE" 로 끝나면 Sample**. 끝자리 고정
  이어야 합니다 — 이름 어디든 "SE" 를 찾으면 PHASE/BASE/SET 이 전부 Sample 이
  되고, recipe_class 가 프론트의 cap 선택 축(D2)이라 위반 판정까지 뒤집힙니다.
- family -> device ctn_desc 에 "pool"/"풀" 이 있으면 Pool, 나머지는 전부 Core.
  **VG_RTC_Cubic 은 실물에서 판별할 근거가 없어 발행하지 않습니다** — 이
  mock 이 세 값을 고루 만드는 것과 다릅니다.
- prod_catg_cd -> R3 카탈로그에만 있습니다. 이 mock 은 M fab lot 에도 값을
  지어내지만(_prod_catg_for 의 fallback), 실물은 빈 값이고 따라서
  memory_class_auto 가 unknown(수동 분류) 으로 떨어집니다.

Internal module: callers outside this feature must import the public
surface from `device_statistics.data` (the provider switch), not this file
directly.
"""

import random
from typing import Literal

from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    ParameterRow,
    RecipeParamsRow,
)
from back_dev_home.ebeam.cdsem.device_statistics.providers.recipe_population import (
    MOTHER_SHARE,
    RecipeIdentity,
    build_population,
    is_exempt_job,
    is_sample_recipe,
    mother_para_all,
)


# mother 표시를 point_count rng 와 갈라놓는 salt. 같은 rng 를 더 굴리면 뒤따르는
# recipe 의 파라미터 값이 전부 달라집니다 (recipe_population._MOTHER_SALT 와 같은
# 이유입니다).
_MOTHER_MARK_SALT = 70009


# recipe 수·이름은 이제 recipe_population 이 정합니다 — 여기서 따로 세면 두 표면의
# recipe_id 가 갈라져 조인이 깨집니다 (예전이 그랬습니다). 도메인 100~200 (D22) 은
# 그 모듈의 POOL_RANGE 와 주차 배율이 함께 만족합니다.

FAMILIES: tuple[str, ...] = ("Core", "Pool", "VG_RTC_Cubic")
PHASES: tuple[str, ...] = ("t-EV", "EV", "TV", "PV")

# Parameter-name templates per type, chosen to exercise ruleEngine.deriveType
# (longest-prefix EDGE_EX > EDGE > WAFER > LEVEL; everything else = OTHER).
WAFER_NAMES = ("WAFER_CD", "WAFER_2", "WAFER_OVL")
LEVEL_NAMES = ("LEVEL_1", "LEVEL_2", "LEVEL_3", "LEVEL_4")
EDGE_NAMES = ("EDGE_L", "EDGE_R", "EDGE_T", "EDGE_B")
EDGE_EX_NAMES = ("EDGE_EX_L", "EDGE_EX_R")
# OTHER bucket — the bag that balloons (D10). Includes a WAFER-companion
# (OVL_WF) so the Main DSPT/WF/WAFER name-override path is exercised.
OTHER_NAMES = ("OVL_X", "OVL_Y", "DSPT_1", "CD_BAR", "PITCH_A", "OVL_WF", "SPACE_1")

# Typical point counts per type (cap-respecting baseline so most recipes pass).
TYPICAL_POINTS = {
    "WAFER": (9, 13),
    "LEVEL": (1, 4),
    "EDGE": (6, 14),
    "EDGE_EX": (0, 0),
    "OTHER": (1, 8),
}

# 특수 측정 job(_WCDU/_FCDU/_FULL/_HALF)의 측정 배율. 웨이퍼 전면을 훑는 job 이라
# 파라미터당 point 수가 정상 recipe 와 자릿수부터 다릅니다.
#
# 이 배율이 없으면 mock 의 CDU job 이 정상 recipe 와 똑같이 측정하는 것처럼
# 보여, **실물에 대해 거짓을 가르칩니다**. 동시에 이 job 들을 중앙값 기준선에서
# 빼는 outlierDetect 의 이유(큰 값이 기준선을 끌어올려 진짜 과다 측정을 가림)가
# 집에서는 한 번도 재현되지 않습니다 — 배율이 1 이면 빼나 마나 같은 값이라
# 회귀가 조용히 통과합니다.
#
# 이미 뽑은 값에 곱하기만 합니다. 여기서 rng 를 더 굴리면 뒤따르는 recipe 의
# 파라미터가 전부 다른 값으로 다시 태어납니다 (_mark_mothers 의 같은 주의).
#
# OFFICE-VERIFY: 실물 배율은 확인된 바 없습니다 — "자릿수가 다르다" 는 성질만
# 재현하고 절대값은 흉내 내지 않습니다.
EXEMPT_JOB_POINT_SCALE = 8


def _memory_class_auto(prod_catg_cd: str) -> str:
    c = prod_catg_cd.upper()
    if c == "DRAM":
        return "DRAM"
    if c in ("NAND", "FLASH"):
        return "NAND"
    return "unknown"  # Tech / Advanced / absent → 수동 (D7)


def _build_parameters(
    rng: random.Random, bloated: bool, over_measured: bool, exempt_job: bool = False
) -> list[ParameterRow]:
    params: list[ParameterRow] = []

    def add(name: str, lo: int, hi: int) -> None:
        # mother 는 _mark_mothers 가 나중에 켭니다 — 여기서 굴리면 아래 난수 순서가
        # 밀려 기존 point_count 가 전부 다른 값이 됩니다.
        params.append({"name": name, "point_count": rng.randint(lo, hi), "mother": False})

    add(rng.choice(WAFER_NAMES), *TYPICAL_POINTS["WAFER"])
    for name in rng.sample(LEVEL_NAMES, rng.randint(1, 4)):
        add(name, *TYPICAL_POINTS["LEVEL"])
    for name in rng.sample(EDGE_NAMES, rng.randint(1, 4)):
        add(name, *TYPICAL_POINTS["EDGE"])

    # OTHER bag: normally a few; a "bloated" recipe carries many (D10 signal).
    other_pool = list(OTHER_NAMES)
    other_count = rng.randint(5, len(other_pool)) if bloated else rng.randint(1, 3)
    for i, name in enumerate(other_pool[:other_count]):
        suffix = f"_{i}" if i >= len(other_pool) else ""
        add(f"{name}{suffix}", *TYPICAL_POINTS["OTHER"])

    # over_measured recipe: push ONE EDGE param far above its peers so both the
    # within-device outlier detector and the R3 EDGE cap flag it.
    if over_measured and params:
        params[-1] = {"name": "EDGE_R", "point_count": rng.randint(40, 60), "mother": False}

    # 특수 측정 job 은 마지막에 통째로 배율만 먹입니다 — 이름·개수·순서는 그대로
    # 두어야 위 난수 순서가 한 칸도 밀리지 않습니다.
    if exempt_job:
        for param in params:
            param["point_count"] *= EXEMPT_JOB_POINT_SCALE

    return params


def _mark_mothers(
    params: list[ParameterRow], has_mother: bool, mother_rng: random.Random
) -> None:
    """``parameters`` 중 mother 인 것을 켭니다 (제자리 수정).

    ``has_mother`` 는 :func:`recipe_population.build_population` 이 만든
    identity 가 정합니다 — 이 표면이 따로 굴리면 안 됩니다. recipe-statistics 의
    mother_normal 버킷 멤버십이 바로 그 identity 로 정해지므로, 두 표면이
    어긋나면 **버킷에는 있는데 mother 파라가 하나도 없는 recipe** 가 생기고
    프론트엔드의 health 가 조용히 0/0(판정 없음)으로 떨어집니다.

    ``mother_rng`` 를 따로 받는 이유도 같습니다 — 위 point_count 를 뽑는 rng 를
    여기서 더 굴리면 뒤따르는 recipe 의 파라미터 값이 전부 달라집니다.
    """
    if not has_mother or not params:
        return
    # son 이 mother 의 image 를 함께 쓰므로 mother 는 소수입니다. 최소 1개는
    # 반드시 켜야 has_mother 가 참이라는 identity 의 말과 일치합니다.
    count = max(1, round(len(params) * mother_rng.uniform(*MOTHER_SHARE)))
    for index in mother_rng.sample(range(len(params)), min(count, len(params))):
        params[index]["mother"] = True


def _build_recipe(
    rng: random.Random,
    mother_rng: random.Random,
    identity: RecipeIdentity,
    lot_cd: str,
    fac_id: str,
    prod_catg_cd: str,
    idx: int
) -> RecipeParamsRow:
    # recipe_class 는 굴리지 않고 **recipe 이름에서 파생**합니다 — 실물도 그렇고
    # (office_example.py: "only_sample 버킷과 같은 규칙"), 굴리면 같은 recipe 가
    # only_sample 버킷에는 있는데 recipe_class 는 Main 인 모순이 생깁니다.
    recipe_class: Literal["Main", "Sample"] = (
        "Sample" if is_sample_recipe(identity["recipe_id"]) else "Main"
    )
    family = rng.choice(FAMILIES)
    phase = rng.choice(PHASES)
    bloated = rng.random() < 0.08       # ~8% of recipes over-parameterized
    over_measured = rng.random() < 0.05  # ~5% with a point-count outlier
    parameters = _build_parameters(
        rng, bloated, over_measured, is_exempt_job(identity["recipe_id"])
    )
    # mother 보유 여부는 identity 가 정합니다 — recipe-statistics 의 mother_normal
    # 버킷 멤버십과 같은 원천이어야 두 표면이 갈라지지 않습니다.
    _mark_mothers(parameters, mother_para_all(identity) > 0, mother_rng)

    return {
        "lot_cd": lot_cd,
        "recipe_id": identity["recipe_id"],
        "fac_id": fac_id,
        "ctn_desc": f"{phase} {prod_catg_cd} {family} recipe {idx} lot {lot_cd}",
        "prod_catg_cd": prod_catg_cd,
        "recipe_class": recipe_class,
        "family": family,
        "phase": phase,
        "memory_class_auto": _memory_class_auto(prod_catg_cd),
        "parameters": parameters,
    }


def _prod_catg_for(lot_cd: str, fac_id: str) -> str:
    """Reuse the device's own prod_catg_cd when it is an R3 lot; M-fab device-desc
    rows carry no prod_catg_cd, so fall back to a deterministic pick."""
    from .mock import get_r3_device_grp  # deferred import — avoid circular load
    for row in get_r3_device_grp():
        if row["lot_cd"] == lot_cd:
            return row["prod_catg_cd"]
    rng = random.Random(_recipe_seed(lot_cd, 9991))
    return rng.choice(["DRAM", "NAND", "FLASH", "Tech", "Advanced"])


def _recipe_seed(lot_cd: str, salt: int) -> int:
    from .statistics import _seed_for  # deferred import
    return _seed_for(lot_cd, salt)


def get_recipe_params(lot_cds: list[str] | None = None) -> list[RecipeParamsRow]:
    """Flat list of recipe rows (RecipeInput shape) for the requested lots.

    Empty / None lot_cds → every known lot (can be large; callers should pass a
    selection). Deterministic per lot_cd via _seed_for."""
    from .statistics import (  # deferred import
        DEFAULT_TREND_POINTS, _lot_index, _resolve_lots, _seed_for,
    )
    index = _lot_index()
    selected = _resolve_lots(lot_cds)

    rows: list[RecipeParamsRow] = []
    for lot_cd in selected:
        fac_id = index[lot_cd]
        prod_catg_cd = _prod_catg_for(lot_cd, fac_id)
        # recipe-statistics 가 보여주는 것은 트렌드의 **마지막 주차**이므로
        # (routes.py recipe_statistics), 같은 주차의 모집단을 부릅니다. 이 한 줄이
        # 두 표면을 recipe_id 로 조인 가능하게 만듭니다.
        population = build_population(
            lot_cd, DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS
        )
        rng = random.Random(_seed_for(lot_cd, 4242))
        mother_rng = random.Random(_seed_for(lot_cd, 4242) ^ _MOTHER_MARK_SALT)
        for idx, identity in enumerate(population):
            rows.append(
                _build_recipe(rng, mother_rng, identity, lot_cd, fac_id, prod_catg_cd, idx)
            )
    return rows


if __name__ == "__main__":
    # 미리보기:  python -m back_dev_home.ebeam.cdsem.device_statistics.providers.recipe_params
    import pprint
    rows = get_recipe_params(["R000"])
    print(f"R000 recipes: {len(rows)}  (expect 100~200)")
    print("\n--- first recipe ---")
    pprint.pprint(rows[0])
    edge_outliers = [
        (r["recipe_id"], p["name"], p["point_count"])
        for r in rows for p in r["parameters"] if p["point_count"] >= 40
    ]
    print(f"\npoint-count outliers (>=40): {len(edge_outliers)}")
    for o in edge_outliers[:5]:
        print(" ", o)
    classes = {}
    for r in rows:
        classes[r["recipe_class"]] = classes.get(r["recipe_class"], 0) + 1
    print(f"\nrecipe_class split: {classes}")
