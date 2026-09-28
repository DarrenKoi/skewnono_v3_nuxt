# TEMPLATE — copy to office.py at the office, then verify against real data.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office FDC adapter — OpenSearch ``network_fdc_cdsem``.

Returns RAW documents ascending by timestamp for one tool inside
``[start, end]``; the top-level ``providers/office.py`` dispatcher wraps them
with ``normalizers.docs_payload``. The page reads ``values`` straight off each
doc, so this adapter only fetches, validates, and orders.

Doc layout (source of truth: ``docs/datatables/hitachi/hardware_network_fdc_cdsem.txt``). Seven
fields — ``eqp_id``, ``eqp_model_cd``, ``fab_name``, ``eqp_ip``, ``fdc_key``,
``timestamp``, ``values`` — one doc = one (eqp_id, timestamp, values).
``values[0]`` repeats ``fdc_key``; the rest follows that key's layout:

* ``TemperatureEChuck``        ``[key, '0', pos('1'|'2'|'3'), temp]``
* ``SPMVoltages``              ``[key, '0', A/B/C, n, n, n, fit model, 107 nums]``
* ``LaserPower``               ``[key, '0', x1, y1, x2, y2]``
* ``ContactpinConductionInfo`` ``[key, '0', A/B/C, pin, judgment, 4 nums, counter]``

Matches ``fdc/mock.py``, which fabricates these same four shapes. CD-SEM ONLY:
``fdc`` is not in ``normalizers.CDSEM_ONLY_SERVICES``, so an HV-SEM tool just
matches no documents (a valid empty result), not an error.

Confirmed at the office (2026-07-23):
* ``network_fdc_cdsem`` is created by ``ops_index_mgmt/network_fdc_cdsem.py``
  with no explicit field mappings, so default dynamic mapping makes every string
  ``text``+``.keyword``. Exact match therefore uses ``eqp_id.keyword`` (a terms
  agg on the bare field errors on fielddata). Do NOT copy the sibling
  ``sharpness_monitor_cdsem`` (bare ``keyword`` for ``ip``) — it is externally
  managed with its own explicit mapping.
* ``timestamp`` is a real ``date``, so the bare field ranges and sorts. It is
  offset-less KST wall clock, as are the route's naive start/end, so the bounds
  compare like-for-like and the raw string reaches the chart verbatim. A stored
  ``Z`` suffix would slide the window 9h.
* Real stored eqp_ids look like ``6MCDE305`` — the Hardware tool selector must
  hand ``build_fdc_docs`` the eqp_id in the index's own spelling (its sem_list
  row) or the term matches nothing. Run this module's ``__main__`` to see the
  live mappings, the eqp_id values present, and which clause (if any) empties
  the result.

Confirmed at the office (2026-09-28, the characterization run):
* The busiest tool logs ~16.5k docs per 30 days across the four keys, so one
  capped request cannot hold a 30-day window. ``_fetch_all`` pages on the
  timestamp: a full page is complete up to its last timestamp, so the next
  page starts there.
* The ``network_fdc_cdsem`` rollover alias spans two backing indices that
  hold byte-identical copies (same ``_id``) of some docs. ``_dedupe`` drops
  them, so every count and chart point is drawn once. The same pass drops
  the docs at a page's last timestamp that the next page reads again.

