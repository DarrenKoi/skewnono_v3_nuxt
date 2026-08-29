"""Office-side plumbing: recent BM/PM maintenance events for a fleet.

``fab_inform_notes`` records maintenance that HAPPENED — one document per job,
with the tool's down and up times and the engineer's free-form notes.
``hardware/providers/bm_pm`` reads it one tool at a time to draw a timeline;
pm_planning and tttm both need the same index answered for a whole FLEET, and
they need one fact out of it each:

* pm_planning — "when did this tool last come back up from a PM", which is what
  its Up-gate is measured from.
* tttm — "did anything happen to this tool inside the comparison window", which
  is what turns a skew step into an explained event instead of a mystery.

One aggregation serves both. Keeping it here rather than in either adapter also
keeps ``classify_category`` applied identically: the raw ``pm_type``/
``eq_event`` text carries characters around the BM/PM part, so an adapter that
compared for equality would classify nothing and silently report a fab with no
maintenance at all.

This module is TRACKED. It carries the index and field names already recorded in
``docs/datatables/hitachi/hardware_bm_pm.txt``, and no query shaped to one screen.

TIMEZONE, inherited and unresolved: ``hardware/providers/bm_pm`` records that
whether this index stores offset-less KST wall clock (like the meas_hist
indices) is UNVERIFIED. A stored ``Z`` suffix slides every window by nine hours.
Both callers pass windows anchored on meas_hist's own anchor, so a mismatch
shows up as maintenance that looks a few hours displaced rather than absent —
check it once at the office, then delete this paragraph.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, NamedTuple

from back_dev_home.ebeam._office_meas_hist import (
    EQP_ID_KW,
    FAB_NAME_KW,
    aggregate,
    query as _query,
    text as _text,
    top_hits as _top_hits,
)
from back_dev_home.ebeam._office_msr_cd import _datetime_range_clause
from back_dev_home.ebeam.hardware.providers.bm_pm._shared import classify_category


__all__ = [
    "BM_PM_INDEX",
    "MaintEvent",
    "latest_pm_by_tool",
    "maintenance_events",
]

_LOG = logging.getLogger(__name__)


BM_PM_INDEX = "fab_inform_notes"
_DOWN_DT = "down_dt"      # the tool went down: the event's own time
_UP_DT = "equp_dt"        # the tool came back up; blank while still down
_SOURCE = [_DOWN_DT, _UP_DT, "pm_type", "eq_event", "eqp_id"]

# Jobs kept per tool. A fab tool sees a handful of maintenance events in a
# 60-day window; this is a guard against a mapping surprise, not a real limit.
_DOCS_PER_TOOL = 24


class MaintEvent(NamedTuple):
    """One maintenance job, reduced to what both callers actually read."""

    eqp_id: str
    category: str        # "PM" | "BM" | "" when the raw text classified as neither
    down_at: str         # ISO-ish, as stored
    up_at: str           # "" while the tool is still down

    @property
    def completed(self) -> bool:
        return bool(self.up_at)


def maintenance_events(
    fab_name: str,
    eqp_ids: list[str],
    start: datetime,
    end: datetime,
) -> dict[str, list[MaintEvent]]:
    """Per tool, maintenance jobs in ``[start, end]``, most recent first.

    An unreadable index is a WARNING and an empty result, never an exception:
    both callers render fine without maintenance (a gate says "기록된 PM 이력이
    없습니다", a trend simply carries no markers), and 502-ing a page over a
    secondary source would be a worse failure than the one it reports.
    """
    if not eqp_ids:
        return {}
    clauses: list[dict[str, Any]] = [
        {"terms": {EQP_ID_KW: eqp_ids}},
        _datetime_range_clause(_DOWN_DT, start, end),
    ]
    if fab_name:
        clauses.append({"term": {FAB_NAME_KW: fab_name.strip().upper()}})

    aggs = {
        "per_tool": {
            "terms": {"field": EQP_ID_KW, "size": len(eqp_ids)},
            "aggs": {
                "recent": _top_hits(
                    _DOCS_PER_TOOL, sort=[{_DOWN_DT: "desc"}], source=_SOURCE
                )
            },
        }
    }
    try:
        result = aggregate(BM_PM_INDEX, aggs, _query(clauses))
    except LookupError:
        _LOG.warning(
            "%s is unreadable from this instance — maintenance history will be "
            "absent from the page (gates show no PM date, trends show no "
            "markers). Check the alias name and read access.",
            BM_PM_INDEX,
        )
        return {}

    events: dict[str, list[MaintEvent]] = {}
    for bucket in result.get("per_tool", {}).get("buckets", []):
        eqp_id = _text(bucket.get("key"))
        rows: list[MaintEvent] = []
        for hit in bucket.get("recent", {}).get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            down_at = _text(source.get(_DOWN_DT))
            if not down_at:
                # Without a down time the job cannot be placed on a timeline
                # or ordered — hardware's own adapter refuses the same row.
                continue
            rows.append(
                MaintEvent(
                    eqp_id=eqp_id,
                    category=classify_category(
                        _text(source.get("pm_type")), _text(source.get("eq_event"))
                    ),
                    down_at=down_at.replace(" ", "T"),
                    up_at=_text(source.get(_UP_DT)).replace(" ", "T"),
                )
            )
        if bucket.get("doc_count", 0) > len(
            bucket.get("recent", {}).get("hits", {}).get("hits", [])
        ):
            # docs/datatables/hitachi/hardware_bm_pm.txt: "잘린 이력을 조용히 보여주지
            # 않고". A truncated history reads as a quiet fab, so the cap is
            # announced. Not raised: unlike a truncated TREND, the two callers
            # here want the most recent jobs and the sort already keeps those.
            _LOG.info(
                "%s: %s has more than %d maintenance jobs in the window; "
                "older ones were not read",
                BM_PM_INDEX, eqp_id, _DOCS_PER_TOOL,
            )
        events[eqp_id] = rows
    return events


def latest_pm_by_tool(events: dict[str, list[MaintEvent]]) -> dict[str, str]:
    """Per tool, the up-time of its most recent COMPLETED PM.

    A job still open (no up time) is skipped: the Up-gate asks how long since
    the tool came back, and a tool that has not come back has no answer. A tool
    with only BM jobs is absent from the result rather than present with "",
    so ``.get(eqp_id)`` gives the ``None`` the contract wants.
    """
    latest: dict[str, str] = {}
    for eqp_id, rows in events.items():
        for event in rows:  # already newest-first
            if event.category == "PM" and event.completed:
                latest[eqp_id] = event.up_at
                break
    return latest
