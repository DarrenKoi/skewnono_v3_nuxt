"""Adaptive backfill window.

Standalone by design: this module is copied to a scheduler service and
must not import anything from back_dev_home. The constants are duplicated
from contracts.py on purpose — the shared contract is the Redis layout,
not Python imports.
"""

from __future__ import annotations

import os

BOARD_WINDOW_SEC = 600
# The steady-state poll window, overridable per deployment (documented in
# .env.example). Read at import like job.py's LIVE_ALARM_PRUNE_SEC — this
# module is copied to the scheduler service, so it reads its own env rather
# than taking config from a host framework.
POLL_WINDOW_SEC = int(os.environ.get("LIVE_ALARM_POLL_WINDOW_SEC", "60"))
SLACK_SEC = 15  # one extra interval, so scheduler jitter cannot shave the edge

__all__ = ["compute_window", "BOARD_WINDOW_SEC", "POLL_WINDOW_SEC"]


def compute_window(
    last_polled_at: int | None,
    events_key_exists: bool,
    *,
    now: int,
) -> tuple[int, int]:
    """How far back to query, and what that covers.

    A fixed 60s window silently loses alarms whenever the writer stalls
    longer than 60s: the recovery poll covers only the last minute, and the
    heartbeat it writes reads fresh, so nothing on screen reveals the loss.

    Deriving the window from the last success closes that. The cap is what
    keeps it simple: the board only ever displays BOARD_WINDOW_SEC, so a
    query that wide fully rebuilds it no matter how long the outage was.
    There is no such thing as a partially recovered board.

    A missing events key (cold start, Redis restart, maxmemory eviction)
    takes the same path — otherwise the next poll would pair 60 seconds of
    events with a fresh heartbeat, i.e. an empty board claiming to be live.
    """
    if last_polled_at is None or not events_key_exists:
        window = BOARD_WINDOW_SEC
    else:
        gap = max(0, now - last_polled_at)
        window = min(max(gap + SLACK_SEC, POLL_WINDOW_SEC), BOARD_WINDOW_SEC)
    return window, now - window
