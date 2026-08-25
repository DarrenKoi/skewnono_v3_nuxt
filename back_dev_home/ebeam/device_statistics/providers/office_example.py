# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 cdsem device_statistics adapter.

네 개의 원천을 씁니다 — 이 기능이 답하는 질문들이 한 저장소에 모여 있지 않기
때문입니다.

    Redis  r3_device_grp       -> R3/R&D device 카탈로그        (r3-device-grp)
    Redis  device_desc         -> M 계열 양산 device 카탈로그    (device-desc)
    OS     sknn-planstep-r3    -> R3 공정 스텝 (oper_seq 순서)   ┐ recipe-params
    OS     ebeam_tas_lot_hist  -> M-fab 공정 스텝 (순서 field X) ┘ recipe-statistics
    OS     cdsem_idp_ver       -> recipe 당 parameters blob     (para_* 집계)
    MinIO  weekly_trend/*.json -> 주차별 summary 스냅샷          (recipe-trend)

recipe 경로는 **fab 계열에 따라 갈라지는 3-hop 체인**입니다. 이 분기를 헷갈리지
않는 것이 이 파일에서 가장 중요합니다.

    R3 / 연구개발                      M 계열 양산
    ─────────────────────────────      ─────────────────────────────
    r3_device_grp -> lot_cd            device_desc -> lot_cd
    lot_cd + "_BASE" -> prod_id        lot_cd 그대로 (접미사 없음)
    sknn-planstep-r3                   ebeam_tas_lot_hist (최근 90일)
      oper_seq/samp_seq 로 정렬          순서 field 없음 -> oper_order.py
      oper_desc, skip_yn 있음            oper_det_desc, skip_yn 없음
    ──────────────────── 공통 ────────────────────
    recipe_id == cdsem_idp_ver.full_name, 최신 version 의 parameters

field 목록과 함정은 docs/datatables/hitachi/ 의 planstep_r3.txt, ebeam_tas_lot_hist.txt,
idp_ver.txt, device_desc.txt, r3_device_grp.txt 에 있습니다.

버킷 정의 (user-confirmed 2026-07-31)
────────────────────────────────────
프론트(comparison.vue)의 네 버킷은 **스텝 이름**으로 갈립니다.

    all            모든 Step (Full job + Sample job)
    only_normal    **skip 되지 않은**(skip_yn != "Y") Step 중 스텝명 끝이
                   **순수한 CD** 인 것 ("CD(E)", "CD(F)" 처럼 괄호가 붙으면 제외)
    mother_normal  only_normal 과 **같은 스텝 필터** + mother 파라미터를 1개
                   이상 가진 recipe 만. para_* 집계도 **mother 파라만** 셉니다.
    only_sample    **recipe 이름**이 "_S" 또는 "SE" 로 끝나는 Step

only_normal 과 mother_normal 이 같은 스텝 필터를 공유하는 것이 핵심입니다 —
mother_normal 은 스텝을 더 좁히는 것이 아니라 **한 단계 아래(파라미터)로**
들어갑니다 (user-confirmed 2026-08-04). 2026-08-04 이전에는 only_normal 이 이름
어디든 CD 토큰이 있으면 통과시켜 추가계측("CD(E)")까지 Main 으로 셌고,
mother_normal 은 파라미터를 보지 않았습니다. 둘 다 틀렸습니다.

skip 을 **멤버십에서** 거르므로 두 버킷의 ``avail_recipe`` 는 항상
``total_recipe`` 와 같습니다. all / only_sample 에서만 두 값이 갈립니다.

Sample 판정만 축이 다릅니다 — 스텝명이 아니라 **recipe 이름**을 봅니다
(user-confirmed 2026-07-31). 스텝 코드로 판단하면 오검출이 생기고, 이름 어디든
"SE" 를 찾으면 PHASE/BASE/SET 같은 평범한 단어가 전부 Sample 이 됩니다. 그래서
**끝자리 고정(anchored)** 규칙입니다.

★ skip_yn — "Y" 만 제외, 나머지는 전부 진행 중 (user-confirmed 2026-07-31)

  ``skip_yn`` 은 **세 값**을 가집니다: "Y", "N", 그리고 **빈 값**. 따라서 판정은
  ``== "N"`` 이 아니라 반드시 **``!= "Y"``** 여야 합니다 — ``== "N"`` 으로 쓰면
  빈 값인 스텝이 통째로 사라지고, 그 손실은 화면에 오류가 아니라 "숫자가 좀
  작다" 로만 나타나 발견이 늦습니다.

  이름 그대로 **"Y" 가 skip(측정하지 않음)** 입니다. 2026-07-30 에 문서에
  기록되었던 "Y = 현재 측정 중" 은 틀린 내용이었고 2026-07-31 에 정정되었습니다
  (docs/datatables/hitachi/planstep_r3.txt). 이 극성은 ``avail_recipe`` 와 mother_normal
  버킷 양쪽을 동시에 뒤집으므로 :func:`_is_measuring` 하나로 모았습니다.

주간 트렌드 — MinIO 스냅샷 (설계 확정 2026-07-31)
──────────────────────────────────────────────
sknn-planstep-r3 는 **현재 상태** index 입니다(문서 1건 = 현재 계획 스텝).
과거 주차를 질의로 복원할 방법이 없으므로, 주차별 스냅샷을 **별도 스케줄러가
MinIO 에 적재**하고 이 어댑터는 그것을 읽습니다.

    과거 주차  -> MinIO ``{MINIO_BASE}/YYYY-MM-DD.json`` (summary 전용)
    이번 주차  -> 라이브 계산 (스냅샷이 아직 없으므로)

스냅샷에 ``*_rcp_info`` 를 담지 않는 것은 의도입니다. recipe-statistics 는
**최신 날짜 하나만** 소비하고(routes.py), recipe-trend 는 ``*_summary`` 만
읽습니다 — 4000 lot × 4 버킷 × recipe 100~200개를 주마다 적재하면 GB 급이
되며(MIGRATION.md 의 1.07 GB 사례), 아무도 읽지 않습니다.

적재는 :func:`write_weekly_snapshot` 하나로 끝납니다. 스케줄러는 주 1회
(월요일) 그 함수만 부르면 되고, 읽기 쪽과 payload 형태가 갈라지지 않도록 생성도
이 모듈이 책임집니다.

계측 룰(get_rules)
─────────────────
룰은 사무실 DB 에서 읽어오는 값이 아니라 **코드가 소유합니다** — office 도
mock 과 같은 ``providers/rules.py`` seed 를 그대로 반환합니다. 앱 내 편집
저장은 하지 않기로 결정했고(user-confirmed 2026-08-04), 룰 변경은 그때그때
rules.py 를 고쳐 배포합니다 — git 이력이 곧 버전 이력입니다. 예전의 Redis
발행(publish_rules / v3_device_statistics_rules)은 이 결정으로 폐기했습니다;
발행 전 404 가 나던 운영 함정만 있었고 사 주는 것이 없었습니다.

At the office
─────────────
``back_dev_home/.env`` 에 REDIS_* / OPENSEARCH_* / MINIO_* 를 채우고
``cp office_example.py office.py`` 하면 그 복사 자체가 스위치입니다. 확인은
MIGRATION.md 의 Verify 명령입니다.

OFFICE-VERIFY 목록
──────────────────
1. ``skip_yn`` 의 빈 값 비율 — ``!= "Y"`` 규칙이 실제로 얼마나 많은 스텝을
   살리는지. probe 의 skip_yn 분포에서 "Y"/"N" 합이 전체보다 작으면 그 차이가
   빈 값입니다.
2. ``.keyword`` 접미사 — 아래 상수는 문서 관례(analyzed text)를 가정합니다.
   실제 mapping 은 ``python -m scripts.probe_planstep_r3`` 가 field 별로
   출력하므로 첫 실행에서 확정하십시오. bare keyword field 에 접미사를 붙이면
   조용히 0건이 됩니다.
3. ``parameters`` key 세분도 — key 가 "WAFER"/"EDGE" 처럼 타입 단어뿐이면
   outlier·bloated recipe 뷰가 입력을 잃습니다 (idp_ver.txt).
4. ``para_all`` 은 **파라미터 총 개수**입니다. 2026-08-10 에 버킷이 정확 일치에서
   구간으로 바뀌면서 다섯 구간이 전체를 덮게 되어, "총 개수" 와 "버킷 합" 이 같은
   값이 되었습니다 — 예전의 잔여분 로그는 셀 것이 없어 사라졌습니다.
5. ``phase`` — ctn_desc 의 "p-EV" 는 계약 Literal 에 없어 None 이 됩니다.
6. M-fab ``oper_seq``/``samp_seq`` 는 원천에 없어 접두사 rank 로 합성합니다.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Literal

from back_dev_home._logging.providers import logger as _LOG
from back_dev_home._runtime.office_redis import (
    STORE_ERRORS,
    read_dataframe,
    redis_client,
    unreachable,
)
from back_dev_home.ebeam.device_statistics.contracts import (
    DeviceDescRow,
    MeasActivityRow,
    ParameterRow,
    R3DeviceGrpRow,
    RecipeInfoRow,
    RecipeParamsRow,
    RuleVersion,
    SummaryRow,
    TrendBucket,
)
from back_dev_home.ebeam.device_statistics.para_buckets import (
    PARA_BUCKETS,
    count_points,
    para_block,
)
from back_dev_home.ebeam.device_statistics.oper_order import (
    sort_key as _oper_sort_key,
)
from back_dev_home.ebeam.device_statistics.providers.rules import (
    get_rules as _seed_rules,
)
from back_dev_home.ebeam._office_search import (
    KST,
    aggregate as _aggregate,
    fetch_hits as _fetch_hits,
    query as _query,
    text as _text,
    ttl_cache,
)


__all__ = [
    "get_r3_device_grp",
    "get_device_desc",
    "get_meas_activity",
    "get_recipe_params",
    "get_weekly_trend_data",
    "get_rules",
    # 스케줄러/운영 진입점 — route 는 호출하지 않습니다.
    "build_weekly_snapshot",
    "write_weekly_snapshot",
    "sweep_weekly_snapshots",
]


# ─────────────────────────── 원천 이름 ───────────────────────────
# Redis 카탈로그 두 개 (user-confirmed 2026-07-31). recipe_tat/fail_issue 가
# 공유하는 _office_meas_hist.py 도 같은 두 key 를 읽으므로, 한쪽만 바꾸면 같은
# device 목록이 화면마다 달라집니다.
RND_KEY = "r3_device_grp"   # R3/R&D 카탈로그 (parquet DataFrame)
HVM_KEY = "device_desc"     # M 계열 양산 카탈로그 (parquet DataFrame)

PLANSTEP_INDEX = "sknn-planstep-r3"
LOT_HIST_INDEX = "ebeam_tas_lot_hist"
IDP_INDEX = "cdsem_idp_ver"

# MinIO 주차 스냅샷 접두사. 설정된 기본 prefix 위에 얹힙니다 — 사무실 자격증명은
# user/<사번>/ 아래로 제한되어 있어 버킷 레벨 조작은 하지 않습니다.
MINIO_BASE = "device_statistics/weekly_trend"

# YYYY-MM-DD.json 인 객체만 스냅샷으로 취급합니다 — sweep 이 같은 prefix 의 다른
# 객체를 지우지 않도록 하는 방어선입니다.
_SNAPSHOT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ─────────────────────── term/agg 대상 field ───────────────────────
# analyzed text 는 `.keyword` 를 써야 term 이 매칭됩니다(datatables README 표기
# 규칙). OFFICE-VERIFY #2 — probe 가 field 별 실제 mapping 을 출력합니다.
PROD_ID_KW = "prod_id.keyword"
FULL_NAME_KW = "full_name.keyword"
LOT_CD_KW = "lot_cd.keyword"
OPER_DET_DESC_KW = "oper_det_desc.keyword"
LOT_HIST_TIME_F = "event_tm"
# upstream field 이름은 fab_id 입니다 — 우리 코드의 fab_name 규칙은 우리 필드
# 이름에 대한 것이고, index 가 저장한 이름으로 질의합니다 (ebeam_tas_lot_hist.txt).
FAB_ID_KW = "fab_id.keyword"

# device code -> prod_id. 다른 접미사가 있는지는 probe 의 [3] 단계가 셉니다.
PROD_ID_SUFFIX = "_BASE"

# skip_yn 중 "이 스텝은 측정하지 않는다"를 뜻하는 값. 나머지("N" 과 **빈 값**)는
# 전부 진행 중입니다 — 판정은 _is_measuring() 하나만 씁니다 (모듈 docstring ★).
SKIPPED = "Y"

# M-fab 스텝 창. recipe_tat 의 60일과 근거가 달라("3개월 안에는 공정이 한 번은
# 돌았다") 일부러 상수를 공유하지 않습니다 — ebeam_tas_lot_hist.txt.
MFAB_WINDOW_DAYS = 90

# 한 device 의 R3 plan step 문서 수 상한. 넘으면 조용히 자르지 않고 실패시킵니다.
#
# 2000 이었다가 10000 으로 올렸습니다 — RJ1B 가 실제로 2000 을 쳤습니다
# (office 확인 2026-08-10, 화면에 upstream_data_error 로 노출). 2000 은 mock 의
# device 당 recipe 175~200 감각으로 잡은 값인데, 이 index 의 문서는 **측정 recipe
# 가 아니라 plan step** 이라 한 자리수 배는 많습니다 (planstep_r3.txt).
#
# 10000 은 임의의 숫자가 아니라 OpenSearch ``index.max_result_window`` 기본값
# 입니다. ``fetch_hits`` 는 search_after 없는 단발 질의라 이 값을 넘는 ``size``
# 는 응답이 잘리는 게 아니라 질의 자체가 거부됩니다. 따라서 **여기서 숫자를 더
# 올리는 것으로는 다음 번을 넘길 수 없고**, 그때는 search_after 페이지네이션이
# 필요합니다 (아래 _r3_steps 의 예외 메시지가 그 사실을 안내합니다).
_RESULT_WINDOW = 10_000
MAX_STEPS_PER_DEVICE = _RESULT_WINDOW

# M-fab 스텝 이름(unique oper_det_desc) terms agg 의 size 상한. R3 의 문서 수
# 상한과 **다른 양** 이라 상수를 나눠 둡니다 — 예전에는 하나를 공유해서, R3 쪽
# 사정으로 숫자를 올리면 M-fab 집계 버킷까지 같이 부풀었습니다. 90일 창의 unique
# 스텝 이름은 수백 규모입니다 (ebeam_tas_lot_hist.txt).
MAX_MFAB_STEP_NAMES = 2000

# para_* 버킷은 **point 수의 구간**입니다 (타입 코드가 아닙니다 — idp_ver.txt).
# 경계와 이름은 para_buckets.py 한 곳에 있습니다 — mock 두 표면과 공유합니다.

RCP_BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")

DEFAULT_TREND_POINTS = 8
DEFAULT_INTERVAL_DAYS = 7


# ───────────────────────── 계약 <- 원천 컬럼 ─────────────────────────
# 계약 이름 -> 원천 컬럼 후보(앞에서부터 먼저 있는 것을 씁니다).
#
# 계약은 plan_catg_type / den_type 인데 실물 컬럼은 plan_catg_typ / den_typ
# 입니다. 이름이 한 글자 차이라 rename 을 빠뜨려도 예외 없이 조용히 빈 값이
# 되므로 표로 고정합니다. 후보를 여러 개 두는 것은 이 카탈로그들의 컬럼 이름이
# 실제로 한 번 이상 엇갈려 기록된 적이 있기 때문이며(ctn_desc / stn_desc),
# 관용은 여기 한 곳에만 둡니다.
_R3_COLUMNS: dict[str, tuple[str, ...]] = {
    "fac_id": ("fac_id",),
    "plan_catg_type": ("plan_catg_typ", "plan_catg_type"),
    "prod_catg_cd": ("prod_catg_cd",),
    "tech_cd": ("tech_cd",),
    "den_type": ("den_typ", "den_type"),
    "prod_grp_typ": ("prod_grp_typ",),
    "gen_typ": ("gen_typ",),
    "lot_cd": ("lot_cd",),
    "plan_grade_cd": ("plan_grade_cd",),
    "lake_load_tm": ("lake_load_tm",),
    "ctn_desc": ("ctn_desc",),
}

_DEVICE_DESC_COLUMNS: dict[str, tuple[str, ...]] = {
    "fac_id": ("fac_id",),
    "lot_cd": ("lot_cd",),
    "ctn_desc": ("ctn_desc", "stn_desc"),
    "chg_tm": ("chg_tm",),
    "tech_nm": ("tech_nm",),
    "rnd_connector": ("rnd_connector",),
}


def _cell(record: dict[str, Any], candidates: tuple[str, ...]) -> str:
    """DataFrame 한 셀 -> 계약용 문자열.

    ``_text`` 가 None/NaN/pd.NA 와 **문자열 "None"** 을 모두 ""로 정규화합니다
    (원천에 둘 다 섞여 있습니다 — device_desc.txt).
    """
    for name in candidates:
        if record.get(name) is not None:
            return _text(record[name])
    return ""


def _catalog(key: str) -> list[dict[str, Any]]:
    """Redis parquet DataFrame -> record dict 목록."""
    try:
        raw = redis_client().get(key)
    except STORE_ERRORS as exc:
        raise unreachable(f"Redis unreachable while reading {key!r}", exc) from exc
    if raw is None:
        raise LookupError(
            f"Redis key {key!r} not found — check REDIS_* in back_dev_home/.env "
            "and that the device catalog is populated."
        )
    return read_dataframe(raw, key).to_dict(orient="records")


@ttl_cache
def _r3_rows() -> list[R3DeviceGrpRow]:
    rows: list[R3DeviceGrpRow] = []
    for record in _catalog(RND_KEY):
        row = {
            contract: _cell(record, sources)
            for contract, sources in _R3_COLUMNS.items()
        }
        if not row["lot_cd"]:
            continue  # lot_cd 가 없으면 조인 키가 없어 쓸 수 없습니다
        # 계약의 `id` 는 원천에 없습니다. 행 번호를 쓰면 카탈로그가 바뀔 때마다
        # 같은 device 의 id 가 움직이므로 안정적인 자연키로 만듭니다.
        row["id"] = f"{row['fac_id'] or 'R3'}-{row['lot_cd']}"
        rows.append(row)  # type: ignore[arg-type]
    return rows


@ttl_cache
def _hvm_rows() -> list[DeviceDescRow]:
    rows: list[DeviceDescRow] = []
    for record in _catalog(HVM_KEY):
        row = {
            contract: _cell(record, sources)
            for contract, sources in _DEVICE_DESC_COLUMNS.items()
        }
        if not row["lot_cd"]:
            continue
        row["id"] = f"{row['fac_id'] or 'M'}-{row['lot_cd']}"
        rows.append(row)  # type: ignore[arg-type]
    return rows


# 최근 활동 창의 unique lot_cd 상한(terms agg size). 카탈로그 자체가 수천 행
# 규모라 이 값이면 전부 담깁니다 — 넘치면 조용히 잘라 device 를 잃는 대신
# 실패시킵니다 (MAX_STEPS_PER_DEVICE 와 같은 방침).
_MAX_ACTIVE_LOTS = 50_000


@ttl_cache
def _active_lot_cds() -> set[str]:
    """최근 ``MFAB_WINDOW_DAYS`` 일의 ebeam_tas_lot_hist 에 나타난 lot_cd 집합.

    두 카탈로그(Redis)는 폐기된 lot_cd 까지 전부 담고 있어(device_desc.txt),
    recipe_tat 이 하듯 최근 측정 활동이 있는 lot 만 목록에 남깁니다
    (user-confirmed 2026-08-04). meas_hist 화면의 device 목록과 같은 원천이라
    두 화면의 "현재 생산 중" 집합이 어긋나지 않습니다.

    창은 스텝 조회(_mfab_steps)와 같은 90일을 씁니다 — 목록에 있는 device 는
    스텝도 있어야 하므로, 두 창이 갈라지면 "목록에는 있는데 스텝이 빈" device
    가 생깁니다. recipe_tat 의 60일과 상수를 공유하지 않는 이유는
    ebeam_tas_lot_hist.txt 에 있습니다.
    """
    floor = (datetime.now(KST) - timedelta(days=MFAB_WINDOW_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    aggs = {"lots": {"terms": {"field": LOT_CD_KW, "size": _MAX_ACTIVE_LOTS}}}
    result = _aggregate(
        LOT_HIST_INDEX,
        aggs,
        _query([{"range": {LOT_HIST_TIME_F: {"gte": floor}}}]),
    )
    buckets = result.get("lots", {}).get("buckets", [])
    if len(buckets) >= _MAX_ACTIVE_LOTS:
        raise LookupError(
            f"{LOT_HIST_INDEX!r} returned {_MAX_ACTIVE_LOTS}+ unique lot_cds in "
            f"the {MFAB_WINDOW_DAYS}-day window. A truncated set silently drops "
            "devices from the picker; raise _MAX_ACTIVE_LOTS or narrow the window."
        )
    return {_text(bucket.get("key")) for bucket in buckets if _text(bucket.get("key"))}


def get_r3_device_grp() -> list[R3DeviceGrpRow]:
    """R3/R&D 카탈로그 — 최근 활동이 있는 lot 만 (query param 없음 — MIGRATION.md)."""
    active = _active_lot_cds()
    return [row for row in _r3_rows() if row["lot_cd"] in active]


def get_device_desc(fac_ids: list[str] | None = None) -> list[DeviceDescRow]:
    """M 계열 양산 카탈로그 — 최근 활동이 있는 lot 만.

    ``fac_ids`` 는 대문자 정확 일치 필터입니다.
    """
    active = _active_lot_cds()
    rows = [row for row in _hvm_rows() if row["lot_cd"] in active]
    if not fac_ids:
        return rows
    wanted = {value.strip().upper() for value in fac_ids if value.strip()}
    if not wanted:
        return rows  # 전부 공백이면 필터 없음 (mock 과 동일)
    return [row for row in rows if row["fac_id"].strip().upper() in wanted]


def get_meas_activity(fac_id: str) -> list[MeasActivityRow]:
    """한 fab 의 lot_cd 별 최근 90일 측정 건수, meas_count 내림차순.

    _active_lot_cds 와 같은 index·같은 창을 fab 하나로 좁힌 terms 집계입니다 —
    doc_count 가 곧 측정 건수(활동량)입니다 (ebeam_tas_lot_hist.txt L52 의
    activity-count 용법). 화면(측정 상위 N 필터)은 이 순위를 카탈로그 행과
    교집합해 상위 N 개만 보여줍니다.

    OFFICE-VERIFY: R3 lot 이 이 index 에 fab_id="R3" 로 실리는지 첫 실행에서
    확인하십시오 — 아니라면 R3 는 순위가 빈 배열로 내려가고, 화면의 측정 상위
    필터가 R3 에서만 조용히 아무것도 남기지 않습니다.
    """
    wanted = fac_id.strip().upper()
    if not wanted:
        return []
    floor = (datetime.now(KST) - timedelta(days=MFAB_WINDOW_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    aggs = {"lots": {"terms": {"field": LOT_CD_KW, "size": _MAX_ACTIVE_LOTS}}}
    result = _aggregate(
        LOT_HIST_INDEX,
        aggs,
        _query([
            {"term": {FAB_ID_KW: wanted}},
            {"range": {LOT_HIST_TIME_F: {"gte": floor}}},
        ]),
    )
    buckets = result.get("lots", {}).get("buckets", [])
    ranked: list[MeasActivityRow] = [
        {"lot_cd": _text(bucket.get("key")), "meas_count": _as_int(bucket.get("doc_count"))}
        for bucket in buckets
        if _text(bucket.get("key"))
    ]
    # terms 는 기본이 doc_count desc 지만, 계약이 정렬을 약속하므로 명시합니다.
    ranked.sort(key=lambda entry: (-entry["meas_count"], entry["lot_cd"]))
    return ranked


# ───────────────────────── lot -> fab 계열 ─────────────────────────


@ttl_cache
def _lot_index() -> dict[str, str]:
    """lot_cd -> fac_id. 두 카탈로그의 합집합 (mock 의 _lot_index 와 같은 역할).

    일부러 최근 활동 필터(_active_lot_cds)를 걸지 않습니다 — 이것은 **목록이
    아니라 해석기**입니다. 카트에 담긴 lot 이 조회 시점에 90일 창 밖으로
    나갔더라도, 명시적으로 요청된 lot 의 fac_id 는 해석해 줘야 화면이 빈 응답
    대신 데이터를 보여줍니다.
    """
    index: dict[str, str] = {}
    for row in _r3_rows():
        index[row["lot_cd"]] = row["fac_id"]
    for row in _hvm_rows():
        index[row["lot_cd"]] = row["fac_id"]
    return index


@ttl_cache
def _lot_meta() -> dict[str, dict[str, str]]:
    """lot_cd -> {ctn_desc, prod_catg_cd}.

    ``prod_catg_cd`` 는 R3 카탈로그에만 있습니다. M-fab device 는 원천에 값이
    없으므로 ""로 두고 ``memory_class_auto`` 를 "unknown"(수동 분류, D7)으로
    떨어뜨립니다 — mock 처럼 임의로 고르면 실물이 모르는 값을 가르치게 됩니다.

    겹치는 ``lot_cd`` 는 **M-fab 이 이깁니다** (user-confirmed 2026-08-10) —
    바로 위 ``_lot_index`` 와 같은 순서입니다. 예전에는 이 함수만 hvm 을 먼저
    넣어 r3 이 이기는 바람에, 두 카탈로그에 모두 있는 lot 이 ``fac_id`` 는
    M-fab 행에서(그래서 ``_is_r3`` 가 M 으로 라우팅) ``ctn_desc`` /
    ``prod_catg_cd`` 는 R3 행에서 가져오는 잡종이 됐습니다. 한 파일 안의 두
    함수가 서로 반대 순서였고, mock 은 양쪽 다 M 우선이라 집에서는 재현되지
    않았습니다 — mock 의 두 생성기는 같은 lot_cd 를 함께 만들지 않습니다.
    """
    meta: dict[str, dict[str, str]] = {}
    for row in _r3_rows():
        meta[row["lot_cd"]] = {
            "ctn_desc": row["ctn_desc"],
            "prod_catg_cd": row["prod_catg_cd"],
        }
    for row in _hvm_rows():
        meta[row["lot_cd"]] = {"ctn_desc": row["ctn_desc"], "prod_catg_cd": ""}
    return meta


def _is_r3(fac_id: str) -> bool:
    """R 계열(연구개발) fab 인가. R3/R4… 는 planstep, 나머지는 lot_hist."""
    return fac_id.strip().upper().startswith("R")


def _resolve_lots(lot_cds: list[str] | None) -> list[str]:
    index = _lot_index()
    if not lot_cds:
        return list(index)
    requested = {value.strip() for value in lot_cds if value.strip()}
    if not requested:
        return list(index)
    return [lot for lot in index if lot in requested]


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _is_measuring(skip_yn: str) -> bool:
    """이 스텝이 skip 되지 않았는가 — ``skip_yn != "Y"``.

    ``== "N"`` 으로 쓰면 안 됩니다. 실제 값은 "Y"/"N" 외에 **빈 값**도 있어서
    (user-confirmed 2026-07-31), 긍정 비교는 빈 값 스텝을 통째로 떨어뜨립니다.
    그 손실은 예외가 아니라 "숫자가 좀 작다" 로만 나타나 발견이 늦습니다.

    ``avail_recipe`` 와 mother_normal 버킷이 모두 이 한 함수를 통과하므로,
    극성이 다시 바뀌더라도 두 곳이 어긋날 수 없습니다.
    """
    return (skip_yn or "").strip().upper() != SKIPPED


# ────────────────────────── 스텝 조회 ──────────────────────────


def _r3_steps(lot_cd: str) -> list[dict[str, Any]]:
    """R3 device 의 공정 스텝, oper_seq -> samp_seq 순.

    문서 반환 순서에 의존하면 안 되므로 정렬은 질의에서 겁니다
    (planstep_r3.txt 조회 방법 2번).
    """
    hits = _fetch_hits(
        PLANSTEP_INDEX,
        _query([{"term": {PROD_ID_KW: f"{lot_cd}{PROD_ID_SUFFIX}"}}]),
        size=MAX_STEPS_PER_DEVICE,
        # prod_id 를 정렬 키의 맨 앞에 둡니다 (user-confirmed 2026-07-31).
        # 한 device 만 조회하는 지금은 무해하지만, 여러 prod_id 를 한 번에
        # 질의하도록 넓힐 때 device 별 스텝이 뒤섞이지 않게 하는 것은 이
        # 첫 번째 키뿐입니다.
        sort=[{PROD_ID_KW: "asc"}, {"oper_seq": "asc"}, {"samp_seq": "asc"}],
        source=[
            "oper_id", "oper_desc", "oper_seq", "samp_seq",
            "eqp_id", "recipe_id", "skip_yn", "chg_tm",
        ],
    )
    if len(hits) == MAX_STEPS_PER_DEVICE:
        raise LookupError(
            f"Device {lot_cd!r} hit the {MAX_STEPS_PER_DEVICE}-step cap in "
            f"{PLANSTEP_INDEX!r}. A truncated step list understates every "
            "para_* total. This cap is already OpenSearch's max_result_window, "
            "so raising it alone will make the query fail outright — page with "
            "search_after, or check ingestion for duplicate step documents "
            "(scripts/probe_planstep_r3 stage [4] prints the real count)."
        )
    return [
        {
            "oper_id": _text(hit.get("oper_id")),
            "oper_desc": _text(hit.get("oper_desc")),
            "oper_seq": _as_int(hit.get("oper_seq")),
            "samp_seq": _as_int(hit.get("samp_seq")),
            "eqp_id": _text(hit.get("eqp_id")),
            "recipe_id": _text(hit.get("recipe_id")),
            "skip_yn": _text(hit.get("skip_yn")).upper(),
            "chg_tm": _text(hit.get("chg_tm")),
        }
        for hit in hits
    ]


def _mfab_steps(lot_cd: str) -> list[dict[str, Any]]:
    """M-fab device 의 공정 스텝 — 최근 90일의 unique ``oper_det_desc``.

    측정 단위 index 이므로 raw row 를 내려받지 않고 terms 집계로 좁힙니다
    (ebeam_tas_lot_hist.txt 의 payload 경고). 순서 field 가 없어
    ``oper_order`` 의 공정 접두사 rank 로 정렬하고, 계약이 요구하는
    ``oper_seq``/``samp_seq`` 는 그 순위로 합성합니다 — 실제 공정 순서를
    주장하는 값이 아닙니다(화면 표기 의무).
    """
    floor = (datetime.now(KST) - timedelta(days=MFAB_WINDOW_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    aggs = {
        "steps": {
            "terms": {"field": OPER_DET_DESC_KW, "size": MAX_MFAB_STEP_NAMES},
            "aggs": {
                "latest": {
                    "top_hits": {
                        "size": 1,
                        "sort": [{LOT_HIST_TIME_F: "desc"}],
                        "_source": ["recipe_id", "eqp_id", "oper_id", LOT_HIST_TIME_F],
                    }
                }
            },
        }
    }
    result = _aggregate(
        LOT_HIST_INDEX,
        aggs,
        _query([
            {"term": {LOT_CD_KW: lot_cd}},
            {"range": {LOT_HIST_TIME_F: {"gte": floor}}},
        ]),
    )
    steps_agg = result.get("steps", {})
    buckets = steps_agg.get("buckets", [])
    # terms agg 도 R3 경로와 같은 방침으로 잘림을 실패로 만듭니다. 여기서는
    # 버킷 수를 세는 대신 ``sum_other_doc_count`` 를 봅니다 — 이 값이 곧
    # "size 밖으로 밀려난 문서 수" 라서, 스텝 수가 정확히 상한과 같을 때
    # 멀쩡한 응답을 실패로 오인하지 않습니다.
    dropped = _as_int(steps_agg.get("sum_other_doc_count"))
    if dropped:
        raise LookupError(
            f"Device {lot_cd!r} exceeded the {MAX_MFAB_STEP_NAMES}-step-name cap "
            f"in {LOT_HIST_INDEX!r} ({dropped:,} measurement doc(s) fell outside "
            "the returned buckets). A truncated step list understates every "
            "para_* total; raise MAX_MFAB_STEP_NAMES or check ingestion."
        )

    steps: list[dict[str, Any]] = []
    for bucket in buckets:
        hits = bucket.get("latest", {}).get("hits", {}).get("hits", [])
        source = hits[0].get("_source", {}) if hits else {}
        steps.append({
            "oper_id": _text(source.get("oper_id")),
            "oper_desc": _text(bucket.get("key")),
            "oper_seq": 0,   # 정렬 뒤에 채웁니다
            "samp_seq": 1,   # 이 경로에는 sample 순서가 없습니다
            "eqp_id": _text(source.get("eqp_id")),
            "recipe_id": _text(source.get("recipe_id")),
            # 이 경로에는 skip_yn field 자체가 없습니다. 90일 창에 나타난 것이
            # 곧 "측정 중"이라는 신호이므로 빈 값으로 둡니다 — _is_measuring 의
            # `!= "Y"` 규칙에서 빈 값은 진행 중이고, "N" 을 넣어 원천에 없는
            # 값을 있는 것처럼 꾸미지도 않습니다.
            "skip_yn": "",
            "chg_tm": _text(source.get(LOT_HIST_TIME_F)),
        })

    steps.sort(key=lambda step: _oper_sort_key(step["oper_desc"]))
    for index, step in enumerate(steps):
        step["oper_seq"] = index + 1
    return steps


def _steps_for(lot_cd: str, fac_id: str) -> list[dict[str, Any]]:
    return _r3_steps(lot_cd) if _is_r3(fac_id) else _mfab_steps(lot_cd)


# ───────────────────── recipe -> parameters (idp_ver) ─────────────────────

# 한 번의 terms 질의에 넣을 recipe 수. device 당 100~200개라 보통 1회로 끝나지만,
# 필터 없는 호출에서도 질의가 무한정 커지지 않게 잘라 둡니다.
_IDP_CHUNK = 500


# mother 플래그가 실릴 수 있는 key 이름. idp 원본 컬럼명은 ``Mother_Para`` 입니다
# (docs/datatables/hitachi/recipe_idp.txt, office 확인 2026-07-28). 나머지 두 개는 적재
# 쪽이 이름을 바꿨을 때를 위한 관용입니다.
_MOTHER_KEYS = ("Mother_Para", "mother_para", "mother")

# raw_data row 에서 parameter 이름이 실린 key. idp 원본 컬럼명은 ``Parameter``.
_PARAM_NAME_KEYS = ("Parameter", "parameter", "name")

# image definition 묶음이 실릴 수 있는 key 이름. idp 원본 컬럼명은 ``Region``
# 입니다 (docs/datatables/hitachi/recipe_idp.txt). 같은 Region = 한 SEQ 그룹이고, 그 안의
# Mother_Para 하나가 image 의 주인입니다 (user-confirmed 2026-08-18).
_REGION_KEYS = ("Region", "region")

# raw_data 가 .idp 의 세 table 을 통째로 감싼 형태일 때 mother 가 든 table.
_IDP_IMAGE_TABLE = "idp_image_info"

# top_hits 가 내려받을 field.
#
# ``raw_data`` 를 **통째로 받으면 안 됩니다** — recipe 1건의 parameter 표 전체이고
# device 당 recipe 100~200 개가 곱해집니다 (idp_ver.txt 의 payload 주의는 이 blob
# 에도 그대로 적용됩니다). object array 에 대한 ``_source`` 필터는 배열 구조를
# 유지한 채 안쪽 field 만 남기므로, 필요한 두 컬럼만 이름으로 집습니다.
#
# ``raw_data.idp_image_info.*`` 를 함께 넣어 두는 것은 blob 이 세 table 을 감싼
# 형태일 경우를 위한 보험입니다 — 매칭되지 않는 include 는 비용이 없습니다.
_IDP_SOURCE = [
    "parameters",
    "parameters_list",
    "raw_data.Parameter",
    "raw_data.Mother_Para",
    "raw_data.Region",
    f"raw_data.{_IDP_IMAGE_TABLE}.Parameter",
    f"raw_data.{_IDP_IMAGE_TABLE}.Mother_Para",
    f"raw_data.{_IDP_IMAGE_TABLE}.Region",
]


def _normalize_parameters(blob: Any) -> tuple[dict[str, int], set[str]]:
    """``parameters`` blob -> ``({name: point_count}, {mother 인 name})``.

    확인된 형태는 dict[str, int] 입니다 — key 가 parameter 이름, value 가 측정
    **point 수**입니다 (user-confirmed 2026-07-30, 2026-08-10 재확인:
    ``{'EDGE': 10, 'LEVEL': 4, 'WAFER': 10}``). 이 형태에는 mother 플래그가 실릴
    자리가 없으므로 두 번째 값은 빈 집합이고, mother 는 ``raw_data`` 에서
    :func:`_mother_names` 가 읽습니다.

    list 분기는 적재 쪽이 ``[{name, point_count, ...}, ...]`` 로 바뀌었을 때를
    위한 관용이며, 그 경우에만 :data:`_MOTHER_KEYS` 중 하나에서 mother 를
    읽습니다. 둘 다 아니면 빈 dict 가 되어 para_* 가 0 이 됩니다.
    """
    if isinstance(blob, dict):
        params: dict[str, int] = {}
        for name, value in blob.items():
            key = _text(name)
            if key:
                params[key] = _as_int(value)
        return params, set()
    if isinstance(blob, list):
        params = {}
        mothers: set[str] = set()
        for entry in blob:
            if not isinstance(entry, dict):
                continue
            key = _text(entry.get("name"))
            if not key:
                continue
            params[key] = _as_int(entry.get("point_count"))
            if any(_flag(entry.get(name)) for name in _MOTHER_KEYS):
                mothers.add(key)
        return params, mothers
    return {}, set()


def _ordered_parameters(params: dict[str, int], order: Any) -> dict[str, int]:
    """``parameters`` 를 ``parameters_list`` 의 **측정 순서**로 재배열합니다.

    ``parameters`` dict 의 key 순서는 측정 순서가 **아닙니다** (office 확인
    2026-08-10). 같은 recipe 가 ``parameters = {'EDGE': 10, 'LEVEL': 4,
    'WAFER': 10}`` 이면서 ``parameters_list = ['WAFER', 'LEVEL', 'EDGE']`` 로
    옵니다 — 즉 dict 순서를 그대로 쓰면 **WAFER 가 목록 맨 아래**로 갑니다.
    2026-08-05 에 "dict 의 key 순서가 곧 recipe 가 적어 둔 순서" 라고 보고
    정렬만 걷어냈던 것은 절반만 맞았습니다: 정렬하지 말아야 한다는 것은 맞고,
    순서의 출처가 이 dict 라는 것은 틀렸습니다.

    ``parameters_list`` 에 없는 parameter 는 버리지 않고 원래 순서대로 뒤에
    붙입니다 — 두 field 가 어긋날 때 화면에서 파라미터가 사라지는 편이
    순서가 조금 어긋나는 것보다 나쁩니다.
    """
    if not isinstance(order, (list, tuple)):
        return params
    names = [name for name in (_text(value) for value in order) if name]
    if not names:
        return params

    ordered = {name: params[name] for name in dict.fromkeys(names) if name in params}
    trailing = {name: pc for name, pc in params.items() if name not in ordered}
    if trailing:
        _LOG.debug(
            "device_statistics: %d parameter(s) absent from parameters_list — "
            "appended in source order", len(trailing),
        )
    ordered.update(trailing)
    return ordered


def _flag(value: Any) -> bool | None:
    """bool 로 읽습니다. 읽을 수 없으면 **추측하지 않고** None.

    문자열을 그냥 ``bool()`` 에 넣으면 안 됩니다 — ``bool("False")`` 는 True
    입니다. recipe_search 가 ``Addressing``/``dnumber_removed`` 에서 겪은 함정과
    같은 것으로(recipe_idp.txt), 틀린 값을 넣느니 모른다고 하는 편이 낫습니다.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    label = _text(value).lower()
    if label in ("true", "t", "y", "yes", "1"):
        return True
    if label in ("false", "f", "n", "no", "0"):
        return False
    return None


def _column_values(column: Any) -> dict[str, Any]:
    """column 지향 blob 의 한 컬럼 -> ``{행 index: 값}``."""
    if isinstance(column, dict):
        return {_text(index): value for index, value in column.items()}
    if isinstance(column, list):
        return {str(index): value for index, value in enumerate(column)}
    return {}


def _raw_data_rows(blob: Any) -> list[dict[str, Any]] | None:
    """``raw_data`` -> row dict 목록. 알아볼 수 없는 형태면 None.

    확인된 형태는 **row dict 의 list** 입니다 (user-confirmed 2026-08-10)::

        [{"Parameter": "WAFER", "Mother_Para": True, ...}, ...]

    나머지 분기는 적재 쪽 표기가 바뀌었을 때를 위한 관용입니다. 형태를 위치가
    아니라 **key 이름으로** 판별하는 것은 recipe_search 의 ``_normalize_frames``
    와 같은 이유입니다 — 순서로 추측하면 조용히 틀립니다.
    """
    if isinstance(blob, list):
        return [entry for entry in blob if isinstance(entry, dict)] or None
    if not isinstance(blob, dict) or not blob:
        return None

    # .idp 의 세 table 을 감싼 형태 — mother 는 idp_image_info 안에 있습니다.
    if _IDP_IMAGE_TABLE in blob:
        return _raw_data_rows(blob[_IDP_IMAGE_TABLE])

    mother_key = next((key for key in _MOTHER_KEYS if key in blob), "")
    if mother_key:
        # column 지향 (``DataFrame.to_dict()``) — {컬럼: {행 index: 값}}.
        name_key = next((key for key in _PARAM_NAME_KEYS if key in blob), "")
        names = _column_values(blob.get(name_key)) if name_key else {}
        # Region 도 함께 실어야 합니다 — 여기서 흘리면 이 형태의 문서만 SEQ 그룹을
        # 잃고, 그 손실은 예외가 아니라 "이 문서에서만 son 이 자기 cap 으로 잡힌다"
        # 로 조용히 나타납니다.
        region_key = next((key for key in _REGION_KEYS if key in blob), "")
        regions = _column_values(blob[region_key]) if region_key else {}
        return [
            {
                "Parameter": names.get(index),
                mother_key: value,
                **({region_key: regions[index]} if index in regions else {}),
            }
            for index, value in _column_values(blob[mother_key]).items()
        ] or None

    # parameter 이름이 key 이고 값이 그 parameter 의 detail dict.
    return [
        {"Parameter": _text(name), **entry}
        for name, entry in blob.items()
        if isinstance(entry, dict)
    ] or None


def _row_is_mother(row: Any) -> bool:
    """이 row 하나가 mother 를 뜻하는가. 읽을 수 없으면 False.

    `_mother_names` 가 이름 집합을 만들 때 쓰는 판정과 같은 것을 row 단위로
    떼어낸 것입니다 — `_param_regions` 가 mother row 를 우선하려면 같은 질문을
    같은 방식으로 물어야 하고, 두 곳이 각자 판정하면 그 순간 다시 어긋납니다.
    """
    for key in _MOTHER_KEYS:
        if key in row:
            return _flag(row[key]) is True
    return False


def _mother_names(raw_data: Any) -> set[str] | None:
    """``raw_data`` -> mother 인 parameter 이름 집합. **판별 불가면 None**.

    빈 집합과 None 은 다릅니다 — 빈 집합은 "읽었고 mother 가 없다", None 은
    "이 문서에서는 mother 를 읽을 수 없다" 입니다. mother_normal 버킷은 두 경우
    모두 비지만 원인이 정반대라, 이 구분이 곧 :func:`_idp_parameters` 가 어느
    경고를 남길지입니다.
    """
    rows = _raw_data_rows(raw_data)
    if rows is None:
        return None

    mothers: set[str] = set()
    readable = False
    for row in rows:
        flag: bool | None = None
        for key in _MOTHER_KEYS:
            if key in row:
                flag = _flag(row[key])
                break
        if flag is None:
            continue
        readable = True
        if not flag:
            continue
        name = next(
            (n for n in (_text(row.get(key)) for key in _PARAM_NAME_KEYS) if n), ""
        )
        if name:
            mothers.add(name)
    return mothers if readable else None


def _param_regions(raw_data: Any) -> dict[str, int]:
    """``raw_data`` -> ``{parameter 이름: Region}``. 읽을 수 없으면 빈 dict.

    한 ``Region`` 은 image definition 1개이고, 같은 Region 인 파라미터들이 한 SEQ
    그룹입니다 — 화면의 "1/8, 2/8, 3/8 …" 이 그 묶음이고 그 안의 ``Mother_Para``
    하나가 image 의 주인, 나머지는 son 입니다 (user-confirmed 2026-08-18).

    프론트엔드의 계측 룰 판정이 이 값을 씁니다: son 은 mother 와 같은 image 에서
    자기 cd_value 를 꺼내므로 자기 이름의 타입 cap 이 아니라 **그 묶음 mother 의
    cap** 으로 잽니다 (utils/ruleEngine.groupCaps). 이 값이 비면 판정은 파라미터
    마다 자기 cap 으로 돌아가고, WAFER(13) mother 의 son 인 CELL_SP·LWR 이 이름이
    OTHER 라는 이유로 ``_other``(9)에 걸려 **고칠 수 없는 위반**이 됩니다.

    :func:`_mother_names` 와 달리 "판별 불가" 를 ``None`` 으로 구분하지 않습니다 —
    Region 이 없으면 프론트엔드가 예전 판정(파라미터별 자기 cap)으로 되돌아가는
    안전한 기본값이 있고, 판별 불가의 경고는 이미 mother 쪽이 냅니다. 두 값은 같은
    row 에서 오므로 한쪽이 안 읽히면 다른 쪽도 대개 안 읽힙니다.

    ``Region`` 은 wafer_mp_info 의 ``P_No`` 와 같은 값이며 recipe 안에서만 뜻이
    있습니다 (docs/datatables/hitachi/recipe_idp.txt) — recipe 를 가로질러 비교하지
    마십시오.
    """
    rows = _raw_data_rows(raw_data)
    if rows is None:
        return {}

    regions: dict[str, int] = {}
    # 이름별로 "mother 인 row 에서 Region 을 이미 읽었다" 는 표시입니다.
    mother_rows: set[str] = set()
    for row in rows:
        raw = next((row[key] for key in _REGION_KEYS if key in row), None)
        if raw is None:
            continue
        name = next(
            (n for n in (_text(row.get(key)) for key in _PARAM_NAME_KEYS) if n), ""
        )
        # 같은 parameter 가 여러 row(=여러 image definition)에 나올 수 있습니다
        # (recipe_idp.txt: "img_* 5개의 주인은 row 이며 Parameter 가 아닙니다").
        # 이 표면의 단위는 parameter 이므로 **먼저 나온 것**을 씁니다 — 측정 순서가
        # 곧 SEQ 순서이니 앞선 row 가 그 parameter 를 처음 재는 자리입니다.
        #
        # 단, **mother 인 row 가 우선입니다**. `_mother_names` 는 "한 row 라도
        # mother 면 mother" 로 읽으므로, 첫 row 의 Region 을 그대로 쓰면 Region 2
        # 에서는 son 이고 Region 5 에서는 mother 인 parameter 가 프론트엔드에
        # {mother: True, region: 2} 라는, 어느 row 에도 없는 짝으로 갑니다. 그러면
        # `groupCaps` 에서 그 이름이 region 2 의 cap 을 가로채고, 정작 region 5 의
        # son 들은 mother 를 못 찾아 자기 cap 으로 되돌아갑니다.
        #
        # mother row 를 우선하면 두 값이 항상 같은 row 에서 나오므로 그 짝이
        # 생기지 않습니다. 어느 쪽 규칙이 옳은지 — 한 parameter 의 Mother_Para 가
        # row 마다 실제로 달라지는지 — 는 여전히 OFFICE-VERIFY 이지만, 답이 어느
        # 쪽이든 이 코드가 만들어 내는 짝은 실재하는 row 하나를 가리킵니다.
        if name and _row_is_mother(row) and name not in mother_rows:
            mother_rows.add(name)
            try:
                regions[name] = int(str(raw).strip())
            except (TypeError, ValueError):
                regions.pop(name, None)
            continue
        if name and name not in regions:
            # `_as_int` 를 쓰지 않습니다 — 그 함수는 못 읽으면 0 을 돌려주는데,
            # 0 은 "모름" 이 아니라 **멀쩡한 group id** 입니다. Region 이
            # "2.0"(float 로 직렬화된 문자열, int("2.0") 은 ValueError) 이거나
            # 빈 문자열로 오면 그 recipe 의 파라미터가 전부 group 0 으로 뭉쳐
            # 서로 남의 mother cap 을 물려받습니다. 이 docstring 이 근거로 삼는
            # 안전한 기본값은 "Region 이 없음"(dict 에 키가 없음)이지 0 이 아니며,
            # 못 읽은 것은 건너뛰어야 그 기본값으로 갑니다.
            #
            # 사내 파서가 숫자 필드를 문자열로 준 전례가 있습니다 —
            # 2026-08-05 `Coordinate.X` 가 "52.676" 로 왔습니다
            # (docs/datatables/hitachi/recipe_idp.txt §dtype).
            try:
                regions[name] = int(str(raw).strip())
            except (TypeError, ValueError):
                continue
    return regions


def _idp_parameters(
    recipe_ids: list[str]
) -> tuple[
    dict[str, dict[str, int]],
    dict[str, set[str]] | None,
    dict[str, dict[str, int]],
]:
    """recipe_id -> ``{parameter_name: point_count}`` (최신 version 1건),
    recipe_id -> ``{mother 인 parameter 이름}``, recipe_id -> ``{이름: Region}``.

    recipe 마다 질의를 날리면 device 하나에 100~200 왕복이 됩니다. terms 집계 +
    ``top_hits(size=1, sort=version desc)`` 로 **device 당 1회**로 줄이고
    ``_source`` 를 :data:`_IDP_SOURCE` 로 제한합니다 — 이 두 제한은 선택이 아니라
    필수입니다(idp_ver.txt payload 주의).

    세 field 를 읽고 각각 다른 것을 답합니다 (office 확인 2026-08-10):

      parameters       {이름: point 수}. para_* 구간 집계의 입력입니다.
      parameters_list  **측정 순서**의 이름 목록. parameters 의 key 순서는 측정
                       순서가 아니므로 화면 순서는 이쪽이 정합니다.
      raw_data         parameter 별 row. ``Mother_Para`` 와 ``Region`` 이 여기
                       있습니다. Region 은 image definition 묶음(SEQ 그룹)이며,
                       프론트엔드가 son 에게 mother 의 cap 을 물려줄 때 쓰는
                       유일한 근거입니다 (user-confirmed 2026-08-18,
                       :func:`_param_regions`).

    ★ mother_para 의 출처 — 해결됨 (office 확인 2026-08-10)

      오랫동안 ``Mother_Para`` 는 **장비 FTP 의 ``.idp`` 원본 파일**에서만 읽을 수
      있다고 보았고(recipe_idp.txt), device 4000개 × recipe 100~200개 규모에서는
      그 경로를 쓸 수 없어 mother_normal 버킷을 비워 두고 있었습니다. 실제로는 이
      index 의 ``raw_data`` 에 같은 값이 실려 있습니다 — recipe_search 의
      recipe-open 이 FTP 파싱의 대안으로 쓰는 것과 같은 blob 입니다.

      두 번째 반환값이 ``None`` 이면 여전히 **판별 불가**(그 blob 에서 플래그를
      찾지 못함)이고, 그때만 mother_normal 이 원인 불명으로 빕니다. 빈 dict 는
      다른 뜻입니다 — 읽었는데 mother 인 recipe 가 하나도 없다는 뜻이고, 그것도
      정상은 아니므로 별도 경고를 남깁니다. 조용히 같아지면 화면이 "mother view
      가 동작한다" 고 거짓말하므로 두 경우를 가르는 것이 요점입니다.
    """
    unique = [rid for rid in dict.fromkeys(recipe_ids) if rid]
    if not unique:
        return {}, None, {}

    out: dict[str, dict[str, int]] = {}
    mothers_out: dict[str, set[str]] = {}
    regions_out: dict[str, dict[str, int]] = {}
    readable = 0
    for start in range(0, len(unique), _IDP_CHUNK):
        chunk = unique[start:start + _IDP_CHUNK]
        aggs = {
            "by_recipe": {
                "terms": {"field": FULL_NAME_KW, "size": len(chunk)},
                "aggs": {
                    "latest": {
                        "top_hits": {
                            "size": 1,
                            "sort": [{"version": "desc"}],
                            "_source": _IDP_SOURCE,
                        }
                    }
                },
            }
        }
        result = _aggregate(
            IDP_INDEX, aggs, _query([{"terms": {FULL_NAME_KW: chunk}}])
        )
        for bucket in result.get("by_recipe", {}).get("buckets", []):
            hits = bucket.get("latest", {}).get("hits", {}).get("hits", [])
            if not hits:
                continue
            source = hits[0].get("_source", {})
            recipe_id = _text(bucket.get("key"))
            params, list_mothers = _normalize_parameters(source.get("parameters"))
            out[recipe_id] = _ordered_parameters(
                params, source.get("parameters_list")
            )
            raw_data = source.get("raw_data")
            regions = _param_regions(raw_data)
            if regions:
                regions_out[recipe_id] = regions
            # raw_data 가 정본입니다. list 형태 parameters 가 플래그를 실어 준
            # 경우만 그 값으로 물러섭니다.
            mothers = _mother_names(raw_data)
            if mothers is None and list_mothers:
                mothers = list_mothers
            if mothers is None:
                continue
            readable += 1
            if mothers:
                mothers_out[recipe_id] = mothers

    if not readable:
        # 한 recipe 에서도 플래그를 **찾지 못했습니다** — "mother 가 없는 device"
        # 가 아니라 판별 자체가 불가능한 상태입니다.
        _LOG.warning(
            "device_statistics: could not read Mother_Para for any of %d recipe(s) "
            "in %r — the mother_normal bucket will be EMPTY. Fetched %s; if the "
            "flag moved, fix _IDP_SOURCE and _raw_data_rows together "
            "(scripts/probe_planstep_r3 stage [5] prints raw_data's real shape).",
            len(unique), IDP_INDEX, _IDP_SOURCE,
        )
        return out, None, regions_out
    if not mothers_out:
        # 위와 정반대의 상태 — 읽히기는 했는데 전부 False 입니다. recipe 마다
        # mother 가 보통 1개는 있으므로(recipe_idp.txt) 이것도 정상은 아닙니다.
        _LOG.warning(
            "device_statistics: Mother_Para readable on %d of %d recipe(s) in %r "
            "but NOT ONE is True — the mother_normal bucket will be EMPTY. Check "
            "whether the flag is being ingested as a string ('False'/'N').",
            readable, len(unique), IDP_INDEX,
        )
    if not regions_out:
        # Region 이 없으면 프론트엔드의 판정이 파라미터마다 자기 cap 으로 돌아가고,
        # WAFER(13) mother 의 son 인 CELL_SP·LWR 이 이름 때문에 _other 에 걸려
        # **고칠 수 없는 위반**이 됩니다. 화면은 오류 없이 위반 수만 부풀므로
        # 로그가 유일한 신호입니다.
        _LOG.warning(
            "device_statistics: no Region on any of %d recipe(s) in %r — SEQ "
            "groups are unavailable, so son parameters will be judged against "
            "their own type cap instead of their mother's. Fetched %s; if the "
            "column moved, fix _IDP_SOURCE and _param_regions together.",
            len(unique), IDP_INDEX, _IDP_SOURCE,
        )
    return out, mothers_out, regions_out


def _percent(part: int, total: int) -> float:
    return round(part / total * 100, 2) if total else 0.0


# ────────────────────────── 스텝 분류 (버킷) ──────────────────────────
# user-confirmed 2026-07-31. 모듈 docstring 의 "버킷 정의" 절이 근거입니다.

# Sample 판정은 **recipe 이름의 끝자리**입니다 (user-confirmed 2026-07-31).
# `$` 로 고정하지 않으면 PHASE/BASE/SET 같은 단어가 전부 Sample 로 잡히고,
# recipe_class 까지 뒤집혀 잘못된 cap 으로 위반 판정이 납니다.
_SAMPLE_SUFFIX = re.compile(r"(_S|SE)$", re.IGNORECASE)


def _is_sample_recipe(recipe_id: str) -> bool:
    """recipe 이름이 "_S"/"SE" 로 끝나는가.

    스텝 코드(괄호 앞)로 판단하지 않습니다 — 오검출 가능성이 있다는 담당자
    확인이 있었습니다. 축이 스텝명이 아니라 recipe 이름인 것이 핵심입니다.
    """
    return bool(_SAMPLE_SUFFIX.search((recipe_id or "").strip()))


def _ends_with_pure_cd(oper_desc: str) -> bool:
    """스텝명 끝이 **순수한 CD** 인가 — "CD(E)" / "CD(F)" 는 제외.

    실제 스텝명은 "CBL ETCH CD" 처럼 공정 접두사로 시작해 띄어쓰기로 이어지고,
    추가계측은 "ISO PTN CD(E)" 처럼 꼬리가 괄호로 닫힙니다 (user-confirmed
    2026-08-09). 그래서 닫는 괄호를 벗긴 뒤 마지막 토큰이 정확히 "CD" 인지
    봅니다 — "ISO PTN CD(E)" 는 벗겨도 마지막 토큰이 "CD(E" 라 걸러집니다.
    """
    stripped = (oper_desc or "").strip().rstrip(")]} \t")
    if not stripped:
        return False
    return stripped.split()[-1].upper() == "CD"


def _is_normal_bucket_step(oper_desc: str, skip_yn: str) -> bool:
    """only_normal / mother_normal 이 **공유**하는 스텝 필터.

    두 버킷이 같은 스텝 집합을 쓴다는 것은 도메인 규칙입니다 — mother_normal 은
    스텝이 아니라 파라미터를 좁힙니다. 조건을 두 군데에 복사하지 않고 이 한
    함수를 양쪽이 부릅니다 (mock 의 ``is_normal_bucket_step`` 과 같은 규칙).
    """
    return _is_measuring(skip_yn) and _ends_with_pure_cd(oper_desc)


def _bucket_members(
    steps: list[dict[str, Any]],
    mothers_by_recipe: dict[str, set[str]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """네 버킷의 스텝 집합. 한 스텝이 여러 버킷에 들어갈 수 있습니다.

    ``mothers_by_recipe`` 는 recipe_id -> mother 파라미터 이름 집합입니다.
    mother_normal 은 그 집합이 비어 있지 않은 recipe 만 남깁니다.

    mother 를 판별할 수 없으면(빈 dict) 이 버킷은 **비어 있게** 됩니다. 규칙을
    데이터에 그대로 적용한 결과이고, 의도된 동작입니다 — only_normal 로 슬쩍
    대체하면 요약은 숫자를 보여주는데 health 는 판정할 파라미터가 없어 0/0 이
    되는, 두 표면이 서로 다른 답을 하는 화면이 됩니다. 빈 버킷은 눈에 보이고,
    이유는 :func:`_idp_parameters` 의 경고 로그가 말합니다.
    """
    mothers = mothers_by_recipe or {}
    normal = [
        s for s in steps
        if _is_normal_bucket_step(s["oper_desc"], s["skip_yn"])
    ]
    return {
        "all": list(steps),
        "only_normal": normal,
        "mother_normal": [s for s in normal if mothers.get(s["recipe_id"])],
        "only_sample": [s for s in steps if _is_sample_recipe(s["recipe_id"])],
    }


# ───────────────────── recipe-params (RecipeInput 형태) ─────────────────────

_POOL_TOKEN = re.compile(r"(pool|풀)", re.IGNORECASE)

# 개발 phase. "t-EV"/"tev" 를 "EV" 보다 먼저 봐야 합니다(부분 일치 함정).
# "p-EV" 는 계약 Literal 에 없어 None 이 됩니다 — OFFICE-VERIFY #5.
_PHASE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("t-EV", re.compile(r"\bt\s*-?\s*EV\b", re.IGNORECASE)),
    ("PV", re.compile(r"\bPV\b", re.IGNORECASE)),
    ("TV", re.compile(r"\bTV\b", re.IGNORECASE)),
    ("EV", re.compile(r"(?<![tp]-)\bEV\b", re.IGNORECASE)),
)


def _phase_of(ctn_desc: str) -> Literal["t-EV", "EV", "TV", "PV"] | None:
    """ctn_desc 의 phase 토큰. ``_family_of`` 와 **독립적으로** 봅니다.

    "DRAM Pool제 (@Spica PV)" 처럼 Pool 과 phase 가 한 문자열에 같이 오는
    device 가 있습니다(user-confirmed 2026-08-25). 그때도 여기서 phase 를
    지우면 안 됩니다 — 두 축은 직교하고 payload 는 둘 다 실어야 합니다.
    Pool 이 phase 를 이기는 것은 **판정** 규칙이고, 판정은 client-side 라
    ``ruleEngine.ts`` 의 ``selectorMatches`` 가 담당합니다.
    """
    for phase, pattern in _PHASE_PATTERNS:
        if pattern.search(ctn_desc or ""):
            return phase  # type: ignore[return-value]
    return None


def _family_of(ctn_desc: str) -> Literal["Core", "Pool", "VG_RTC_Cubic"]:
    """Pool 여부만 판별하고 나머지는 Core (user-confirmed 2026-07-31).

    ``VG_RTC_Cubic`` 은 원천에서 판별할 근거가 없어 **발행하지 않습니다**.
    틀린 분류보다 미분류가 낫다는 판단이며, 근거가 생기면 여기만 고칩니다.
    """
    return "Pool" if _POOL_TOKEN.search(ctn_desc or "") else "Core"


def _memory_class_auto(prod_catg_cd: str) -> Literal["DRAM", "NAND", "unknown"]:
    """D7 — prod_catg_cd 에서만 파생. Tech/Advanced/빈 값은 수동 분류."""
    code = (prod_catg_cd or "").upper()
    if code == "DRAM":
        return "DRAM"
    if code in ("NAND", "FLASH"):
        return "NAND"
    return "unknown"


def _recipe_class(recipe_id: str) -> Literal["Main", "Sample"]:
    """only_sample 버킷과 같은 규칙 — recipe 이름이 "_S"/"SE" 로 끝나면 Sample.

    이 값이 프론트 ruleEngine 의 cap 선택 축(D2)이므로, 버킷 분류와 어긋나면
    같은 recipe 가 Sample 버킷에 있으면서 Main cap 으로 판정받게 됩니다.
    """
    return "Sample" if _is_sample_recipe(recipe_id) else "Main"


def get_recipe_params(lot_cds: list[str] | None = None) -> list[RecipeParamsRow]:
    """선택된 device 들의 recipe × parameter 원본 행.

    프론트(ruleEngine.ts)가 cap 위반·outlier 를 client-side 로 판정하므로
    백엔드는 raw 만 내려보냅니다(§8-bis).
    """
    index = _lot_index()
    meta = _lot_meta()
    rows: list[RecipeParamsRow] = []

    for lot_cd in _resolve_lots(lot_cds):
        fac_id = index[lot_cd]
        info = meta.get(lot_cd, {"ctn_desc": "", "prod_catg_cd": ""})
        prod_catg_cd = info["prod_catg_cd"]
        family = _family_of(info["ctn_desc"])
        phase = _phase_of(info["ctn_desc"])
        memory_class = _memory_class_auto(prod_catg_cd)

        steps = _steps_for(lot_cd, fac_id)
        params_by_recipe, mothers_by_recipe, regions_by_recipe = _idp_parameters(
            [s["recipe_id"] for s in steps]
        )

        seen: set[str] = set()
        for step in steps:
            recipe_id = step["recipe_id"]
            # 같은 recipe 가 여러 스텝에 걸리면 recipe 행은 한 번만 냅니다 —
            # 계약의 단위가 recipe 이기 때문입니다.
            if not recipe_id or recipe_id in seen:
                continue
            seen.add(recipe_id)
            # mother 를 판별할 수 없으면(None) 전부 False 로 둡니다 — 프론트엔드의
            # mother_normal 필터가 빈 결과를 내는 편이, 임의로 True 를 칠해
            # "mother view 가 동작한다" 고 거짓말하는 것보다 낫습니다. 판별
            # 불가는 위 _idp_parameters 가 로그로 알립니다.
            mothers = (mothers_by_recipe or {}).get(recipe_id, set())
            # 여기서 정렬하지 않습니다 — 순서 자체가 정보입니다. WAFER 계열이
            # 맨 앞에 오는 것이 관례이고 엔지니어가 drill 을 위에서부터 읽는데,
            # 예전에는 이름순으로 정렬해 "WAFER" 가 알파벳상 거의 끝이라 **가장
            # 중요한 파라미터가 목록 맨 아래로** 밀려 있었습니다.
            #
            # 그 순서를 정하는 것은 ``parameters`` dict 의 key 순서가 아니라
            # ``parameters_list`` 이며, 재배열은 _ordered_parameters 가 이미
            # 끝냈습니다 (office 확인 2026-08-10 — 두 field 의 순서가 실제로
            # 다릅니다). 여기는 그 순서를 **그대로 흘려보내기만** 합니다.
            # Region 은 image definition 묶음(SEQ 그룹)입니다. 못 읽으면 None 이고,
            # 그때 프론트엔드는 파라미터마다 자기 cap 으로 판정합니다 — 묶을 근거가
            # 없는데 임의로 묶으면 son 에게 엉뚱한 mother 의 cap 이 갑니다.
            regions = regions_by_recipe.get(recipe_id, {})
            parameters: list[ParameterRow] = [
                {
                    "name": name,
                    "point_count": point_count,
                    "mother": name in mothers,
                    "region": regions.get(name),
                }
                for name, point_count in params_by_recipe.get(recipe_id, {}).items()
            ]
            rows.append({
                "lot_cd": lot_cd,
                "recipe_id": recipe_id,
                "fac_id": fac_id,
                # recipe 설명은 그 recipe 가 걸린 공정 스텝 이름입니다 —
                # mock 처럼 문장을 지어내지 않습니다.
                "ctn_desc": step["oper_desc"],
                "prod_catg_cd": prod_catg_cd,
                "recipe_class": _recipe_class(recipe_id),
                "family": family,
                "phase": phase,
                "memory_class_auto": memory_class,
                "parameters": parameters,
            })
    return rows


# ─────────────────────── 주간 트렌드 (요약 + 스냅샷) ───────────────────────


def _params_for_bucket(
    bucket: str,
    recipe_id: str,
    points_by_recipe: dict[str, dict[str, int]],
    mothers_by_recipe: dict[str, set[str]] | None,
) -> dict[str, int]:
    """이 버킷이 para_* 로 세어야 할 파라미터.

    mother_normal 만 mother 로 좁힙니다 — 나머지 세 버킷은 recipe 의 파라미터를
    그대로 셉니다. mother 를 판별할 수 없으면 그 recipe 는 애초에 mother_normal
    멤버가 아니므로(:func:`_bucket_members`), 여기 빈 dict 가 오는 일은 없습니다.
    """
    points = points_by_recipe.get(recipe_id, {})
    if bucket != "mother_normal":
        return points
    mothers = (mothers_by_recipe or {}).get(recipe_id, set())
    return {name: pc for name, pc in points.items() if name in mothers}


def _recipe_row(
    lot_cd: str,
    fac_id: str,
    step: dict[str, Any],
    params: dict[str, int],
) -> RecipeInfoRow:
    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "oper_id": step["oper_id"],
        "oper_desc": step["oper_desc"],
        "oper_seq": step["oper_seq"],
        "samp_seq": step["samp_seq"],
        "eqp_id": step["eqp_id"],
        "recipe_id": step["recipe_id"],
        "skip_yn": step["skip_yn"],
        "chg_tm": step["chg_tm"],
        "ctn_desc": step["oper_desc"],
        # 이름째로 넘깁니다 — count_points 가 Dummy/Align 을 거릅니다.
        **para_block(count_points(params)),
    }


def _summarize(
    lot_cd: str,
    fac_id: str,
    ctn_desc: str,
    recipes: list[RecipeInfoRow],
) -> SummaryRow:
    total_recipe = len(recipes)
    avail_recipe = sum(1 for row in recipes if _is_measuring(row["skip_yn"]))
    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        **para_block({
            key: sum(row[key] for row in recipes) for key in PARA_BUCKETS
        }),
        "ctn_desc": ctn_desc,
        "total_recipe": total_recipe,
        "avail_recipe": avail_recipe,
        "avail_recipe_percent": _percent(avail_recipe, total_recipe),
    }


def _empty_bucket(include_recipes: bool) -> TrendBucket:
    bucket: dict[str, list] = {}
    for name in RCP_BUCKETS:
        if include_recipes:
            bucket[f"{name}_rcp_info"] = []
        bucket[f"{name}_summary"] = []
    return bucket  # type: ignore[return-value]


def _live_bucket(lot_cds: list[str], include_recipes: bool) -> TrendBucket:
    """현재 상태로 계산한 한 주차 bucket.

    스냅샷이 아직 없는 **이번 주차** 에만 씁니다. 과거 주차를 이 값으로 채우면
    없는 변화를 지어내게 되므로 하지 않습니다.
    """
    index = _lot_index()
    meta = _lot_meta()
    bucket = _empty_bucket(include_recipes)

    for lot_cd in lot_cds:
        fac_id = index.get(lot_cd, "")
        if not fac_id:
            continue
        ctn_desc = meta.get(lot_cd, {}).get("ctn_desc", "")
        steps = _steps_for(lot_cd, fac_id)
        params_by_recipe, mothers_by_recipe, _ = _idp_parameters(
            [s["recipe_id"] for s in steps]
        )

        for name, members in _bucket_members(steps, mothers_by_recipe).items():
            recipes = [
                _recipe_row(
                    lot_cd, fac_id, step,
                    _params_for_bucket(
                        name, step["recipe_id"], params_by_recipe, mothers_by_recipe
                    ),
                )
                for step in members
            ]
            if include_recipes:
                bucket[f"{name}_rcp_info"].extend(recipes)  # type: ignore[literal-required]
            bucket[f"{name}_summary"].append(  # type: ignore[literal-required]
                _summarize(lot_cd, fac_id, ctn_desc, recipes)
            )
    return bucket


def _week_anchor(day: date) -> date:
    """그 주의 월요일. 주차 키는 항상 월요일 ISO 날짜입니다."""
    return day - timedelta(days=day.weekday())


def _weekly_dates(points: int, interval_days: int) -> list[str]:
    latest = _week_anchor(datetime.now(KST).date())
    return [
        (latest - timedelta(days=interval_days * offset)).isoformat()
        for offset in range(points - 1, -1, -1)
    ]


def _snapshot_key(date_key: str) -> str:
    return f"{MINIO_BASE}/{date_key}.json"


def _is_missing_object(exc: Exception) -> bool:
    """MinIO 의 "없음"(NoSuchKey) 인가 — 권한/네트워크 오류와 구분합니다.

    사무실 자격증명은 user/<사번>/ prefix 밖에서 NotFound 가 아니라
    **AccessDenied** 를 돌려주므로, 그것을 "없음"으로 오해하면 경로 오타가
    조용히 빈 트렌드로 나타납니다.
    """
    code = getattr(exc, "code", "") or ""
    return str(code) in ("NoSuchKey", "NoSuchObject")


def _read_snapshot(date_key: str) -> dict[str, Any] | None:
    """주차 스냅샷 JSON. 없으면 None (아직 적재되지 않은 주차)."""
    from minio_handler import MinioObject  # office 전용 의존성 — 지연 import

    key = _snapshot_key(date_key)
    try:
        payload = MinioObject().get_json(key)
    except Exception as exc:  # noqa: BLE001 — 아래에서 "없음"만 걸러냅니다
        if _is_missing_object(exc):
            return None
        raise LookupError(f"MinIO read failed for {key!r}: {exc}") from exc
    return payload if isinstance(payload, dict) else None


def _bucket_from_snapshot(
    payload: dict[str, Any],
    lot_cds: list[str],
    include_recipes: bool,
) -> TrendBucket:
    """스냅샷 payload 를 요청된 lot 으로 좁혀 bucket 으로 만듭니다.

    스냅샷은 summary 전용이므로 ``include_recipes=True`` 여도 ``*_rcp_info`` 는
    빈 리스트입니다 — recipe-statistics 는 최신 날짜만 읽고 그 날짜는 라이브로
    계산되므로 실제로는 이 경로를 타지 않습니다.
    """
    wanted = set(lot_cds)
    bucket = _empty_bucket(include_recipes)
    summaries = payload.get("summaries", {})
    for name in RCP_BUCKETS:
        rows = summaries.get(name, [])
        bucket[f"{name}_summary"] = [  # type: ignore[literal-required]
            row for row in rows
            if isinstance(row, dict) and row.get("lot_cd") in wanted
        ]
    return bucket


def get_weekly_trend_data(
    lot_cds: list[str] | None = None,
    points: int = DEFAULT_TREND_POINTS,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    include_recipes: bool = True,
) -> dict[str, TrendBucket]:
    """ISO 날짜 -> bucket. 과거는 MinIO 스냅샷, 이번 주차는 라이브 계산.

    스냅샷이 없는 과거 주차는 **키 자체를 넣지 않습니다**. 빈 bucket 을 넣으면
    트렌드 차트가 0 으로 내려꽂혀 "그 주에는 측정이 없었다"는 거짓을 그립니다.
    """
    selected = _resolve_lots(lot_cds)
    dates = _weekly_dates(points, interval_days)
    current = dates[-1] if dates else None

    trend: dict[str, TrendBucket] = {}
    for date_key in dates:
        if date_key == current:
            trend[date_key] = _live_bucket(selected, include_recipes)
            continue
        payload = _read_snapshot(date_key)
        if payload is None:
            continue
        trend[date_key] = _bucket_from_snapshot(payload, selected, include_recipes)
    return trend


# ───────────────────────── 스냅샷 적재 (스케줄러) ─────────────────────────


def build_weekly_snapshot(date_key: str | None = None) -> dict[str, Any]:
    """이번 주차 스냅샷 payload — **모든 device 의 summary 만**.

    읽기 쪽(:func:`_bucket_from_snapshot`)과 형태가 갈라지지 않도록 생성도 이
    모듈이 합니다. ``*_rcp_info`` 는 일부러 담지 않습니다(모듈 docstring).
    """
    anchor = date_key or _week_anchor(datetime.now(KST).date()).isoformat()
    bucket = _live_bucket(_resolve_lots(None), include_recipes=False)
    return {
        "date": anchor,
        # timespec="seconds", matching snapshot_store.py. 마이크로초까지
        # 찍으면 같은 필드가 두 provider 에서 다른 길이의 문자열이 됩니다.
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "summaries": {
            name: bucket[f"{name}_summary"]  # type: ignore[literal-required]
            for name in RCP_BUCKETS
        },
    }


def write_weekly_snapshot(date_key: str | None = None) -> str:
    """주차 스냅샷을 MinIO 에 올리고 그 key 를 돌려줍니다.

    스케줄러의 유일한 진입점입니다 — 주 1회(월요일) 이것만 부르면 됩니다. 같은
    주차를 다시 불러도 덮어쓰므로 재실행에 안전합니다.
    """
    from minio_handler import MinioObject  # office 전용 의존성 — 지연 import

    payload = build_weekly_snapshot(date_key)
    key = _snapshot_key(payload["date"])
    MinioObject().put_json(key, payload)
    _LOG.info(
        "device_statistics: wrote weekly snapshot %s (%d lots)",
        key, len(payload["summaries"].get("all", [])),
    )
    return key


def sweep_weekly_snapshots(keep_weeks: int = 26) -> int:
    """가장 최근 ``keep_weeks`` 주차만 남기고 MinIO 객체를 지웁니다.

    **key 의 날짜로 판단하며 ``last_modified`` 로 하지 않습니다.** 이미지 캐시는
    객체가 연속적으로 도착하므로 쓰기 시각이 곧 나이지만, 스냅샷은 key 가 곧
    주차입니다. 놓친 주를 메우려 재적재하면 그 객체의 ``last_modified`` 는
    오늘이 되므로, ``last_modified`` 기준 sweep 은 그 오래된 백필을 남기고
    정상적인 최근 것을 지웁니다.

    MinIO 자격증명이 prefix 로 제한되어 native lifecycle 을 걸 수 없기 때문에
    애플리케이션 쪽에서 지웁니다(docs/datatables/hitachi/device_statistics_weekly_trend.txt
    의 OFFICE-VERIFY 항목).

    **``AccessDenied`` 를 "지울 것 없음"으로 삼키지 않습니다.** 사무실 자격증명은
    허용된 prefix 밖에서 NotFound 가 아니라 AccessDenied 를 돌려주므로, 삼키면
    경로 오타가 "성공"을 보고하면서 영원히 아무것도 하지 않습니다.

    OFFICE-VERIFY: 첫 실행에서 실제로 지워지는 개수와 남는 개수.
    """
    from minio_handler import MinioObject  # office 전용 의존성 — 지연 import

    store = MinioObject()
    prefix = f"{MINIO_BASE}/"
    dated: list[str] = []
    for obj in store.list(prefix=prefix, recursive=True):
        stem = str(obj.object_name).rsplit("/", 1)[-1].removesuffix(".json")
        if _SNAPSHOT_NAME.match(stem):
            dated.append(str(obj.object_name))
    if not dated:
        return 0
    dated.sort()
    doomed = set(dated[:-keep_weeks]) if keep_weeks > 0 else set(dated)
    if not doomed:
        return 0
    # ``delete_many(doomed)`` 은 여기서 **틀립니다**. ``list()`` 가 주는
    # ``object_name`` 은 이미 클라이언트의 default_prefix 가 붙은 전체 key 인데
    # ``delete_many`` 는 그것을 ``_resolve_key()`` 로 한 번 더 감싸므로
    # ``2067928/2067928/...`` 라는 없는 key 를 지우게 됩니다. S3 DeleteObjects 는
    # 없는 key 에 오류를 내지 않으므로 errors 는 비고, "N 개 정리" 를 찍으면서
    # 실제로는 0 개를 지웁니다. 그 key 도 허용된 prefix 안이라 AccessDenied 조차
    # 나지 않습니다. 같은 함정의 설명이 msr_image/minio_cache.py 의
    # ``_default_client()`` 주석에 있습니다.
    #
    # ``delete_matching`` 은 predicate 에 ``object_name`` 을 **그대로** 넘기고
    # 그대로 지우므로 prefix 가 두 번 붙지 않습니다(minio_handler/object.py).
    # ``use_prefix(None)`` 로 눌러도 되지만, 그러면 list 보다 뒤에 와야만 맞는
    # 순서 의존이 생겨 다음 사람이 줄을 옮기면 조용히 깨집니다.
    errors = store.delete_matching(lambda key: key in doomed, prefix=prefix) or []
    if errors:
        _LOG.warning("device_statistics: %d snapshot deletions failed: %s", len(errors), errors)
    removed = len(doomed) - len(errors)
    _LOG.info("device_statistics: swept %d weekly snapshots", removed)
    return removed


# ──────────────────────────── 계측 룰 ────────────────────────────


def get_rules(fac_id: str) -> RuleVersion | None:
    """현재 룰 버전 — mock 과 같은 코드 seed(providers/rules.py)를 그대로.

    룰은 앱 내에서 편집 저장하지 않기로 결정했으므로(user-confirmed
    2026-08-04) office 별 저장소가 필요 없습니다. 룰을 바꿀 때는 rules.py 를
    고쳐 배포합니다 — 두 provider 가 한 seed 를 읽으니 집과 사무실 화면이
    갈라질 수 없습니다. 알 수 없는 fab 은 None (route 가 404 로 변환).
    """
    return _seed_rules(fac_id)


if __name__ == "__main__":
    # 사무실 스모크 테스트 — 반드시 저장소 루트에서:
    #   .venv/bin/python -m back_dev_home.ebeam.device_statistics.providers.office
    import sys

    r3 = get_r3_device_grp()
    hvm = get_device_desc()
    print(f"{RND_KEY}: {len(r3):,} rows   {HVM_KEY}: {len(hvm):,} rows")
    if not r3:
        print("R3 카탈로그가 비었습니다 — 이후 단계를 진행할 수 없습니다.")
        raise SystemExit(2)

    lot_cd = sys.argv[1] if len(sys.argv) > 1 else r3[0]["lot_cd"]
    fac_id = _lot_index().get(lot_cd, "")
    route = "R3(planstep)" if _is_r3(fac_id) else "M-fab(lot_hist)"
    print(f"\n대상 device: {lot_cd} (fac_id={fac_id}, {route} 경로)")

    steps = _steps_for(lot_cd, fac_id)
    print(f"  스텝: {len(steps)}건")
    for step in steps[:5]:
        print(
            f"    seq {step['oper_seq']:>3}/{step['samp_seq']:<2} "
            f"skip_yn={step['skip_yn']:<2} {step['oper_desc'][:40]:<40} "
            f"{step['recipe_id']}"
        )

    # mother 를 실제로 조회해서 넘깁니다 — 기본값으로 부르면 mother_normal 이
    # 늘 0 으로 나와, 진단이 "읽지 못했다" 를 "이 device 에 mother 가 없음" 처럼
    # 보여 줍니다.
    _, mothers_by_recipe, _regions = _idp_parameters([s["recipe_id"] for s in steps])
    members = _bucket_members(steps, mothers_by_recipe)
    print("\n  버킷별 스텝 수:")
    for name in RCP_BUCKETS:
        print(f"    {name:<14} {len(members[name]):>5}")
    if mothers_by_recipe is None:
        print(
            "    NOTE: 어느 recipe 에서도 Mother_Para 를 **읽지 못해** "
            f"mother_normal 이 0 입니다. 내려받은 field: {_IDP_SOURCE}"
        )
    elif not mothers_by_recipe:
        print(
            "    NOTE: Mother_Para 는 읽혔는데 True 인 recipe 가 하나도 없어 "
            "mother_normal 이 0 입니다 — 문자열('False')로 적재되고 있는지 확인."
        )

    params = get_recipe_params([lot_cd])
    print(f"\n  recipe-params: {len(params)}행 (기대: 100~200)")
    if params:
        first = params[0]
        print(
            f"    {first['recipe_id']} class={first['recipe_class']} "
            f"family={first['family']} phase={first['phase']} "
            f"params={len(first['parameters'])}"
        )
        names = {p["name"] for row in params for p in row["parameters"]}
        if names and all("_" not in name for name in names):
            print(
                "    NOTE: parameter key 에 접미사가 없습니다 — outlier·bloated "
                "recipe 뷰가 입력을 잃습니다 (OFFICE-VERIFY #3)."
            )

    trend = get_weekly_trend_data([lot_cd])
    print(f"\n  주간 트렌드: {len(trend)}개 시점 {sorted(trend)}")
    for date_key in sorted(trend):
        rows = trend[date_key]["all_summary"]
        if rows:
            print(
                f"    {date_key}  para_all={rows[0]['para_all']:>6} "
                f"avail={rows[0]['avail_recipe']}/{rows[0]['total_recipe']}"
            )

    # OFFICE-VERIFY #1 — skip_yn 의 실제 값 분포. "Y"/"N" 말고 빈 값이 얼마나
    #되는지가 `!= "Y"` 규칙이 살려 내는 스텝의 양입니다.
    distribution: dict[str, int] = {}
    for step in steps:
        key = step["skip_yn"] or "(빈 값)"
        distribution[key] = distribution.get(key, 0) + 1
    measuring = sum(1 for step in steps if _is_measuring(step["skip_yn"]))
    print(f"\n  skip_yn 분포: {distribution}")
    print(f"    != {SKIPPED!r} (진행 중): {measuring}/{len(steps)}")

    r3_rules = get_rules("R3")
    cells = len(r3_rules["cells"]) if r3_rules else 0
    print(f"\n  rules(R3): 코드 seed, cells {cells}개")
