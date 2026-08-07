# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 fail-issue adapter backed by the office OpenSearch cluster.

Reads ``align_fail`` / ``fail_ratio`` directly from the meas_hist_* aliases
(one document per measurement execution) and performs the same aggregations
as the mock natively in OpenSearch — per MIGRATION.md this must NOT be
implemented by joining on recipe_tat's output.

Connection plumbing, the composite aggregation walker, the lot_id<->lot_cd
bridge, and the device catalogs are shared with recipe_tat via
``back_dev_home/ebeam/hitachi/_office_meas_hist.py`` (see its docstring for
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

* summary       — one filtered query: ``value_count(meastime)`` (executions)
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
                  ``avg(fail_ratio)`` over the FULL group (not just fails).
* devices       — composite over ``lot_id.keyword`` with align/meas filter
                  sub-aggs, rolled up per lot_cd through the bridge, joined
                  with the exactly-one metadata rule (R3 ``prod_catg_cd`` vs
                  M-fab ``tech_nm``), sorted by combined fail count.

At the office: fill in OPENSEARCH_* / REDIS_* in ``back_dev_home/.env``,
then ``cp office_example.py office.py`` — that file's existence is the
switch, no env var needed — and run the Verify command in MIGRATION.md. recipe_tat's office.py must be
re-copied from ITS template in the same pull (both now import the shared
module).
"""

from typing import Any

from back_dev_home.ebeam.hitachi._office_meas_hist import (
    EQP_ID_KW as _EQP_KW,
    FULL_NAME_KW as _FULL_KW,
    INDEX as _INDEX,
    LOT_ID_KW as _LOT_ID_KW,
    MEAS_FIELD as _MEAS_F,
    TIME_FIELD as _TIME_F,
    aggregate as _aggregate,
    composite_buckets as _composite_buckets,
    device_desc as _device_desc,
    filter_clauses as _filter_clauses,
    get_anchor_time,
    lot_id_to_lot_cd as _lot_id_to_lot_cd,
    lot_ids_for_lot_cd as _lot_ids_for_lot_cd,
    query as _query,
    r3_device_grp as _r3_device_grp,
    text as _text,
    try_bridge as _try_bridge,
)
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    MeasRankingRow,
    SummaryPayload,
)
# Single source for the threshold — pinned by the YAML contract; importing it
# (instead of redefining 0.15 here) makes Phase 1/2 disagreement impossible.
from back_dev_home.ebeam.hitachi.fail_issue.providers.mock import (
    MEAS_FAIL_THRESHOLD,
)
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import ToolType


__all__ = [
    "MEAS_FAIL_THRESHOLD",
    "get_anchor_time",
    "get_summary",
    "get_daily_trend",
    "get_align_ranking",
    "get_meas_ranking",
    "get_devices",
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


def _rate(count: int, total: int) -> float:
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
        "execs": {"value_count": {"field": _MEAS_F}},
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
    # x-axis (mirrors the mock's backfill). extended_bounds needs both ends.
    if start_date and end_date:
        histogram["extended_bounds"] = {"min": start_date, "max": end_date}

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
        "ratio": {"avg": {"field": "fail_ratio"}},
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
                avg_fail_ratio=round(
                    float(bucket.get("ratio", {}).get("value") or 0.0), 4
                ),
                sample_eqp_ids=_sample_eqp_ids(bucket),
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
        # Exactly one of the pair: R3/R&D -> prod_catg_cd, M-fab -> tech_nm.
        prod_catg_cd = r3.get(lot_cd)
        tech_nm = None if prod_catg_cd else (catalog.get(lot_cd, {}).get("tech_nm") or None)
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


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.hitachi.fail_issue.providers.office
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
