"""Phase 1 adapter. No Redis, no network — but not empty either.

An always-empty mock makes the page impossible to develop against, so
this emits a deterministic set of alarms derived from the current
minute. The same minute always produces the same board, which keeps
tests stable while the screen still visibly changes as time passes.

WHAT THIS MOCK DELIBERATELY SHAPES (and where it therefore differs):

The board's 측정 실패 view groups alarms by `(eqp_id, ppid)` and ranks by
count, because the situation worth acting on is one tool running one recipe
failing over and over. So this mock places such a pile on every non-empty
board — see `_HOT_BURST`. That correlation is FABRICATED: the shape is real
(it is what the screen was built for), the RATE is not something home can
know, and is marked OFFICE-VERIFY.

Until 2026-08-03 the volume was `(now // 60) % 4`, i.e. 0..3 events spread
over a dozen tools, and two alarms sharing a tool AND a recipe essentially
never occurred. Every path the grouped view added was unreachable at home
while every shape test passed — a mock whose value domain was narrower than
the thing it stands for, which is the failure mode CLAUDE.md warns about.
`tests/test_mock.py` now guards that domain: volume, the repeat, the quiet
board, the blank ppid, and the roster gap.

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
office cut the board the same way: BOARD_WINDOW_SEC (1200) back, and only
FUTURE_TOLERANCE_SEC (300) forward — not +inf, because one upstream clock
running fast would otherwise pin a far-future alarm to the top of the board
permanently. PRUNE_SEC must be >= the board window or the refresh would delete
events the reader still shows; contracts.py asserts that at import.

OFFICE-VERIFY: how far back `get_ebeam_metrology_alarms(fac_id)` reaches is
unknown. The ZSET accumulates successive snapshots and prunes at PRUNE_SEC, so
the board is rebuilt correctly whether the office returns a rolling history or only the
alarms active right now.

SETTLED (user-confirmed 2026-08-03): the feed covers BOTH Hitachi families.
The POC's `get_cdsem_alarms()` is now `get_ebeam_metrology_alarms(fac_id)`, and
CD-SEM and HV-SEM share the three ALIDs in `contracts.ALID_KIND`. So `/api/
hvsem/live-alarm` is a real board, not the dead-feed-wearing-a-quiet-fab's-face
this mock used to warn about. AMAT tools are a different matter: their
measurement-failure codes are not known, so this board stays Hitachi-only and
the roster's `model_to_tool_type` is what keeps AMAT rows off it.

SETTLED (user-confirmed 2026-08-03): RECIPE_ID and PPID ALWAYS agree. This mock
briefly emitted them differing (PPID with a `.rcp` tail) while that was an open
question; it now emits them equal, because a mock that disagrees with the office
on a settled fact teaches the wrong thing to every home session. Both fields are
still carried — the office DataFrame has both columns, and dropping one here
would mean normalize.py silently choosing which spelling is canonical.

The fac_id set is R3 / M16 / M15 / M14 / M11 / M10 (user-confirmed 2026-08-03).
This mock does not hardcode them — it reads whatever the sem_list mock roster
carries, which is the same list.

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
    ALID_KIND,
    BOARD_WINDOW_SEC,
    AlarmEvent,
    LiveAlarmPayload,
)


_RECIPES = ("MONITOR/CD_TOP_01", "MONITOR/CD_BOT_04", "", "PROD/EV_MAIN_12")

# alid -> the AL_TEXT the tool actually emits for it. Verbatim from the office
# (user-confirmed 2026-08-03) because these strings are the row's headline: a
# paraphrase here would teach a wrong label to anyone building the screen
# against the mock. The alid set itself lives in contracts.ALID_KIND — this
# table only supplies the wording, and asserts below that it covers the same
# ids, so a new alid cannot be added there and silently render blank here.
_AL_TEXT = {
    "9006": "ALIGNMENT FAIL",
    "9007": "FAILURE IN DETECTION OF PATTERN",
    "9035": "FAILURE IN AUTO MEASUREMENT",
}
_ALIDS = tuple(sorted(_AL_TEXT))

assert set(_AL_TEXT) == set(ALID_KIND), (
    "the mock must emit exactly the alids contracts.ALID_KIND renders"
)

# MESEVENTNAME / EQ_STAT / AL_TYPE / LOT_TYPE_CD value SHAPES, not office
# values: these are the spellings the office uses (lowercase-ish free text),
# cycled so the screen sees more than one of each. Only the AL_TEXT strings
# above are claimed to be exact.
_MES_EVENTS = ("waferload", "endrun", "measstart")
_EQ_STATS = ("proc", "wait")
_AL_TYPES = ("warning", "inform")

# Set SKEWNONO_LIVE_ALARM_MOCK_STALE=1 to see the "feed died" screen at home.
_STALE_ENV = "SKEWNONO_LIVE_ALARM_MOCK_STALE"

# An eqp_id no roster carries, so it lands in unmatched_count exactly as a
# still-firewalled tool would at the office. Fabricating one deliberately is
# the only way the roster-gap path is reachable at home: every id the sem_list
# mock emits is, by construction, in the roster.
_UNROSTERED_EQP_ID = "MCD999"

# Events per board, cycled by minute. One slot is 0 so a quiet board stays
# reachable; the rest are sized so that cycling `eqp_ids` (8-17 per fab) against
# `_RECIPES` (4) wraps often enough to put several alarms on the same tool.
_COUNTS = (0, 11, 19, 27)

# ONE tool running ONE recipe, failing over and over: the situation the 측정
# 실패 grouping exists to surface, and the reason that view ranks by count.
#
# Placed deliberately rather than left to the cycling above, which produces a
# pile of 3 at best and only by coincidence — too weak to develop a ranked view
# against, and too fragile to rely on (it moves whenever the roster size does).
#
# FABRICATED CORRELATION, not an office observation. How often a single PPID
# actually piles up within the board window is OFFICE-VERIFY. The mock claims only
# that the SHAPE occurs, which is what the screen was built for; it claims
# nothing about the rate. See CLAUDE.md on marking where a mock deliberately
# differs from what it stands in for.
_HOT_BURST = 6


def _index() -> roster.RosterIndex:
    """The same roster the office reader uses, over the sem_list MOCK fleet.

    Built from sem_list rather than a hardcoded fab whitelist so home and
    office answer "is this fab configured?" by the SAME mechanism. The
    whitelist this replaced listed four fac_ids (M11, M14, M15, M16) among its
    fab names, so 14 of the 17 fabs the sem_list mock generates rendered 미설정
    at home while the office would have served them a board — the exact
    fab/fac confusion MIGRATION.md warns about, reproduced in our own mock.
    """
    from back_dev_home.sem_list.providers.mock import get_sem_list

    return roster.build_index(get_sem_list())


def _event(
    now: int,
    index: int,
    eqp_id: str,
    model: str = "CG6300",
    alid: str | None = None,
    recipe_id: str | None = None,
) -> AlarmEvent:
    """One alarm. `alid` and `recipe_id` default to cycling off the index.

    They are overridable so a caller can PIN them — which is what the repeat
    burst in `get_board` does. Cycling alone can only produce a repeated
    (eqp_id, ppid) by coincidence, and coincidence is not a property a screen
    can be developed against.
    """
    occurred = now - (index * 137) % BOARD_WINDOW_SEC
    alid = alid if alid is not None else _ALIDS[index % len(_ALIDS)]
    occurred_at = board.iso(occurred)
    recipe_id = recipe_id if recipe_id is not None else _RECIPES[index % len(_RECIPES)]
    # RAWID is an int at the office; carried as a string because every other
    # AlarmEvent field is one and the id is only ever compared, never summed.
    # Derived from the minute so the same minute rebuilds the same board.
    #
    # The minute is multiplied by 100, not 10, so the per-minute id blocks do
    # not overlap: at *10, minute N's index 12 collided with minute N+1's
    # index 2. The frontend decides "new since the last poll" by id, and polls
    # straddle minute boundaries constantly — a collision there would make a
    # genuinely new alarm fail to highlight, and it would look like a bug in
    # the highlight code rather than in this line.
    rawid = str(880_000 + (now // 60 % 1000) * 100 + index)
    return {
        # Mirrors normalize.py: RAWID is the id when the feed has one. The
        # composite fallback is not exercised here on purpose — the office
        # feed always carries RAWID, so a mock that dropped it would make the
        # weaker path look like the normal one.
        "id": rawid,
        "rawid": rawid,
        "eqp_id": eqp_id,
        "alarm_modelname": model,
        "alid": alid,
        # AL_CODE is a number key for a category ABOVE the alid (confirmed
        # 2026-08-03); we key off the alid and no screen shows this. WHICH
        # alids share a code is not known, so this varies per alid rather than
        # inventing buckets — a mock that grouped 9007+9035 under one code
        # would be teaching a grouping nobody has verified. Not left blank
        # either: then a screen that ever shows it looks empty only at home.
        "al_code": f"C{alid[-2:]}",
        "al_type": _AL_TYPES[index % len(_AL_TYPES)],
        "kind": ALID_KIND[alid],
        "alarm_name": _AL_TEXT[alid],
        "occurred_at": occurred_at,
        "occurred_epoch": occurred,
        # One lot can trip several alarms, so lot_id cycles slower than the
        # event index — a board where every row had its own lot would hide
        # the "same lot failing on three tools" case the screen is for.
        "lot_id": f"NX{4200 + index // 2:04d}.{index % 2 + 1}",
        "cassette_id": f"FOUP{100 + index % 7:03d}",
        "recipe_id": recipe_id,
        # Byte-equal to recipe_id: the office confirmed the two columns always
        # agree (2026-08-03). Emitted anyway rather than hardcoded blank, so a
        # screen reading either name sees the same thing at home as at work.
        "ppid": recipe_id,
        "operation_desc": "CD MEASUREMENT",
        "step_id": f"{1000 + index % 9:04d}",
        "lot_type_cd": "PROD" if index % 3 else "MONI",
        "meseventname": _MES_EVENTS[index % len(_MES_EVENTS)],
        "eq_stat": _EQ_STATS[index % len(_EQ_STATS)],
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
    # The cycle keeps a 0 so the "최근 20분간 알람이 없습니다." screen stays
    # reachable at home; the other slots are large enough that the 측정 실패
    # view has something to group. See _HOT_BURST below for why size alone is
    # not sufficient.
    slot = (now // 60) % len(_COUNTS)
    count = _COUNTS[slot]
    # Real ids from the roster, so an alarm row resolves to the fab being
    # viewed exactly as it does at the office. The previous fabricated ids
    # (MXCD*) matched no prefix sem_list emits, so the whole attribution path
    # went unexercised at home.
    eqp_ids = index.eqp_ids_in(fab_name, tool_type) or [_UNROSTERED_EQP_ID]
    # ALARM_MODELNAME follows the tool family, since the alarm carries the
    # model of the tool that raised it. A single hardcoded model would have
    # stamped every HV-SEM row CG6300 — the same vendor/family confusion the
    # sem_list mock had to be corrected for.
    model = "TP4000" if tool_type == "hv-sem" else "CG6300"
    events = [_event(now, i, eqp_ids[i % len(eqp_ids)], model) for i in range(count)]

    # The repeat burst: one tool, one recipe, several measurement failures.
    # Indices continue past `count` so every event on the board still has a
    # distinct id. Skipped entirely on the quiet slot — a board that is
    # supposed to be empty must actually be empty.
    hot_eqp = eqp_ids[0]
    hot_recipe = _RECIPES[0]
    burst = [
        # Alternates 9007/9035: both are `meas`, so they land in ONE group.
        # That is the point — the view groups by kind and (eqp_id, ppid), not
        # by alid, and a burst of a single alid would not prove it.
        _event(
            now, count + n, hot_eqp, model,
            alid="9007" if n % 2 else "9035",
            recipe_id=hot_recipe,
        )
        for n in range(_HOT_BURST if count else 0)
    ]
    events += burst

    # One minute in four the facility feed also carries an alarm from
    # equipment no roster knows. Generated as a REAL event and then withheld,
    # rather than incrementing a bare counter, so unmatched_count never claims
    # more was dropped than the feed actually held — the office computes it
    # the same way, by counting events it could not attribute.
    #
    # Keyed on the CYCLE SLOT, not on `count`. It used to read `count == 3`,
    # which silently became unreachable the moment the volume cycle stopped
    # producing a 3 — taking the whole roster-gap path with it.
    withheld = (
        [_event(now, count + _HOT_BURST, _UNROSTERED_EQP_ID)]
        if slot == len(_COUNTS) - 1
        else []
    )

    return board.payload(
        tool_type=tool_type,
        fab_name=fab_name,
        now=now,
        configured=True,
        meta={"fetched_at": now - 2000 if stale else now},
        unmatched_count=len(withheld),
        events=sorted(events, key=lambda e: e["occurred_epoch"], reverse=True),
    )
