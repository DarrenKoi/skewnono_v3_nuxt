"""[Office template] live_alarm reader. Copy to office.py to activate.

    cp office_example.py office.py

Unlike most office adapters this one both reads and writes: the board it reads
is refreshed on demand by refresh.py, behind a short cache and a lock, so
opening the page calls the in-house alarm API at most once per facility per
CACHE_TTL_SEC no matter how many people are watching, and not at all when
nobody is.

Fab attribution is a LOOKUP through the sem_list roster, never a parse of the
eqp_id — see roster.py and _tool_specs.py for why that distinction has teeth.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from back_dev_home._runtime.office_redis import STORE_ERRORS, redis_client, unreachable
from back_dev_home.ebeam._office_search import ttl_cache
from back_dev_home.ebeam._tool_specs import ToolType
from back_dev_home.ebeam.live_alarm import board, refresh, roster
from back_dev_home.ebeam.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    FUTURE_TOLERANCE_SEC,
    LiveAlarmPayload,
)


@ttl_cache
def _index() -> roster.RosterIndex:
    """``eqp_id``/``fab_name`` lookups for the whole fleet.

    Cached because ``get_sem_list()`` deserializes two parquet blobs from
    Redis and merges them — the same reason ``recipe_search`` and the three
    ``hardware`` tabs cache it. It matters more here than anywhere else: this
    endpoint is polled every 15 seconds by every open tab, so an uncached
    roster load would sit in front of the alarm cache and undo the point of
    capping the office API at one call per facility per 20 seconds.

    The cost is a tool added at the office taking up to the TTL to appear.
    ``roster.py`` promises day-scale freshness for that, so a 15-minute TTL
    is well inside it. ``ttl_cache`` also serves the previous index when a
    refresh fails, so a hiccup on the sem_list keys no longer blanks an alarm
    board whose own ZSET is perfectly healthy.
    """
    return roster.load_index()


def _office_fetch():
    """Bind the office alarm reader, or explain why it is missing.

    Imported inside the function because office_utils is gitignored and does
    not exist at home. Bound HERE rather than inside refresh.py so that module
    stays office-free, and called by get_board BEFORE ensure_fresh so a
    missing office_utils surfaces as a 503 instead of being swallowed as a
    transient fetch failure — and without holding a lock on the way out.
    """
    try:
        from office_utils.live_alarm import get_ebeam_metrology_alarms
    except ImportError as exc:
        raise RuntimeError(
            "office_utils.live_alarm.get_ebeam_metrology_alarms is not "
            "importable — live_alarm's office provider needs the office-only "
            "office_utils package on sys.path. Copy it onto this host, or run "
            "with SKEWNONO_LIVE_ALARM_PROVIDER=mock. (The function was called "
            "get_cdsem_alarms/get_live_alarms in earlier builds; an ImportError "
            "naming only the module usually means an old office_utils.)"
        ) from exc

    def fetch(fac_id: str) -> list[dict]:
        # DataFrame -> dict rows (CLAUDE.md's dataframe-dict convention).
        # Returns EVERY alid for the facility; normalize.to_events is what
        # cuts it to ALID_KIND, so a newly interesting alarm code is a
        # contracts.py edit and not an office_utils change.
        #
        # NaN survives to_dict; normalize._text is what guards it. No
        # duck-typed fallback: anything without to_dict is a contract
        # violation that must raise, because list() of a DataFrame yields
        # COLUMN NAMES, which to_events would silently drop into an empty
        # board stamped with a fresh timestamp.
        return get_ebeam_metrology_alarms(fac_id).to_dict(orient="records")

    return fetch


def _build_board(
    client,
    index: roster.RosterIndex,
    tool_type: ToolType,
    *,
    fab_names: list[str],
    wanted_fabs: set[str],
    fac_ids: Sequence[str],
    not_configured_fabs: Sequence[str],
    now: int,
    meta: dict | None,
) -> LiveAlarmPayload:
    """Merge the selected fabs' boards out of their facilities' ZSETs."""
    mine: list = []
    unmatched = 0
    for fac_id in fac_ids:
        raw = client.zrangebyscore(
            refresh.keys(fac_id).events,
            now - BOARD_WINDOW_SEC,
            # Not "+inf": a fast upstream clock would otherwise pin a
            # far-future event to the top of the board forever.
            now + FUTURE_TOLERANCE_SEC,
        )

        for event in board.dedupe_by_id(board.parse_members(raw)):
            placement = index.placement_of(event.get("eqp_id", ""))
            if placement is None:
                # In the facility's feed but in no fab: equipment the roster
                # does not carry yet (typically still firewalled). Counted,
                # so a roster gap cannot masquerade as a quiet fab. A tool
                # that IS rostered but sits in a sibling fab is a filter, not
                # a gap, and is not counted.
                unmatched += 1
            elif placement[1] == tool_type and placement[0] in wanted_fabs:
                stamped = dict(event)
                stamped["fab_name"] = placement[0]
                mine.append(stamped)

    mine.sort(key=lambda e: e["occurred_epoch"], reverse=True)
    return board.payload(
        tool_type=tool_type, fab_names=fab_names, now=now, configured=True,
        meta=meta, unmatched_count=unmatched,
        not_configured_fabs=not_configured_fabs, events=mine,
    )


def get_board(tool_type: ToolType, fab_names: Sequence[str]) -> LiveAlarmPayload:
    index = _index()
    placements = [(fab, index.fac_id_for(fab, tool_type)) for fab in fab_names]
    configured = [(fab, fac) for fab, fac in placements if fac is not None]
    not_configured = [fab for fab, fac in placements if fac is None]
    if not configured:
        # Answered before any Redis or office work: there is nothing to fetch
        # for fabs that hold no tool of this family.
        return board.payload(
            tool_type=tool_type, fab_names=list(fab_names),
            now=int(time.time()), configured=False,
            not_configured_fabs=not_configured,
        )

    # Bound before the lock, and before any Redis work, so a host missing
    # office_utils fails loudly rather than serving an empty board.
    fetch = _office_fetch()

    try:
        client = redis_client()
        # Redis is the single clock authority — the refresh prunes against
        # this same clock, so the two never disagree about the boundary.
        now = int(client.time()[0])
        # Distinct facs: sibling fabs share one feed and must not double-fetch.
        distinct_facs = list(dict.fromkeys(fac for _fab, fac in configured))
        metas = [
            refresh.ensure_fresh(client, fac, now=now, fetch=fetch)
            for fac in distinct_facs
        ]
        return _build_board(
            client, index, tool_type,
            fab_names=list(fab_names),
            wanted_fabs={roster.norm(fab) for fab, _fac in configured},
            fac_ids=distinct_facs,
            not_configured_fabs=not_configured,
            now=now,
            meta=board.merged_meta(metas),
        )
    except STORE_ERRORS as exc:
        raise unreachable("live_alarm board is unreachable", exc) from exc
