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

BOARD_WINDOW_SEC = 600      # what the reader cuts to — the screen's horizon
PRUNE_SEC = 900             # how much history the ZSET keeps
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

ALID_KIND: dict[str, Kind] = {"9006": "align", "9100": "meas"}


class AlarmEvent(TypedDict):
    id: str              # f"{eqp_id}|{alid}|{occurred_at}"
    eqp_id: str
    alid: str
    kind: Kind
    alarm_name: str
    occurred_at: str     # "YYYY-MM-DD HH:MM:SS+09:00"
    occurred_epoch: int  # ZSET score; parsed once at refresh time
    recipe_id: str
    operation_desc: str
    lot_type_cd: str


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
