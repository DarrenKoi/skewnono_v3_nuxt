# TEMPLATE — copy to office.py at the office, then verify against real data.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office FDC adapter — OpenSearch ``network_fdc_cdsem``.

Returns RAW documents ascending by timestamp for one tool inside
``[start, end]``; the top-level ``providers/office.py`` dispatcher wraps them
with ``normalizers.docs_payload``. The page's chart selectors read ``values``
straight off each doc, so nothing here interprets the measurements — this
adapter fetches, validates, and orders, and that is all.

Doc layout (source of truth: ``docs/datatables/network_fdc_cdsem.txt``). The
index carries exactly seven fields — ``eqp_id``, ``eqp_model_cd``,
``fab_name``, ``eqp_ip``, ``fdc_key``, ``timestamp``, ``values`` — and one doc
= one (eqp_id, timestamp, values). ``values[0]`` repeats ``fdc_key`` and the
rest follows that key's own layout:

* ``TemperatureEChuck``        ``[key, '0', pos('1'|'2'|'3'), temp]`` — three
  chuck positions sampled on a cycle, each landing on its own timestamp.
* ``SPMVoltages``              ``[key, '0', A/B/C, n, n, n, judgment, ~100
  numbers]`` — the judgment is a string (``spline``, ``quartic``, …); the
  numbers between the A/B/C slot and the judgment vary and are not yet
  understood, so they are passed through untouched.
* ``LaserPower``               ``[key, '0', x1, y1, x2, y2]`` — two pairs on
  deliberately different scales, both believed meaningful.
* ``ContactpinConductionInfo`` ``[key, '0', A/B/C, n, judgment, 5 numbers]`` —
  judgment is ``Conduction`` / ``NotConduction``, decided by the tool.

Matches ``fdc/mock.py``, which fabricates these same four shapes.

CD-SEM ONLY. The index name says ``_cdsem`` and no HV-SEM FDC data has been
gathered yet. The dispatcher does not gate ``fdc`` on tool family (``fdc`` is
absent from ``normalizers.CDSEM_ONLY_SERVICES``) and this builder is not
handed ``tool_slug``, so an HV-SEM tool simply matches no documents and gets a
valid empty result rather than an error. If HV-SEM FDC is ever ingested under
its own index, select the index by tool family here.

Timestamps: ``timestamp`` is an offset-less KST wall-clock string
(``2026-06-17T09:20:00``) and the route's ``start``/``end`` are naive
datetimes anchored to the same wall clock, so the range bounds compare
like-for-like and the raw string reaches the frontend verbatim — exactly what
the mock does. No ``+09:00`` tagging here, unlike ``lateral_recipe``, which
had to tag because it emits a *parsed* field.

MAPPING — the whole query hinges on this. ``network_fdc_cdsem`` is created by
``ops_index_mgmt/network_fdc_cdsem.py``, whose ``build_mappings()`` declares NO
explicit mapping for ``eqp_id`` / ``fab_name`` / ``fdc_key`` / ``timestamp``.
They fall through to OpenSearch default dynamic mapping, which maps a string as
``text`` WITH a ``keyword`` sub-field. So exact match goes through ``.keyword``.
(Do NOT copy the sibling ``sharpness_monitor_cdsem``, whose ``ip`` is a bare
``keyword`` — that index is externally managed with its own explicit mapping;
its convention does not carry here.)

CONFIRMED AT THE OFFICE (2026-07-23), so these are settled, not open questions:
1. ``eqp_id`` is ``text`` + ``.keyword`` — a terms agg on the bare field errors
   (fielddata disabled), so ``EQP_ID_KW`` (``eqp_id.keyword``) is REQUIRED.
2. ``timestamp`` is a real ``date`` — the bare ``TS_FIELD`` range/sort is
   correct; there is no ``.keyword`` on it.
3. The index holds data, and real stored eqp_ids look like ``6MCDE305`` — NOT
   the ``MCD018`` shape earlier comments assumed. The long-running "empty pull"
   was simply a tool id that does not exist in this index; querying a real
   eqp_id returns documents. The Hardware tool selector must therefore hand
   ``build_fdc_docs`` an eqp_id in the index's own spelling (its sem_list row),
   or the term matches nothing.

