"""Recipe statistics mock data for device_statistics.

The lot_cd column on r3_device_grp / device_desc (see providers/mock.py) is
the join key. When the frontend selects one or more lot_cds, this module
returns matching recipe-info and summary rows for each weekly date in
a trend window — keyed by ISO date so the frontend can plot the
trend directly without re-shaping.

사무실 원천 (user-confirmed 2026-07-31) — 이 모듈이 대역하는 실제 경로는 **fab
계열에 따라 둘로 갈리고**, 파라미터 개수만 공통입니다. 자세한 내용은
docs/datatables/planstep_r3.txt, ebeam_tas_lot_hist.txt, idp_ver.txt 입니다.

  R3 / 연구개발:
    r3_device_grp (Redis)          -> lot_cd
      + "_BASE"                    -> prod_id
    sknn-planstep-r3 (OpenSearch)  -> prod_id/oper_seq/samp_seq 정렬,
                                      skip_yn != "Y" -> oper_desc, recipe_id

  M 계열 양산:
    ebeam_tas_lot_hist (OpenSearch) -> 최근 3개월(약 90일) × fab_id
                                      -> lot_cd 별 unique oper_det_desc,
                                         recipe_id  (lot_cd 그대로, 접미사 없음)

  공통 (파라미터 개수):
    cdsem_idp_ver (OpenSearch)     -> full_name == recipe_id, 최신 version
                                      -> parameters -> para_* 집계

이 mock 이 실물과 의도적으로 다른 점:

- 이 모듈은 R3 lot 과 M fab lot 을 **같은 방식으로** 만들지만, 실물은 위처럼
  소스가 다릅니다. 특히 M fab 은 **공정 순서 field 가 없습니다** — 여기서 채우는
  oper_seq / samp_seq 는 M fab 실물에 대응 값이 없으므로, 어댑터가 event_tm
  시간순으로 합성하거나 계약을 넓혀야 합니다 (OFFICE-VERIFY).
- R3 실물의 한 문서는 (prod_id, oper_seq, samp_seq) 스텝 1건이고 lot_cd 컬럼이
  아예 없습니다. 여기서는 계약(RecipeInfoRow)대로 lot_cd 를 직접 들고 있습니다.
- 스텝 이름 field 이름이 다릅니다 — R3 는 oper_desc, M fab 은 oper_det_desc.
- para_16/13/9/5 는 어느 스텝 소스에도 없는 값입니다. 실제로는 recipe_id 를
  cdsem_idp_ver.full_name 과 조인해 최신 version 의 parameters blob 에서
  집계해야 하며, 그 blob 의 내부 구조는 아직 확인되지 않았습니다
  (OFFICE-VERIFY). 여기서는 그냥 난수로 만듭니다.
- R3 실물 필드명은 fac_id 가 아니라 det_fac_id 이고(M fab 은 fab_id/fab_name),
  계약에 대응이 없는 main_oper_id / main_oper_yn / bak_eqp_yn /
  bak_eqp_id_lval / eqp_grp_id / reticle_id 가 더 있습니다.
- skip_yn 은 R3 planstep 의 field 입니다. M fab 경로에는 없고, "측정 중" 판정을
  최근 3개월 창에 나타나는지로 대신합니다.

skip_yn 은 실물과 값 도메인·극성을 맞췄습니다 (user-confirmed 2026-07-31) —
**"Y"/"N"/빈 값 세 가지**이고, 이름 그대로 **"Y" 가 skip(측정하지 않음)**
입니다. 따라서 판정은 반드시 ``!= "Y"``(:func:`_is_measuring`)이며 ``== "N"``
이 아닙니다 — 긍정 비교로 쓰면 빈 값 스텝이 통째로 빠지고, 그 손실은 예외가
아니라 "숫자가 좀 작다" 로만 나타납니다. 이 mock 이 일부러 빈 값을 섞는 이유가
그것입니다.

이 값은 두 번 정정되었습니다: "Yes"/"No" -> "Y"/"N"(2026-07-30), 그리고
"Y = 측정 중" 이라는 잘못된 극성 -> **"Y" = skip**(2026-07-31). 되돌리지
마십시오.

네 버킷의 실제 의미 (user-confirmed 2026-07-31)
──────────────────────────────────────────────
이 mock 은 버킷마다 recipe 수를 난수 범위(RECIPE_COUNT_RANGES)로 만들지만,
실물에서 버킷은 **스텝 이름과 recipe 이름으로 갈라지는 분류**입니다. 집에서
개발할 때 "버킷 = 크기가 다른 네 덩어리" 로만 이해하면 어댑터를 읽을 때 어긋
납니다.

  all            모든 Step (Full job + Sample job)
  only_normal    스텝명에 CD 가 포함된 Step
  mother_normal  skip 되지 않은(skip_yn != "Y") Step 중 스텝명 끝이 순수한 CD
                 ("CD(E)", "CD(F)" 는 제외)
  only_sample    **recipe 이름**이 "_S" 또는 "SE" 로 끝나는 Step

주간 트렌드의 실물 경로 (설계 확정 2026-07-31)
─────────────────────────────────────────────
이 mock 은 날짜별 값을 seed 로 만들어 내지만, 실물 스텝 index 에는 **과거가
없습니다**(현재 계획만 있는 index). 따라서 사무실에서는 주차별 스냅샷을 MinIO
에 적재해 두고 읽습니다 — 과거 주차는 스냅샷, 이번 주차만 라이브입니다.
자세한 내용은 docs/datatables/device_statistics_weekly_trend.txt.

Internal module: callers outside this feature must import the public surface
from `device_statistics.data` (the provider switch); `recipe_tat`'s mock
provider is the one sanctioned exception and imports `_lot_index` straight
from `device_statistics.providers.mock` (mock-to-mock, never through the
switch — see that module's own docstring). Imports of `.mock` are deferred
to function bodies — eager module-top imports would form a circular load
with `mock.py` (which itself re-exports the symbols below), so the import
order is fragile when this module is entered first (e.g. `python -m ...
providers.statistics` running the __main__ block, or any future test that
imports this module directly).
"""

