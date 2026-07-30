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


# Recipes per device. Domain: 100~200 (D22).
RECIPE_COUNT_RANGE = (100, 200)

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


def _memory_class_auto(prod_catg_cd: str) -> str:
    c = prod_catg_cd.upper()
    if c == "DRAM":
        return "DRAM"
    if c in ("NAND", "FLASH"):
        return "NAND"
    return "unknown"  # Tech / Advanced / absent → 수동 (D7)


def _build_parameters(rng: random.Random, bloated: bool, over_measured: bool) -> list[ParameterRow]:
    params: list[ParameterRow] = []

    def add(name: str, lo: int, hi: int) -> None:
        params.append({"name": name, "point_count": rng.randint(lo, hi)})

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
        params[-1] = {"name": "EDGE_R", "point_count": rng.randint(40, 60)}

    return params


def _build_recipe(rng: random.Random, lot_cd: str, fac_id: str, prod_catg_cd: str, idx: int) -> RecipeParamsRow:
    recipe_class: Literal["Main", "Sample"] = "Sample" if rng.random() < 0.2 else "Main"
    family = rng.choice(FAMILIES)
    phase = rng.choice(PHASES)
    bloated = rng.random() < 0.08       # ~8% of recipes over-parameterized
    over_measured = rng.random() < 0.05  # ~5% with a point-count outlier
    parameters = _build_parameters(rng, bloated, over_measured)

    return {
        "lot_cd": lot_cd,
        "recipe_id": f"RCP-{lot_cd}-{idx:03d}",
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
    from .statistics import _lot_index, _resolve_lots  # deferred import
    index = _lot_index()
    selected = _resolve_lots(lot_cds)

    rows: list[RecipeParamsRow] = []
    for lot_cd in selected:
        fac_id = index[lot_cd]
        prod_catg_cd = _prod_catg_for(lot_cd, fac_id)
        rng = random.Random(_recipe_seed(lot_cd, 4242))
        count = rng.randint(*RECIPE_COUNT_RANGE)
        for idx in range(count):
            rows.append(_build_recipe(rng, lot_cd, fac_id, prod_catg_cd, idx))
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
