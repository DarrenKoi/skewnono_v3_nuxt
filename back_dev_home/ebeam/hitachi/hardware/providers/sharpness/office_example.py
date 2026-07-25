# TEMPLATE — copy to office.py at the office, then verify against real data.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office sharpness adapter — OpenSearch ``sharpness_monitor_cdsem``.

Returns RAW documents ascending by timestamp for one tool inside
``[start, end]``; the top-level ``providers/office.py`` dispatcher wraps them
with ``normalizers.docs_payload``. SharpnessPanel reads the nested objects
straight off each doc, so nothing here interprets a measurement — this adapter
resolves identity, fetches, validates, and orders, and that is all.

Doc layout (source of truth: ``docs/datatables/sharpness_monitor_cdsem.txt``).
The index carries exactly eight fields, user-confirmed 2026-07-22:

* ``ip`` (keyword)      — the ONLY tool identity (see IDENTITY below).
* ``timestamp`` (date)  — tool clock; what the page plots and what we filter on.
* ``os_inserted`` (date)— ingest time; carried for lag diagnosis, never filtered.
* ``beam_condition``    — object; ``SEM_Cond_No`` + ``Vacc`` are paired and are
                          what the page groups by, plus ``Vsup`` (worth watching),
                          ``Serial_No``, ``Ip``, ``Optics``, ``Detector``, ``AL3_*``.
* ``reso_detector``     — object keyed "0.0".."337.5" step 22.5, values ~0.005.
* ``noise``             — same keys, values ~6.10.
* ``reso_eb``           — same keys, values ~8.00.
* ``summ_beam``         — object of float scalars: Ellipticity, Major Axis,
                          Minor Axis, Offset, Tilt, x_range, y_range.

All three per-degree objects are projected, not curated down to the one that
looks most useful: which profile is the real lever on tool condition is still
open, so the page offers all three as radar metrics and the engineer chooses.
Three 16-key objects per doc is a few thousand floats over a 30-day window —
cheap next to closing off a comparison someone needs.

Matches ``sharpness/mock.py``, which fabricates this same field set.

IDENTITY — why this adapter is not shaped like ``fdc/office_example.py``.
``network_fdc_cdsem`` carries ``eqp_id`` and can be term-queried with the id the
Hardware tool selector supplies. This index carries no ``eqp_id`` at all, only
``ip``, so the lookup has to go eqp_id -> eqp_ip -> ``ip``. The eqp_id/eqp_ip
pairing lives in the sem_list roster (``sem_list.data.get_sem_list()``), the same
source behind the tool-inventory view and the same one ``storage`` and
``lateral_recipe`` resolve against. Deriving an IP any other way — parsing the
eqp_id, a local table — would let this page disagree with the inventory view
with no way to tell which is right. ``ip`` is mapped ``keyword``, so it takes a
bare term query; no ``.keyword`` suffix, unlike FDC's analyzed ``eqp_id``.

CD-SEM ONLY, and already enforced upstream: ``sharpness`` is in
``normalizers.CDSEM_ONLY_SERVICES``, so ``service_gate`` returns the
"CD-SEM 장비에서만 제공됩니다" payload before the dispatcher reaches this adapter.
An HV-SEM tool therefore never gets here, which means an empty result from this
function is unambiguous: the tool is a CD-SEM and simply logged nothing in the
window.

Timestamps: ``timestamp`` is handled exactly as every other office index here —
offset-less KST wall clock (``2026-06-17T09:20:00``) — and the route's
``start``/``end`` are naive datetimes on the same wall clock, so the range bounds
compare like-for-like and the raw string reaches the frontend verbatim. No
``+09:00`` tagging, unlike ``lateral_recipe``, which tags because it emits a
*parsed* field.

OFFICE-VERIFY on the first real run:
1. ``timestamp`` really is offset-less. A ``Z`` suffix in the stored value means
   the range bounds below silently slide 9 hours.
2. ``ip`` matches sem_list's ``eqp_ip`` character-for-character — a bare dotted
   quad on both sides, no port, no hostname, no zero-padding difference. A
   mismatch here returns zero hits, not an error.
3. ``beam_condition.SEM_Cond_No`` / ``Vacc`` really are paired: **5 -> 500 and
   6 -> 800**. The page's condition selector is built from that pair, and the
   panel defaults to the condition whose ``Vacc == 800`` — i.e. cond 6.
   (This line previously said 5/800 and 6/500, a positional misreading of
   docs/datatables/sharpness_monitor_cdsem.txt, which lists the two value sets
   in opposite order. ``sharpness/mock.py`` had it right all along.)

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env``,
``cp providers/office_example.py providers/office.py`` (the dispatcher), then
``cp providers/sharpness/office_example.py providers/sharpness/office.py``, set
``SKEWNONO_HARDWARE_PROVIDER=office``, and run the Verify command in
hardware/MIGRATION.md.
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