import random
from datetime import timedelta
from functools import lru_cache

from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    RecipeInfoRow,
    SummaryRow,
)


RCP_BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")
DEFAULT_TREND_POINTS = 8
DEFAULT_INTERVAL_DAYS = 7

# skip_yn 값 중 "이 스텝은 측정하지 않는다"를 뜻하는 쪽 (user-confirmed
# 2026-07-31, docs/datatables/planstep_r3.txt). 실물 값 도메인은 "Y"/"N"/빈 값
# 세 가지이므로 판정은 아래 _is_measuring 의 `!= "Y"` 하나로만 합니다.
SKIPPED = "Y"

# 실물에 섞여 있는 빈 값의 비율. `== "N"` 으로 판정하는 코드가 있으면 이 만큼이
# 조용히 사라지므로, mock 이 그 경로를 실제로 밟게 하려고 일부러 만듭니다.
BLANK_SKIP_YN_RATIO = 0.15
SKIPPED_RATIO = 0.15


def _is_measuring(skip_yn: str) -> bool:
    """이 스텝이 skip 되지 않았는가 — ``skip_yn != "Y"``.

    office 어댑터(providers/office_example.py)의 동명 함수와 같은 규칙입니다.
    """
    return (skip_yn or "").strip().upper() != SKIPPED

OPER_DESCS = (
    "Initial Material Prep", "Primary Etching", "Deposition Layer 1",
    "Photolithography", "Ion Implantation", "Chemical Cleaning",
    "Annealing Process", "Final Inspection", "Wafer Testing"
)

OPER_PREFIXES = (
    "ETCH", "DEPO", "LITH", "IMPL", "CLEAN", "ANNL", "INSP", "MEAS",
    "CMP", "STRIP", "OXID", "DIFF"
)

EQP_FAMILIES = ("CDSEM", "CDS2", "MET", "VS", "INSP")

# Per-bucket recipe-count range. "all" is widest; "only_sample" narrowest —
# the summary chart aggregates from these counts, so this also governs the
# relative visual hierarchy of the bucket bars on the comparison page.
RECIPE_COUNT_RANGES = {
    "all": (130, 200),
    "only_normal": (80, 150),
    "mother_normal": (50, 110),
    "only_sample": (25, 70),
}