The smoke test still prints the live mappings and doc count on every run, so a
future ingestion change that alters either mapping is caught immediately.
Remaining watch item: ``timestamp`` stays offset-less — a stored ``Z`` suffix
would slide the window 9h.

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env``,
``cp providers/office_example.py providers/office.py`` (the dispatcher), then
``cp providers/fdc/office_example.py providers/fdc/office.py``, set
``SKEWNONO_HARDWARE_PROVIDER=office``, and run the Verify command in
hardware/MIGRATION.md.
"""

from datetime import datetime
from typing import Any

from back_dev_home.ebeam.hitachi._office_search import (
    fetch_hits,
    query as _query,
    text as _text,
)


__all__ = ["build_fdc_docs"]


INDEX = "network_fdc_cdsem"

# Exact match goes through the `.keyword` sub-field. `eqp_id` has no explicit
# mapping in `ops_index_mgmt/network_fdc_cdsem.py`, so default dynamic mapping
# makes it `text` + a `keyword` sub-field — `.keyword` is the exact-match field.
# (NOT a bare `keyword` like the externally-managed sibling `sharpness_monitor_cdsem`.)
EQP_ID_KW = "eqp_id.keyword"

# The field used to BOTH range-filter and sort by time. `timestamp` has no
# explicit mapping, so its type is whatever default dynamic mapping produced:
#   * a real `date`   -> this bare field is correct for range and sort;
#   * `text`+`.keyword` -> range must use `timestamp.keyword` (a bare range runs
#     against analyzed tokens and matches almost nothing), AND sort must too
#     (sorting on an analyzed `text` field ERRORS: fielddata is disabled).
# One constant drives range + sort so the two never disagree. The index script's
# docstring says ISO-8601 is NOT date-detected → `text` → `.keyword`, but that
# depends on the live cluster. Left bare (original behavior); flip to
# "timestamp.keyword" if the OFFICE-VERIFY smoke test reports `timestamp: text`.
TS_FIELD = "timestamp"

# The four documented FDC record shapes. An unknown key means the index grew a
# shape the frontend parser has never seen — worth failing on rather than
# rendering as a blank chart.
KNOWN_FDC_KEYS = frozenset(
    {
        "TemperatureEChuck",
        "SPMVoltages",
        "LaserPower",
        "ContactpinConductionInfo",
    }
)

# Single non-paginated request. A 30-day window over one tool holds a few
# thousand docs; hitting this cap means that assumption broke, so truncation
# raises instead of silently drawing a partial history (see _check_cap).
MAX_FDC_DOCS = 10_000

# The index's complete field set, user-confirmed 2026-07-22. Listed explicitly
# rather than left as None so a new ingestion field cannot silently start
# riding along in every doc — `values` alone runs ~100 entries on SPMVoltages,
# and this payload is handed to the SPA whole.
SOURCE_FIELDS = [
    "eqp_id",
    "eqp_model_cd",
    "fab_name",
    "eqp_ip",
    "fdc_key",
    "timestamp",
    "values",
]


def _validate(doc: dict[str, Any], eqp_id: str) -> dict[str, Any]:
    """Reject a doc that would reach the chart parser malformed.

    Every failure names the equipment and the offending field: at the office
    these surface as a 500 on one tool's FDC tab, and the message is the only
    clue about which document shape drifted.
    """
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

    # Normalize only the two fields the dispatcher and the sort below read, so
    # a stringified None never reaches the page as literal "None" text.
    return {**doc, "timestamp": timestamp, "fdc_key": fdc_key}


def _check_cap(hits: list[dict[str, Any]], eqp_id: str) -> None:
    if len(hits) >= MAX_FDC_DOCS:
        raise LookupError(
            f"{INDEX}: {eqp_id} returned the full {MAX_FDC_DOCS}-doc cap for "
            "the requested window, so the result is probably truncated. "
            "Narrow the date range, or add pagination/downsampling to this "
            "adapter before raising the cap."
        )


def build_fdc_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Raw ``network_fdc_cdsem`` docs for one tool, ascending by timestamp.

    ``fab_name`` is deliberately NOT an extra filter: ``eqp_id`` is already
    the lookup identity the Hardware tool selector supplies, and a tool
    belongs to one fab. Filtering on both would turn a stale fab label in the
    caller's state into a silently empty chart. The document's own
    ``fab_name`` stays in the returned source, so the page still shows where
    the tool actually lives.

    ``eqp_id`` is never None here — ``normalizers.service_gate`` returns the
    empty "pick a tool" payload before the dispatcher reaches this adapter.
    """
    clauses: list[dict[str, Any]] = [
        {"term": {EQP_ID_KW: eqp_id}},
        {
            "range": {
                TS_FIELD: {
                    "gte": start.isoformat(),
                    "lte": end.isoformat(),
                }
            }
        },
    ]

    hits = fetch_hits(
        INDEX,
        _query(clauses),
        size=MAX_FDC_DOCS,
        sort=[{TS_FIELD: {"order": "asc"}}],
        source=SOURCE_FIELDS,
    )
    _check_cap(hits, eqp_id)

    docs = [_validate(hit, eqp_id) for hit in hits]

    # OpenSearch orders by timestamp alone, which leaves the A/B/C and 1/2/3
    # position docs sharing a second in arbitrary order. Re-sort on the mock's
    # exact key so both providers hand the chart the same sequence.
    docs.sort(key=lambda d: (d["timestamp"], d["fdc_key"], str(d["values"][2:3])))
    return docs


