"""Phase 1 adapter. No Redis, no network — but not empty either.

An always-empty mock makes the page impossible to develop against, so
this emits a small deterministic set of alarms derived from the current
minute. The same minute always produces the same board, which keeps
tests stable while the screen still visibly changes as time passes.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    AlarmEvent,
    LiveAlarmPayload,
)


KST = timezone(timedelta(hours=9))

_EQP_IDS = ("MXCD101", "MXCD204", "MXCD317", "TP0421")
_RECIPES = ("MONITOR/CD_TOP_01", "MONITOR/CD_BOT_04", "", "PROD/EV_MAIN_12")
_ALIDS = ("9006", "9100")

# Set SKEWNONO_LIVE_ALARM_MOCK_STALE=1 to see the "feed died" screen at home.
_STALE_ENV = "SKEWNONO_LIVE_ALARM_MOCK_STALE"

# Fabs the mock pretends have a live-alarm feed. A fab outside this set
# resolves to "not_configured" — same status-body model the office reader
# uses for a fab absent from the writer's registry. Keeping the mock and
# office consistent here is the point: a typo'd or unwired fab must look the
# same at home as at the office (a clear "미설정" panel), not a healthy board.
# Visiting e.g. /ebeam/cd-sem/ZZZ/live-alarm renders that state at home.
_CONFIGURED_FABS = frozenset({"R3", "M11", "M12", "M14", "M15", "M16A", "M16B"})


def _text(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, KST).strftime("%Y-%m-%d %H:%M:%S%z")


def _iso(epoch: int) -> str:
    raw = _text(epoch)
    return f"{raw[:-2]}:{raw[-2:]}"  # +0900 -> +09:00


def _event(now: int, index: int) -> AlarmEvent:
    occurred = now - (index * 137) % BOARD_WINDOW_SEC
    eqp_id = _EQP_IDS[index % len(_EQP_IDS)]
    alid = _ALIDS[index % len(_ALIDS)]
    occurred_at = _iso(occurred)
    return {
        "id": f"{eqp_id}|{alid}|{occurred_at}",
        "eqp_id": eqp_id,
        "alid": alid,
        "kind": "align" if alid == "9006" else "meas",
        "alarm_name": (
            "Align Fail" if alid == "9006" else "Measurement Consecutive Fail (23/100)"
        ),
        "occurred_at": occurred_at,
        "occurred_epoch": occurred,
        "recipe_id": _RECIPES[index % len(_RECIPES)],
        "operation_desc": "CD MEASUREMENT",
        "lot_type_cd": "PROD" if index % 3 else "MONI",
    }


def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    import os

    now = int(time.time())

    # An unconfigured fab: no feed, no heartbeat — the panel says "미설정",
    # not a healthy empty board. This is how a typo'd fab surfaces.
    if fab_name.upper() not in _CONFIGURED_FABS:
        return {
            "fab_name": fab_name,
            "tool_type": tool_type,
            "feed_status": "not_configured",
            "polled_at": None,
            "covered_since": None,
            "server_now": _iso(now),
            "board_window_sec": BOARD_WINDOW_SEC,
            "events": [],
        }

    stale = os.environ.get(_STALE_ENV, "").strip().lower() in {"1", "true", "yes"}
    # Vary the count by minute so the board visibly changes during development.
    count = (now // 60) % 4
    events = [_event(now, i) for i in range(count)]
    polled_at = now - 2000 if stale else now
    return {
        "fab_name": fab_name,
        "tool_type": tool_type,
        "feed_status": "stale" if stale else "live",
        "polled_at": _iso(polled_at),
        "covered_since": _iso(now - BOARD_WINDOW_SEC),
        "server_now": _iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "events": sorted(events, key=lambda e: e["occurred_epoch"], reverse=True),
    }