# Per-recipe parameter ranges. Sums across ~150 recipes land in the legacy
# summary range of ~5k–10k for `all`, which keeps existing chart axes
# meaningful.
PARA_RANGES = {
    "para_16": (10, 50),
    "para_13": (6, 32),
    "para_9": (3, 16),
    "para_5": (1, 9),
}


def _percent(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)


def _skip_yn(rng: random.Random) -> str:
    """실물의 세 값("Y" / "N" / 빈 값)을 그 비율대로 만듭니다."""
    roll = rng.random()
    if roll < SKIPPED_RATIO:
        return SKIPPED
    if roll < SKIPPED_RATIO + BLANK_SKIP_YN_RATIO:
        return ""
    return "N"


def _seed_for(lot_cd: str, point_index: int) -> int:
    digest = 0
    for ch in lot_cd:
        digest = (digest * 131 + ord(ch)) & 0xFFFFFFFF
    return (digest * 1009 + point_index * 7919) & 0xFFFFFFFF


def _trend_dates(points: int, interval_days: int) -> tuple[str, ...]:
    from .mock import BASE_TIME  # deferred import — avoid circular load
    base_monday = (BASE_TIME - timedelta(days=BASE_TIME.weekday())).date()
    dates = [
        (base_monday - timedelta(days=interval_days * offset)).isoformat()
        for offset in range(points - 1, -1, -1)
    ]
    return tuple(dates)


@lru_cache(maxsize=1)
def _lot_index() -> dict[str, str]:
    """lot_cd -> fac_id, sourced from both R3 and per-fab generators."""
    from .mock import get_device_desc, get_r3_device_grp  # deferred import
    index: dict[str, str] = {}

    for row in get_r3_device_grp():
        index[row["lot_cd"]] = row["fac_id"]

    for row in get_device_desc():
        index[row["lot_cd"]] = row["fac_id"]

    return index


@lru_cache(maxsize=1)
def _lot_ctn_desc() -> dict[str, str]:
    """lot_cd -> device-level ctn_desc, joined from both lot sources.

    The frontend uses this on chart tooltips and the slideover summary
    card so analysts can identify devices without memorizing lot codes.
    Later sources win on conflict, matching `_lot_index`.
    """
    from .mock import get_device_desc, get_r3_device_grp  # deferred import
    descs: dict[str, str] = {}

    for row in get_r3_device_grp():
        descs[row["lot_cd"]] = row["ctn_desc"]

    for row in get_device_desc():
        descs[row["lot_cd"]] = row["ctn_desc"]

    return descs


def _build_recipe_row(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    bucket: str,
    idx: int,
    date_key: str
) -> RecipeInfoRow:
    para_16 = rng.randint(*PARA_RANGES["para_16"])
    para_13 = rng.randint(*PARA_RANGES["para_13"])
    para_9 = rng.randint(*PARA_RANGES["para_9"])
    para_5 = rng.randint(*PARA_RANGES["para_5"])
    para_all = para_16 + para_13 + para_9 + para_5

    oper_prefix = rng.choice(OPER_PREFIXES)
    oper_id = f"{oper_prefix}-{rng.randint(100, 999)}"
    eqp_id = f"{rng.choice(EQP_FAMILIES)}-{rng.randint(1, 24):02d}"
    recipe_id = f"RCP-{lot_cd}-{bucket[:3].upper()}-{idx:03d}"

    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "oper_id": oper_id,
        "oper_desc": rng.choice(OPER_DESCS),
        "oper_seq": idx + 1,
        "samp_seq": rng.randint(1, 5),
        "eqp_id": eqp_id,
        "recipe_id": recipe_id,
        # "Y" == skip(측정하지 않음) (user-confirmed 2026-07-31). 값 도메인은
        # 실물과 같은 "Y"/"N"/빈 값 세 가지이며, skip 비율 15% 를 유지해 측정
        # 비율은 예전과 같은 약 85% 입니다 — 극성 표기만 바로잡은 것이라 화면
        # 숫자는 뒤집히지 않습니다.
        "skip_yn": _skip_yn(rng),
        # 실물 chg_tm 은 offset 없는 KST wall-clock datetime("2025-07-17T12:26:01")
        # 입니다. 예전에는 시각(HH:MM:SS)만 만들어 날짜가 없었습니다.
        "chg_tm": (
            f"{date_key}T{rng.randint(0, 23):02d}:"
            f"{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
        ),
        "ctn_desc": f"{oper_prefix} {rng.choice(OPER_DESCS)} step",
        "para_all": para_all,
        "para_16": para_16,
        "para_13": para_13,
        "para_9": para_9,
        "para_5": para_5,
        "para_16_percent": _percent(para_16, para_all),
        "para_13_percent": _percent(para_13, para_all),
        "para_9_percent": _percent(para_9, para_all),
        "para_5_percent": _percent(para_5, para_all),
    }


