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
from datetime import datetime, timedelta, timezone

from back_dev_home._runtime.office_redis import STORE_ERRORS, redis_client, unreachable
from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm import board, refresh, roster
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    FUTURE_TOLERANCE_SEC,
    LiveAlarmPayload,
)


KST = timezone(timedelta(hours=9))


def _iso(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), KST).isoformat(sep=" ")


def _not_configured(tool_type: ToolType, fab_name: str, *, now: int) -> LiveAlarmPayload:
    """A fab the roster holds no tool of this family for.

    Distinct from a quiet board: there is no feed here and none is expected,
    so the screen says 미설정 rather than implying everything is fine.
    """
    return {
        "fab_name": fab_name,
        "tool_type": tool_type,
        "feed_status": "not_configured",
        "fetched_at": None,
        "covered_since": None,
        "server_now": _iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "unmatched_count": 0,
        "events": [],
    }


def _build_board(
    client,
    index: roster.RosterIndex,
    tool_type: ToolType,
    fab_name: str,
    *,
    now: int,
) -> LiveAlarmPayload:
    """Read one fab's board out of its facility's ZSET. Assumes it is fresh."""
    fac_id = index.fac_id_for(fab_name)
    events_key, _, _ = refresh.keys(fac_id)

    raw = client.zrangebyscore(
        events_key,
        now - BOARD_WINDOW_SEC,
        # Not "+inf": a fast upstream clock would otherwise pin a far-future
        # event to the top of the board forever.
        now + FUTURE_TOLERANCE_SEC,
    )

    wanted = (fab_name.strip().upper(), tool_type)
    mine: list = []
    unmatched = 0
    for event in board.dedupe_by_id(board.parse_members(raw)):
        placement = index.placement_of(event.get("eqp_id", ""))
        if placement is None:
            # In the facility's feed but in no fab: equipment the roster does
            # not carry yet (typically still firewalled). Counted, so a roster
            # gap cannot masquerade as a quiet fab.
            unmatched += 1
        elif placement == wanted:
            mine.append(event)

    mine.sort(key=lambda e: e["occurred_epoch"], reverse=True)
    meta = refresh.read_meta(client, fac_id)

    return {
        "fab_name": fab_name,
        "tool_type": tool_type,
        "feed_status": board.feed_status_for(meta, True, now=now),
        "fetched_at": _iso(meta["fetched_at"]) if meta else None,
        # The board always covers a fixed horizon, so this is derived rather
        # than reported by a writer's adaptive backfill window.
        "covered_since": _iso(now - BOARD_WINDOW_SEC),
        "server_now": _iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "unmatched_count": unmatched,
        "events": mine,
    }


def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    index = roster.load_index()
    if not index.has_tools(tool_type, fab_name):
        # Answered before any Redis or office work: there is nothing to fetch
        # for a fab that holds no tool of this family.
        return _not_configured(tool_type, fab_name, now=int(time.time()))

    try:
        client = redis_client()
        # Redis is the single clock authority — the refresh prunes against
        # this same clock, so the two never disagree about the boundary.
        now = int(client.time()[0])
        refresh.ensure_fresh(client, index.fac_id_for(fab_name), now=now)
        return _build_board(client, index, tool_type, fab_name, now=now)
    except STORE_ERRORS as exc:
        raise unreachable("live_alarm board is unreachable", exc) from exc
