# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 Recipe-TAT adapter backed by the office OpenSearch cluster.

Connection plumbing, the composite aggregation walker, the lot_id<->lot_cd
bridge, and the device catalogs live in the SHARED tracked module
``back_dev_home/ebeam/hitachi/_office_meas_hist.py`` (used by every
meas_hist-backed office adapter — see its docstring for the data layout,
.keyword conventions, and the KST-as-UTC timezone contract). This file only
holds the Recipe-TAT query shapes.

Each meas_hist document is one measurement execution. The TAT dashboard never
needs the raw rows — every endpoint is a server-side aggregation over
``meastime`` (the per-execution turnaround, in seconds) sliced by
``timestamp`` (the date range) and optionally ``fab_name`` / ``lot_cd``:

* ranking      — composite over ``full_name.keyword`` (the class/recipe
                 composite), ``sum(meastime)`` + ``top_hits`` per bucket.
* summary      — ``sum(meastime)`` + ``cardinality(full_name.keyword)`` +
                 ``value_count(meastime)`` over the same filter.
* daily-trend  — ``date_histogram`` (calendar day) with ``extended_bounds``
                 so empty days are zero-filled, matching the mock.
* anchor       — ``max(timestamp)`` across both aliases: the date-picker
                 ceiling (the real latest data date, NOT wall-clock).

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env``,
``cp office_example.py office.py``, set ``SKEWNONO_RECIPE_TAT_PROVIDER=office``
(or just leave it unset — this file's
existence is the switch), then run the Verify command in MIGRATION.md.
"""

from typing import Any

from back_dev_home.ebeam.hitachi._office_meas_hist import (
    CURRENT_WINDOW_DAYS as _CURRENT_WINDOW_DAYS,
    EQP_ID_KW as _EQP_KW,
    FAB_NAME_KW as _FAB_KW,
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
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    RankingRow,
    SummaryPayload,
    ToolType,
)


__all__ = [
    "get_anchor_time",
    "get_meas_hist",
    "get_ranking",
    "get_summary",
    "get_daily_trend",
    "get_devices",
]


def get_meas_hist(*args: Any, **kwargs: Any) -> Any:
    # Not used by the TAT routes (they only call the aggregation endpoints)
    # and not part of the contract gate. Raw-row export would also need the
    # lot_cd source; use the aggregation endpoints instead.
    raise NotImplementedError(
        "get_meas_hist (raw rows) is intentionally not connected for office "
        "mode — the Recipe-TAT routes use the aggregation endpoints below."
    )


def get_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None,
) -> list[RankingRow]:
    lot_ids = _lot_ids_for_lot_cd(lot_cd) if lot_cd else None
    clauses = _filter_clauses(fab_names, start_date, end_date, lot_ids)

    # Composite (not terms) so the ranking covers EVERY recipe in the range:
    # a terms agg both truncates at its size cap and, when ordered by the sum
    # sub-agg, returns approximate totals. All buckets are fetched page by
    # page, then ranked here; limit>0 trims only the final, complete ranking.
    sub_aggs = {
        "tat": {"sum": {"field": _MEAS_F}},
        "eqps": {"terms": {"field": _EQP_KW, "size": 5}},
        # A handful of lot_ids per recipe, mapped to lot_cds below.
        "lots": {"terms": {"field": _LOT_ID_KW, "size": 25}},
        "fabs": {"terms": {"field": _FAB_KW, "size": 16}},
        "top": {
            "top_hits": {
                "size": 1,
                "_source": ["class_name", "recipe_name", "full_name"],
            }
        },
    }
    buckets = _composite_buckets(_INDEX[tool_type], _FULL_KW, sub_aggs, _query(clauses))
    buckets.sort(key=lambda b: int(b.get("tat", {}).get("value") or 0), reverse=True)
    if limit > 0:
        buckets = buckets[:limit]
    # Nice-to-have: never let a lot-history hiccup break the ranking table.
    bridge = _try_bridge()

    rows: list[RankingRow] = []
    for index, bucket in enumerate(buckets):
        meas_counts = int(bucket["doc_count"])
        total = int(bucket.get("tat", {}).get("value") or 0)
        avg = round(total / meas_counts, 2) if meas_counts else 0.0
        source = (bucket.get("top", {}).get("hits", {}).get("hits") or [{}])[0].get(
            "_source", {}
        )
        eqp_buckets = bucket.get("eqps", {}).get("buckets", [])
        sample_eqps = sorted(str(b["key"]) for b in eqp_buckets)[:5]
        # Map the recipe's sample lot_ids to their lot_cds (drop unmapped).
        lot_buckets = bucket.get("lots", {}).get("buckets", [])
        sample_lot_cds = sorted(
            {bridge.get(_text(b["key"]), "") for b in lot_buckets} - {""}
        )[:5]
        fab_buckets = bucket.get("fabs", {}).get("buckets", [])
        fab_names = sorted({str(b["key"]).upper() for b in fab_buckets})

        rows.append(
            RankingRow(
                rank=index + 1,
                class_name=str(source.get("class_name", "")),
                recipe_name=str(source.get("recipe_name", "")),
                full_name=str(source.get("full_name") or bucket["key"].get("group", "")),
                meas_counts=meas_counts,
                total_meastime=total,
                avg_meastime=avg,
                sample_lot_cds=sample_lot_cds,
                sample_eqp_ids=sample_eqps,
                fab_names=fab_names,
            )
        )
    return rows


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
        "tat": {"sum": {"field": _MEAS_F}},
        "execs": {"value_count": {"field": _MEAS_F}},
        "recipes": {"cardinality": {"field": _FULL_KW}},
    }
    result = _aggregate(_INDEX[tool_type], aggs, _query(clauses))

    total_tat = int(result.get("tat", {}).get("value") or 0)
    total_executions = int(result.get("execs", {}).get("value") or 0)
    total_recipes = int(result.get("recipes", {}).get("value") or 0)
    avg = round(total_tat / total_executions, 2) if total_executions else 0.0

    return SummaryPayload(
        tool_type=tool_type,
        fab_names=list(fab_names or []),
        start_date=start_date,
        end_date=end_date,
        anchor_date=get_anchor_time().date().isoformat(),
        total_tat_seconds=total_tat,
        total_recipes=total_recipes,
        total_executions=total_executions,
        avg_meastime=avg,
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
            "aggs": {"tat": {"sum": {"field": _MEAS_F}}},
        }
    }
    result = _aggregate(_INDEX[tool_type], aggs, _query(clauses))
    buckets = result.get("by_day", {}).get("buckets", [])

    return [
        DailyTrendPoint(
            date=str(bucket["key_as_string"]),
            total_meastime=int(bucket.get("tat", {}).get("value") or 0),
            exec_count=int(bucket["doc_count"]),
        )
        for bucket in buckets
    ]


def get_devices(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> list[DeviceRow]:
    """Devices (lot_cds) with measurements in scope, ranked by total TAT.

    meas_hist_* is aggregated by ``lot_id`` within the tool/fab/date scope, each
    ``lot_id`` is mapped to its ``lot_cd`` through the lot-history bridge, and
    the per-lot sums are rolled up per device. Because the bridge only knows
    recently-active lot_ids, an in-scope ``lot_id`` with no mapping is dropped
    (keeps retired/unknown lots out).

    ``exec_count``/``total_meastime`` are the real in-scope execution count and
    summed ``meastime`` per device. Metadata follows the mock's exactly-one
    rule: R3/R&D devices carry ``prod_catg_cd`` (from ``r3_device_grp``),
    M-fab devices carry ``tech_nm`` (from ``device_desc``).
    """
    clauses = _filter_clauses(fab_names, start_date, end_date)
    # Composite pagination (see composite_buckets): every in-scope lot_id,
    # not a top-N — a capped terms agg would drop lots (and thus understate
    # or lose whole devices) on fleet-wide date ranges.
    lot_buckets = _composite_buckets(
        _INDEX[tool_type],
        _LOT_ID_KW,
        {"tat": {"sum": {"field": _MEAS_F}}},
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
        agg = rolled.setdefault(lot_cd, {"exec": 0, "tat": 0})
        agg["exec"] += int(bucket["doc_count"])
        agg["tat"] += int(bucket.get("tat", {}).get("value") or 0)

    rows: list[DeviceRow] = []
    for lot_cd, agg in rolled.items():
        # Exactly one of the pair: R3/R&D -> prod_catg_cd, M-fab -> tech_nm.
        prod_catg_cd = r3.get(lot_cd)
        tech_nm = None if prod_catg_cd else (catalog.get(lot_cd, {}).get("tech_nm") or None)
        rows.append(
            DeviceRow(
                lot_cd=lot_cd,
                exec_count=agg["exec"],
                total_meastime=agg["tat"],
                prod_catg_cd=prod_catg_cd,
                tech_nm=tech_nm,
            )
        )
    rows.sort(key=lambda r: (r["total_meastime"], r["exec_count"]), reverse=True)
    return rows


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.hitachi.recipe_tat.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # The shared client loads back_dev_home/.env itself if the env isn't set.
    from datetime import timedelta

    anchor = get_anchor_time()
    end = anchor.date().isoformat()
    start = (anchor.date() - timedelta(days=30)).isoformat()
    print(f"anchor (latest data date): {anchor.isoformat()}")

    for tool in ("cd-sem", "hv-sem"):
        summary = get_summary(tool, None, start, end)  # type: ignore[arg-type]
        ranking = get_ranking(tool, None, start, end, limit=5)  # type: ignore[arg-type]
        trend = get_daily_trend(tool, None, start, end)  # type: ignore[arg-type]
        print(
            f"\n[{tool}] {start}..{end}  "
            f"execs={summary['total_executions']}  "
            f"recipes={summary['total_recipes']}  "
            f"total_tat={summary['total_tat_seconds']}s  "
            f"avg={summary['avg_meastime']}s"
        )
        for row in ranking:
            print(
                f"  #{row['rank']:>2} {row['full_name']:<28} "
                f"counts={row['meas_counts']:>5} total={row['total_meastime']:>8}s"
            )
        if trend:
            print(f"  daily-trend points: {len(trend)} ({trend[0]['date']}..{trend[-1]['date']})")

    # /devices needs BOTH Redis (device_desc) and ebeam_tas_lot_hist. Guard it
    # so the OpenSearch results above still print if Redis isn't configured.
    try:
        devices = get_devices("cd-sem", None, start, end)  # type: ignore[arg-type]
        print(f"\ndevices (current, last {_CURRENT_WINDOW_DAYS}d ∩ device_desc): {len(devices)}")
        for dev in devices[:5]:
            print(f"  {dev['lot_cd']:<14} exec={dev['exec_count']:>5} tech_nm={dev['tech_nm']}")
    except Exception as exc:  # noqa: BLE001 — smoke test, surface & continue
        print(f"\ndevices: skipped ({type(exc).__name__}: {exc})")