def _build_recipes_for_bucket(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    bucket: str,
    date_key: str
) -> list[RecipeInfoRow]:
    count_min, count_max = RECIPE_COUNT_RANGES[bucket]
    count = rng.randint(count_min, count_max)
    return [
        _build_recipe_row(rng, lot_cd, fac_id, bucket, i, date_key)
        for i in range(count)
    ]


def _summarize(
    lot_cd: str,
    fac_id: str,
    ctn_desc: str,
    recipes: list[RecipeInfoRow]
) -> SummaryRow:
    para_16 = sum(r["para_16"] for r in recipes)
    para_13 = sum(r["para_13"] for r in recipes)
    para_9 = sum(r["para_9"] for r in recipes)
    para_5 = sum(r["para_5"] for r in recipes)
    para_all = para_16 + para_13 + para_9 + para_5

    total_recipe = len(recipes)
    # 측정 중인 recipe 수. "Y" 가 skip 이므로 그 외 전부(빈 값 포함)를 셉니다 —
    # `== "N"` 으로 세면 빈 값 스텝이 빠져 운용 레시피수가 조용히 작아집니다.
    avail_recipe = sum(1 for r in recipes if _is_measuring(r["skip_yn"]))

    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "para_all": para_all,
        "para_16": para_16,
        "para_13": para_13,
        "para_9": para_9,
        "para_5": para_5,
        "para_16_percent": _percent(para_16, para_all),
        "para_13_percent": _percent(para_13, para_all),
        "para_9_percent": _percent(para_9, para_all),
        "para_5_percent": _percent(para_5, para_all),
        "ctn_desc": ctn_desc,
        "total_recipe": total_recipe,
        "avail_recipe": avail_recipe,
        "avail_recipe_percent": _percent(avail_recipe, total_recipe),
    }


def _resolve_lots(lot_cds: list[str] | None) -> list[str]:
    index = _lot_index()

    if not lot_cds:
        return list(index.keys())

    requested = {lot.strip() for lot in lot_cds if lot.strip()}

    if not requested:
        return list(index.keys())

    return [lot for lot in index.keys() if lot in requested]


def get_weekly_trend_data(
    lot_cds: list[str] | None = None,
    points: int = DEFAULT_TREND_POINTS,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    include_recipes: bool = True
) -> dict[str, dict[str, list]]:
    """Return trend data keyed by ISO date.

    Each date entry maps to a flat dict with eight keys — the four
    recipe buckets paired with their summaries:

      {
        "2026-02-09": {
          "all_rcp_info":           [RecipeInfoRow, ...],
          "all_summary":            [SummaryRow, ...],
          "only_normal_rcp_info":   [...],
          "only_normal_summary":    [...],
          "mother_normal_rcp_info": [...],
          "mother_normal_summary":  [...],
          "only_sample_rcp_info":   [...],
          "only_sample_summary":    [...],
        },
        ...
      }

    Dates are spaced `interval_days` apart (default 7 = weekly), with
    `points` total samples ending at the most recent Monday before
    BASE_TIME. Per-(lot, date) seeding keeps the output deterministic
    across calls.
    """
    index = _lot_index()
    descs = _lot_ctn_desc()
    selected = _resolve_lots(lot_cds)
    dates = _trend_dates(points, interval_days)
    trend: dict[str, dict[str, list]] = {}

    for point_index, date_key in enumerate(dates):
        bucketed: dict[str, list] = {}
        for bucket in RCP_BUCKETS:
            if include_recipes:
                bucketed[f"{bucket}_rcp_info"] = []
            bucketed[f"{bucket}_summary"] = []

        for lot_cd in selected:
            fac_id = index[lot_cd]
            ctn_desc = descs.get(lot_cd, "")
            rng = random.Random(_seed_for(lot_cd, point_index))

            for bucket in RCP_BUCKETS:
                recipes = _build_recipes_for_bucket(rng, lot_cd, fac_id, bucket, date_key)
                if include_recipes:
                    bucketed[f"{bucket}_rcp_info"].extend(recipes)
                bucketed[f"{bucket}_summary"].append(
                    _summarize(lot_cd, fac_id, ctn_desc, recipes)
                )

        trend[date_key] = bucketed

    return trend


