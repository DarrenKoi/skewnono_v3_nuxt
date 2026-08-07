"""Stable response contracts for the live_alarm endpoint.

The board is refreshed on demand by refresh.py, behind a short cache and a
lock, rather than by a separate writer service. These constants are the whole
tuning surface: the cache TTL bounds office API load, the board window bounds
what the screen shows, and PRUNE_SEC bounds what Redis keeps.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType


__all__ = [
    "Kind",
    "FeedStatus",
    "AlarmEvent",
    "LiveAlarmPayload",
    "BOARD_WINDOW_SEC",
    "PRUNE_SEC",
    "STALE_AFTER_SEC",
    "FUTURE_TOLERANCE_SEC",
    "CACHE_TTL_SEC",
    "LOCK_TTL_SEC",
    "KEY_TTL_SEC",
    "ALID_KIND",
    "KST",
]

# Korea has no DST, so a fixed +09:00 offset is exact. Declared once here
# rather than per module: two copies is two places to get an offset wrong.
KST = timezone(timedelta(hours=9))


Kind = Literal["align", "meas"]
FeedStatus = Literal["live", "stale", "not_configured"]

# 20 minutes, widened from 10 on 2026-08-07: viewers reported that alarms fell
# off the board before anyone had finished triaging them. PRUNE_SEC keeps its
# 1.5x headroom over the window (see the assert below).
BOARD_WINDOW_SEC = 1200     # what the reader cuts to — the screen's horizon
PRUNE_SEC = 1800            # how much history the ZSET keeps
STALE_AFTER_SEC = 90        # ~3 missed refreshes at the viewer-driven cadence
FUTURE_TOLERANCE_SEC = 300  # events dated further ahead than this are dropped

# How long one successful office call is reused. The in-house alarm API is
# called at most once per facility per this many seconds, no matter how many
# viewers are polling or how fast they poll.
CACHE_TTL_SEC = 20
# In-flight guard AND failure backoff: the lock is released on success but
# left to expire on failure, so an office API already in trouble is not
# retried by every poll of every viewer.
LOCK_TTL_SEC = 20
# Garbage collection for a facility nobody has opened in a day. Distinct from
# PRUNE_SEC, which trims events inside a board that IS being read.
KEY_TTL_SEC = 86_400

assert PRUNE_SEC >= BOARD_WINDOW_SEC, (
    "PRUNE_SEC must be >= BOARD_WINDOW_SEC, otherwise the refresh deletes "
    "events the reader is still supposed to show."
)

# The alarm ids this board renders; everything else in the facility feed is
# discarded by normalize.to_events. All three are HITACHI-only codes, which is
# why the endpoint serves cd-sem and hv-sem and nothing else — the AMAT tools
# in the same sem_list roster report measurement failure under codes nobody
# has looked up yet (user-confirmed 2026-08-03).
#
#   9006  align   ALIGNMENT FAIL
#   9007  meas    FAILURE IN DETECTION OF PATTERN
#   9035  meas    FAILURE IN AUTO MEASUREMENT
#
# MANY ids map to ONE kind, so `kind` is what the UI groups and counts by and
# `alid`/`alarm_name` is what says which failure it actually was. Adding an id
# is a line here; adding a KIND means touching the badge and the counters too.
ALID_KIND: dict[str, Kind] = {"9006": "align", "9007": "meas", "9035": "meas"}


class AlarmEvent(TypedDict):
    """One alarm row, flattened from the office feed by normalize.py.

    Every field is a string except `occurred_epoch`, because the office feed
    is all-str apart from `UTC9` (datetime64[us]) and `RAWID` (int) — see
    `docs/datatables/live_alarm_board.txt` for the column-by-column source.
    Absent or null cells become "" rather than being omitted: the ZSET member
    is this dict verbatim, and a key that appears only sometimes would make
    two spellings of the same alarm two distinct members.
    """

    # RAWID when the feed carries one (it is the feed's own unique key), else
    # f"{eqp_id}|{alid}|{occurred_at}". Dedupe key for the ZSET.
    id: str
    rawid: str
    eqp_id: str
    alarm_modelname: str  # ALARM_MODELNAME — tool model, e.g. CG5000
    alid: str
    al_code: str
    al_type: str           # AL_TYPE — inform / warning / ...
    kind: Kind
    alarm_name: str        # AL_TEXT — the human-readable alarm description
    occurred_at: str       # "YYYY-MM-DD HH:MM:SS+09:00"
    occurred_epoch: int    # ZSET score; parsed once at refresh time
    lot_id: str
    cassette_id: str       # FOUP id
    recipe_id: str
    ppid: str              # the recipe id as MES spells it
    operation_desc: str    # step 명
    step_id: str           # process id
    lot_type_cd: str
    meseventname: str    # MESEVENTNAME — waferload / endrun / ...
    eq_stat: str           # proc / wait / ...


class LiveAlarmPayload(TypedDict):
    fab_name: str
    tool_type: ToolType
    feed_status: FeedStatus
    # Last SUCCESSFUL office fetch. None when there has never been one.
    fetched_at: str | None
    # Always now - BOARD_WINDOW_SEC for a configured fab: the board covers a
    # fixed horizon, so this is derived rather than reported by a writer.
    covered_since: str | None
    server_now: str
    board_window_sec: int
    # Alarms in this facility's feed whose eqp_id is absent from the sem_list
    # roster, so they belong to no fab. Counted rather than shown: a roster
    # gap and a genuinely quiet fab would otherwise render identically.
    unmatched_count: int
    events: list[AlarmEvent]
