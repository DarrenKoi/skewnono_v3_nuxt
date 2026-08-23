"""Recipe statistics mock data for device_statistics.

The lot_cd column on r3_device_grp / device_desc (see providers/mock.py) is
the join key. When the frontend selects one or more lot_cds, this module
returns matching recipe-info and summary rows for each weekly date in
a trend window — keyed by ISO date so the frontend can plot the
trend directly without re-shaping.

사무실 원천 (user-confirmed 2026-07-31) — 이 모듈이 대역하는 실제 경로는 **fab
계열에 따라 둘로 갈리고**, 파라미터 개수만 공통입니다. 자세한 내용은
docs/datatables/hitachi/planstep_r3.txt, ebeam_tas_lot_hist.txt, idp_ver.txt 입니다.

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
- para_* 는 어느 스텝 소스에도 없는 값입니다. 실제로는 recipe_id 를
  cdsem_idp_ver.full_name 과 조인해 최신 version 의 parameters blob 에서
  집계합니다 — 그 blob 은 {이름: point 수} 이고(office 확인 2026-08-10),
  point 수를 다섯 **구간**으로 나눈 것이 para_* 입니다(para_buckets.py).
  여기서는 구간별 개수를 그냥 난수로 만듭니다.
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
실물에서 버킷은 **스텝 이름과 recipe 이름으로 갈라지는 분류**입니다 — 크기가 다른
네 덩어리가 아니라 **한 모집단 위의 겹치는 필터**이고, 한 스텝이 여러 버킷에 동시에
들어갑니다. 이 mock 도 2026-08-01 부터 그렇게 만듭니다
(providers/recipe_population.py). 예전에는 버킷마다 recipe 를 따로 만들고 id 에
버킷 이름을 박아서, recipe-params 와 recipe_id 로 조인이 아예 되지 않았습니다.

  all            모든 Step (Full job + Sample job)
  only_normal    skip 되지 않은(skip_yn != "Y") Step 중 스텝명 끝이 순수한 CD
                 ("CD(E)", "CD(F)" 는 제외)
  mother_normal  only_normal 과 같은 스텝 필터 + mother 파라가 있는 recipe 만.
                 para_* 도 mother 파라만 셉니다 (한 단계 아래로 들어갑니다).
  only_sample    **recipe 이름**이 "_S" 또는 "SE" 로 끝나는 Step

only_normal / mother_normal 은 skip 을 **멤버십에서** 거르므로 두 버킷의
``avail_recipe`` 는 항상 ``total_recipe`` 와 같습니다 (user-confirmed
2026-08-04). all / only_sample 에서만 두 값이 갈립니다.

규칙 전문과 정정 이력은 providers/recipe_population.py 의 docstring 입니다.

주간 트렌드의 실물 경로 (설계 확정 2026-07-31)
─────────────────────────────────────────────
이 mock 은 날짜별 값을 seed 로 만들어 내지만, 실물 스텝 index 에는 **과거가
없습니다**(현재 계획만 있는 index). 따라서 사무실에서는 주차별 스냅샷을 MinIO
에 적재해 두고 읽습니다 — 과거 주차는 스냅샷, 이번 주차만 라이브입니다.
자세한 내용은 docs/datatables/hitachi/device_statistics_weekly_trend.txt.

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

from back_dev_home.ebeam.device_statistics.para_buckets import (
    PARA_BUCKETS,
    para_block,
)
from back_dev_home.ebeam.device_statistics.contracts import (
    RecipeInfoRow,
    SummaryRow,
    step_key,
)
from back_dev_home.ebeam.device_statistics.providers.recipe_population import (
    RecipeIdentity,
    build_population,
    bucket_members,
    is_measuring as _is_measuring,
)


RCP_BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")
DEFAULT_TREND_POINTS = 8
DEFAULT_INTERVAL_DAYS = 7

# recipe 모집단·이름 어휘·버킷 분류는 providers/recipe_population.py 가 갖습니다.
# 예전에는 이 모듈이 버킷마다 recipe 를 따로 만들고 id 에 버킷 이름을 박았는데,
# 그러면 recipe-params 와 recipe_id 로 조인할 수 없습니다 (실물에서 recipe_id 는
# cdsem_idp_ver.full_name 과 같은 조인 키입니다 — docs/datatables/hitachi/idp_ver.txt L55).
# `_is_measuring` 는 그 모듈에서 가져와 avail_recipe 집계에 그대로 씁니다.


def _percent(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)


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


def _to_recipe_row(
    rng: random.Random,
    identity: RecipeIdentity,
    lot_cd: str,
    fac_id: str,
    date_key: str
) -> RecipeInfoRow:
    """모집단의 recipe 한 건을 계약(RecipeInfoRow) 모양으로 펼칩니다.

    recipe_id / oper_desc / skip_yn 은 모집단이 정합니다 — 이 셋이 버킷 분류의
    입력이자 recipe-params 와의 조인 키라, 여기서 다시 뽑으면 두 표면이 어긋납니다.
    """
    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "oper_id": identity["oper_id"],
        "oper_desc": identity["oper_desc"],
        "oper_seq": identity["oper_seq"],
        "samp_seq": identity["samp_seq"],
        "eqp_id": identity["eqp_id"],
        "recipe_id": identity["recipe_id"],
        # "Y" == skip(측정하지 않음) (user-confirmed 2026-07-31). 값 도메인은
        # 실물과 같은 "Y"/"N"/빈 값 세 가지이며, skip 비율 15% 를 유지해 측정
        # 비율은 예전과 같은 약 85% 입니다 — 극성 표기만 바로잡은 것이라 화면
        # 숫자는 뒤집히지 않습니다.
        "skip_yn": identity["skip_yn"],
        # 실물 chg_tm 은 offset 없는 KST wall-clock datetime("2025-07-17T12:26:01")
        # 입니다. 예전에는 시각(HH:MM:SS)만 만들어 날짜가 없었습니다.
        "chg_tm": (
            f"{date_key}T{rng.randint(0, 23):02d}:"
            f"{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
        ),
        "ctn_desc": identity["step_ctn_desc"],
        **para_block({key: identity[key] for key in PARA_BUCKETS}),
    }


def _to_mother_row(row: RecipeInfoRow, identity: RecipeIdentity) -> RecipeInfoRow:
    """mother_normal 버킷용 행 — 같은 recipe 인데 ``para_*`` 만 mother 기준입니다.

    이미 만들어 둔 행에서 **파생**합니다. ``_to_recipe_row`` 를 한 번 더 부르면
    chg_tm 난수가 recipe 당 두 배로 뽑혀 나머지 세 버킷의 chg_tm 이 전부 다른
    값이 됩니다 — 버킷 하나를 고치는 변경이 화면 전체를 흔들면 안 됩니다.

    recipe_id 는 그대로이므로 recipe-params 와의 조인은 유지됩니다. 이 버킷에서
    "같은 recipe 인데 para 가 작다" 는 것이 곧 mother view 의 정의입니다.
    """
    return {
        **row,
        **para_block({key: identity[f"mother_{key}"] for key in PARA_BUCKETS}),
    }


def _bucketed_recipe_rows(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    date_key: str,
    point_index: int,
    points: int
) -> dict[str, list[RecipeInfoRow]]:
    """이 (lot, date) 의 네 버킷 recipe 행.

    버킷은 **한 모집단 위의 겹치는 필터**입니다 — 예전처럼 버킷마다 따로 만들지
    않습니다. 같은 recipe 가 여러 버킷에 나오면 같은 recipe_id 를 갖고, 그 id 로
    recipe-params 와 조인됩니다 (실물에서 recipe_id 가 cdsem_idp_ver.full_name
    과 같은 조인 키이기 때문입니다 — docs/datatables/hitachi/idp_ver.txt L55).

    mother_normal 만 자기 행을 따로 만듭니다 — 같은 recipe 라도 이 버킷에서는
    para_* 가 mother 기준이라 다른 세 버킷과 행 객체를 공유할 수 없습니다.

    캐시 키가 recipe_id 가 **아닌** 것이 중요합니다. 한 recipe 는 여러 스텝에서
    재사용되므로(recipe_population `_apply_shared_recipes`), recipe_id 로 캐시하면
    두 스텝이 한 행으로 접혀 뒤 스텝의 oper_*·eqp_id 가 조용히 사라집니다. 행 1건의
    정체성은 계약이 정의하는 ``contracts.step_key`` 입니다.
    """
    population = build_population(lot_cd, point_index, points)
    rows_by_step = {
        step_key(identity): _to_recipe_row(rng, identity, lot_cd, fac_id, date_key)
        for identity in population
    }
    return {
        bucket: [
            _to_mother_row(rows_by_step[step_key(identity)], identity)
            if bucket == "mother_normal"
            else rows_by_step[step_key(identity)]
            for identity in members
        ]
        for bucket, members in bucket_members(population).items()
    }


def _summarize(
    lot_cd: str,
    fac_id: str,
    ctn_desc: str,
    recipes: list[RecipeInfoRow]
) -> SummaryRow:
    total_recipe = len(recipes)
    # 측정 중인 recipe 수. "Y" 가 skip 이므로 그 외 전부(빈 값 포함)를 셉니다 —
    # `== "N"` 으로 세면 빈 값 스텝이 빠져 운용 레시피수가 조용히 작아집니다.
    avail_recipe = sum(1 for r in recipes if _is_measuring(r["skip_yn"]))

    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        **para_block({
            key: sum(r[key] for r in recipes) for key in PARA_BUCKETS
        }),
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

            rows_by_bucket = _bucketed_recipe_rows(
                rng, lot_cd, fac_id, date_key, point_index, len(dates)
            )
            for bucket in RCP_BUCKETS:
                recipes = rows_by_bucket[bucket]
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
    #   python -m back_dev_home.ebeam.device_statistics.providers.statistics
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