def get_lot_index() -> list[dict]:
    """Flat lot_cd -> fac_id listing, useful as a frontend lot picker."""
    return [{"lot_cd": lot_cd, "fac_id": fac_id} for lot_cd, fac_id in _lot_index().items()]


if __name__ == "__main__":
    # Standalone mock-data preview. Run from the project root with:
    #   python -m back_dev_home.ebeam.cdsem.device_statistics.providers.statistics
    import pprint

    print("=" * 72)
    print("LOT INDEX")
    print("=" * 72)
    index = _lot_index()
    fac_breakdown: dict[str, int] = {}
    for fac_id in index.values():
        fac_breakdown[fac_id] = fac_breakdown.get(fac_id, 0) + 1
    print(f"Total lots: {len(index)}")
    print(f"By fac_id:  {fac_breakdown}")

    print("\n" + "=" * 72)
    print("SHAPE SPOT-CHECK: single lot 'R007', latest date")
    print("=" * 72)
    trend = get_weekly_trend_data(["R007"])
    date_keys = list(trend.keys())
    print(f"Date keys (oldest -> newest): {date_keys}")

    latest = date_keys[-1]
    print(f"\nKeys at trend[{latest!r}]:")
    pprint.pprint(list(trend[latest].keys()))

    print(f"\n--- trend[{latest!r}]['all_rcp_info'][0] ---")
    pprint.pprint(trend[latest]["all_rcp_info"][0])

    print(f"\n--- trend[{latest!r}]['all_summary'][0] ---")
    pprint.pprint(trend[latest]["all_summary"][0])

    print(f"\n--- trend[{latest!r}]['only_sample_summary'][0] ---")
    pprint.pprint(trend[latest]["only_sample_summary"][0])

    print("\n" + "=" * 72)
    print("TREND VIEW: para_all per bucket across dates (single lot 'R007')")
    print("=" * 72)
    print(f"{'date':<12} | {'all':>6} | {'only_normal':>11} | "
          f"{'mother_normal':>13} | {'only_sample':>11}")
    print("-" * 72)
    for date_key, payload in trend.items():
        all_v = payload["all_summary"][0]["para_all"]
        norm_v = payload["only_normal_summary"][0]["para_all"]
        moth_v = payload["mother_normal_summary"][0]["para_all"]
        samp_v = payload["only_sample_summary"][0]["para_all"]
        print(f"{date_key:<12} | {all_v:>6} | {norm_v:>11} | "
              f"{moth_v:>13} | {samp_v:>11}")

    print("\n" + "=" * 72)
    print("MULTI-LOT FILTER: mix of R3 and M-fab lots")
    print("=" * 72)
    multi = get_weekly_trend_data(["R000", "R001", "100", "1001", "60B2"])
    latest_multi = list(multi.keys())[-1]
    print(f"Latest date: {latest_multi}")
    print("\nall_rcp_info rows (one per selected lot):")
    for row in multi[latest_multi]["all_rcp_info"]:
        print(f"  lot_cd={row['lot_cd']:<6} fac_id={row['fac_id']:<4} "
              f"recipe={row['recipe_id']:<14} para_all={row['para_all']}")

    print("\n" + "=" * 72)
    print("SCALE CHECK: full dataset (all lots, all dates)")
    print("=" * 72)
    full = get_weekly_trend_data()
    total_rows = 0
    for payload in full.values():
        for rows in payload.values():
            total_rows += len(rows)
    print(f"Lots:      {len(index)}")
    print(f"Dates:     {len(full)}")
    print("Buckets per date: 8 (4 rcp_info + 4 summary)")
    print(f"Total rows across the whole payload: {total_rows:,}")
