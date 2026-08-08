"""Diagnose why the office Recipe-TAT daily trend collapses to a single point.

The adapter's aggregation is windowed to [anchor-30d, anchor] where anchor is
``max(timestamp)`` across BOTH meas_hist aliases. A single visible datum in the
chart therefore means the window is almost empty, which has three known causes:

  (a) the alias only has ~1 day of history ingested so far,
  (b) a stray future-dated document drags the anchor forward past the real
      data, leaving one populated day inside the default window,
  (c) the requested fab_name doesn't match the stored fab_name values
      (all-zero rather than single-point, but checked here anyway).

Run FROM THE REPO ROOT at the office (reads OPENSEARCH_* from
back_dev_home/.env like the adapter does):

    .venv/bin/python -m scripts.diagnose_recipe_tat_office
"""

from __future__ import annotations

import os
from datetime import timedelta

from back_dev_home._runtime.office_redis import load_env_file
from back_dev_home.ebeam.recipe_tat.providers.office import (  # type: ignore[attr-defined]
    _INDEX,
    get_anchor_time,
)
from ops_store import OSSearch, create_client


def main() -> None:
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")
    client = create_client()

    anchor = get_anchor_time()
    window_start = (anchor.date() - timedelta(days=30)).isoformat()
    print(f"adapter anchor (max timestamp, both aliases): {anchor.isoformat()}")
    print(f"default window the routes will query:         {window_start} .. {anchor.date().isoformat()}")

    for tool, index in _INDEX.items():
        search = OSSearch(client=client, index=index)
        aggs = {
            "min_ts": {"min": {"field": "timestamp"}},
            "max_ts": {"max": {"field": "timestamp"}},
            "fabs": {"terms": {"field": "fab_name.keyword", "size": 10}},
            # Unbounded histogram: the REAL distribution of data by day,
            # independent of the adapter's anchor-derived window.
            "by_day": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day",
                    "format": "yyyy-MM-dd",
                    "min_doc_count": 1,
                }
            },
        }
        result = search.aggregate(aggs, query=None).get("aggregations", {})
        total = search.count().get("count")

        print(f"\n[{tool}] alias={index}  total docs={total}")
        print(f"  timestamp span: {result.get('min_ts', {}).get('value_as_string')}"
              f" .. {result.get('max_ts', {}).get('value_as_string')}")
        fabs = result.get("fabs", {}).get("buckets", [])
        print("  fab_name values:", ", ".join(f"{b['key']}({b['doc_count']})" for b in fabs) or "(none)")

        # Raw _source timestamps (newest first): the KST sanity check. The
        # adapter assumes KST wall-clock WITHOUT an offset ("2026-07-22
        # 10:30:00" or "2026-07-22T10:30:00"). A trailing "Z"/"+09:00" or an
        # epoch number here breaks that assumption — daily buckets would then
        # be UTC days (KST days split at 09:00), and the histogram/range
        # would need time_zone handling instead.
        sample = search.search_raw({
            "size": 3,
            "sort": [{"timestamp": "desc"}],
            "_source": ["timestamp", "fab_name"],
        })
        hits = sample.get("hits", {}).get("hits", [])
        print("  newest raw timestamps:",
              ", ".join(repr(h.get("_source", {}).get("timestamp")) for h in hits) or "(none)")

        days = result.get("by_day", {}).get("buckets", [])
        print(f"  days with data: {len(days)}")
        for bucket in days[-40:]:
            print(f"    {bucket['key_as_string']}  docs={bucket['doc_count']}")


if __name__ == "__main__":
    main()
