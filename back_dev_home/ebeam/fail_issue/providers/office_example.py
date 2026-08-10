# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 fail-issue adapter backed by the office OpenSearch cluster.

Reads ``align_fail`` / ``fail_ratio`` directly from the meas_hist_* aliases
(one document per measurement execution) and performs the same aggregations
as the mock natively in OpenSearch — per MIGRATION.md this must NOT be
implemented by joining on recipe_tat's output.

Connection plumbing, the composite aggregation walker, the lot_id<->lot_cd
bridge, and the device catalogs are shared with recipe_tat via
``back_dev_home/ebeam/_office_meas_hist.py`` (see its docstring for
the data layout, .keyword conventions, and the KST-as-UTC timezone
contract). Sharing ``get_anchor_time`` also keeps the 데이터 기준 date
identical across the recipe-status page's TAT and Align/Meas tabs.

Fail criteria (identical to the mock, pinned by the YAML contract
``docs/api-contracts/fail-issue.yaml``):

* align fail — ``align_fail == "Fail"`` (``term`` on ``align_fail.keyword``;
  the third state ``"NA"`` is counted separately for the summary KPI).
* meas fail  — ``fail_ratio > MEAS_FAIL_THRESHOLD`` (strict ``gt`` range;
  the threshold is imported from the mock so Phase 1/2 can never disagree).
  Both are PERCENT, 0..100 — the scale the index stores and the contract
  carries, so the stored field is used as-is with no conversion.

Aggregation shapes per endpoint:

* summary       — one filtered query: a document count (executions; NOT
                  ``value_count(meastime)``, which omits msr_check != "Yes")
                  + ``filter`` sub-aggs for align-fail/align-NA/meas-fail +
                  ``cardinality`` for equipment/recipes; ``distinct_lots``
                  walks in-scope lot_ids and maps them through the bridge.
* daily-trend   — ``date_histogram`` (calendar day, ``extended_bounds``
                  zero-fill) with align/meas ``filter`` sub-aggs.
* align-ranking — composite over ``full_name.keyword``; per bucket an
                  align-fail ``filter`` sub-agg (with ``terms(eqp_id)``
                  inside it, because the mock samples eqp_ids from FAILING
                  rows only) + ``top_hits``. Zero-fail groups are dropped in
                  Python — a triage table, not a full recipe listing.
* meas-ranking  — same, keyed on the fail_ratio range, plus
                  ``sum(fail_ratio)`` over the FULL group (not just fails),
                  divided by the group's doc_count — see the comment there for
                  why this is not the ``avg`` aggregation.
* devices       — composite over ``lot_id.keyword`` with align/meas filter
                  sub-aggs, rolled up per lot_cd through the bridge, joined
                  with the exactly-one metadata rule (R3 ``prod_catg_cd`` vs
                  M-fab ``tech_nm``), sorted by combined fail count.
* equipments   — composite over (eqp_id, fab_name, eqp_model_cd, full_name);
                 버킷당 doc_count 와 align/meas filter 서브집계 2개.
                 지수·구간·분위수는 _shape 가 파생합니다.
* equipment-compare — 같은 필터에 eqp_id terms 를 더해 두 번 walk:
                 (eqp_id, 날짜)와 (eqp_id, full_name).