__all__ = ["build_network_sharpness_docs"]


INDEX = "sharpness_monitor_cdsem"

# `ip` is mapped `keyword`, so the term query goes against the field directly.
IP_FIELD = "ip"

# The index's complete field set. Listed explicitly rather than left as None so
# a new ingestion field cannot silently start riding along in every doc — each
# doc already carries three 16-key objects, and this payload is handed to the
# SPA whole.
SOURCE_FIELDS = [
    "ip",
    "timestamp",
    "os_inserted",
    "beam_condition",
    "reso_detector",
    "noise",
    "reso_eb",
    "summ_beam",
]

# The per-degree objects the page can plot as radars, and the paired keys it
# groups by. Validated per doc because an empty object renders as a blank chart
# rather than an error, which is far harder to trace back to ingestion.
PROFILE_FIELDS = ("reso_eb", "noise", "reso_detector")
CONDITION_KEYS = ("SEM_Cond_No", "Vacc")

# Single non-paginated request. The monitor runs every 6~8h and emits one doc
# per condition pair, so a 30-day window over one tool is ~250 docs — three
# orders of magnitude under this cap. Hitting it means that assumption broke,
# so truncation raises rather than silently drawing a partial history.
MAX_SHARPNESS_DOCS = 10_000


@ttl_cache
def _ip_by_eqp_id() -> dict[str, str]:
    """``eqp_id -> eqp_ip`` from the sem_list roster, refreshed on the shared TTL.

    Cached because every sharpness request needs it and the roster changes on
    the order of days, not seconds. ``ttl_cache`` serves the previous map if a
    refresh fails, so a Redis hiccup degrades to a slightly stale IP rather than
    a blank page.
    """
    if get_data_provider("sem_list") != "office":
        # The roster would be fabricated IPs while this index holds real ones:
        # every query would match nothing and the page would show an empty chart
        # with no hint as to why. Name the cause instead.
        raise LookupError(
            f"{INDEX}: the hardware provider is 'office' but sem_list is on the "
            "mock provider, so eqp_id -> ip resolution would use fabricated "
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
            "sharpness data cannot be located — this index keys on ip only. "
            "Check the tool's row in the tool-inventory view."
        )
    return ip


def _validate(doc: dict[str, Any], eqp_id: str, ip: str) -> dict[str, Any]:
    """Reject a doc that would reach the page malformed.

    Every failure names the equipment and the offending field: at the office
    these surface as a 500 on one tool's sharpness tab, and the message is the
    only clue about which document shape drifted. The alternative — letting a
    missing object through — is a blank radar with no error anywhere.
    """
    doc_ip = _text(doc.get("ip"))
    if doc_ip != ip:
        raise ValueError(
            f"{INDEX}: expected ip {ip!r} for {eqp_id!r} but a hit carries "
            f"{doc_ip!r} — check the {IP_FIELD} term query."
        )

    timestamp = _text(doc.get("timestamp"))
    if not timestamp:
        raise ValueError(f"{INDEX}: doc for {eqp_id!r} has an empty timestamp.")

    condition = doc.get("beam_condition")
    if not isinstance(condition, dict):
        raise ValueError(
            f"{INDEX}: doc for {eqp_id!r} at {timestamp} has beam_condition="
            f"{condition!r}; expected an object."
        )
    missing = [key for key in CONDITION_KEYS if condition.get(key) is None]
    if missing:
        raise ValueError(
            f"{INDEX}: doc for {eqp_id!r} at {timestamp} is missing "
            f"beam_condition {missing} — the page's condition selector is built "
            "from the (SEM_Cond_No, Vacc) pair."
        )

    for field in (*PROFILE_FIELDS, "summ_beam"):
        value = doc.get(field)
        if not isinstance(value, dict) or not value:
            raise ValueError(
                f"{INDEX}: doc for {eqp_id!r} at {timestamp} has {field}="
                f"{value!r}; expected a non-empty object."
            )

    # Normalize only the field the sort below and the dispatcher read, so a
    # stringified None never reaches the page as literal "None" text.
    return {**doc, "timestamp": timestamp}


def _check_cap(hits: list[dict[str, Any]], eqp_id: str) -> None:
    if len(hits) >= MAX_SHARPNESS_DOCS:
        raise LookupError(
            f"{INDEX}: {eqp_id} returned the full {MAX_SHARPNESS_DOCS}-doc cap "
            "for the requested window, so the result is probably truncated. "
            "Narrow the date range, or add pagination/downsampling to this "
            "adapter before raising the cap."
        )