def _describe_field_mappings() -> str:  # pragma: no cover — smoke-test only
    """Live report of how ``eqp_id`` and ``timestamp`` are actually mapped.

    These two fields decide the whole query, so the smoke test prints them on
    every run — an empty pull is then diagnosed, not guessed:

    * ``eqp_id``    ``text``+``keyword`` → ``EQP_ID_KW`` (``.keyword``) is right;
                    a bare ``keyword``     → drop the suffix.
    * ``timestamp`` ``date``              → ``TS_FIELD`` bare is right;
                    ``text``+``keyword``   → the range/sort MUST use
                    ``timestamp.keyword`` — set ``TS_FIELD = "timestamp.keyword"``.

    A field printed as ``(absent)`` means no document carries it yet, i.e. the
    index is empty — the pull is empty for lack of data, not a field-name bug.
    """
    from back_dev_home.ebeam.hitachi._office_search import client

    try:
        fm = client().indices.get_field_mapping(
            index=INDEX, fields="eqp_id,timestamp"
        )
    except Exception as exc:  # noqa: BLE001 — diagnostic path, never fatal
        return f"(could not read mapping: {exc})"
    for per_index in fm.values():
        mappings = per_index.get("mappings", {})
        parts = []
        for field in ("eqp_id", "timestamp"):
            spec = mappings.get(field, {}).get("mapping", {}).get(field, {})
            if not spec:
                parts.append(f"{field}=(absent - no docs?)")
                continue
            subs = ", ".join((spec.get("fields") or {}).keys())
            parts.append(f"{field}={spec.get('type')}" + (f"+[{subs}]" if subs else ""))
        return "  ".join(parts)
    return "(no mapping returned - wrong index or empty)"


def _diagnose(eqp_id: str, start: datetime, end: datetime) -> None:  # pragma: no cover
    """Step-by-step: why does this tool's pull come back empty?

    Runs against the live index through the adapter's own client and prints
    ASCII only, so a Korean Windows console (cp949) never raises on output.
    Each line isolates one hypothesis, so a single run names the culprit --
    a wrong eqp_id value, a too-narrow window, or a mapping/field-name drift --
    with no separate diagnostic script.
    """
    from datetime import timedelta
    from back_dev_home.ebeam.hitachi._office_search import client

    os_client = client()

    def _count(filters: list) -> Any:
        body = {"size": 0, "query": {"bool": {"filter": filters}}}
        res = os_client.search(index=INDEX, body=body)
        total = res.get("hits", {}).get("total", {})
        return total.get("value") if isinstance(total, dict) else total

    def _rng(field: str, lo: datetime, hi: datetime) -> dict:
        return {"range": {field: {"gte": lo.isoformat(), "lte": hi.isoformat()}}}

    print("=== FDC diagnosis: index=%s tool=%s ===" % (INDEX, eqp_id))

    # [1] does the index hold anything at all?
    try:
        print("[1] total docs in index: %s" % _count([]))
    except Exception as exc:  # noqa: BLE001 — diagnostic path, never fatal
        print("[1] count FAILED: %s" % exc)

    # [2] how eqp_id and timestamp are ACTUALLY mapped (decides the fields).
    print("[2] mappings: %s" % _describe_field_mappings())

    # [3] which eqp_id values exist, and is this tool among them, spelled how?
    #     A terms agg on a bare `text` field errors (fielddata off); that error
    #     is itself the signal that the value lives under `.keyword`.
    for field in (EQP_ID_KW, "eqp_id"):
        try:
            body = {"size": 0,
                    "aggs": {"ids": {"terms": {"field": field, "size": 50}}}}
            buckets = (os_client.search(index=INDEX, body=body)
                       .get("aggregations", {}).get("ids", {}).get("buckets", []))
            names = [b["key"] for b in buckets]
            print("[3] terms on %r: %d values; %r present exactly: %s"
                  % (field, len(names), eqp_id, eqp_id in names))
            if names:
                print("    " + ", ".join("%s(%s)" % (b["key"], b["doc_count"])
                                         for b in buckets[:20]))
        except Exception as exc:  # noqa: BLE001
            print("[3] terms on %r FAILED: %s" % (field, exc))

    # [4] the timestamp span, so you can see if the window even overlaps data.
    try:
        body = {"size": 0, "aggs": {
            "lo": {"min": {"field": TS_FIELD}},
            "hi": {"max": {"field": TS_FIELD}}}}
        aggs = os_client.search(index=INDEX, body=body).get("aggregations", {})
        print("[4] timestamp span: %s .. %s"
              % (aggs.get("lo", {}).get("value_as_string"),
                 aggs.get("hi", {}).get("value_as_string")))
    except Exception as exc:  # noqa: BLE001
        print("[4] timestamp span FAILED: %s" % exc)

    # [5] THE decisive test: which single clause drops the count to zero?
    wide = end - timedelta(days=365)
    probes = [
        ("eqp_id.keyword only (no time)", [{"term": {EQP_ID_KW: eqp_id}}]),
        ("eqp_id bare only (no time)", [{"term": {"eqp_id": eqp_id}}]),
        ("time range only (this window)", [_rng(TS_FIELD, start, end)]),
        ("eqp_id.keyword + this window [adapter]",
         [{"term": {EQP_ID_KW: eqp_id}}, _rng(TS_FIELD, start, end)]),
        ("eqp_id.keyword + last 365 days",
         [{"term": {EQP_ID_KW: eqp_id}}, _rng(TS_FIELD, wide, end)]),
    ]
    print("[5] clause isolation (window %s .. %s):"
          % (start.isoformat(), end.isoformat()))
    for label, filters in probes:
        try:
            print("    %-40s: %s docs" % (label, _count(filters)))
        except Exception as exc:  # noqa: BLE001
            print("    %-40s: ERROR %s" % (label, exc))
    print("    reading: both eqp_id rows 0 -> tool id not stored (see [3] spelling);")
    print("             eqp_id>0 but this-window 0 and 365d>0 -> data older than window;")
    print("             this-window>0 -> query is fine (empty page = validate/frontend).")


