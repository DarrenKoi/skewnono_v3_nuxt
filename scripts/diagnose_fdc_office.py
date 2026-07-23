"""Diagnose why the office FDC tab returns no data from OpenSearch.

The adapter is a chain of assumptions, and every link fails the same way from
the UI — an empty chart. This walks the chain one link at a time and prints
what it finds, so a single run says WHICH assumption is wrong:

  0. providers/fdc/office.py exists and matches the tracked template
     (a stale copy predating a fix has bitten us before — see the recipe_tat
     single-point collapse)
  1. OPENSEARCH_* config is loaded
  2. the cluster is reachable
  3. the alias `network_fdc_cdsem` EXISTS — and if not, what fdc-ish
     aliases do exist (`network_sharpness_cdsem` turned out to be a
     design-doc name that was never real, so this is not paranoia)
  4. the index has documents at all
  5. what a raw document actually looks like — real field names, verbatim
  6. how `eqp_id` is mapped (text+.keyword vs bare keyword)
  7. which eqp_id values exist, queried BOTH ways
  8. the real timestamp span and spelling (offset or not)
  9. the adapter's own query, then the adapter itself

Every check is independent: a failure prints and the run continues, so you
get the whole picture from one invocation rather than peeling one onion layer
per trip to the office.

Run FROM THE REPO ROOT at the office (reads OPENSEARCH_* from
back_dev_home/.env exactly like the adapter does):

    .venv/bin/python -m scripts.diagnose_fdc_office
    .venv/bin/python -m scripts.diagnose_fdc_office MCD320 30
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from back_dev_home._runtime.office_redis import load_env_file
from back_dev_home.ebeam.hitachi.hardware.providers.fdc import office_example
from ops_store import OSIndex, OSSearch, create_client


INDEX = office_example.INDEX
EQP_ID_FIELD = office_example.EQP_ID_FIELD


def _rule(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def _fail(label: str, exc: Exception) -> None:
    print(f"  !! {label} FAILED: {type(exc).__name__}: {exc}")


def check_adapter_copy() -> None:
    _rule("[0] providers/fdc/office.py — present? same as the template?")
    template = Path(office_example.__file__)
    live = template.with_name("office.py")
    if not live.exists():
        print(f"  !! {live} does NOT exist.")
        print("     The dispatcher falls back to fdc/mock.py, so the tab is")
        print("     serving FABRICATED data and no query is ever sent.")
        print(f"     Fix: cp {template.name} office.py  (in {template.parent})")
        return
    same = live.read_text() == template.read_text()
    print(f"  office.py exists, {live.stat().st_size} bytes")
    print(f"  identical to office_example.py: {same}")
    if not same:
        print("     ^ NOT a fresh copy. If it predates a template fix it can")
        print("       carry an old index name or query. Diff them before")
        print("       trusting anything below.")


def check_config() -> None:
    _rule("[1] OPENSEARCH_* configuration")
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")
    for key in ("OPENSEARCH_HOST", "OPENSEARCH_PORT", "OPENSEARCH_USER"):
        print(f"  {key:<18}= {os.environ.get(key) or '(unset)'}")
    pw = os.environ.get("OPENSEARCH_PASSWORD")
    print(f"  {'OPENSEARCH_PASSWORD':<18}= {'(set)' if pw else '(unset)'}")


def check_connectivity(client: Any) -> None:
    _rule("[2] cluster reachable")
    try:
        info = client.info()
        print(f"  cluster: {info.get('cluster_name')}  "
              f"version: {info.get('version', {}).get('number')}")
    except Exception as exc:
        _fail("client.info()", exc)


def check_alias(client: Any) -> bool:
    """Return True if INDEX resolves. This is the hypothesis to kill first."""
    _rule(f"[3] does {INDEX!r} exist?")
    resolved = False
    try:
        resolved = OSIndex(client=client, index=INDEX).exists()
        print(f"  exists({INDEX!r}) -> {resolved}")
    except Exception as exc:
        _fail("OSIndex.exists", exc)

    # Whether or not it resolved, show what IS there. If the name is wrong,
    # the right one is almost certainly in this list.
    for pattern in ("*fdc*", "*FDC*"):
        try:
            found = client.indices.get_alias(index=pattern)
        except Exception:
            continue
        if not found:
            continue
        print(f"\n  indices/aliases matching {pattern}:")
        for name, body in sorted(found.items()):
            aliases = sorted(body.get("aliases", {}))
            print(f"    {name}"
                  + (f"   aliases: {', '.join(aliases)}" if aliases else ""))
    if not resolved:
        print(f"\n  >> {INDEX!r} DOES NOT RESOLVE. Everything below will be")
        print("     empty for that reason alone. Compare the real names above")
        print("     against docs/datatables/network_fdc_cdsem.txt.")
    return resolved


def check_documents(search: OSSearch) -> None:
    _rule("[4/5] document count, and one raw document verbatim")
    try:
        print(f"  total docs in {INDEX}: {search.count().get('count')}")
    except Exception as exc:
        _fail("count", exc)
    try:
        raw = search.search_raw({"size": 1})
        hits = raw.get("hits", {}).get("hits", [])
        if not hits:
            print("  no documents at all — ingestion has not populated this index.")
            return
        source = hits[0].get("_source", {})
        print(f"  field names present: {sorted(source)}")
        print("  (adapter expects: eqp_id, eqp_model_cd, fab_name, eqp_ip, "
              "fdc_key, timestamp, values)")
        missing = [
            f for f in office_example.SOURCE_FIELDS if f not in source
        ]
        if missing:
            print(f"  !! adapter projects fields NOT in the doc: {missing}")
        for key, value in sorted(source.items()):
            shown = value if key != "values" else f"{str(value)[:120]}..."
            print(f"    {key:<14}= {shown!r}")
    except Exception as exc:
        _fail("search_raw", exc)


def check_eqp_id_mapping(client: Any) -> None:
    _rule("[6] how is eqp_id mapped?")
    try:
        mapping = OSIndex(client=client, index=INDEX).get_mapping()
        for name, body in mapping.items():
            props = body.get("mappings", {}).get("properties", {})
            for field in ("eqp_id", "fdc_key", "timestamp", "values"):
                spec = props.get(field)
                print(f"  [{name}] {field:<10}: {spec}")
            eqp = props.get("eqp_id", {})
            has_kw = "keyword" in eqp.get("fields", {})
            if eqp.get("type") == "keyword":
                print(f"  >> eqp_id is a BARE keyword — the adapter queries "
                      f"{EQP_ID_FIELD!r}, which is CORRECT for this mapping "
                      "(OFFICE-VERIFY #2).")
            elif has_kw:
                print(f"  >> eqp_id is text with a .keyword subfield — the "
                      f"adapter now queries the bare {EQP_ID_FIELD!r}, which "
                      "matches NOTHING here. Restore the .keyword subfield.")
            else:
                print(f"  >> eqp_id is {eqp.get('type')!r} with no keyword "
                      "subfield — it cannot be exact-matched as a term at all.")
            break
    except Exception as exc:
        _fail("get_mapping", exc)


def check_eqp_ids(search: OSSearch, tool: str) -> None:
    _rule(f"[7] which eqp_id values exist? (and is {tool!r} among them?)")
    # Query BOTH field forms so the buckets themselves reveal the mapping:
    # a bare-keyword index answers on "eqp_id" and returns nothing on
    # "eqp_id.keyword"; a text+.keyword index does the reverse.
    for field in ("eqp_id", "eqp_id.keyword"):
        try:
            aggs = {"ids": {"terms": {"field": field, "size": 40}}}
            buckets = (search.aggregate(aggs, query=None)
                       .get("aggregations", {}).get("ids", {})
                       .get("buckets", []))
            if not buckets:
                print(f"  terms on {field!r}: (no buckets)")
                continue
            keys = [b["key"] for b in buckets]
            print(f"  terms on {field!r}: {len(keys)} values")
            print(f"    {', '.join(f'{b['key']}({b['doc_count']})' for b in buckets[:15])}")
            print(f"    {tool!r} present: {tool in keys}")
        except Exception as exc:
            _fail(f"terms agg on {field}", exc)


def check_timestamps(search: OSSearch) -> None:
    _rule("[8] timestamp span and spelling")
    try:
        aggs = {
            "min_ts": {"min": {"field": "timestamp"}},
            "max_ts": {"max": {"field": "timestamp"}},
        }
        result = search.aggregate(aggs, query=None).get("aggregations", {})
        print(f"  span: {result.get('min_ts', {}).get('value_as_string')}"
              f" .. {result.get('max_ts', {}).get('value_as_string')}")
    except Exception as exc:
        _fail("min/max agg", exc)
    try:
        raw = search.search_raw(
            {"size": 3, "sort": [{"timestamp": {"order": "desc"}}]}
        )
        print("  newest raw _source timestamps (adapter assumes NO offset):")
        for hit in raw.get("hits", {}).get("hits", []):
            ts = hit.get("_source", {}).get("timestamp")
            flag = ""
            if isinstance(ts, str) and (ts.endswith("Z") or "+" in ts):
                flag = "   <<< CARRIES AN OFFSET — window slides 9h"
            print(f"    {ts!r}{flag}")
    except Exception as exc:
        _fail("sorted search_raw", exc)


def check_adapter_query(search: OSSearch, tool: str, days: int) -> None:
    _rule(f"[9] the adapter's own query for {tool}, last {days}d")
    end = datetime.now()
    start = end - timedelta(days=days)
    clauses: list[dict[str, Any]] = [
        {"term": {EQP_ID_FIELD: tool}},
        {"range": {"timestamp": {"gte": start.isoformat(),
                                 "lte": end.isoformat()}}},
    ]
    # Narrow one clause at a time: whichever addition drops the count to zero
    # is the clause that is wrong. This is THE decisive test —
    #   "eqp_id only" > 0 and "both" == 0  -> the time clause is at fault
    #   "eqp_id only" == 0                 -> the eqp_id clause is at fault
    #     (field-name mismatch — e.g. mapping is text+.keyword while the
    #      adapter sends the bare field — or this tool has no FDC data)
    wide_start = end - timedelta(days=365)
    probes = [
        ("eqp_id only, NO time filter", [clauses[0]]),
        ("eqp_id + last 365d", [
            clauses[0],
            {"range": {"timestamp": {"gte": wide_start.isoformat(),
                                     "lte": end.isoformat()}}},
        ]),
        ("timestamp range only", [clauses[1]]),
        ("both (what the adapter sends)", clauses),
    ]
    for label, body in probes:
        try:
            hits = search.search_raw(
                {"size": 0, "query": {"bool": {"filter": body}}}
            )
            total = hits.get("hits", {}).get("total", {})
            count = total.get("value") if isinstance(total, dict) else total
            print(f"  {label:<32}: {count} docs")
        except Exception as exc:
            _fail(label, exc)

    # What the ROUTE computes for a real browser request, which is not what
    # this script computes above. HardwareView sends `new Date().toISOString()`
    # — UTC with a Z — and routes._parse_iso strips the Z and keeps the naive
    # UTC clock, while stored timestamps are offset-less KST. The window the
    # office actually queries is therefore 9 hours early.
    print("\n  --- what the ROUTE computes for a browser request ---")
    browser_end = end - timedelta(hours=9)  # toISOString() of the same moment
    print(f"    this script's window : {start.isoformat()} .. {end.isoformat()}")
    print(f"    the route's window   : "
          f"{(browser_end - timedelta(days=days)).isoformat()} .. "
          f"{browser_end.isoformat()}   (9h early)")
    print("    If the two rows above return different counts, the UTC/KST")
    print("    skew is real — but it clips 9h, it cannot empty 30 days.")

    print("\n  --- calling the adapter itself ---")
    try:
        from back_dev_home.ebeam.hitachi.hardware.providers.fdc import (  # type: ignore
            office as live,
        )
    except ImportError:
        # ImportError, not ModuleNotFoundError: an absent office.py surfaces as
        # "cannot import name 'office'" from the package, which is a plain
        # ImportError and would otherwise crash the run at its last step.
        print("  providers/fdc/office.py not importable — see [0].")
        return
    try:
        docs = live.build_fdc_docs(tool, None, start, end)
        print(f"  build_fdc_docs -> {len(docs)} docs")
        if docs:
            print(f"  first: {docs[0].get('fdc_key')!r} @ "
                  f"{docs[0].get('timestamp')!r}")
    except Exception as exc:
        _fail("build_fdc_docs", exc)


def main() -> None:
    tool = sys.argv[1] if len(sys.argv) > 1 else "MCD018"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    print(f"FDC office diagnosis — index={INDEX!r} tool={tool!r} window={days}d")
    check_adapter_copy()
    check_config()

    try:
        client = create_client()
    except Exception as exc:
        _fail("create_client", exc)
        print("\nCannot continue without a client. Fix [1] first.")
        return

    check_connectivity(client)
    check_alias(client)

    search = OSSearch(client=client, index=INDEX)
    check_documents(search)
    check_eqp_id_mapping(client)
    check_eqp_ids(search, tool)
    check_timestamps(search)
    check_adapter_query(search, tool, days)


if __name__ == "__main__":
    main()