At the office: fill OPENSEARCH_* in ``backend/.env``, ``cp`` both
``office_example.py`` files to ``office.py``, set
``SKEWNONO_HARDWARE_PROVIDER=office``, and run hardware/MIGRATION.md's Verify.
"""

from datetime import datetime, timedelta
from typing import Any

from backend.ebeam._office_search import (
    fetch_hits,
    query as _query,
    text as _text,
)


__all__ = ["build_fdc_docs"]


INDEX = "network_fdc_cdsem"

# eqp_id is text+keyword (default dynamic mapping), so exact match uses the
# .keyword sub-field; timestamp is a real date, so the bare field ranges+sorts.
EQP_ID_KW = "eqp_id.keyword"
TS_FIELD = "timestamp"

# The four documented FDC record shapes. An unknown key means the index grew a
# shape the frontend parser has never seen — fail rather than draw a blank chart.
KNOWN_FDC_KEYS = frozenset({
    "TemperatureEChuck",
    "SPMVoltages",
    "LaserPower",
    "ContactpinConductionInfo",
})

# Per-request cap. A request that fills it is truncated, so _fetch_all asks
# again from the page's last timestamp rather than drawing a partial history.
MAX_FDC_DOCS = 10_000

# The page's field set, listed explicitly so an ingestion field cannot ride
# along in every doc (values alone runs 107 entries on SPMVoltages). The typed
# side-fields the writer adds (temp_c, pin, counter, ...; see
# ops_index_mgmt/network_fdc_cdsem.side_fields) are for fleet aggregations and
# deliberately stay out.
SOURCE_FIELDS = [
    "eqp_id", "eqp_model_cd", "fab_name", "eqp_ip", "fdc_key", "timestamp",
    "values",
]


def _validate(doc: dict[str, Any], eqp_id: str) -> dict[str, Any]:
    """Reject a doc that would reach the chart parser malformed. Each failure
    names the equipment and field — at the office it surfaces as a 500 whose
    message is the only clue which document shape drifted."""
    doc_eqp = _text(doc.get("eqp_id"))
    if doc_eqp != eqp_id:
        raise ValueError(
            f"{INDEX}: expected eqp_id {eqp_id!r} but a hit carries "
            f"{doc_eqp!r} — check the {EQP_ID_KW} mapping."
        )
    timestamp = _text(doc.get("timestamp"))
    if not timestamp:
        raise ValueError(f"{INDEX}: doc for {eqp_id!r} has an empty timestamp.")
    fdc_key = _text(doc.get("fdc_key"))
    if fdc_key not in KNOWN_FDC_KEYS:
        raise ValueError(
            f"{INDEX}: doc for {eqp_id!r} at {timestamp} carries unknown "
            f"fdc_key {fdc_key!r} — expected one of {sorted(KNOWN_FDC_KEYS)}."
        )
    values = doc.get("values")
    if not isinstance(values, list) or not values:
        raise ValueError(
            f"{INDEX}: doc for {eqp_id!r} at {timestamp} ({fdc_key}) has "
            f"values={values!r}; expected a non-empty list."
        )
    if _text(values[0]) != fdc_key:
        raise ValueError(
            f"{INDEX}: doc for {eqp_id!r} at {timestamp} has values[0]="
            f"{values[0]!r} but fdc_key={fdc_key!r}; they must agree."
        )
    # Normalize the two fields the dispatcher and the sort read, so a
    # stringified None never reaches the page as literal "None".
    return {**doc, "timestamp": timestamp, "fdc_key": fdc_key}


def _fetch_all(eqp_id: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Every hit for one tool in ``[start, end]``, paging on the timestamp.

    Hits arrive ascending, so a page that fills the cap is complete up to its
    last timestamp; the next page starts AT that timestamp (``gte``), which
    re-reads the docs sharing it and lets ``_dedupe`` drop the repeats. Only
    the term + range + sort query proven at the office is used — no
    search_after or point-in-time, which home cannot verify.
    """
    hits: list[dict[str, Any]] = []
    cursor = start.isoformat()
    while True:
        clauses: list[dict[str, Any]] = [
            {"term": {EQP_ID_KW: eqp_id}},
            {"range": {TS_FIELD: {"gte": cursor, "lte": end.isoformat()}}},
        ]
        page = fetch_hits(
            INDEX,
            _query(clauses),
            size=MAX_FDC_DOCS,
            sort=[{TS_FIELD: {"order": "asc"}}],
            source=SOURCE_FIELDS,
        )
        hits += page
        if len(page) < MAX_FDC_DOCS:
            return hits
        last = _text(page[-1].get("timestamp"))
        if not last or last == cursor:
            raise LookupError(
                f"{INDEX}: {eqp_id} has {MAX_FDC_DOCS}+ docs at the single "
                f"timestamp {cursor!r}, so paging on the timestamp cannot advance."
            )
        cursor = last