if __name__ == "__main__":  # pragma: no cover
    # Office diagnosis, no Flask / Nuxt / provider switch involved:
    #   python -m back_dev_home.ebeam.hitachi.hardware.providers.fdc.office
    #   python -m ...providers.fdc.office 6MCDE305 30
    #
    # Real stored eqp_ids look like `6MCDE305` (confirmed at the office
    # 2026-07-23) -- NOT `MCD018`. Use one from the [3] value list below.
    #
    # Runs the query ONE CLAUSE AT A TIME (see _diagnose) so an empty pull says
    # WHICH clause is at fault, then runs the real build_fdc_docs and dumps the
    # raw pull per fdc_key. The window is relative to NOW (live ingestion), so a
    # hardcoded historical window cannot masquerade as a broken query.
    #
    # An eqp_id does NOT encode tool family -- an empty pull can also mean the
    # tool is not a CD-SEM (this index is CD-SEM only). Resolve the family from
    # the tool's sem_list row, not its id.
    #
    # All output is ASCII and stdout is switched to UTF-8, so a Korean Windows
    # console (cp949) never raises on print. This file reads no source files, so
    # the cp949 *decode* error the separate scripts hit cannot occur here.
    import sys
    from collections import Counter
    from datetime import timedelta

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # ============================ EDIT HERE ============================
    # Set the tool and window right here, then just run the file — no
    # command-line args needed (Run button, `python office.py`, REPL).
    # Passing args still overrides: `... office 6MCDE305 90`.
    TOOL = "6MCDE305"   # a real eqp_id in network_fdc_cdsem (confirmed 2026-07-23)
    DAYS = 30
    # ==================================================================
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
    print("%s  last %dd: %s .. %s"
          % (tool, days, window_start.isoformat(), window_end.isoformat()))
    print("%d docs  by key: %s"
          % (len(pulled), dict(Counter(d["fdc_key"] for d in pulled))))
    if not pulled:
        print(
            "  EMPTY -- read the [5] clause table above for which filter is at\n"
            "  fault. If this-window > 0 there but 0 docs here, it is validate or\n"
            "  the sort, and the exception (if any) is printed just above."
        )
    for key in sorted(KNOWN_FDC_KEYS):
        first = next((d for d in pulled if d["fdc_key"] == key), None)
        print("\n--- %s ---" % key)
        if first is None:
            print("  (no documents in this window)")
            continue
        print("  timestamp raw : %r" % first["timestamp"])
        print("  fab_name      : %r" % first.get("fab_name"))
        print("  eqp_model_cd  : %r" % first.get("eqp_model_cd"))
        print("  values[:12]   : %s" % first["values"][:12])
        print("  len(values)   : %s" % len(first["values"]))