At the office: fill in OPENSEARCH_* / REDIS_* in ``back_dev_home/.env``,
then ``cp office_example.py office.py`` — that file's existence is the
switch, no env var needed — and run the Verify command in MIGRATION.md. recipe_tat's office.py must be
re-copied from ITS template in the same pull (both now import the shared
module).
"""

from typing import Any

from back_dev_home.ebeam._office_meas_hist import (
    EQP_ID_KW as _EQP_KW,
    EQP_MODEL_CD_KW as _EQP_MODEL_KW,
    FAB_NAME_KW as _FAB_KW,
    FULL_NAME_KW as _FULL_KW,
    INDEX as _INDEX,
    LOT_ID_KW as _LOT_ID_KW,
    TIME_FIELD as _TIME_F,
    aggregate as _aggregate,
    composite_buckets as _composite_buckets,
    device_desc as _device_desc,
    DOC_COUNT_AGG as _DOC_COUNT_AGG,
    filter_clauses as _filter_clauses,
    histogram_bounds as _histogram_bounds,
    get_anchor_time,
    lot_id_to_lot_cd as _lot_id_to_lot_cd,
    lot_ids_for_lot_cd as _lot_ids_for_lot_cd,
    query as _query,
    r3_device_grp as _r3_device_grp,
    text as _text,
    try_bridge as _try_bridge,
)
from back_dev_home.ebeam.fail_issue.contracts import (
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    EquipmentComparePayload,
    EquipmentsPayload,
    MeasRankingRow,
    SummaryPayload,
)
from back_dev_home.ebeam.fail_issue.providers._shape import (
    EquipmentGridRow,
    RecipeGridRow,
    TrendGridRow,
    build_equipment_compare_payload,
    build_equipments_payload,
)
# Single source for the threshold — pinned by the YAML contract; importing it
# (instead of redefining 0.15 here) makes Phase 1/2 disagreement impossible.
from back_dev_home.ebeam.fail_issue.providers.mock import (
    MEAS_FAIL_THRESHOLD,
)
from back_dev_home.ebeam.recipe_tat.contracts import ToolType


__all__ = [
    "MEAS_FAIL_THRESHOLD",
    "get_anchor_time",
    "get_summary",
    "get_daily_trend",
    "get_align_ranking",
    "get_meas_ranking",
    "get_devices",
    "get_equipments",
    "get_equipment_compare",
]


# align_fail is a text field ("Pass"/"Fail"/"NA") — exact match goes through
# the .keyword sub-field like every other text field on these indices.
_ALIGN_KW = "align_fail.keyword"

_ALIGN_FAIL_FILTER = {"term": {_ALIGN_KW: "Fail"}}
_ALIGN_NA_FILTER = {"term": {_ALIGN_KW: "NA"}}
# Strict gt, matching the mock's `fail_ratio > MEAS_FAIL_THRESHOLD`. Both
# sides are percentages (0..100), so the stored field compares directly —
# see meas_hist/providers/_shared.py for why the scale is what it is.
_MEAS_FAIL_FILTER = {"range": {"fail_ratio": {"gt": MEAS_FAIL_THRESHOLD}}}


def _rate(count: float, total: int) -> float:
    # float 도 받습니다 — avg_fail_ratio 가 sum(fail_ratio)/doc_count 로
    # 같은 나눗셈을 씁니다.
    return round(count / total, 4) if total else 0.0


def _distinct_lot_cds(tool_type: ToolType, clauses: list[dict[str, Any]]) -> int:
    """Distinct lot_cds (devices) with measurements in scope.

    ``cardinality(lot_id.keyword)`` would overcount — several lot_ids roll up
    to one lot_cd — so the in-scope lot_ids are walked exactly (composite,
    no sub-aggs) and mapped through the bridge. A KPI is a nice-to-have:
    on a bridge hiccup this degrades to 0 (logged) instead of failing the
    whole summary card, mirroring try_bridge's philosophy.
    """
    buckets = _composite_buckets(_INDEX[tool_type], _LOT_ID_KW, {}, _query(clauses))
    bridge = _try_bridge()
    return len(
        {bridge.get(_text(b["key"]["group"]), "") for b in buckets} - {""}
    )


def get_summary(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> SummaryPayload:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_names, start_date, end_date, lot_ids)

    aggs = {
        # Documents, NOT value_count(meastime). This number is both the
        # execution count and the denominator of every rate below, while the
        # numerators are filter doc_counts that include every matching
        # document. meastime is absent when msr_check != "Yes" (user-confirmed
        # 2026-08-10), so the old denominator excluded documents whose failures
        # the numerators still counted — inflating both rates, and doing it
        # worst exactly where problems cluster, since a missing MSR file is
        # itself a failure signal.
        "execs": _DOC_COUNT_AGG,
        "align_fail": {"filter": _ALIGN_FAIL_FILTER},
        "align_na": {"filter": _ALIGN_NA_FILTER},
        "meas_fail": {"filter": _MEAS_FAIL_FILTER},
        # cardinality is approximate above ~3000 distinct values — fine for
        # a KPI tile (the mock's exact set-count differs only at fleet scale).
        "eqps": {"cardinality": {"field": _EQP_KW}},
        "recipes": {"cardinality": {"field": _FULL_KW}},
    }
    result = _aggregate(_INDEX[tool_type], aggs, _query(clauses))

    total = int(result.get("execs", {}).get("value") or 0)
    align_fails = int(result.get("align_fail", {}).get("doc_count") or 0)
    align_na = int(result.get("align_na", {}).get("doc_count") or 0)
    meas_fails = int(result.get("meas_fail", {}).get("doc_count") or 0)

    return SummaryPayload(
        tool_type=tool_type,
        fab_names=list(fab_names or []),
        start_date=start_date,
        end_date=end_date,
        anchor_date=get_anchor_time().date().isoformat(),
        total_executions=total,
        align_fail_count=align_fails,
        align_fail_rate=_rate(align_fails, total),
        align_na_count=align_na,
        meas_fail_count=meas_fails,
        meas_fail_rate=_rate(meas_fails, total),
        meas_fail_threshold=MEAS_FAIL_THRESHOLD,
        distinct_equipment=int(result.get("eqps", {}).get("value") or 0),
        distinct_recipes=int(result.get("recipes", {}).get("value") or 0),
        distinct_lots=_distinct_lot_cds(tool_type, clauses),
    )


def get_daily_trend(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> list[DailyTrendPoint]:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_names, start_date, end_date, lot_ids)

    histogram: dict[str, Any] = {
        "field": _TIME_F,
        "calendar_interval": "day",
        "format": "yyyy-MM-dd",
        "min_doc_count": 0,
    }
    # Zero-fill the whole requested range so the trend chart has a continuous
    # x-axis (mirrors the mock's backfill). histogram_bounds returns None
    # unless both ends parse and are the right way round -- the mock's backfill
    # is gated the same way, and a raw unparseable bound here is an OpenSearch
    # parse error rather than a missing zero-fill.
    bounds = _histogram_bounds(start_date, end_date)
    if bounds is not None:
        histogram["extended_bounds"] = bounds

    aggs = {
        "by_day": {
            "date_histogram": histogram,
            "aggs": {
                "af": {"filter": _ALIGN_FAIL_FILTER},
                "mf": {"filter": _MEAS_FAIL_FILTER},
            },
        }
    }
    result = _aggregate(_INDEX[tool_type], aggs, _query(clauses))
    buckets = result.get("by_day", {}).get("buckets", [])

    return [
        DailyTrendPoint(
            date=str(bucket["key_as_string"]),
            exec_count=int(bucket["doc_count"]),
            align_fail_count=int(bucket.get("af", {}).get("doc_count") or 0),
            meas_fail_count=int(bucket.get("mf", {}).get("doc_count") or 0),
        )
        for bucket in buckets
    ]


def _ranked_recipe_buckets(
    tool_type: ToolType,
    clauses: list[dict[str, Any]],
    fail_sub_aggs: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    """Complete recipe buckets, ranked by (fail count, fail rate) desc.

    Composite (not terms) so every recipe in the range is counted before the
    zero-fail drop and the sort — a capped terms agg would rank a truncated
    subset. ``fail_sub_aggs`` must place the criterion under key ``"fail"``
    (a filter agg, so ``fail.doc_count`` is the group's fail count).
    """
    sub_aggs = {
        **fail_sub_aggs,
        "fabs": {"terms": {"field": _FAB_KW, "size": 16}},
        "top": {
            "top_hits": {
                "size": 1,
                "_source": ["class_name", "recipe_name", "full_name"],
            }
        },
    }
    buckets = _composite_buckets(_INDEX[tool_type], _FULL_KW, sub_aggs, _query(clauses))
    # Triage table: recipes with zero fails never appear (mock parity).
    buckets = [
        b for b in buckets if int(b.get("fail", {}).get("doc_count") or 0) > 0
    ]
    buckets.sort(
        key=lambda b: (
            int(b["fail"]["doc_count"]),
            int(b["fail"]["doc_count"]) / int(b["doc_count"]),
        ),
        reverse=True,
    )
    if limit > 0:
        buckets = buckets[:limit]
    return buckets


def _bucket_identity(bucket: dict[str, Any]) -> tuple[str, str, str]:
    source = (bucket.get("top", {}).get("hits", {}).get("hits") or [{}])[0].get(
        "_source", {}
    )
    return (
        str(source.get("class_name", "")),
        str(source.get("recipe_name", "")),
        str(source.get("full_name") or bucket["key"].get("group", "")),
    )


def _sample_eqp_ids(bucket: dict[str, Any]) -> list[str]:
    # Nested inside the "fail" filter agg — the mock samples eqp_ids from
    # FAILING rows only, not from every execution of the recipe.
    eqp_buckets = bucket.get("fail", {}).get("eqps", {}).get("buckets", [])
    return sorted(str(b["key"]) for b in eqp_buckets)[:5]


def _bucket_fab_names(bucket: dict[str, Any]) -> list[str]:
    fab_buckets = bucket.get("fabs", {}).get("buckets", [])
    return sorted({str(b["key"]).upper() for b in fab_buckets})


def get_align_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None,
) -> list[AlignRankingRow]:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_names, start_date, end_date, lot_ids)

    fail_sub_aggs = {
        "fail": {
            "filter": _ALIGN_FAIL_FILTER,
            "aggs": {"eqps": {"terms": {"field": _EQP_KW, "size": 5}}},
        }
    }
    buckets = _ranked_recipe_buckets(tool_type, clauses, fail_sub_aggs, limit)

    rows: list[AlignRankingRow] = []
    for index, bucket in enumerate(buckets):
        class_name, recipe_name, full_name = _bucket_identity(bucket)
        exec_count = int(bucket["doc_count"])
        fail_count = int(bucket["fail"]["doc_count"])
        rows.append(
            AlignRankingRow(
                rank=index + 1,
                class_name=class_name,
                recipe_name=recipe_name,
                full_name=full_name,
                exec_count=exec_count,
                align_fail_count=fail_count,
                align_fail_rate=_rate(fail_count, exec_count),
                sample_eqp_ids=_sample_eqp_ids(bucket),
                fab_names=_bucket_fab_names(bucket),
            )
        )
    return rows


def get_meas_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None,
) -> list[MeasRankingRow]:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_names, start_date, end_date, lot_ids)

    fail_sub_aggs = {
        "fail": {
            "filter": _MEAS_FAIL_FILTER,
            "aggs": {"eqps": {"terms": {"field": _EQP_KW, "size": 5}}},
        },
        # Over the FULL group, not just the failing subset (mock parity —
        # MIGRATION.md: "do not average only the fail rows").
        #
        # sum + divide by doc_count, NOT `avg`. OpenSearch's `avg` divides by
        # the documents that HAVE the field, but the row path coerces a missing
        # fail_ratio to 0.0 (`normalize_fail_ratio`; the contract types it as a
        # plain float) — so `avg` would drop a row the table shows as 0.0% and
        # the card would stop being the average of what the user can see. The
        # mock divides by every row in the group for the same reason.
        #
        # This is the OPPOSITE call from meastime, deliberately: 0 seconds is
        # not a real measurement time, so that average excludes its blanks.
        "ratio_sum": {"sum": {"field": "fail_ratio"}},
    }
    buckets = _ranked_recipe_buckets(tool_type, clauses, fail_sub_aggs, limit)

    rows: list[MeasRankingRow] = []
    for index, bucket in enumerate(buckets):
        class_name, recipe_name, full_name = _bucket_identity(bucket)
        exec_count = int(bucket["doc_count"])
        fail_count = int(bucket["fail"]["doc_count"])
        rows.append(
            MeasRankingRow(
                rank=index + 1,
                class_name=class_name,
                recipe_name=recipe_name,
                full_name=full_name,
                exec_count=exec_count,
                meas_fail_count=fail_count,
                meas_fail_rate=_rate(fail_count, exec_count),
                avg_fail_ratio=_rate(
                    float(bucket.get("ratio_sum", {}).get("value") or 0.0),
                    exec_count,
                ),
                sample_eqp_ids=_sample_eqp_ids(bucket),
                fab_names=_bucket_fab_names(bucket),
            )
        )
    return rows


def get_devices(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> list[DeviceRow]:
    """Devices (lot_cds) in scope, ranked by combined fail count.

    Same bridge/roll-up mechanics as recipe_tat's /devices (see that
    docstring), but the per-lot sums are align/meas fail counts, and the
    sort surfaces the most-problematic devices first — matching the mock's
    "which device should I look at?" ordering.
    """
    clauses = _filter_clauses(fab_names, start_date, end_date)
    lot_buckets = _composite_buckets(
        _INDEX[tool_type],
        _LOT_ID_KW,
        {
            "af": {"filter": _ALIGN_FAIL_FILTER},
            "mf": {"filter": _MEAS_FAIL_FILTER},
        },
        _query(clauses),
    )

    bridge = _lot_id_to_lot_cd()
    catalog = _device_desc()
    r3 = _r3_device_grp()

    rolled: dict[str, dict[str, int]] = {}
    for bucket in lot_buckets:
        lot_cd = bridge.get(_text(bucket["key"]["group"]))
        if not lot_cd:              # lot_id not in the recent bridge -> drop
            continue
        agg = rolled.setdefault(lot_cd, {"exec": 0, "af": 0, "mf": 0})
        agg["exec"] += int(bucket["doc_count"])
        agg["af"] += int(bucket.get("af", {}).get("doc_count") or 0)
        agg["mf"] += int(bucket.get("mf", {}).get("doc_count") or 0)

    rows: list[DeviceRow] = []
    for lot_cd, agg in rolled.items():
        # Exactly one of the pair: M-fab -> tech_nm, R3/R&D -> prod_catg_cd.
        #
        # M-fab WINS when a lot_cd sits in both catalogs (user-confirmed
        # 2026-08-10): device_desc reflects what the device is now. This used
        # to test prod_catg_cd first, so an overlapping lot showed a
        # product-category chip at the office and a tech-node chip at home —
        # the mock's lot_metadata() lets device_desc overwrite the r3 entry.
        tech_nm = catalog.get(lot_cd, {}).get("tech_nm") or None
        prod_catg_cd = None if tech_nm else (r3.get(lot_cd) or None)
        rows.append(
            DeviceRow(
                lot_cd=lot_cd,
                exec_count=agg["exec"],
                align_fail_count=agg["af"],
                meas_fail_count=agg["mf"],
                prod_catg_cd=prod_catg_cd,
                tech_nm=tech_nm,
            )
        )
    rows.sort(
        key=lambda r: r["align_fail_count"] + r["meas_fail_count"], reverse=True
    )
    return rows


def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> EquipmentsPayload:
    """장비별 집계. composite 한 번으로 표에 필요한 값이 전부 나옵니다.

    소스가 4개인 이유: fab_name 과 eqp_model_cd 는 eqp_id 에 함수 종속이라
    버킷 수를 곱하지 않고(장비 수 × 레시피 수 그대로), 대신 top_hits 서브집계
    없이 표의 fab/model 열을 채울 수 있습니다. 카티전 폭발이 아니므로
    top_hits 로 "최적화" 하지 마십시오 — 버킷당 문서를 하나씩 더 읽는 쪽이
    비쌉니다.

    지수·구간·중앙값·분위수는 파이썬에서 파생합니다 — mock 과 같은 코드
    경로를 타야 두 provider 의 숫자가 어긋나지 않습니다.

    OFFICE-VERIFY: 위 함수 종속 가정은 한 eqp_id 가 fab_name/eqp_model_cd
    각각 표기가 정확히 하나일 때만 성립합니다. 어떤 창(window) 안에서 같은
    eqp_id 가 두 가지 fab_name 또는 eqp_model_cd 표기로 나타나면 composite
    버킷이 둘로 갈라집니다 — 그런데 `_shape.py` 의 `per_tool` 딕셔너리는
    eqp_id 하나로만 키를 잡으므로, 실행·align/meas 카운트는 두 버킷이
    합산되어 그대로 맞고 fab_name/eqp_model_cd 만 먼저 도착한 버킷 쪽 값을
    조용히 남깁니다. 화면에 보이는 증상은 열 하나가 틀리는 정도가 아니라,
    표 전체의 배지가 꺼지는 것입니다 — fab_name 이 섞이면 프런트의
    `isPeerGroupComparable` 이 그 표를 비교 불가로 판정하기 때문입니다.
    `test_each_tool_belongs_to_exactly_one_fab` 는 이 상황을 잡지 못합니다 —
    그 테스트는 eqp_id 중복 행이 없는지만 확인하는데, 병합 후에는 중복이
    없기 때문입니다.

    OFFICE-VERIFY: eqp_model_cd.keyword 의 존재는 미확인입니다. 매핑에 없는
    필드를 composite 소스로 쓰면 **예외가 아니라 빈 버킷**이 나와
    /equipments 가 200 에 빈 표를 돌려줍니다("이 기간에 데이터 없음"과
    구분되지 않습니다). 자세한 대처는 _office_meas_hist.EQP_MODEL_CD_KW
    위의 주석에 있습니다.
    """
    clauses = _filter_clauses(fab_names, start_date, end_date)
    buckets = _composite_buckets(
        _INDEX[tool_type],
        [
            ("eqp", _EQP_KW),
            ("fab", _FAB_KW),
            ("model", _EQP_MODEL_KW),
            ("recipe", _FULL_KW),
        ],
        {
            "align_fails": {"filter": _ALIGN_FAIL_FILTER},
            "meas_fails": {"filter": _MEAS_FAIL_FILTER},
        },
        _query(clauses),
    )

    # 격자 타입은 조립기에서 가져옵니다 — fab 과 model 을, align 과 meas 를
    # 서로 바꿔 넣는 실수가 집에서는 테스트로 잡히지 않는 종류이기 때문입니다.
    # 2026-08-09부터 EquipmentGridRow 는 NamedTuple 이라 이름으로 채웁니다.
    grid: list[EquipmentGridRow] = [
        EquipmentGridRow(
            eqp_id=_text(b["key"]["eqp"]),
            fab_name=_text(b["key"]["fab"]),
            eqp_model_cd=_text(b["key"]["model"]),
            full_name=_text(b["key"]["recipe"]),
            exec_count=int(b["doc_count"]),
            align_fails=int(b.get("align_fails", {}).get("doc_count") or 0),
            meas_fails=int(b.get("meas_fails", {}).get("doc_count") or 0),
        )
        for b in buckets
    ]
    return build_equipments_payload(
        tool_type, fab_names, start_date, end_date, grid
    )


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...],
) -> EquipmentComparePayload:
    """선택 장비의 (장비, 날짜)·(장비, 레시피) 두 격자.

    두 격자는 서로 다른 집계 메커니즘을 씁니다. 레시피 격자는 composite
    walk 입니다 — after_key 로 페이지네이션해 정확하고 절단이 없습니다.
    날짜 격자는 composite 가 아니라 ``terms(eqp) × date_histogram(day)``
    입니다: composite 는 날짜를 **일 단위로 묶을 수 없어서**(아래 주석 참고)
    다른 메커니즘이 필요합니다.

    (eqp, 날짜, 레시피) 3중 소스 하나로 걷지 않는 이유는 여전합니다: 버킷
    수가 장비 × 일수 × 레시피로 곱해져, 90일 × 200레시피 × 5대면 9만
    버킷이고 그중 대부분이 doc_count 0 입니다. 두 번(또는 두 메커니즘으로)
    나눠 도는 쪽이 싸고, 두 격자의 쓰임이 서로 독립적입니다.
    """
    selected = list(dict.fromkeys(eqp_ids))
    if not selected:
        return build_equipment_compare_payload(
            tool_type, fab_names, start_date, end_date, [], [], []
        )

    clauses = _filter_clauses(fab_names, start_date, end_date)
    # eqp_id 는 정확 일치 키입니다 — 대문자로 정규화하지 않습니다.
    clauses = [*clauses, {"terms": {_EQP_KW: selected}}]

    sub_aggs = {
        "align_fails": {"filter": _ALIGN_FAIL_FILTER},
        "meas_fails": {"filter": _MEAS_FAIL_FILTER},
    }

    # 추이는 composite 가 아니라 terms(eqp) × date_histogram(day) 입니다.
    # composite 로는 날짜를 **일 단위로 묶을 수 없습니다**: _composite_sources 가
    # (이름, 필드) 를 언제나 {"terms": {"field": ...}} 로 감싸므로, timestamp 를
    # 소스로 주면 ns 정밀도 instant 마다 버킷이 하나씩 생깁니다. 키도 epoch
    # millis 로 나와 조립기의 "YYYY-MM-DD" 칸과 하나도 맞지 않고, 그러면 추이가
    # **예외 없이 전부 0** 이 됩니다 — 빈 데이터와 구분되지 않습니다. 게다가
    # 90일 × 5대면 버킷이 수만 개라 페이지 왕복만 수백 번입니다.
    #
    # 이 모듈에서 `terms` 가 안전한 유일한 자리입니다: 선택은 라우트에서 5개로
    # 상한이 걸려 있어(_analytics_routes.MAX_COMPARE_EQPS) `size` 가 후보를 전부
    # 덮습니다. 위의 dedupe 와 조립기의 dedupe 가 같은 규칙이라 size 는 응답이
    # 에코하는 eqp_ids 수와 정확히 일치합니다.
    #
    # date_histogram 에 format 을 주면 key_as_string 이 곧바로 "YYYY-MM-DD"
    # 이므로 문자열을 잘라 쓸 필요가 없습니다. min_doc_count 0 + extended_bounds
    # 는 조용한 날도 버킷을 내게 합니다 — get_daily_trend 와 같은 zero-fill.
    histogram: dict[str, Any] = {
        "field": _TIME_F,
        "calendar_interval": "day",
        "format": "yyyy-MM-dd",
        "min_doc_count": 0,
    }
    if start_date and end_date:
        histogram["extended_bounds"] = {"min": start_date, "max": end_date}

    trend_result = _aggregate(
        _INDEX[tool_type],
        {
            "by_eqp": {
                "terms": {"field": _EQP_KW, "size": len(selected)},
                "aggs": {"by_day": {"date_histogram": histogram, "aggs": sub_aggs}},
            }
        },
        _query(clauses),
    )
    trend_grid: list[TrendGridRow] = [
        (
            _text(eqp_bucket["key"]),
            str(day_bucket["key_as_string"]),
            int(day_bucket["doc_count"]),
            int(day_bucket.get("align_fails", {}).get("doc_count") or 0),
            int(day_bucket.get("meas_fails", {}).get("doc_count") or 0),
        )
        for eqp_bucket in trend_result.get("by_eqp", {}).get("buckets", [])
        for day_bucket in eqp_bucket.get("by_day", {}).get("buckets", [])
    ]

    recipe_buckets = _composite_buckets(
        _INDEX[tool_type],
        [("eqp", _EQP_KW), ("recipe", _FULL_KW)],
        sub_aggs,
        _query(clauses),
    )
    recipe_grid: list[RecipeGridRow] = [
        (
            _text(b["key"]["eqp"]),
            _text(b["key"]["recipe"]),
            int(b["doc_count"]),
            int(b.get("align_fails", {}).get("doc_count") or 0),
            int(b.get("meas_fails", {}).get("doc_count") or 0),
        )
        for b in recipe_buckets
    ]

    return build_equipment_compare_payload(
        tool_type, fab_names, start_date, end_date, selected,
        trend_grid, recipe_grid,
    )


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.fail_issue.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # The shared client loads back_dev_home/.env itself if the env isn't set.
    from datetime import timedelta

    anchor = get_anchor_time()
    end = anchor.date().isoformat()
    start = (anchor.date() - timedelta(days=30)).isoformat()
    print(f"anchor (latest data date): {anchor.isoformat()}")

    for tool in ("cd-sem", "hv-sem"):
        summary = get_summary(tool, None, start, end)  # type: ignore[arg-type]
        print(
            f"\n[{tool}] {start}..{end}  "
            f"execs={summary['total_executions']}  "
            f"align_fail={summary['align_fail_count']} ({summary['align_fail_rate']:.2%})  "
            f"meas_fail={summary['meas_fail_count']} ({summary['meas_fail_rate']:.2%})  "
            f"lots={summary['distinct_lots']}"
        )
        for row in get_align_ranking(tool, None, start, end, limit=5):  # type: ignore[arg-type]
            print(
                f"  align #{row['rank']:>2} {row['full_name']:<28} "
                f"fails={row['align_fail_count']:>4}/{row['exec_count']:>5} "
                f"rate={row['align_fail_rate']:.2%}"
            )
        for row in get_meas_ranking(tool, None, start, end, limit=5):  # type: ignore[arg-type]
            print(
                f"  meas  #{row['rank']:>2} {row['full_name']:<28} "
                f"fails={row['meas_fail_count']:>4}/{row['exec_count']:>5} "
                f"avg_ratio={row['avg_fail_ratio']:.3f}"
            )
        trend = get_daily_trend(tool, None, start, end)  # type: ignore[arg-type]
        if trend:
            print(f"  daily-trend points: {len(trend)} ({trend[0]['date']}..{trend[-1]['date']})")

    # /devices needs BOTH Redis (device_desc) and ebeam_tas_lot_hist. Guard it
    # so the OpenSearch results above still print if Redis isn't configured.
    try:
        devices = get_devices("cd-sem", None, start, end)  # type: ignore[arg-type]
        print(f"\ndevices: {len(devices)}")
        for dev in devices[:5]:
            print(
                f"  {dev['lot_cd']:<14} exec={dev['exec_count']:>5} "
                f"align={dev['align_fail_count']:>4} meas={dev['meas_fail_count']:>4}"
            )
    except Exception as exc:  # noqa: BLE001 — smoke test, surface & continue
        print(f"\ndevices: skipped ({type(exc).__name__}: {exc})")
