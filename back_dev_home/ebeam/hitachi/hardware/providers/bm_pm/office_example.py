# TEMPLATE — copy to office.py at the office, then verify against real data.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office BM/PM adapter — OpenSearch ``fab_inform_notes`` + ``tool_maintenance_plan``.

Two indices, one per table section (schema: ``docs/datatables/*.txt``):

* ``fab_inform_notes`` — maintenance that HAPPENED. ``down_dt``/``equp_dt`` are
  the tool's down/up times and the three free-form engineer notes
  (``note_comment``, ``zzproblem``, ``hltext``) are the substance of the tab.
* ``tool_maintenance_plan`` — maintenance that is SCHEDULED.
  ``tool_start_tm``/``tool_end_tm`` bound the planned window; ``chg_tm`` is the
  document's own timestamp.

Returns the same shape as ``bm_pm/mock.py``'s ``build_bm_pm_data``: ``past``
rows, ``future`` rows, and derived ``cards``, which the top-level
``providers/office.py`` dispatcher hands to ``normalizers.bm_pm_history_payload``.
``anchor`` is the request's ``end`` datetime.

Deliberately unread: ``up_dt`` (an expected-up field that is not maintained —
the planned side lives in ``tool_maintenance_plan``), ``fac_id`` (coarser than
fab and not a join key), and ``ll_dt``/``limit_dt``/``org_dt`` (normally empty).

UNVERIFIED until run at the office: whether these two indices store offset-less
KST wall clock like ``network_fdc_cdsem``. A stored ``Z`` suffix would slide
every window by nine hours. Run this module's ``__main__`` — it prints raw
stored values next to the reformatted ones — before trusting the tab.

At the office: fill OPENSEARCH_* in ``back_dev_home/.env``, ``cp`` this file
and ``providers/office_example.py`` to ``office.py``, set
``SKEWNONO_HARDWARE_PROVIDER=office``, and run hardware/MIGRATION.md's Verify.
"""

from datetime import datetime, timedelta
from typing import Any

from back_dev_home.ebeam.hitachi._office_search import (
    fetch_hits,
    parse_dt,
    query as _query,
    text as _text,
)
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm._shared import (
    classify_category,
    derive_cards,
    fmt_dt,
    merge_notes,
)


__all__ = ["build_bm_pm_data"]


INDEX_PAST = "fab_inform_notes"
INDEX_FUTURE = "tool_maintenance_plan"

# Both indices dynamic-map eqp_id as text+keyword, so exact match needs the
# subfield; the date fields are declared `date`, so they range and sort bare.
EQP_ID_KW = "eqp_id.keyword"
DOWN_DT = "down_dt"
PLAN_START = "tool_start_tm"

# The dispatcher passes only `anchor`, so the adapter owns its windows.
PAST_DAYS = 180
FUTURE_DAYS = 90

# One non-paginated request per side. Hitting the cap means a single tool has
# more than 1000 maintenance records in half a year — the assumption broke, so
# raise rather than silently showing a truncated history.
MAX_ROWS = 1000

# Explicit field lists so a new ingestion column cannot ride along into rows.
PAST_SOURCE = [
    "eqp_id", "down_dt", "equp_dt", "hub_load_tm", "pm_type", "eq_event",
    "lot_id", "last_recipe_id", "note_comment", "zzproblem", "hltext",
]
FUTURE_SOURCE = [
    "eqp_id", "tool_start_tm", "tool_end_tm", "chg_tm", "event_name",
    "work_item_nm", "work_user_cd",
]


def _fmt_stored(value: Any) -> str:
    """Reformat a stored OpenSearch date to the chart's ``TS_FMT``.

    Reformats only — never converts. The stored wall clock reaches the table
    verbatim, which is what keeps overlay markers aligned with chart x-values
    whichever convention the index turns out to use. An unparseable value is
    passed through as trimmed text rather than raising: a malformed *display*
    timestamp should not blank the whole tab. The two fields that order the
    tables are validated separately, in the row mappers.
    """
    raw = _text(value)
    if not raw:
        return ""
    try:
        return fmt_dt(parse_dt(raw))
    except ValueError:
        return raw


def _check_eqp(doc: dict[str, Any], eqp_id: str, index: str) -> str:
    """Fail loudly if a hit belongs to another tool.

    A mismatch means the term clause matched more than intended — usually a
    mapping drift on the ``.keyword`` subfield — and the page would otherwise
    show another tool's maintenance under this tool's name.
    """
    doc_eqp = _text(doc.get("eqp_id"))
    if doc_eqp and doc_eqp != eqp_id:
        raise ValueError(
            f"{index}: expected eqp_id {eqp_id!r} but a hit carries "
            f"{doc_eqp!r} — check the {EQP_ID_KW} mapping."
        )
    return doc_eqp or eqp_id


def past_row(doc: dict[str, Any], eqp_id: str) -> dict[str, Any]:
    """One ``fab_inform_notes`` hit as a past-work row."""
    tool = _check_eqp(doc, eqp_id, INDEX_PAST)
    job_starts = _fmt_stored(doc.get("down_dt"))
    if not job_starts:
        raise ValueError(
            f"{INDEX_PAST}: a hit for {eqp_id!r} has an empty down_dt, so it "
            "cannot be ordered or placed on the timeline."
        )
    row = {
        "eqp_id": tool,
        "job_starts": job_starts,
        # Blank while the tool is still down — expected, not an error.
        "job_end": _fmt_stored(doc.get("equp_dt")),
        "category": classify_category(
            _text(doc.get("pm_type")), _text(doc.get("eq_event"))
        ),
        "pm_type": _text(doc.get("pm_type")),
        "eq_event": _text(doc.get("eq_event")),
        "lot_id": _text(doc.get("lot_id")),
        "last_recipe_id": _text(doc.get("last_recipe_id")),
        "note_comment": _text(doc.get("note_comment")),
        "zzproblem": _text(doc.get("zzproblem")),
        "hltext": _text(doc.get("hltext")),
        "timestamp": _fmt_stored(doc.get("hub_load_tm")),
    }
    row["engr_note"] = merge_notes(row)
    return row


def future_row(doc: dict[str, Any], eqp_id: str) -> dict[str, Any]:
    """One ``tool_maintenance_plan`` hit as a planned-work row."""
    tool = _check_eqp(doc, eqp_id, INDEX_FUTURE)
    job_starts = _fmt_stored(doc.get("tool_start_tm"))
    if not job_starts:
        raise ValueError(
            f"{INDEX_FUTURE}: a hit for {eqp_id!r} has an empty "
            "tool_start_tm, so it cannot be ordered or placed on the timeline."
        )
    work_item_nm = _text(doc.get("work_item_nm"))
    event_name = _text(doc.get("event_name"))
    return {
        "eqp_id": tool,
        "job_starts": job_starts,
        "job_end": _fmt_stored(doc.get("tool_end_tm")),
        "category": classify_category(event_name, work_item_nm),
        "event_name": event_name,
        "work_item_nm": work_item_nm,
        "work_user_cd": _text(doc.get("work_user_cd")),
        "timestamp": _fmt_stored(doc.get("chg_tm")),
    }


def _fetch(
    index: str,
    eqp_id: str,
    range_field: str,
    gte: datetime,
    lte: datetime,
    order: str,
    source: list[str],
) -> list[dict[str, Any]]:
    """One capped, sorted, tool-scoped pull from one index.

    ``fab_name`` is deliberately NOT a filter: ``eqp_id`` is already the lookup
    identity and a tool belongs to one fab, so filtering on both would let a
    stale fab label silently empty the table. The two indices also spell fab
    differently (``fab_name`` vs ``det_fac_id``), which is exactly the kind of
    mismatch that empties a result without erroring.
    """
    clauses: list[dict[str, Any]] = [
        {"term": {EQP_ID_KW: eqp_id}},
        {"range": {range_field: {"gte": gte.isoformat(), "lte": lte.isoformat()}}},
    ]
    hits = fetch_hits(
        index,
        _query(clauses),
        size=MAX_ROWS,
        sort=[{range_field: {"order": order}}],
        source=source,
    )
    if len(hits) >= MAX_ROWS:
        raise LookupError(
            f"{index}: {eqp_id} returned the full {MAX_ROWS}-row cap, so the "
            "result is probably truncated. Narrow the window, or add "
            "pagination before raising the cap."
        )
    return hits


def build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]:
    """Past/future BM/PM rows + summary cards for one tool.

    Past covers ``anchor - PAST_DAYS .. anchor`` by ``down_dt`` (newest first);
    future covers ``anchor .. anchor + FUTURE_DAYS`` by ``tool_start_tm``
    (soonest first). ``eqp_id`` is never None here — ``normalizers.service_gate``
    returns the "pick a tool" payload before the dispatcher reaches this call.

    A tool with no maintenance in either window is a valid empty result, not an
    error: empty tables and "—" cards.
    """
    past_hits = _fetch(
        INDEX_PAST, eqp_id, DOWN_DT,
        anchor - timedelta(days=PAST_DAYS), anchor, "desc", PAST_SOURCE,
    )
    future_hits = _fetch(
        INDEX_FUTURE, eqp_id, PLAN_START,
        anchor, anchor + timedelta(days=FUTURE_DAYS), "asc", FUTURE_SOURCE,
    )
    past = [past_row(hit, eqp_id) for hit in past_hits]
    future = [future_row(hit, eqp_id) for hit in future_hits]
    return {"past": past, "future": future, "cards": derive_cards(past, future)}