def build_network_sharpness_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Raw ``sharpness_monitor_cdsem`` docs for one tool, ascending by timestamp.

    ``fab_name`` is accepted for dispatcher signature parity and deliberately
    unused: the index has no fab field to filter on, and the tool's own ``ip``
    is already a unique identity. The payload's fab label comes from
    ``normalizers.docs_payload``, not from these docs.

    ``eqp_id`` is never None here — ``normalizers.service_gate`` returns the
    empty "pick a tool" payload before the dispatcher reaches this adapter.
    """
    ip = _resolve_ip(eqp_id)

    clauses: list[dict[str, Any]] = [
        {"term": {IP_FIELD: ip}},
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
        size=MAX_SHARPNESS_DOCS,
        sort=[{"timestamp": {"order": "asc"}}],
        source=SOURCE_FIELDS,
    )
    _check_cap(hits, eqp_id)

    docs = [_validate(hit, eqp_id, ip) for hit in hits]

    # OpenSearch orders by timestamp alone, which leaves the condition-pair docs
    # sharing a second in arbitrary order. Re-sort on the mock's exact key so
    # both providers hand the page the same sequence.
    #
    # NUMERIC, matching sharpness/mock.py. This used to coerce with str(), which
    # sorts "10" before "5" — so a two-digit SEM_Cond_No made the two providers
    # emit different orders for identical data, defeating the very purpose of
    # this line. _validate() has already coerced SEM_Cond_No to an int, so the
    # str() was not guarding against a None or a stringified value either.
    docs.sort(key=lambda d: (d["timestamp"], d["beam_condition"]["SEM_Cond_No"]))
    return docs


if __name__ == "__main__":  # pragma: no cover
    # Office smoke check, no Flask / Nuxt / provider switch involved:
    #   python -m back_dev_home.ebeam.hitachi.hardware.providers.sharpness.office
    #   python -m ...providers.sharpness.office MCD018 30
    #
    # This one exercises TWO systems, not one: the sem_list roster lookup and
    # the OpenSearch query. The output separates them, because "no data" and
    # "wrong IP" look identical from the chart and are fixed in different places.
    #
    # An eqp_id does NOT encode tool family — `MCD` spans CD-SEM, HV-SEM,
    # VeritySEM and Provision — so pick a tool that sem_list shows as CD-SEM;
    # this index holds nothing else. The window is relative to NOW, not the
    # mock's 2026-05-24 anchor: against live ingestion a hardcoded historical
    # window returns an empty pull indistinguishable from a broken query.
    import sys
    from collections import Counter
    from datetime import timedelta

    tool = sys.argv[1] if len(sys.argv) > 1 else "MCD018"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    window_end = datetime.now()
    window_start = window_end - timedelta(days=days)

    print(f"--- identity ---")
    resolved_ip = _resolve_ip(tool)
    print(f"  {tool} -> ip {resolved_ip!r}  (from sem_list roster)")
    print(f"  roster size: {len(_ip_by_eqp_id())} tools with an eqp_ip")

    pulled = build_network_sharpness_docs(tool, None, window_start, window_end)
    print(f"\n{tool}  last {days}d: {window_start.isoformat()} .. "
          f"{window_end.isoformat()}")
    conditions = Counter(
        f"{d['beam_condition'].get('SEM_Cond_No')}/{d['beam_condition'].get('Vacc')}"
        for d in pulled
    )
    print(f"{len(pulled)} docs  by SEM_Cond_No/Vacc: {dict(conditions)}")

    if not pulled:
        print(
            f"\n  EMPTY. The ip resolved fine, so either {tool} logged no\n"
            f"  sharpness in the last {days}d, or the stored `ip` is spelled\n"
            f"  differently from sem_list's eqp_ip ({resolved_ip!r}). Check a\n"
            "  raw doc in OpenSearch Dashboards before assuming the former.\n"
            "  Widen the window with: ... <tool> 90"
        )
        sys.exit(0)

    first = pulled[0]
    print("\n--- first doc ---")
    # Print timestamps verbatim and confirm they carry NO offset (OFFICE-VERIFY
    # #1): a `Z` suffix here means the range bounds slide 9 hours.
    print(f"  timestamp raw  : {first['timestamp']!r}")
    print(f"  os_inserted raw: {first.get('os_inserted')!r}   (ingest lag check)")
    print(f"  beam_condition : {first['beam_condition']}")
    print(f"  summ_beam      : {first['summ_beam']}")
    for field in PROFILE_FIELDS:
        profile = first[field]
        degrees = sorted(profile, key=float)
        print(f"  {field:<14}: {len(profile)} keys "
              f"{degrees[:3]}..{degrees[-1:]}  e.g. {profile[degrees[0]]!r}")
