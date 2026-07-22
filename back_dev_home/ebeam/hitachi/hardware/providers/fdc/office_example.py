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

* ``TemperatureEchuck``        ``[key, '0', pos('1'|'2'|'3'), temp]`` — three
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

OFFICE-VERIFY on the first real run:
1. ``timestamp`` really is offset-less. If ingestion writes a ``Z`` suffix,
   the range bounds below need the same spelling or the window silently
   slides 9 hours.
2. ``eqp_id`` is ``text`` with a ``.keyword`` subfield. If it is mapped as a
   bare ``keyword``, drop the ``.keyword`` suffix from ``EQP_ID_KW``.

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

# Exact match goes through the .keyword subfield: the base `eqp_id` mapping is
# `text` (analyzed), so a term query on it matches nothing.
EQP_ID_KW = "eqp_id.keyword"

# The four documented FDC record shapes. An unknown key means the index grew a
# shape the frontend parser has never seen — worth failing on rather than
# rendering as a blank chart.
KNOWN_FDC_KEYS = frozenset(
    {
        "TemperatureEchuck",
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
                "timestamp": {
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
        sort=[{"timestamp": {"order": "asc"}}],
        source=SOURCE_FIELDS,
    )
    _check_cap(hits, eqp_id)

    docs = [_validate(hit, eqp_id) for hit in hits]

    # OpenSearch orders by timestamp alone, which leaves the A/B/C and 1/2/3
    # position docs sharing a second in arbitrary order. Re-sort on the mock's
    # exact key so both providers hand the chart the same sequence.
    docs.sort(key=lambda d: (d["timestamp"], d["fdc_key"], str(d["values"][2:3])))
    return docs


if __name__ == "__main__":  # pragma: no cover
    # Office smoke check, no Flask / Nuxt / provider switch involved:
    #   python -m back_dev_home.ebeam.hitachi.hardware.providers.fdc.office
    #   python -m ...providers.fdc.office MCD320 30
    # MCD018 / MCD320 are the reference tools for this index (user-supplied).
    # An eqp_id does NOT encode tool family — `MCD` spans CD-SEM, HV-SEM,
    # VeritySEM and Provision — so an empty pull is ambiguous between "no data
    # in this window" and "this tool is not a CD-SEM and is therefore absent
    # from a _cdsem index". Resolve the family from the tool's sem_list row,
    # never from its id. The output below spells that out.
    #
    # The window is relative to NOW, not to the mock's 2026-05-24 anchor: this
    # runs against live ingestion, and a hardcoded historical window would
    # report an empty pull that looks identical to a broken query.
    #
    # Dumps the RAW pull per fdc_key. The contract response is a doc count and
    # one timestamp — far too small to reveal schema drift, so print the
    # timestamps verbatim and confirm they carry NO offset (see OFFICE-VERIFY
    # above): a `Z` suffix here means the range bounds slide 9 hours.
    import sys
    from collections import Counter
    from datetime import timedelta

    tool = sys.argv[1] if len(sys.argv) > 1 else "MCD018"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    window_end = datetime.now()
    window_start = window_end - timedelta(days=days)

    pulled = build_fdc_docs(tool, None, window_start, window_end)
    print(f"{tool}  last {days}d: {window_start.isoformat()} .. "
          f"{window_end.isoformat()}")
    print(f"{len(pulled)} docs  by key: {dict(Counter(d['fdc_key'] for d in pulled))}")
    if not pulled:
        print(
            f"\n  EMPTY. Either {tool} logged no FDC in the last {days}d, or it\n"
            f"  is not a CD-SEM tool at all ({INDEX} is CD-SEM only, and an\n"
            "  eqp_id does not encode the family). Look the tool up in sem_list\n"
            "  and check its eqp_model_cd — CG*/GT* is CD-SEM — before assuming\n"
            "  the query is wrong. Widen the window with: ... <tool> 90"
        )
    for key in sorted(KNOWN_FDC_KEYS):
        first = next((d for d in pulled if d["fdc_key"] == key), None)
        print(f"\n--- {key} ---")
        if first is None:
            print("  (no documents in this window)")
            continue
        print(f"  timestamp raw : {first['timestamp']!r}")
        print(f"  fab_name      : {first.get('fab_name')!r}")
        print(f"  eqp_model_cd  : {first.get('eqp_model_cd')!r}")
        print(f"  values[:12]   : {first['values'][:12]}")
        print(f"  len(values)   : {len(first['values'])}")
