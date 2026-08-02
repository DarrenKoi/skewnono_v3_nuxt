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

OFFICE-VERIFY: whether HV-SEM alarms are in the feed at all. The POC function
was named `get_cdsem_alarms`. If the feed is CD-SEM-only, `/api/hvsem/live-alarm`
will read "live" with an empty board forever — the roster resolves TP tools to
a real fac_id, so it never falls to not_configured. That is a dead feed wearing
a quiet fab's face, the exact state this feature exists to make visible. If the
office confirms CD-SEM-only, hv-sem must return not_configured explicitly.

OFFICE-VERIFY: the real fac_id value set beyond R3 / M16.

Office reads take `now` from REDIS's clock, not the app server's, because the
refresh prunes against that same clock — the two can then never disagree about
the boundary. This mock uses the local clock, which is the honest home
equivalent and the reason its output shifts by the minute.
"""

from __future__ import annotations

import time

from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm import board, roster
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    AlarmEvent,
    LiveAlarmPayload,
)


_RECIPES = ("MONITOR/CD_TOP_01", "MONITOR/CD_BOT_04", "", "PROD/EV_MAIN_12")
_ALIDS = ("9006", "9100")

# Set SKEWNONO_LIVE_ALARM_MOCK_STALE=1 to see the "feed died" screen at home.
_STALE_ENV = "SKEWNONO_LIVE_ALARM_MOCK_STALE"

# An eqp_id no roster carries, so it lands in unmatched_count exactly as a
# still-firewalled tool would at the office. Fabricating one deliberately is
# the only way the roster-gap path is reachable at home: every id the sem_list
# mock emits is, by construction, in the roster.
_UNROSTERED_EQP_ID = "MCD999"


def _index() -> roster.RosterIndex:
    """The same roster the office reader uses, over the sem_list MOCK fleet.

    Built from sem_list rather than a hardcoded fab whitelist so home and
    office answer "is this fab configured?" by the SAME mechanism. The
    whitelist this replaced listed four fac_ids (M11, M12, M14, M15) among its
    fab names, so 14 of the 17 fabs the sem_list mock generates rendered 미설정
    at home while the office would have served them a board — the exact
    fab/fac confusion MIGRATION.md warns about, reproduced in our own mock.
    """
    from back_dev_home.sem_list.providers.mock import get_sem_list

    return roster.build_index(get_sem_list())


def _event(now: int, index: int, eqp_id: str) -> AlarmEvent:
    occurred = now - (index * 137) % BOARD_WINDOW_SEC
    alid = _ALIDS[index % len(_ALIDS)]
    occurred_at = board.iso(occurred)
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
    index = _index()

    # A fab holding no tool of this family: no feed, no heartbeat — the panel
    # says "미설정", not a healthy empty board. Decided by the roster, which is
    # how the office decides it too.
    if index.fac_id_for(fab_name, tool_type) is None:
        return board.payload(
            tool_type=tool_type, fab_name=fab_name, now=now, configured=False,
        )

    stale = os.environ.get(_STALE_ENV, "").strip().lower() in {"1", "true", "yes"}
    # Vary the count by minute so the board visibly changes during development.
    count = (now // 60) % 4
    # Real ids from the roster, so an alarm row resolves to the fab being
    # viewed exactly as it does at the office. The previous fabricated ids
    # (MXCD*) matched no prefix sem_list emits, so the whole attribution path
    # went unexercised at home.
    eqp_ids = index.eqp_ids_in(fab_name, tool_type) or [_UNROSTERED_EQP_ID]
    events = [_event(now, i, eqp_ids[i % len(eqp_ids)]) for i in range(count)]

    # One minute in four the facility feed also carries an alarm from
    # equipment no roster knows. Generated as a REAL event and then withheld,
    # rather than incrementing a bare counter, so unmatched_count never claims
    # more was dropped than the feed actually held — the office computes it
    # the same way, by counting events it could not attribute.
    withheld = [_event(now, count, _UNROSTERED_EQP_ID)] if count == 3 else []

    return board.payload(
        tool_type=tool_type,
        fab_name=fab_name,
        now=now,
        configured=True,
        meta={"fetched_at": now - 2000 if stale else now},
        unmatched_count=len(withheld),
        events=sorted(events, key=lambda e: e["occurred_epoch"], reverse=True),
    )
