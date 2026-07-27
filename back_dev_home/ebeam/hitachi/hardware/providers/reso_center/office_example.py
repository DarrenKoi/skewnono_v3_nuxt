# TEMPLATE — copy to office.py at the office, then run the Verify command.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office Reso Center adapter — faithful ``reso_center_cdsem`` docs.

RECONSTRUCTED FROM THE SCHEMA DOC, NOT COPIED FROM THE OFFICE. A working
``office.py`` has existed at the office since 2026-07-27, but it is gitignored
and never reached this repo, so this body was written from
``docs/datatables/hardware_reso_center_data.txt`` plus the sibling adapters
(``bsm`` for the query shape, ``sharpness`` for the identity hop). **Diff it
against the office copy before overwriting that copy** — `cp`-ing this file
over a working ``office.py`` would replace verified code with a reconstruction.

Source: OpenSearch alias ``reso_center_cdsem`` (CD-SEM only), office-confirmed
2026-07-27. Returns RAW documents ascending by ``(timestamp, beam_condition)``
for one tool inside ``[start, end]``; the top-level ``providers/office.py``
dispatcher wraps them with ``normalizers.docs_payload``. The panel reads fields
straight off each doc, so the field NAMES must stay identical to
``reso_center/mock.py`` — only value SHAPES are normalized here.

NOTE ``reso_center_log`` is the value of each doc's ``category`` field, NOT the
index name — it names no index, so querying it as one fails. Every .py and .md
in this repo said otherwise until 2026-07-27; the datatables doc was the only
thing that had it right, and it is the source of truth when the two disagree.

IDENTITY — this index is keyed on ``eqp_ip``, not ``eqp_id``, so the lookup goes
eqp_id -> eqp_ip -> term query, resolved against the ``sem_list`` roster exactly
as ``sharpness`` does. Deriving an IP any other way (parsing the eqp_id, a local
table) would let this page disagree with the tool-inventory view with no way to
tell which is right.

FIELD SET — exactly the 13 flat fields the mock emits. Focus Sweep was removed,
so ``Resolution_Range`` / ``Resolution_Range_Raw`` / ``Resolution_Range_Smooth``
and ``fdc_category`` are NOT returned. They are mapped ``enabled: false`` and so
still ride along in ``_source``; the explicit ``SOURCE_FIELDS`` projection is
what keeps them off the wire rather than a post-hoc delete.

``ResoDelta`` is the stored difference ``ResoIScenter - BestReso`` (>= 0) — it is
passed through as indexed and never recomputed. Recomputing would paper over an
ingestion bug that the two-line trend chart is meant to expose.

OFFICE-VERIFY on the first real run:
1. ``eqp_ip`` / ``fab_name`` match through their ``.keyword`` sub-fields. That is
   the convention for the analyzed ``text`` mappings here (``beam_shape`` does
   the same), but ``sharpness_monitor_cdsem`` proves the sibling indices do not
   agree: its ``ip`` is an explicitly-mapped bare ``keyword``. If these are bare
   keywords too, drop the ``.keyword`` suffix or the terms match nothing.