def _dedupe(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop exact repeats of (eqp_id, fdc_key, timestamp, values), keeping the
    first. Two docs that differ in any value are both kept: only a byte-level
    copy is a duplicate."""
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for doc in docs:
        key = (
            _text(doc.get("eqp_id")),
            doc["fdc_key"],
            doc["timestamp"],
            tuple(_text(v) for v in doc["values"]),
        )
        if key not in seen:
            seen.add(key)
            out.append(doc)
    return out


def build_fdc_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Raw ``network_fdc_cdsem`` docs for one tool, ascending by timestamp.

    ``fab_name`` is deliberately NOT a filter: ``eqp_id`` is already the lookup
    identity and a tool belongs to one fab, so filtering on both would let a
    stale fab label silently empty the chart. ``eqp_id`` is never None here —
    ``normalizers.service_gate`` returns the "pick a tool" payload first.
    """
    hits = _fetch_all(eqp_id, start, end)
    docs = _dedupe([_validate(hit, eqp_id) for hit in hits])
    # OpenSearch orders by timestamp alone, leaving A/B/C and 1/2/3 docs that
    # share a second in arbitrary order. Re-sort on the mock's exact key so both
    # providers hand the chart the same sequence.
    docs.sort(key=lambda d: (d["timestamp"], d["fdc_key"], str(d["values"][2:3])))
    return docs


# --------------------------------------------------------------------------- #
# Office smoke test / diagnosis — run this module directly (see __main__).
# --------------------------------------------------------------------------- #
def _diagnose(eqp_id: str, start: datetime, end: datetime) -> None:  # pragma: no cover
    """Run the query one clause at a time so an empty pull names its own cause:
    a wrong eqp_id, a too-narrow window, or a mapping drift. ASCII-only output,
    so a cp949 Windows console never raises."""
    from backend.ebeam._office_search import client

    os_client = client()

    def _count(filters: list) -> Any:
        res = os_client.search(
            index=INDEX, body={"size": 0, "query": {"bool": {"filter": filters}}}
        )
        total = res.get("hits", {}).get("total", {})
        return total.get("value") if isinstance(total, dict) else total

    def _rng(lo: datetime, hi: datetime) -> dict:
        return {"range": {TS_FIELD: {"gte": lo.isoformat(), "lte": hi.isoformat()}}}

    print("=== FDC diagnosis: index=%s tool=%s ===" % (INDEX, eqp_id))

    # [1] mappings — the fields the query depends on.
    try:
        fm = os_client.indices.get_field_mapping(
            index=INDEX, fields="eqp_id,timestamp"
        )
        parts = []
        for per_index in fm.values():
            m = per_index.get("mappings", {})
            for f in ("eqp_id", "timestamp"):
                spec = m.get(f, {}).get("mapping", {}).get(f, {})
                subs = ", ".join((spec.get("fields") or {}).keys()) if spec else ""
                parts.append("%s=%s%s" % (
                    f, spec.get("type") if spec else "(absent)",
                    "+[%s]" % subs if subs else ""))
            break
        print("[1] mappings: %s" % "  ".join(parts))
    except Exception as exc:  # noqa: BLE001 — diagnostic path, never fatal
        print("[1] mappings FAILED: %s" % exc)

    # [2] which eqp_id values exist — is this tool among them, spelled how?
    try:
        body = {"size": 0,
                "aggs": {"ids": {"terms": {"field": EQP_ID_KW, "size": 50}}}}
        buckets = (os_client.search(index=INDEX, body=body)
                   .get("aggregations", {}).get("ids", {}).get("buckets", []))
        names = [b["key"] for b in buckets]
        print("[2] %d eqp_ids; %r present: %s" % (len(names), eqp_id, eqp_id in names))
        if names:
            print("    " + ", ".join("%s(%s)" % (b["key"], b["doc_count"])
                                     for b in buckets[:20]))
    except Exception as exc:  # noqa: BLE001
        print("[2] eqp_id terms FAILED: %s" % exc)

    # [3] the decisive test: which single clause drops the count to zero?
    wide = end - timedelta(days=365)
    eqp = {"term": {EQP_ID_KW: eqp_id}}
    probes = [
        ("eqp_id only (no time)", [eqp]),
        ("time range only (window)", [_rng(start, end)]),
        ("eqp_id + window [adapter]", [eqp, _rng(start, end)]),
        ("eqp_id + last 365 days", [eqp, _rng(wide, end)]),
    ]
    print("[3] clause isolation (window %s .. %s):"
          % (start.isoformat(), end.isoformat()))
    for label, filters in probes:
        try:
            print("    %-28s: %s docs" % (label, _count(filters)))
        except Exception as exc:  # noqa: BLE001
            print("    %-28s: ERROR %s" % (label, exc))
    print("    reading: eqp_id 0 -> tool id not stored (see [2]); eqp_id>0 &"
          " window 0 & 365d>0 -> data older than window; window>0 -> query fine.")


if __name__ == "__main__":  # pragma: no cover
    #   python -m backend.ebeam.hardware.providers.fdc.office
    # Diagnoses one tool one clause at a time, then runs the real build_fdc_docs.
    # Edit TOOL/DAYS below and run with no args (Run button / REPL / python
    # office.py); passing args overrides. Output is ASCII and stdout is UTF-8, and
    # this file reads no source files, so a cp949 Windows console never raises.
    import sys
    from collections import Counter

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # ---- EDIT: real eqp_ids look like "6MCDE305" (NOT "MCD018") ----
    TOOL = "6MCDE305"
    DAYS = 30
    tool = sys.argv[1] if len(sys.argv) > 1 else TOOL
    days = int(sys.argv[2]) if len(sys.argv) > 2 else DAYS
    window_end = datetime.now()
    window_start = window_end - timedelta(days=days)

    _diagnose(tool, window_start, window_end)

    print("\n=== build_fdc_docs (term + range + sort + validate) ===")
    try:
        pulled = build_fdc_docs(tool, None, window_start, window_end)
    except Exception as exc:  # noqa: BLE001 — show the error, keep the diagnosis
        print("build_fdc_docs raised: %s: %s" % (type(exc).__name__, exc))
        pulled = []
    print("%s  last %dd: %d docs  by key: %s"
          % (tool, days, len(pulled), dict(Counter(d["fdc_key"] for d in pulled))))
    for key in sorted(KNOWN_FDC_KEYS):
        first = next((d for d in pulled if d["fdc_key"] == key), None)
        if first is None:
            print("  %-24s (none)" % key)
        else:
            print("  %-24s ts=%r values[:8]=%s"
                  % (key, first["timestamp"], first["values"][:8]))
