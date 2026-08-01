"""Phase 1 adapter. No Redis, no network — but not empty either.

An always-empty mock makes the page impossible to develop against, so
this emits a small deterministic set of alarms derived from the current
minute. The same minute always produces the same board, which keeps
tests stable while the screen still visibly changes as time passes.

Office counterpart — schema of record: `docs/datatables/live_alarm_board.txt`.
Unlike every other feature here, the office READ SOURCE IS NOT THE SYSTEM OF
RECORD. Redis is a short cache in front of the in-house alarm API, refreshed
by the same request that reads it: a page view calls `refresh.ensure_fresh`,
which fetches only when the facility's cache is older than CACHE_TTL_SEC and
only after winning a lock. Opening the page therefore costs at most one office
call per facility per 20 seconds, shared by every viewer, and none at all when
nobody is watching.

    page --(cache miss + lock)--> 사내 alarm API --> Redis board --> page
    page --(cache hit)---------------------------> Redis board --> page

    skewnono:live_alarm:{fac_id}:events   ZSET, score = occurred_epoch
    skewnono:live_alarm:{fac_id}:meta     JSON, fetched_at
    skewnono:live_alarm:{fac_id}:lock     stampede guard

Keys are scoped by fac_id (the coarse facility: M16, R3), NOT by fab_name
(M16A, R3, R4) — one office call covers a whole facility, and the reader
filters it down to the requested fab through the sem_list roster. Fab
attribution is a roster lookup, never a parse of the eqp_id.

"This fab was never configured" is answered by that same roster: a fab holding
no tool of the requested family is `not_configured`, which is a different fact
from a configured fab that is merely quiet.

Windows come from `contracts.py` and are shared with this mock, so home and
office cut the board the same way: BOARD_WINDOW_SEC (600) back, and only
FUTURE_TOLERANCE_SEC (300) forward — not +inf, because one upstream clock
running fast would otherwise pin a far-future alarm to the top of the board
permanently. PRUNE_SEC must be >= the board window or the refresh would delete
events the reader still shows; contracts.py asserts that at import.

OFFICE-VERIFY: how far back `get_live_alarms(fac_id)` reaches is unknown. The
ZSET accumulates successive snapshots and prunes at PRUNE_SEC, so the board is
rebuilt correctly whether the office returns a rolling history or only the
alarms active right now.

Office reads take `now` from REDIS's clock, not the app server's, because the
refresh prunes against that same clock — the two can then never disagree about
the boundary. This mock uses the local clock, which is the honest home
equivalent and the reason its output shifts by the minute.
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
            "fetched_at": None,
            "covered_since": None,
            "server_now": _iso(now),
            "board_window_sec": BOARD_WINDOW_SEC,
            "unmatched_count": 0,
            "events": [],
        }

    stale = os.environ.get(_STALE_ENV, "").strip().lower() in {"1", "true", "yes"}
    # Vary the count by minute so the board visibly changes during development.
    count = (now // 60) % 4
    events = [_event(now, i) for i in range(count)]
    fetched_at = now - 2000 if stale else now
    return {
        "fab_name": fab_name,
        "tool_type": tool_type,
        "feed_status": "stale" if stale else "live",
        "fetched_at": _iso(fetched_at),
        "covered_since": _iso(now - BOARD_WINDOW_SEC),
        "server_now": _iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        # Non-zero on one minute in four, so the "roster gap" line is
        # reachable at home. A mock that always reported 0 would leave that UI
        # path unexercised until it first appeared at the office.
        "unmatched_count": 1 if count == 3 else 0,
        "events": sorted(events, key=lambda e: e["occurred_epoch"], reverse=True),
    }
