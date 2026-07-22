"""Stable response contracts for the live_alarm endpoint.

The writer runs in a different service and does NOT import this module —
the shared contract is the Redis key layout, not Python types. This file
is the SKEWNONO-side statement of that same shape.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType


__all__ = [
    "Kind",
    "FeedStatus",
    "AlarmEvent",
    "LiveAlarmPayload",
    "BOARD_WINDOW_SEC",
    "POLL_WINDOW_SEC",
    "WRITER_INTERVAL_SEC",
    "WRITER_PRUNE_SEC",
    "STALE_AFTER_SEC",
    "FUTURE_TOLERANCE_SEC",
    "ALID_KIND",
]


Kind = Literal["align", "meas"]
FeedStatus = Literal["live", "stale", "not_configured"]

BOARD_WINDOW_SEC = 600      # what the reader cuts to — the screen's horizon
POLL_WINDOW_SEC = 60        # normal writer query window
WRITER_INTERVAL_SEC = 15    # writer job period
WRITER_PRUNE_SEC = 900      # what the writer keeps
STALE_AFTER_SEC = 90        # 6 missed cycles; absorbs uWSGI worker recycles
FUTURE_TOLERANCE_SEC = 300  # events dated further ahead than this are dropped

assert WRITER_PRUNE_SEC >= BOARD_WINDOW_SEC, (
    "WRITER_PRUNE_SEC must be >= BOARD_WINDOW_SEC, otherwise the writer "
    "deletes events the reader is still supposed to show."
)

ALID_KIND: dict[str, Kind] = {"9006": "align", "9100": "meas"}


class AlarmEvent(TypedDict):
    id: str              # f"{eqp_id}|{alid}|{occurred_at}"
    eqp_id: str
    alid: str
    kind: Kind
    alarm_name: str
    occurred_at: str     # "YYYY-MM-DD HH:MM:SS+09:00"
    occurred_epoch: int  # ZSET score; parsed once by the writer
    recipe_id: str
    operation_desc: str
    lot_type_cd: str


class LiveAlarmPayload(TypedDict):
    fab_name: str
    tool_type: ToolType
    feed_status: FeedStatus
    polled_at: str | None
    covered_since: str | None
    server_now: str
    board_window_sec: int
    events: list[AlarmEvent]