2. ``timestamp`` is offset-less KST wall clock, like the other office indices. A
   stored ``Z`` suffix slides the window 9 hours.

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env``,
``cp providers/office_example.py providers/office.py`` (the dispatcher), then
``cp providers/reso_center/office_example.py providers/reso_center/office.py``,
set ``SKEWNONO_HARDWARE_PROVIDER=office``, and run hardware/MIGRATION.md's
Verify.
"""

from datetime import datetime
from typing import Any

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi._office_search import (
    fetch_hits,
    query as _query,
    text as _text,
    ttl_cache,
)
from back_dev_home.sem_list.data import get_sem_list


__all__ = ["build_reso_center_docs"]


INDEX = "reso_center_cdsem"

# The value of each doc's `category` field — a marker, never an index name.
CATEGORY = "reso_center_log"

# Exact-match fields go through their .keyword sub-fields: the base mappings are
# analyzed `text`, so a term query on them matches nothing (OFFICE-VERIFY #1).
EQP_IP_KW = "eqp_ip.keyword"
FAB_NAME_KW = "fab_name.keyword"
TIME_FIELD = "timestamp"  # date field: drives the range filter and the sort

# One doc per (timestamp, beam_condition). Reso center is logged at BM/PM time
# over a couple of conditions, so a 30-day window is dozens of docs — this cap
# exists only so a mapping surprise cannot pull an unbounded result set.
# Truncation raises rather than silently drawing a partial history.
MAX_DOCS = 10_000

# The 13 flat fields, listed explicitly so the dropped Focus Sweep objects
# cannot ride back in and so a new ingestion column cannot either.
SOURCE_FIELDS = [
    "category",
    "CenterX",
    "CenterY",
    "BestReso",
    "ResoIScenter",
    "ResoDelta",
    "beam_condition",
    "timestamp",
    "timestamp_date",
    "eqp_ip",
    "eqp_id",
    "fac_id",
    "fab_name",
]

# Numeric scalars: the source mixes floats and numeric strings within one index
# (the same pattern beam_shape shows), so every one is coerced.
_NUMERIC_FIELDS = ("CenterX", "CenterY", "BestReso", "ResoIScenter", "ResoDelta")


def _as_float(value: Any) -> float | None:
    """Coerce a source cell (float OR numeric string) to a finite float.

    `bool` is rejected explicitly: it is an `int` subclass, so a stray `True`
    would otherwise land on a resolution chart as 1.0.
    """
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in (float("inf"), float("-inf")) else None


@ttl_cache
def _ip_by_eqp_id() -> dict[str, str]:
    """``eqp_id -> eqp_ip`` from the sem_list roster, refreshed on the shared TTL.

    Cached because every reso-center request needs it and the roster changes on
    the order of days. ``ttl_cache`` serves the previous map if a refresh fails,
    so a Redis hiccup degrades to a slightly stale IP rather than a blank page.
    """
    if get_data_provider("sem_list") != "office":
        # The roster would hand back fabricated IPs while this index holds real
        # ones: every query matches nothing and the page shows an empty chart
        # with no hint as to why. Name the cause instead.
        raise LookupError(
            f"{INDEX}: the hardware provider is 'office' but sem_list is on the "
            "mock provider, so eqp_id -> eqp_ip resolution would use fabricated "
            "IPs and match zero documents. Unset SKEWNONO_SEM_LIST_PROVIDER or "
            "set it to 'office'."
        )
    return {
        eqp_id: ip
        for row in get_sem_list()
        if (eqp_id := _text(row.get("eqp_id"))) and (ip := _text(row.get("eqp_ip")))
    }


def _resolve_ip(eqp_id: str) -> str:
    ip = _ip_by_eqp_id().get(eqp_id)
    if not ip:
        raise LookupError(
            f"{INDEX}: {eqp_id!r} has no eqp_ip in the sem_list roster, so its "
            "reso-center data cannot be located — this index keys on eqp_ip. "
            "Check the tool's row in the tool-inventory view."
        )
    return ip


def _normalize(doc: dict[str, Any], eqp_id: str, ip: str) -> dict[str, Any]:
    """One raw hit -> the mock's flat 13-field doc.

    Field names pass through untouched; only the numeric scalars are coerced.
    A doc belonging to another tool raises rather than rendering under this
    tool's name — that means the term clause matched more than intended, which
    is usually ``.keyword`` mapping drift (OFFICE-VERIFY #1).
    """
    doc_ip = _text(doc.get("eqp_ip"))
    if doc_ip and doc_ip != ip:
        raise ValueError(
            f"{INDEX}: expected eqp_ip {ip!r} for {eqp_id!r} but a hit carries "
            f"{doc_ip!r} — check the {EQP_IP_KW} term query."
        )

    timestamp = _text(doc.get("timestamp"))
    if not timestamp:
        raise ValueError(f"{INDEX}: doc for {eqp_id!r} has an empty timestamp.")

    # The query selected this tool BY IP, so the row is this tool's even when
    # the index carries no eqp_id. A present-but-different eqp_id is a genuine
    # roster/index disagreement and is caught above via eqp_ip; an absent one is
    # filled from the request so the page never renders a blank tool label.
    doc_eqp_id = _text(doc.get("eqp_id")) or eqp_id

    out: dict[str, Any] = {
        "category": _text(doc.get("category")) or CATEGORY,
        "beam_condition": _text(doc.get("beam_condition")),
        "timestamp": timestamp,
        "timestamp_date": _text(doc.get("timestamp_date")) or timestamp[:10],
        "eqp_ip": doc_ip or ip,
        "eqp_id": doc_eqp_id,
        "fac_id": _text(doc.get("fac_id")),
        "fab_name": _text(doc.get("fab_name")),
    }
    for field in _NUMERIC_FIELDS:
        out[field] = _as_float(doc.get(field))
    return out


def _check_cap(hits: list[dict[str, Any]], eqp_id: str) -> None:
    if len(hits) >= MAX_DOCS:
        raise LookupError(
            f"{INDEX}: {eqp_id} returned the full {MAX_DOCS}-doc cap for the "
            "requested window, so the result is probably truncated. Narrow the "
            "date range, or add pagination to this adapter before raising the cap."
        )


def build_reso_center_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Raw ``reso_center_cdsem`` docs for one tool, ascending by timestamp.

    ``eqp_id`` is never None here — ``normalizers.service_gate`` returns the
    empty "pick a tool" payload before the dispatcher reaches this adapter.

    ``start`` / ``end`` are the route's naive datetimes, compared against the
    index's offset-less KST wall clock, so both sides are like-for-like and the
    stored string reaches the chart verbatim (OFFICE-VERIFY #2).
    """
    ip = _resolve_ip(eqp_id)

    clauses: list[dict[str, Any]] = [
        {"term": {EQP_IP_KW: ip}},
        {"range": {TIME_FIELD: {"gte": start.isoformat(), "lte": end.isoformat()}}},
    ]
    if fab_name:
        # Stored uppercase, like the other office indices.
        clauses.append({"term": {FAB_NAME_KW: fab_name.strip().upper()}})

    hits = fetch_hits(
        INDEX,
        _query(clauses),
        size=MAX_DOCS,
        sort=[{TIME_FIELD: {"order": "asc"}}],
        source=SOURCE_FIELDS,
    )
    _check_cap(hits, eqp_id)

    docs = [_normalize(hit, eqp_id, ip) for hit in hits]

    # OpenSearch orders by timestamp alone, leaving the per-condition docs that
    # share a second in arbitrary order. Re-sort on the mock's exact key so both
    # providers hand the page the same sequence.
    docs.sort(key=lambda d: (d["timestamp"], d["beam_condition"]))
    return docs


if __name__ == "__main__":  # pragma: no cover
    # Office smoke check, no Flask / Nuxt / provider switch involved:
    #   python -m back_dev_home.ebeam.hitachi.hardware.providers.reso_center.office
    #   python -m ...providers.reso_center.office MCD018 30
    #
    # Like sharpness, this exercises TWO systems: the sem_list roster lookup and
    # the OpenSearch query. The output separates them, because "no data" and
    # "wrong IP" look identical from the chart and are fixed in different places.
    import sys
    from collections import Counter
    from datetime import timedelta

    tool = sys.argv[1] if len(sys.argv) > 1 else "MCD018"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    window_end = datetime.now()
    window_start = window_end - timedelta(days=days)

    print("--- identity ---")
    resolved_ip = _resolve_ip(tool)
    print(f"  {tool} -> eqp_ip {resolved_ip!r}  (from sem_list roster)")
    print(f"  roster size: {len(_ip_by_eqp_id())} tools with an eqp_ip")

    pulled = build_reso_center_docs(tool, None, window_start, window_end)
    print(f"\n{tool}  last {days}d: {len(pulled)} docs")
    print("by beam_condition:", dict(Counter(d["beam_condition"] for d in pulled)))

    if not pulled:
        print(
            f"\n  EMPTY. The ip resolved fine, so either {tool} logged no reso\n"
            f"  center in the last {days}d, or the stored eqp_ip is spelled\n"
            f"  differently from sem_list's ({resolved_ip!r}), or the .keyword\n"
            "  suffixes are wrong for this index (OFFICE-VERIFY #1). Check a raw\n"
            "  doc in OpenSearch Dashboards before assuming the former."
        )
        sys.exit(0)

    first = pulled[0]
    print("\n--- first doc ---")
    # Print the timestamp verbatim and confirm it carries NO offset
    # (OFFICE-VERIFY #2): a `Z` suffix means the range bounds slide 9 hours.
    print(f"  timestamp raw : {first['timestamp']!r}")
    print(f"  category      : {first['category']!r}")
    for key in _NUMERIC_FIELDS:
        print(f"  {key:<13} : {first[key]!r}")
    delta = first["ResoDelta"]
    derived = (first["ResoIScenter"] or 0) - (first["BestReso"] or 0)
    print(f"  ResoDelta stored={delta!r}  vs ResoIScenter-BestReso={derived:.2f}")
    print("  (stored value is passed through as indexed; a mismatch here is an")
    print("   ingestion bug to report, NOT something this adapter should fix)")
