"""Probe ``ebeam_tas_lot_hist`` for the M-fab half of device_statistics' steps.

device_statistics' process-step source splits by fab family:

    R3 / 연구개발  -> sknn-planstep-r3     (scripts/probes/probe_planstep_r3.py)
    M 계열 양산    -> ebeam_tas_lot_hist   (this script)

The M-fab branch differs from R3 in ways that each break a different
assumption, so each gets a stage:

* there is **no sequence field** - no oper_seq/samp_seq to sort by, and
  RecipeInfoRow demands both, so something has to fill them;
* `lot_cd` is stored directly, with no `prod_id` / `_BASE` suffix to strip;
* the step name lives in `oper_det_desc`, not `oper_desc`;
* the window is the last **3 months**, not recipe_tat's 60 days, on an index
  the datatable doc already warns is measurement-grained and very large.

That size warning is why every stage here aggregates instead of downloading
rows: "unique oper_det_desc per lot_cd" is a nested terms aggregation, not a
`range_dataframe_all` followed by a pandas groupby.

Run FROM THE REPO ROOT at the office:

    .venv/bin/python -m scripts.probes.probe_lot_hist_mfab

    # narrow to one fab, or change the window
    .venv/bin/python -m scripts.probes.probe_lot_hist_mfab --fab M14 --days 90
    .venv/bin/python -m scripts.probes.probe_lot_hist_mfab --devices 5 --recipes 8

Whatever this proves belongs in TWO places (CLAUDE.md):
``docs/datatables/hitachi/ebeam_tas_lot_hist.txt`` AND the device_statistics mock
docstrings. Mark each fact ``office 확인 YYYY-MM-DD``.

Read-only: count / search / aggregate / mapping reads only.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from pathlib import Path
# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed -- a file manager, an IDE "run this file" button and tab
# completion all produce the by-path one -- so support both.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free
# because -m imports the package first; running this file by path does not,
# and would then die on the ANSI code page. One line covers both.
import scripts  # noqa: E402,F401

from back_dev_home._runtime.office_redis import load_env_file  # noqa: E402
from back_dev_home.ebeam.device_statistics.oper_order import (  # noqa: E402
    oper_prefix,
    sort_oper_descs,
    unknown_prefixes,
)
from ops_store import OSIndex, OSSearch, create_client  # noqa: E402

# Shared with the R3 probe rather than duplicated - the `.keyword` resolution in
# particular is the trap both scripts have to get right (see that module).
from scripts.probes.probe_planstep_r3 import IDP_INDEX, _agg_field, _properties, _rule, stage_idp_join  # noqa: E402


INDEX = "ebeam_tas_lot_hist"

# user-confirmed 2026-07-30. Deliberately NOT shared with recipe_tat's 60-day
# constant: the rationale differs ("at least one process ran in the fab within
# 3 months"), so coupling them would let one screen's tuning silently move the
# other's coverage.
DEFAULT_DAYS = 90

TIME_FIELD = "event_tm"

DOCUMENTED_FIELDS = (
    "fab_id",
    "fab_name",
    "lot_cd",
    "lot_id",
    "main_oper_id",
    "oper_id",
    "oper_det_desc",
    "event_tm",
    "eqp_id",
    "recipe_id",
)

# Fields R3's planstep has that this index does not. Their absence is the
# finding, so it is asserted rather than assumed.
R3_ONLY_FIELDS = ("oper_seq", "samp_seq", "prod_id", "skip_yn", "det_fac_id")

ENUM_FIELDS = ("fab_id", "fab_name")


def _window_query(days: int, fab: str | None, fab_field: str) -> dict[str, Any]:
    """range on event_tm, optionally narrowed to one fab."""
    filters: list[dict[str, Any]] = [{"range": {TIME_FIELD: {"gte": f"now-{days}d"}}}]
    if fab:
        filters.append({"term": {fab_field: fab}})
    return {"bool": {"filter": filters}}


def stage_mapping(client: Any, props: dict[str, Any]) -> None:
    _rule(f"[1] {INDEX} - exists, size, mapping")

    if not OSIndex(client=client, index=INDEX).exists():
        print("  index/alias NOT found - nothing else can run.")
        return

    total = OSSearch(client=client, index=INDEX).count().get("count")
    print(f"  total docs (all time): {total:,}" if isinstance(total, int) else f"  total: {total}")

    print(f"\n  {'field':<18} {'mapping type':<14} {'term/agg field'}")
    print(f"  {'-' * 18} {'-' * 14} {'-' * 30}")
    missing = []
    for name in DOCUMENTED_FIELDS:
        spec = props.get(name)
        if spec is None:
            missing.append(name)
            print(f"  {name:<18} {'ABSENT':<14} -")
            continue
        print(f"  {name:<18} {str(spec.get('type')):<14} {_agg_field(props, name)}")

    if missing:
        print(f"\n  DOCUMENTED BUT ABSENT: {', '.join(missing)}")
        print("  -> fix docs/datatables/hitachi/ebeam_tas_lot_hist.txt before writing the adapter.")

    present_r3 = [name for name in R3_ONLY_FIELDS if name in props]
    print("\n  R3-only fields (expected ABSENT here):")
    for name in R3_ONLY_FIELDS:
        print(f"      {name:<14} {'PRESENT' if name in props else 'absent (as documented)'}")
    if present_r3:
        print(
            f"      -> {', '.join(present_r3)} unexpectedly EXISTS. If a sequence\n"
            "         field is really here, the 'M fab has no order' rule is wrong\n"
            "         and the adapter should sort by it instead of event_tm."
        )
    else:
        print(
            "      -> confirms no sequence field. RecipeInfoRow.oper_seq/samp_seq\n"
            "         must be synthesized (event_tm order) or the contract widened."
        )


def stage_window(search: OSSearch, props: dict[str, Any], days: int, fab: str | None) -> None:
    _rule(f"[2] the last {days} days ({TIME_FIELD})")

    fab_field = _agg_field(props, "fab_id") if "fab_id" in props else "fab_id"
    query = _window_query(days, fab, fab_field)
    scoped = search.count(query=query).get("count", 0)
    print(f"  docs in window{f' (fab_id={fab})' if fab else ''}: {scoped:,}")
    if not scoped:
        print("  -> empty window. Widen --days or check the fab value before concluding.")
        return

    for name in ENUM_FIELDS:
        if name not in props:
            print(f"\n  {name}: ABSENT - skipped")
            continue
        field = _agg_field(props, name)
        result = search.aggregate(
            {"v": {"terms": {"field": field, "size": 40}}}, query=query
        )
        buckets = result.get("aggregations", {}).get("v", {}).get("buckets", [])
        print(f"\n  {name} (via {field}): {len(buckets)} distinct in window")
        for bucket in buckets:
            print(f"      {str(bucket['key']):<20} {bucket['doc_count']:>10,}")

    # fab_id vs fab_name granularity, stated rather than assumed: the repo treats
    # fab_name as the granular key and fab_id as the coarse one.
    if "fab_id" in props and "fab_name" in props:
        agg = search.aggregate(
            {
                "by_id": {
                    "terms": {"field": _agg_field(props, "fab_id"), "size": 20},
                    "aggs": {
                        "names": {
                            "terms": {"field": _agg_field(props, "fab_name"), "size": 20}
                        }
                    },
                }
            },
            query=query,
        )
        print("\n  fab_id -> fab_name granularity:")
        for bucket in agg.get("aggregations", {}).get("by_id", {}).get("buckets", []):
            names = [
                str(n["key"]) for n in bucket.get("names", {}).get("buckets", [])
            ]
            print(f"      {str(bucket['key']):<10} -> {', '.join(names) or '(none)'}")

    sample = search.search_raw(
        {
            "size": 3,
            "query": query,
            "sort": [{TIME_FIELD: "desc"}],
            "_source": list(DOCUMENTED_FIELDS),
        }
    )
    hits = sample.get("hits", {}).get("hits", [])
    print(f"\n  newest {len(hits)} doc(s):")
    for hit in hits:
        src = hit.get("_source", {})
        print(
            f"      {src.get(TIME_FIELD)}  {src.get('fab_id')}/{src.get('fab_name')}  "
            f"lot_cd={src.get('lot_cd')}"
        )
        print(
            f"          oper_det_desc={str(src.get('oper_det_desc'))[:48]!r} "
            f"recipe_id={src.get('recipe_id')}"
        )
    suspect = [
        src.get(TIME_FIELD)
        for src in (h.get("_source", {}) for h in hits)
        if isinstance(src.get(TIME_FIELD), str)
        and (src[TIME_FIELD].endswith("Z") or "+" in src[TIME_FIELD])
    ]
    if suspect:
        print(f"      NOTE: {TIME_FIELD} carries an offset/Z ({suspect[0]!r}) - the repo")
        print("            convention is offset-less KST. Record the difference.")


def stage_steps_per_device(
    search: OSSearch, props: dict[str, Any], days: int, fab: str | None, devices: int
) -> list[str]:
    """The actual deliverable: unique oper_det_desc per lot_cd, via aggregation."""
    _rule(f"[3] unique oper_det_desc per lot_cd (top {devices} lot_cd by activity)")

    for required in ("lot_cd", "oper_det_desc"):
        if required not in props:
            print(f"  {required} ABSENT - cannot build the step list.")
            return []

    fab_field = _agg_field(props, "fab_id") if "fab_id" in props else "fab_id"
    lot_field = _agg_field(props, "lot_cd")
    desc_field = _agg_field(props, "oper_det_desc")
    recipe_field = _agg_field(props, "recipe_id") if "recipe_id" in props else None
    query = _window_query(days, fab, fab_field)

    # Nested terms, not a row download: this is the shape the adapter should use.
    aggs: dict[str, Any] = {
        "steps": {"terms": {"field": desc_field, "size": 200}},
        "distinct_steps": {"cardinality": {"field": desc_field}},
    }
    if recipe_field:
        aggs["recipes"] = {"cardinality": {"field": recipe_field}}

    result = search.aggregate(
        {"lots": {"terms": {"field": lot_field, "size": devices}, "aggs": aggs}},
        query=query,
    )
    buckets = result.get("aggregations", {}).get("lots", {}).get("buckets", [])
    if not buckets:
        print("  no lot_cd in window.")
        return []

    recipes_seen: list[str] = []
    for bucket in buckets:
        distinct = bucket.get("distinct_steps", {}).get("value")
        recipe_count = bucket.get("recipes", {}).get("value") if recipe_field else "?"
        print(
            f"\n  lot_cd {str(bucket['key']):<10} {bucket['doc_count']:>8,} row(s), "
            f"{distinct} unique oper_det_desc, {recipe_count} unique recipe_id"
        )
        for step in bucket.get("steps", {}).get("buckets", [])[:8]:
            print(f"      {str(step['key'])[:56]:<56} {step['doc_count']:>7,}")
        listed = len(bucket.get("steps", {}).get("buckets", []))
        if isinstance(distinct, int) and listed < distinct:
            print(f"      ... {distinct - listed} more not shown (terms size cap)")

        # The ordering rule, applied to real values. Printing the sorted list is
        # how the documented prefix order gets checked against the fab rather
        # than taken on faith; unlisted prefixes mean OPER_PREFIX_ORDER is stale.
        names = [str(s["key"]) for s in bucket.get("steps", {}).get("buckets", [])]
        if names:
            print("      sorted by OPER_PREFIX_ORDER:")
            for name in sort_oper_descs(names)[:8]:
                prefix = oper_prefix(name)
                print(f"          [{prefix or '?':>4}] {name[:56]}")
            unlisted = unknown_prefixes(names)
            if unlisted:
                print(
                    f"      UNLISTED PREFIX ({len(unlisted)}): "
                    f"{', '.join(unlisted[:6])}"
                )
                print(
                    "          -> these sort last. Add them to OPER_PREFIX_ORDER\n"
                    "             (oper_order.py) and to ebeam_tas_lot_hist.txt."
                )

    # Collect measured recipe_ids for the idp_ver join, reusing the R3 stage.
    if recipe_field:
        top_lot = str(buckets[0]["key"])
        rq = {
            "bool": {
                "filter": [
                    {"range": {TIME_FIELD: {"gte": f"now-{days}d"}}},
                    {"term": {lot_field: top_lot}},
                ]
            }
        }
        if fab:
            rq["bool"]["filter"].append({"term": {fab_field: fab}})
        agg = search.aggregate({"r": {"terms": {"field": recipe_field, "size": 25}}}, query=rq)
        recipes_seen = [
            str(b["key"]) for b in agg.get("aggregations", {}).get("r", {}).get("buckets", [])
        ]
        print(f"\n  recipe_id sample from lot_cd {top_lot}: {len(recipes_seen)} distinct")

    return recipes_seen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.probes.probe_lot_hist_mfab",
        description=(
            "Probe ebeam_tas_lot_hist for device_statistics' M-fab process steps "
            "(last 3 months, unique oper_det_desc per lot_cd)."
        ),
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"Window in days (default: {DEFAULT_DAYS} - the confirmed 3 months).")
    parser.add_argument("--fab", default=None, help="Narrow to one fab_id (e.g. M14).")
    parser.add_argument("--devices", type=int, default=3,
                        help="lot_cd values to break down (default: 3).")
    parser.add_argument("--recipes", type=int, default=5,
                        help=f"recipe_ids to join to {IDP_INDEX} (default: 5).")
    args = parser.parse_args(argv)

    load_env_file("OPENSEARCH_HOST")
    try:
        client = create_client()
    except Exception as err:  # 설정/연결 실패는 여기서 끝내는 편이 명확합니다
        print(f"OpenSearch is not configured or unreachable: {err}", file=sys.stderr)
        return 2

    props = _properties(client, INDEX)
    search = OSSearch(client=client, index=INDEX)

    stage_mapping(client, props)
    if not props:
        print("\nNo mapping properties resolved - stopping.")
        return 2

    stage_window(search, props, args.days, args.fab)
    recipes = stage_steps_per_device(search, props, args.days, args.fab, args.devices)
    stage_idp_join(client, recipes, args.recipes)

    _rule("NEXT")
    print(
        "  Record what this proved in BOTH places (CLAUDE.md):\n"
        "    1. docs/datatables/hitachi/ebeam_tas_lot_hist.txt (and idp_ver.txt)\n"
        "    2. device_statistics/providers/ mock docstrings\n"
        "  Open question this run should settle: what fills\n"
        "  RecipeInfoRow.oper_seq / samp_seq for M fab, given no sequence field.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
