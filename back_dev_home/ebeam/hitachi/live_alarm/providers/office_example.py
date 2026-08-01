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

from back_dev_home._runtime.office_redis import STORE_ERRORS, redis_client, unreachable
from back_dev_home.ebeam.hitachi._office_search import ttl_cache
from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm import board, refresh, roster
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
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
        from office_utils.live_alarm import get_live_alarms
    except ImportError as exc:
        raise RuntimeError(
            "office_utils.live_alarm is not importable — live_alarm's office "
            "provider needs the office-only office_utils package on sys.path. "
            "Copy it onto this host, or run with "
            "SKEWNONO_LIVE_ALARM_PROVIDER=mock."
        ) from exc

    def fetch(fac_id: str) -> list[dict]:
        # DataFrame -> dict rows (CLAUDE.md's dataframe-dict convention).
        # NaN survives to_dict; normalize._text is what guards it. No
        # duck-typed fallback: anything without to_dict is a contract
        # violation that must raise, because list() of a DataFrame yields
        # COLUMN NAMES, which to_events would silently drop into an empty
        # board stamped with a fresh timestamp.
        return get_live_alarms(fac_id).to_dict(orient="records")

    return fetch


def _build_board(
    client,
    index: roster.RosterIndex,
    tool_type: ToolType,
    fab_name: str,
    fac_id: str,
    *,
    now: int,
    meta: dict | None,
) -> LiveAlarmPayload:
    """Read one fab's board out of its facility's ZSET. Assumes it is fresh."""
    events_key, _, _ = refresh.keys(fac_id)

    raw = client.zrangebyscore(
        events_key,
        now - BOARD_WINDOW_SEC,
        # Not "+inf": a fast upstream clock would otherwise pin a far-future
        # event to the top of the board forever.
        now + FUTURE_TOLERANCE_SEC,
    )

    wanted = (roster.norm(fab_name), tool_type)
    mine: list = []
    unmatched = 0
    for event in board.dedupe_by_id(board.parse_members(raw)):
        placement = index.placement_of(event.get("eqp_id", ""))
        if placement is None:
            # In the facility's feed but in no fab: equipment the roster does
            # not carry yet (typically still firewalled). Counted, so a roster
            # gap cannot masquerade as a quiet fab. A tool that IS rostered but
            # sits in a sibling fab is a filter, not a gap, and is not counted.
            unmatched += 1
        elif placement == wanted:
            mine.append(event)

    mine.sort(key=lambda e: e["occurred_epoch"], reverse=True)

    return board.payload(
        tool_type=tool_type,
        fab_name=fab_name,
        now=now,
        configured=True,
        meta=meta,
        unmatched_count=unmatched,
        events=mine,
    )


def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    index = _index()
    fac_id = index.fac_id_for(fab_name, tool_type)
    if fac_id is None:
        # Answered before any Redis or office work: there is nothing to fetch
        # for a fab that holds no tool of this family.
        return board.payload(
            tool_type=tool_type, fab_name=fab_name,
            now=int(time.time()), configured=False,
        )

    # Bound before the lock, and before any Redis work, so a host missing
    # office_utils fails loudly rather than serving an empty board.
    fetch = _office_fetch()

    try:
        client = redis_client()
        # Redis is the single clock authority — the refresh prunes against
        # this same clock, so the two never disagree about the boundary.
        now = int(client.time()[0])
        meta = refresh.ensure_fresh(client, fac_id, now=now, fetch=fetch)
        return _build_board(
            client, index, tool_type, fab_name, fac_id, now=now, meta=meta,
        )
    except STORE_ERRORS as exc:
        raise unreachable("live_alarm board is unreachable", exc) from exc
