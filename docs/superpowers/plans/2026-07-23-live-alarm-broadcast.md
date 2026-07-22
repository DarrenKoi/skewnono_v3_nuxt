# Live Alarm Broadcast Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a per-fab live board that shows align-fail (`ALID=9006`) and measurement-consecutive-fail (`ALID=9100`) alarms from the last 10 minutes, refreshed every 15 seconds.

**Architecture:** A portable writer job on a Flask/APScheduler server polls the in-house alarm API every 15s and keeps a rolling board in office Redis (ZSET keyed by alarm time). SKEWNONO's Flask is a stateless read-only consumer that cuts the board to 10 minutes with a `ZRANGEBYSCORE`. The browser polls that endpoint and replaces its list wholesale. In-house API load is fixed at 4 requests/minute/fab regardless of viewer count.

**Tech Stack:** Flask blueprints + TypedDict contracts (backend), Nuxt 4 + `useState` composables (frontend), Redis sorted sets, APScheduler `IntervalTrigger`.

**Spec:** `docs/superpowers/specs/2026-07-22-live-alarm-broadcast-design.md`

## Global Constraints

- Board horizon `BOARD_WINDOW_SEC = 600`; writer retention `WRITER_PRUNE_SEC = 900`; the invariant `WRITER_PRUNE_SEC >= BOARD_WINDOW_SEC` is asserted at import.
- Normal poll window `POLL_WINDOW_SEC = 60`; writer interval `WRITER_INTERVAL_SEC = 15`; stale threshold `STALE_AFTER_SEC = 90`; future tolerance `FUTURE_TOLERANCE_SEC = 300`.
- Target ALIDs are exactly `9006` → `align` and `9100` → `meas`. Everything else is discarded.
- Redis is the **single clock authority**. Both writer and reader take "now" from the `TIME` command, never from `datetime.now()`.
- Redis is the same instance SKEWNONO's office adapters read, at **db=0** — `_runtime/office_redis.py:73` passes no `db`, so redis-py's default applies and `REDIS_DB` in `.env` is ignored.
- That client sets `decode_responses=False`, so every read returns `bytes` and must be decoded explicitly.
- Key namespace is `skewnono:live_alarm:`; every key carries a 24-hour TTL refreshed on each successful poll.
- The writer imports **nothing** from `back_dev_home`. Its only dependencies are `redis` and `requests`.
- No browser notifications and no audio — production is plain HTTP (`http://sknn.skhynix.com`), where the Notification API is unavailable.
- Backend tests: `.venv/bin/pytest`. Frontend tests: `npm test` in `front-dev-home/` (runs `node --test "app/**/*.test.ts"`).
- Markdown edits require `npm run lint:md` to pass with 0 errors.
- Commit directly to `main`.

## File Structure

**SKEWNONO backend** — `back_dev_home/ebeam/hitachi/live_alarm/`

| File | Responsibility |
| --- | --- |
| `contracts.py` | `AlarmEvent`, `LiveAlarmPayload`, constants, the retention invariant assert |
| `board.py` | Pure functions: `feed_status_for`, `dedupe_by_id`, `parse_members` |
| `data.py` | mock/office dispatcher — the stable seam, never edited afterwards |
| `routes.py` | `GET /api/ebeam/<tool_slug>/live-alarm` |
| `providers/mock.py` | Phase 1 adapter, no Redis |
| `providers/office_example.py` | Redis reader (tracked template; `office.py` is the gitignored copy) |
| `writer/window.py` | Adaptive backfill window (pure) |
| `writer/normalize.py` | In-house rows → `AlarmEvent` + `canonical_json` (pure) |
| `writer/job.py` | `run_once()` — the only thing the host scheduler calls |
| `writer/office_example.py` | In-house API call + `(tool, fab)` → URL map |
| `tests/` | Contract gate + unit tests, including a hand-rolled fake Redis |

**SKEWNONO frontend** — `front-dev-home/app/`

| File | Responsibility |
| --- | --- |
| `utils/liveAlarm.ts` | Pure: `diffNewIds`, `formatElapsed`, `boardCounts` |
| `utils/liveAlarm.test.ts` | Unit tests for the above |
| `composables/useLiveAlarmFeed.ts` | Polling, clock offset, visibility, new-id diffing |
| `components/live-alarm/FeedStatusBar.vue` | Status + last-updated + counts |
| `components/live-alarm/AlarmRow.vue` | One event row |
| `pages/ebeam/cd-sem/[fab]/live-alarm.vue` | CD-SEM page |
| `pages/ebeam/hv-sem/[fab]/live-alarm.vue` | HV-SEM page |
| `utils/features.ts` | Register the `live-alarm` slug |
| `components/nav/FeatureTabs.vue` | Add the tab |

**Scheduler platform** — `/Users/daeyoung/Codes/flask_modules/api/` (separate repo)

| File | Responsibility |
| --- | --- |
| `extension.py` | Add a `fast` executor alongside `default` |
| `schedule.py` | Forward optional per-job scheduler kwargs to `add_job` |

Blueprints need no manual wiring: `back_dev_home/__init__.py:147` globs `**/routes.py` and registers any module exporting `bp`.

---

### Task 1: Contracts and pure board functions

Nothing here touches Redis, Flask, or the network. Establishing it first gives every later task its vocabulary.

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/__init__.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/contracts.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/board.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/__init__.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py`

**Interfaces:**

- Consumes: `ToolType` from `back_dev_home.ebeam.hitachi._tool_specs` (`Literal["cd-sem", "hv-sem"]`).
- Produces:
  - `AlarmEvent`, `LiveAlarmPayload`, `Kind`, `FeedStatus` TypedDicts/Literals
  - `BOARD_WINDOW_SEC`, `WRITER_PRUNE_SEC`, `POLL_WINDOW_SEC`, `WRITER_INTERVAL_SEC`, `STALE_AFTER_SEC`, `FUTURE_TOLERANCE_SEC`, `ALID_KIND`
  - `board.feed_status_for(meta: dict | None, known: bool, *, now: int) -> FeedStatus`
  - `board.dedupe_by_id(events: Iterable[AlarmEvent]) -> list[AlarmEvent]`
  - `board.parse_members(raw: Iterable[bytes]) -> list[AlarmEvent]`

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py`:

```python
"""Pure board logic. No Redis, no Flask — every 'now' is injected."""

from back_dev_home.ebeam.hitachi.live_alarm import board
from back_dev_home.ebeam.hitachi.live_alarm.contracts import STALE_AFTER_SEC


def _meta(polled_at: int, covered_since: int = 0) -> dict:
    return {"polled_at": polled_at, "covered_since": covered_since}


def test_unknown_fab_is_not_configured():
    # Not in the writer's registry: this fab was never wired, which is a
    # different fact from "the feed died" and must look different on screen.
    assert board.feed_status_for(_meta(1000), known=False, now=1000) == "not_configured"


def test_missing_meta_on_a_known_fab_is_stale():
    assert board.feed_status_for(None, known=True, now=1000) == "stale"


def test_fresh_meta_is_live():
    assert board.feed_status_for(_meta(1000), known=True, now=1000) == "live"


def test_exactly_at_threshold_is_still_live():
    now = 1000 + STALE_AFTER_SEC
    assert board.feed_status_for(_meta(1000), known=True, now=now) == "live"


def test_one_second_past_threshold_is_stale():
    now = 1000 + STALE_AFTER_SEC + 1
    assert board.feed_status_for(_meta(1000), known=True, now=now) == "stale"


def test_dedupe_keeps_one_row_per_id():
    rows = [
        {"id": "EQ1|9006|t", "alarm_name": "B"},
        {"id": "EQ1|9006|t", "alarm_name": "A"},
        {"id": "EQ2|9006|t", "alarm_name": "C"},
    ]
    out = board.dedupe_by_id(rows)
    assert len(out) == 2


def test_dedupe_is_deterministic_regardless_of_input_order():
    # Two reader processes must render the same screen from the same ZSET.
    a = {"id": "EQ1|9006|t", "alarm_name": "B"}
    b = {"id": "EQ1|9006|t", "alarm_name": "A"}
    assert board.dedupe_by_id([a, b]) == board.dedupe_by_id([b, a])


def test_parse_members_decodes_bytes():
    raw = [b'{"id":"EQ1|9006|t","eqp_id":"EQ1"}']
    assert board.parse_members(raw) == [{"id": "EQ1|9006|t", "eqp_id": "EQ1"}]


def test_parse_members_skips_a_broken_member():
    # The writer is a separate deployment; a partial schema rollout must not
    # take the whole endpoint down.
    raw = [b'{"id":"ok"}', b'not json at all', b'{"id":"also-ok"}']
    assert [e["id"] for e in board.parse_members(raw)] == ["ok", "also-ok"]


def test_parse_members_survives_every_member_being_broken():
    assert board.parse_members([b'{{{', b'}}}']) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: collection error — `ModuleNotFoundError: No module named 'back_dev_home.ebeam.hitachi.live_alarm'`

- [ ] **Step 3: Write `contracts.py`**

```python
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
```

- [ ] **Step 4: Write `board.py`**

```python
"""Pure board logic shared by every live_alarm provider.

Every function takes `now` as an argument. Nothing here reads a clock, so
boundary behaviour is testable without sleeping or freezing time.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    STALE_AFTER_SEC,
    AlarmEvent,
    FeedStatus,
)


log = logging.getLogger(__name__)

__all__ = ["feed_status_for", "dedupe_by_id", "parse_members"]


def feed_status_for(meta: dict[str, Any] | None, known: bool, *, now: int) -> FeedStatus:
    """Which of the three empty states is this?

    "No alarms" is ambiguous on its own: a healthy quiet fab, a dead feed,
    and an unconfigured fab all render as an empty list. `known` (is this
    fab in the writer's registry?) separates the third; the heartbeat age
    separates the first two.
    """
    if not known:
        return "not_configured"
    if not meta or "polled_at" not in meta:
        return "stale"
    return "live" if now - int(meta["polled_at"]) <= STALE_AFTER_SEC else "stale"


def dedupe_by_id(events: Iterable[AlarmEvent]) -> list[AlarmEvent]:
    """One row per id, chosen deterministically.

    ZSET members are canonical JSON, so the same alarm reported with a
    different decorative field (alarm_name, operation_desc) lands as a
    second member under the same id. Sorting by the serialized member
    before picking makes every reader process render the same screen.
    """
    best: dict[str, tuple[str, AlarmEvent]] = {}
    for event in events:
        key = str(event.get("id", ""))
        marker = json.dumps(event, sort_keys=True, separators=(",", ":"))
        current = best.get(key)
        if current is None or marker < current[0]:
            best[key] = (marker, event)
    return [event for _, event in best.values()]


def parse_members(raw: Iterable[bytes]) -> list[AlarmEvent]:
    """Decode ZSET members, skipping anything unreadable.

    The writer is deployed separately, so a partial rollout can leave a
    member this build cannot parse. Dropping that one member beats 500ing
    the endpoint — same leniency `flask_modules`' read_task_logs applies
    to malformed log entries.
    """
    out: list[AlarmEvent] = []
    for member in raw:
        try:
            text = member.decode("utf-8") if isinstance(member, bytes) else member
            out.append(json.loads(text))
        except (UnicodeDecodeError, ValueError, TypeError):
            log.warning("dropping unparseable live_alarm member: %r", member[:120])
    return out
```

- [ ] **Step 5: Create the package `__init__.py` files**

`back_dev_home/ebeam/hitachi/live_alarm/__init__.py`:

```python
"""Live alarm board — align fail and measurement consecutive fail."""
```

`back_dev_home/ebeam/hitachi/live_alarm/tests/__init__.py`: empty file.

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: 10 passed

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/
git commit -m "feat(live-alarm): add contracts and pure board logic

feed_status_for distinguishes the three empty states (healthy quiet,
dead feed, unconfigured fab) that would otherwise render identically.
dedupe_by_id resolves duplicate ZSET members deterministically so every
reader process renders the same screen. parse_members drops unreadable
members rather than failing the request, since the writer ships
separately and can be mid-rollout."
```

---

### Task 2: Mock provider, dispatcher, and route

At the end of this task the endpoint answers with live-looking data at home, with no Redis anywhere.

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/providers/__init__.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/providers/mock.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/data.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/routes.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_contract.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_routes.py`

**Interfaces:**

- Consumes: `contracts.LiveAlarmPayload`, `contracts.ALID_KIND`, `board` (Task 1); `get_data_provider` from `back_dev_home._runtime.data_provider`; `resolve_tool_type_from_slug` from `back_dev_home.ebeam.hitachi._tool_specs`.
- Produces: `data.get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload`; blueprint `bp` serving `GET /api/ebeam/<tool_slug>/live-alarm?fab_name=<name>`.

- [ ] **Step 1: Write the failing contract test**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_contract.py`:

```python
"""Contract gate for live_alarm. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
Office: SKEWNONO_LIVE_ALARM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.live_alarm import data
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    ALID_KIND,
    AlarmEvent,
    LiveAlarmPayload,
)


def test_get_board_matches_contract():
    assert_matches(data.get_board("cd-sem", "R3"), LiveAlarmPayload)


def test_events_match_contract():
    board = data.get_board("cd-sem", "R3")
    assert isinstance(board["events"], list)
    for event in board["events"]:
        assert_matches(event, AlarmEvent)


def test_every_event_carries_a_known_kind():
    for event in data.get_board("cd-sem", "R3")["events"]:
        assert event["kind"] == ALID_KIND[event["alid"]]


def test_feed_status_is_one_of_three():
    assert data.get_board("cd-sem", "R3")["feed_status"] in {
        "live", "stale", "not_configured",
    }
```

- [ ] **Step 2: Write the failing route test**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_routes.py`:

```python
import pytest

from back_dev_home import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_returns_a_board_for_a_valid_tool_slug(client):
    response = client.get("/api/ebeam/cd-sem/live-alarm?fab_name=R3")
    assert response.status_code == 200
    assert response.get_json()["fab_name"] == "R3"


def test_hv_sem_url_exists_too(client):
    assert client.get("/api/ebeam/hv-sem/live-alarm?fab_name=R3").status_code == 200


def test_unknown_tool_slug_is_400(client):
    assert client.get("/api/ebeam/nope/live-alarm?fab_name=R3").status_code == 400


def test_missing_fab_name_is_400(client):
    assert client.get("/api/ebeam/cd-sem/live-alarm").status_code == 400
```

- [ ] **Step 3: Run both to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...live_alarm.data'`

- [ ] **Step 4: Write `providers/mock.py`**

```python
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
```

- [ ] **Step 5: Write `data.py`**

```python
"""Stable live_alarm data seam with mock/office adapters.

Do not edit this file when wiring the office: it dispatches, nothing more.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm.contracts import LiveAlarmPayload
from back_dev_home.ebeam.hitachi.live_alarm.providers import mock as mock_provider


__all__ = ["get_board"]


def _provider():
    if get_data_provider("live_alarm") == "office":
        from back_dev_home.ebeam.hitachi.live_alarm.providers import office
        return office
    return mock_provider


def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    return _provider().get_board(tool_type, fab_name)
```

- [ ] **Step 6: Write `routes.py`**

```python
from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import resolve_tool_type_from_slug
from back_dev_home.ebeam.hitachi.live_alarm.data import get_board


bp = Blueprint("ebeam_live_alarm", __name__)


@bp.get("/ebeam/<tool_slug>/live-alarm")
def live_alarm_board(tool_slug: str):
    tool_type = resolve_tool_type_from_slug(tool_slug)
    if tool_type is None:
        return jsonify(error=f"unknown tool slug: {tool_slug}"), 400

    fab_name = (request.args.get("fab_name") or "").strip()
    if not fab_name:
        return jsonify(error="fab_name is required"), 400

    return jsonify(get_board(tool_type, fab_name))
```

- [ ] **Step 7: Create `providers/__init__.py`**

Empty file at `back_dev_home/ebeam/hitachi/live_alarm/providers/__init__.py`.

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: 18 passed

- [ ] **Step 9: Verify the whole backend suite still passes**

Run: `.venv/bin/pytest back_dev_home -q`
Expected: all pass, count increased by 18

- [ ] **Step 10: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/
git commit -m "feat(live-alarm): add mock provider, dispatcher, and route

GET /api/ebeam/<tool_slug>/live-alarm?fab_name=R3 now answers from the
mock adapter, so the page can be built and reviewed at home with no
Redis. The mock varies its board by the current minute so the screen
visibly changes during development, and SKEWNONO_LIVE_ALARM_MOCK_STALE
renders the dead-feed state on demand.

No blueprint wiring needed: the app factory globs **/routes.py."
```

---

### Task 3: Frontend pure utilities

**Files:**

- Create: `front-dev-home/app/utils/liveAlarm.ts`
- Create: `front-dev-home/app/utils/liveAlarm.test.ts`

**Interfaces:**

- Produces:
  - `export interface LiveAlarmEvent { id: string; eqp_id: string; alid: string; kind: 'align' | 'meas'; alarm_name: string; occurred_at: string; occurred_epoch: number; recipe_id: string; operation_desc: string; lot_type_cd: string }`
  - `export interface LiveAlarmPayload { fab_name: string; tool_type: string; feed_status: 'live' | 'stale' | 'not_configured'; polled_at: string | null; covered_since: string | null; server_now: string; board_window_sec: number; events: LiveAlarmEvent[] }`
  - `diffNewIds(prev: string[], next: string[]): string[]`
  - `formatElapsed(ms: number): string`
  - `boardCounts(events: LiveAlarmEvent[]): { align: number; meas: number }`

- [ ] **Step 1: Write the failing tests**

Create `front-dev-home/app/utils/liveAlarm.test.ts`:

```ts
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { diffNewIds, formatElapsed, boardCounts } from './liveAlarm'
import type { LiveAlarmEvent } from './liveAlarm'

const event = (id: string, kind: 'align' | 'meas'): LiveAlarmEvent => ({
  id, eqp_id: 'EQ1', alid: kind === 'align' ? '9006' : '9100', kind,
  alarm_name: 'x', occurred_at: '2026-07-23 10:00:00+09:00', occurred_epoch: 1,
  recipe_id: '', operation_desc: '', lot_type_cd: ''
})

describe('diffNewIds', () => {
  it('returns ids present in next but not prev', () => {
    assert.deepEqual(diffNewIds(['a'], ['a', 'b']), ['b'])
  })

  it('returns nothing when the sets match', () => {
    assert.deepEqual(diffNewIds(['a', 'b'], ['b', 'a']), [])
  })

  it('ignores ids that disappeared', () => {
    assert.deepEqual(diffNewIds(['a', 'b'], ['a']), [])
  })

  it('treats the first load as all-new', () => {
    assert.deepEqual(diffNewIds([], ['a', 'b']), ['a', 'b'])
  })
})

describe('formatElapsed', () => {
  it('shows seconds under a minute', () => {
    assert.equal(formatElapsed(45_000), '45초 전')
  })

  it('shows minutes past a minute', () => {
    assert.equal(formatElapsed(185_000), '3분 전')
  })

  it('shows hours past an hour', () => {
    assert.equal(formatElapsed(7_400_000), '2시간 전')
  })

  it('clamps negatives to now instead of rendering "-2분 전"', () => {
    // A clock still settling must never produce a negative elapsed label.
    assert.equal(formatElapsed(-5_000), '방금')
  })
})

describe('boardCounts', () => {
  it('counts each kind', () => {
    const counts = boardCounts([event('1', 'align'), event('2', 'meas'), event('3', 'align')])
    assert.deepEqual(counts, { align: 2, meas: 1 })
  })

  it('returns zeroes for an empty board', () => {
    assert.deepEqual(boardCounts([]), { align: 0, meas: 0 })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd front-dev-home && npm test`
Expected: FAIL — cannot find module `./liveAlarm`

- [ ] **Step 3: Write `liveAlarm.ts`**

```ts
// Pure helpers for the live alarm board. Everything here is deterministic
// and clock-free so the board's time-dependent behaviour can be tested
// without faking timers.

export interface LiveAlarmEvent {
  id: string
  eqp_id: string
  alid: string
  kind: 'align' | 'meas'
  alarm_name: string
  occurred_at: string
  occurred_epoch: number
  recipe_id: string
  operation_desc: string
  lot_type_cd: string
}

export type FeedStatus = 'live' | 'stale' | 'not_configured'

export interface LiveAlarmPayload {
  fab_name: string
  tool_type: string
  feed_status: FeedStatus
  polled_at: string | null
  covered_since: string | null
  server_now: string
  board_window_sec: number
  events: LiveAlarmEvent[]
}

// Which ids arrived since the previous poll. Per-viewer by design: "new"
// means new to the person watching, not new to the fab.
export const diffNewIds = (prev: string[], next: string[]): string[] => {
  const seen = new Set(prev)
  return next.filter(id => !seen.has(id))
}

export const formatElapsed = (ms: number): string => {
  if (ms < 1000) return '방금'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}초 전`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}분 전`
  return `${Math.floor(minutes / 60)}시간 전`
}

export const boardCounts = (events: LiveAlarmEvent[]): { align: number, meas: number } => ({
  align: events.filter(e => e.kind === 'align').length,
  meas: events.filter(e => e.kind === 'meas').length
})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && npm test`
Expected: all pass, 10 new assertions from this file

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/liveAlarm.ts front-dev-home/app/utils/liveAlarm.test.ts
git commit -m "feat(live-alarm): add pure frontend helpers

diffNewIds, formatElapsed, boardCounts kept clock-free so the board's
time-dependent behaviour is testable without faking timers. formatElapsed
clamps negatives to '방금' — a clock offset still settling must never
render '-2분 전'."
```

---

### Task 4: The polling composable

**Files:**

- Create: `front-dev-home/app/composables/useLiveAlarmFeed.ts`
- Create: `front-dev-home/app/composables/useLiveAlarmFeed.test.ts`

**Interfaces:**

- Consumes: `LiveAlarmPayload`, `LiveAlarmEvent`, `diffNewIds` from `~/utils/liveAlarm` (Task 3); the endpoint from Task 2.
- Produces:
  - `POLL_INTERVAL_MS = 15_000`, `POLL_JITTER_MS = 3_000`
  - `nextDelay(random: number): number` — exported for testing
  - `applyPoll(state, payload, receivedAt)` — exported pure reducer
  - `useLiveAlarmFeed(toolSlug: Ref<string> | string, fabName: Ref<string> | string)` returning `{ events, feedStatus, polledAt, serverOffsetMs, newIds, error, markSeen }`

- [ ] **Step 1: Write the failing tests**

Create `front-dev-home/app/composables/useLiveAlarmFeed.test.ts`:

```ts
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { nextDelay, applyPoll, POLL_INTERVAL_MS, POLL_JITTER_MS } from './useLiveAlarmFeed'
import type { LiveAlarmPayload } from '~/utils/liveAlarm'

const payload = (ids: string[], serverNowEpochMs: number): LiveAlarmPayload => ({
  fab_name: 'R3',
  tool_type: 'cd-sem',
  feed_status: 'live',
  polled_at: '2026-07-23 10:00:00+09:00',
  covered_since: '2026-07-23 09:50:00+09:00',
  server_now: new Date(serverNowEpochMs).toISOString(),
  board_window_sec: 600,
  events: ids.map(id => ({
    id, eqp_id: 'EQ1', alid: '9006', kind: 'align' as const, alarm_name: 'Align Fail',
    occurred_at: '2026-07-23 10:00:00+09:00', occurred_epoch: 1,
    recipe_id: '', operation_desc: '', lot_type_cd: ''
  }))
})

describe('nextDelay', () => {
  it('sits at the interval when random is centred', () => {
    assert.equal(nextDelay(0.5), POLL_INTERVAL_MS)
  })

  it('never goes below interval minus jitter', () => {
    assert.equal(nextDelay(0), POLL_INTERVAL_MS - POLL_JITTER_MS)
  })

  it('never goes above interval plus jitter', () => {
    assert.equal(nextDelay(1), POLL_INTERVAL_MS + POLL_JITTER_MS)
  })
})

describe('applyPoll', () => {
  it('replaces the list rather than merging', () => {
    // The server sends a complete board every time; merging client-side
    // would resurrect events the server already aged out.
    const first = applyPoll({ ids: [], seenIds: [] }, payload(['a', 'b'], 1000), 1000)
    const second = applyPoll(first, payload(['c'], 2000), 2000)
    assert.deepEqual(second.events.map(e => e.id), ['c'])
  })

  it('reports ids that are new since the previous poll', () => {
    const first = applyPoll({ ids: [], seenIds: ['a'] }, payload(['a'], 1000), 1000)
    const second = applyPoll(first, payload(['a', 'b'], 2000), 2000)
    assert.deepEqual(second.newIds, ['b'])
  })

  it('derives the clock offset from server_now minus receive time', () => {
    const state = applyPoll({ ids: [], seenIds: [] }, payload([], 5_000), 3_000)
    assert.equal(state.serverOffsetMs, 2_000)
  })

  it('handles a browser clock running ahead of the server', () => {
    const state = applyPoll({ ids: [], seenIds: [] }, payload([], 3_000), 5_000)
    assert.equal(state.serverOffsetMs, -2_000)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd front-dev-home && npm test`
Expected: FAIL — cannot find module `./useLiveAlarmFeed`

- [ ] **Step 3: Write `useLiveAlarmFeed.ts`**

```ts
import { diffNewIds } from '~/utils/liveAlarm'
import type { LiveAlarmEvent, LiveAlarmPayload, FeedStatus } from '~/utils/liveAlarm'

export const POLL_INTERVAL_MS = 15_000
export const POLL_JITTER_MS = 3_000

// Jitter keeps many open tabs from hitting Flask in the same millisecond.
// Exported (rather than calling Math.random inline) so it stays testable.
export const nextDelay = (random: number): number =>
  POLL_INTERVAL_MS + Math.round((random * 2 - 1) * POLL_JITTER_MS)

interface FeedState {
  events: LiveAlarmEvent[]
  ids: string[]
  seenIds: string[]
  newIds: string[]
  feedStatus: FeedStatus
  polledAt: string | null
  serverOffsetMs: number
}

// Pure reducer: one poll response in, next state out. The server ships a
// complete 10-minute board, so this replaces rather than merges — that is
// the whole reason the client carries no accumulation logic.
export const applyPoll = (
  prev: Partial<FeedState>,
  payload: LiveAlarmPayload,
  receivedAtMs: number
): FeedState => {
  const ids = payload.events.map(e => e.id)
  const seenIds = prev.seenIds ?? []
  return {
    events: payload.events,
    ids,
    seenIds,
    newIds: diffNewIds(seenIds.length ? seenIds : (prev.ids ?? []), ids),
    feedStatus: payload.feed_status,
    polledAt: payload.polled_at,
    serverOffsetMs: Date.parse(payload.server_now) - receivedAtMs
  }
}

export const useLiveAlarmFeed = (toolSlug: string, fabName: string) => {
  const key = `live-alarm:${toolSlug}:${fabName}`
  const state = useState<FeedState>(key, () => ({
    events: [], ids: [], seenIds: [], newIds: [],
    feedStatus: 'live', polledAt: null, serverOffsetMs: 0
  }))
  const error = useState<string | null>(`${key}:error`, () => null)

  let timer: ReturnType<typeof setTimeout> | null = null
  let consecutiveFailures = 0

  const poll = async () => {
    try {
      const payload = await $fetch<LiveAlarmPayload>(
        `/api/ebeam/${toolSlug}/live-alarm`,
        { params: { fab_name: fabName } }
      )
      state.value = applyPoll(state.value, payload, Date.now())
      consecutiveFailures = 0
      error.value = null
    } catch (e) {
      // One or two misses are ordinary; only sustained failure is worth
      // showing, and the previous board stays on screen meanwhile.
      consecutiveFailures += 1
      if (consecutiveFailures >= 3) error.value = '연결이 불안정합니다'
    }
  }

  const schedule = () => {
    stop()
    timer = setTimeout(async () => {
      await poll()
      schedule()
    }, nextDelay(Math.random()))
  }

  const stop = () => {
    if (timer !== null) clearTimeout(timer)
    timer = null
  }

  const onVisibility = () => {
    if (document.visibilityState === 'hidden') {
      stop()
      return
    }
    // The server holds the whole board, so returning needs no catch-up
    // logic — one ordinary poll restores the full screen.
    void poll()
    schedule()
  }

  onMounted(() => {
    void poll()
    schedule()
    document.addEventListener('visibilitychange', onVisibility)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', onVisibility)
  })

  const markSeen = () => {
    state.value = { ...state.value, seenIds: state.value.ids, newIds: [] }
  }

  return {
    events: computed(() => state.value.events),
    feedStatus: computed(() => state.value.feedStatus),
    polledAt: computed(() => state.value.polledAt),
    serverOffsetMs: computed(() => state.value.serverOffsetMs),
    newIds: computed(() => state.value.newIds),
    error,
    markSeen
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd front-dev-home && npm test`
Expected: all pass, 7 new assertions from this file

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useLiveAlarmFeed.ts front-dev-home/app/composables/useLiveAlarmFeed.test.ts
git commit -m "feat(live-alarm): add the polling composable

Owns polling, clock offset, tab visibility, and new-id diffing so the
page component only renders. applyPoll and nextDelay are exported as pure
functions to keep that logic testable without timers or a DOM.

Replaces rather than merges on each poll: the server ships a complete
10-minute board, so client-side accumulation would resurrect events the
server already aged out. Poll delay carries +/-3s jitter so many open
tabs do not hit Flask in the same millisecond."
```

---

### Task 5: Page, components, and navigation

At the end of this task the feature is usable end-to-end at home.

**Files:**

- Create: `front-dev-home/app/components/live-alarm/FeedStatusBar.vue`
- Create: `front-dev-home/app/components/live-alarm/AlarmRow.vue`
- Create: `front-dev-home/app/pages/ebeam/cd-sem/[fab]/live-alarm.vue`
- Create: `front-dev-home/app/pages/ebeam/hv-sem/[fab]/live-alarm.vue`
- Modify: `front-dev-home/app/utils/features.ts:4-15` (the `FEATURE_SLUGS` array)
- Modify: `front-dev-home/app/components/nav/FeatureTabs.vue`

**Interfaces:**

- Consumes: `useLiveAlarmFeed` (Task 4), `formatElapsed` / `boardCounts` / `LiveAlarmEvent` (Task 3).
- Produces: routes `/ebeam/cd-sem/[fab]/live-alarm` and `/ebeam/hv-sem/[fab]/live-alarm`; the `'live-alarm'` entry in `FEATURE_SLUGS`.

- [ ] **Step 1: Register the feature slug**

In `front-dev-home/app/utils/features.ts`, add `'live-alarm'` to the `FEATURE_SLUGS` array (after `'hardware'`):

```ts
export const FEATURE_SLUGS = [
  'storage',
  'recipe-search',
  // recipe-tat / fail-issue merged into recipe-status; their old routes
  // redirect via route middleware before any layout observes the path, so
  // the legacy slugs never appear in route.path and are not listed here.
  'recipe-status',
  'hardware',
  'live-alarm',
  'device-statistics',
  'skewvoir',
  'skew-check'
] as const
```

Do **not** add it to `FABLESS_FEATURES` — this page is fab-scoped.

- [ ] **Step 2: Verify existing frontend tests still pass**

Run: `cd front-dev-home && npm test`
Expected: all pass. `FEATURE_SLUG_REGEX` is built from this array, so a typo here surfaces as a routing test failure.

- [ ] **Step 3: Write `FeedStatusBar.vue`**

```vue
<script setup lang="ts">
import { formatElapsed, boardCounts } from '~/utils/liveAlarm'
import type { LiveAlarmEvent, FeedStatus } from '~/utils/liveAlarm'

const props = defineProps<{
  feedStatus: FeedStatus
  polledAt: string | null
  serverOffsetMs: number
  events: LiveAlarmEvent[]
}>()

const counts = computed(() => boardCounts(props.events))

// The last-updated time is shown whether or not there are alarms. An empty
// board means nothing on its own: "quiet fab" and "we know nothing" render
// identically without it.
const sinceLastPoll = computed(() => {
  if (!props.polledAt) return null
  const now = Date.now() + props.serverOffsetMs
  return formatElapsed(now - Date.parse(props.polledAt))
})

const tone = computed(() => ({
  live: { color: 'success' as const, label: '수신 중' },
  stale: { color: 'warning' as const, label: '피드 지연' },
  not_configured: { color: 'neutral' as const, label: '미설정' }
}[props.feedStatus]))
</script>

<template>
  <div class="flex flex-wrap items-center gap-3 rounded-lg border border-default px-4 py-3">
    <UBadge :color="tone.color" variant="subtle">{{ tone.label }}</UBadge>

    <span v-if="sinceLastPoll" class="text-sm text-muted">
      마지막 갱신 {{ sinceLastPoll }}
    </span>
    <span v-else class="text-sm text-muted">갱신 기록 없음</span>

    <span class="ml-auto text-sm">
      Align <strong>{{ counts.align }}</strong>건
      <span class="mx-2 text-muted">·</span>
      측정 <strong>{{ counts.meas }}</strong>건
    </span>
  </div>
</template>
```

- [ ] **Step 4: Write `AlarmRow.vue`**

```vue
<script setup lang="ts">
import { formatElapsed } from '~/utils/liveAlarm'
import type { LiveAlarmEvent } from '~/utils/liveAlarm'

const props = defineProps<{
  event: LiveAlarmEvent
  serverOffsetMs: number
  isNew: boolean
  toolSlug: string
  fab: string
}>()

const elapsed = computed(() =>
  formatElapsed(Date.now() + props.serverOffsetMs - props.event.occurred_epoch * 1000)
)

// Checking the recipe is the natural next action after seeing the alarm.
const recipeLink = computed(() =>
  props.event.recipe_id
    ? `/ebeam/${props.toolSlug}/${props.fab}/recipe-search?q=${encodeURIComponent(props.event.recipe_id)}`
    : null
)
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-default px-4 py-3"
    :class="isNew ? 'bg-primary-50 dark:bg-primary-950' : ''"
  >
    <UBadge :color="event.kind === 'align' ? 'error' : 'warning'" variant="subtle">
      {{ event.kind === 'align' ? 'Align Fail' : '측정 연속 실패' }}
    </UBadge>

    <span class="text-lg font-semibold tracking-tight">{{ event.eqp_id }}</span>

    <span class="text-sm text-muted">{{ elapsed }}</span>

    <NuxtLink v-if="recipeLink" :to="recipeLink" class="text-sm underline">
      {{ event.recipe_id }}
    </NuxtLink>
    <span v-else class="text-sm text-muted">레시피 정보 없음</span>

    <span class="ml-auto text-xs text-muted">
      {{ event.operation_desc }}
      <template v-if="event.lot_type_cd"> · {{ event.lot_type_cd }}</template>
    </span>
  </div>
</template>
```

- [ ] **Step 5: Write the CD-SEM page**

`front-dev-home/app/pages/ebeam/cd-sem/[fab]/live-alarm.vue`:

```vue
<script setup lang="ts">
const route = useRoute()
const fab = computed(() => String(route.params.fab))
const toolSlug = 'cd-sem'

const { events, feedStatus, polledAt, serverOffsetMs, newIds, error, markSeen } =
  useLiveAlarmFeed(toolSlug, fab.value)

const newIdSet = computed(() => new Set(newIds.value))

useHead({
  title: computed(() =>
    newIds.value.length
      ? `(${newIds.value.length}) 라이브 알람 · ${fab.value}`
      : `라이브 알람 · ${fab.value}`
  )
})
</script>

<template>
  <div class="space-y-4" @click="markSeen" @scroll.passive="markSeen">
    <FeedStatusBar
      :feed-status="feedStatus"
      :polled-at="polledAt"
      :server-offset-ms="serverOffsetMs"
      :events="events"
    />

    <UAlert v-if="error" color="error" variant="subtle" :description="error" />

    <UAlert
      v-if="feedStatus === 'not_configured'"
      color="neutral"
      variant="subtle"
      title="라이브 알람 미설정"
      :description="`${fab} 팹은 아직 라이브 알람 수집 대상이 아닙니다.`"
    />

    <div v-else-if="events.length" class="rounded-lg border border-default">
      <AlarmRow
        v-for="event in events"
        :key="event.id"
        :event="event"
        :server-offset-ms="serverOffsetMs"
        :is-new="newIdSet.has(event.id)"
        :tool-slug="toolSlug"
        :fab="fab"
      />
    </div>

    <div v-else class="rounded-lg border border-default px-4 py-10 text-center text-muted">
      최근 10분간 알람이 없습니다.
    </div>
  </div>
</template>
```

- [ ] **Step 6: Write the HV-SEM page**

`front-dev-home/app/pages/ebeam/hv-sem/[fab]/live-alarm.vue` — identical to Step 5 except:

```ts
const toolSlug = 'hv-sem'
```

- [ ] **Step 7: Add the navigation tab**

In `front-dev-home/app/components/nav/FeatureTabs.vue`, add a tab entry alongside the existing ones, following whatever shape that file already uses for `recipe-status` and `hardware`. Label it `라이브 알람`, slug `live-alarm`, and place it after `hardware`.

- [ ] **Step 8: Run the frontend suite**

Run: `cd front-dev-home && npm test`
Expected: all pass

- [ ] **Step 9: Verify in the running app**

Start Flask and Nuxt per the `verify` skill, then open
`http://100.103.116.55:3000/ebeam/cd-sem/R3/live-alarm`.

Confirm: the status bar shows 수신 중 with a last-updated time; the row count changes as minutes pass; new rows highlight; the tab title gains a `(N)` prefix and clears on click. Then restart Flask with `SKEWNONO_LIVE_ALARM_MOCK_STALE=1` and confirm the bar flips to 피드 지연 while the last-updated time keeps growing.

- [ ] **Step 10: Commit**

```bash
git add front-dev-home/app/components/live-alarm/ front-dev-home/app/pages/ebeam/ front-dev-home/app/utils/features.ts front-dev-home/app/components/nav/FeatureTabs.vue
git commit -m "feat(live-alarm): add the board page for CD-SEM and HV-SEM

The status bar shows feed state and last-updated time whether or not
there are alarms: an empty board is ambiguous without it, since a quiet
fab and a dead feed look identical. not_configured renders as its own
message so an unwired fab is not mistaken for a broken one.

Registered 'live-alarm' in FEATURE_SLUGS (fab-scoped, so not in
FABLESS_FEATURES) and added the nav tab."
```

---

### Task 6: Scheduler platform changes (`flask_modules` repo)

This lands **before** Task 9's deployment, because the writer job cannot be registered correctly without it. Both changes are additive: existing jobs specify neither new key and keep their current behaviour.

**Files (different repo — `/Users/daeyoung/Codes/flask_modules/`):**

- Modify: `api/extension.py:117-119` (`SCHEDULER_EXECUTORS`)
- Modify: `api/schedule.py:172-178` (the `add_job` call inside `init_jobs`)
- Test: `tests/test_api_schedule.py`

**Interfaces:**

- Produces: a `fast` executor name usable as `"executor": "fast"` in `JOB_FUNCTIONS`; pass-through of the `misfire_grace_time` and `executor` keys from a `JOB_FUNCTIONS` entry into `add_job`.

- [ ] **Step 1: Write the failing test**

Add to `/Users/daeyoung/Codes/flask_modules/tests/test_api_schedule.py`:

```python
def test_optional_scheduler_kwargs_reach_add_job(monkeypatch):
    """A 15s job needs its own misfire window and executor.

    Without this pass-through the SCHEDULER_JOB_DEFAULTS misfire_grace_time
    of 60s applies to every job, which is far too long for a job that fires
    every 15 seconds.
    """
    captured = {}

    def fake_add_job(**kwargs):
        captured[kwargs["id"]] = kwargs

    monkeypatch.setattr(schedule.scheduler, "add_job", fake_add_job)
    monkeypatch.setitem(
        schedule.JOB_FUNCTIONS,
        "probe",
        {
            "fn": lambda: None,
            "trigger": IntervalTrigger(seconds=15),
            "lock_ttl": 45,
            "manual_dispatch": True,
            "misfire_grace_time": 10,
            "executor": "fast",
        },
    )

    schedule.init_jobs(_app_with_config(), register_with_scheduler=True)

    assert captured["probe"]["misfire_grace_time"] == 10
    assert captured["probe"]["executor"] == "fast"


def test_existing_jobs_pass_no_optional_kwargs(monkeypatch):
    """Backward compatibility: jobs without the keys must be unchanged."""
    captured = {}

    def fake_add_job(**kwargs):
        captured[kwargs["id"]] = kwargs

    monkeypatch.setattr(schedule.scheduler, "add_job", fake_add_job)
    schedule.init_jobs(_app_with_config(), register_with_scheduler=True)

    assert "misfire_grace_time" not in captured["task1"]
    assert "executor" not in captured["task1"]


def test_fast_executor_is_registered():
    app = _app_with_config()
    assert "fast" in app.config["SCHEDULER_EXECUTORS"]
    assert "default" in app.config["SCHEDULER_EXECUTORS"]
```

Add whatever imports and the `_app_with_config()` helper the existing tests in that file already use — follow their established shape rather than inventing a new fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/daeyoung/Codes/flask_modules && python -m pytest tests/test_api_schedule.py -v`
Expected: FAIL — `misfire_grace_time` missing from the captured kwargs, and `KeyError: 'fast'`

- [ ] **Step 3: Add the `fast` executor**

In `api/extension.py`, replace the `SCHEDULER_EXECUTORS` assignment:

```python
    # 2 CPU / 8 GiB cloud env, 4 uWSGI workers → ~2 GiB per worker. Cap the
    # scheduler thread pool at 4 so the worker hosting it (worker_id=1) keeps
    # headroom for HTTP traffic and doesn't OOM when long jobs (10-20 min,
    # pandas/OpenSearch heavy) overlap.
    #
    # "fast" is a separate single-thread lane for sub-minute jobs. Sharing
    # "default" would let four concurrent long jobs starve a 15s job for
    # 10+ minutes, and coalesce=True silently drops the missed fires.
    app.config["SCHEDULER_EXECUTORS"] = {
        "default": ThreadPoolExecutor(max_workers=4),
        "fast": ThreadPoolExecutor(max_workers=1),
    }
```

- [ ] **Step 4: Forward the optional kwargs**

In `api/schedule.py`, inside `init_jobs`, replace the `scheduler.add_job(...)` call:

```python
        if register_with_scheduler:
            # Optional per-job scheduler settings. Entries that omit these
            # keys behave exactly as before (SCHEDULER_JOB_DEFAULTS applies).
            optional = {
                key: spec[key]
                for key in ("misfire_grace_time", "executor")
                if key in spec
            }
            scheduler.add_job(
                id=name,
                func="api.schedule:run_registered_job",
                args=[name],
                trigger=spec["trigger"],
                replace_existing=True,
                **optional,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/daeyoung/Codes/flask_modules && python -m pytest tests/ -v`
Expected: all pass, including the three new tests

- [ ] **Step 6: Commit (in the `flask_modules` repo)**

```bash
cd /Users/daeyoung/Codes/flask_modules
git add api/extension.py api/schedule.py tests/test_api_schedule.py
git commit -m "feat(api): add a fast executor and per-job scheduler kwargs

init_jobs forwarded only id/func/args/trigger/replace_existing to
add_job, so a misfire_grace_time written in a JOB_FUNCTIONS entry was
silently ignored and the 60s default applied. Sub-minute jobs need a
much shorter window.

The new single-thread 'fast' executor gives sub-minute jobs their own
lane. On the shared 4-slot default pool, four concurrent 10-20 minute
jobs can starve a 15s job for the whole time they run, and coalesce=True
drops the missed fires rather than queueing them.

Both are opt-in: entries that specify neither key are unchanged."
```

---

### Task 7: Writer pure logic — window and normalization

The writer imports nothing from `back_dev_home`, so these are standalone modules that happen to live in the SKEWNONO repo.

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/writer/__init__.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/writer/window.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/writer/normalize.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_window.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_normalize.py`

**Interfaces:**

- Consumes: nothing from SKEWNONO. Constants are redeclared locally on purpose.
- Produces:
  - `window.compute_window(last_polled_at: int | None, events_key_exists: bool, *, now: int) -> tuple[int, int]` returning `(window_sec, covered_since_epoch)`
  - `normalize.to_events(rows: list[dict], *, now: int) -> list[dict]`
  - `normalize.canonical_json(event: dict) -> str`

- [ ] **Step 1: Write the failing window tests**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_window.py`:

```python
"""Adaptive backfill. A fixed window loses alarms whenever the writer
stalls longer than that window, and the heartbeat still reads fresh —
so the loss is invisible. These tests pin the recovery behaviour."""

from back_dev_home.ebeam.hitachi.live_alarm.writer.window import (
    BOARD_WINDOW_SEC,
    POLL_WINDOW_SEC,
    compute_window,
)


NOW = 1_000_000


def test_steady_state_uses_the_normal_window():
    window, _ = compute_window(NOW - 15, events_key_exists=True, now=NOW)
    assert window == POLL_WINDOW_SEC


def test_a_short_gap_still_uses_the_normal_window():
    # 45s gap is inside the 60s window already — no widening needed.
    window, _ = compute_window(NOW - 45, events_key_exists=True, now=NOW)
    assert window == POLL_WINDOW_SEC


def test_a_gap_past_the_window_widens_the_query():
    # This is the case a fixed 60s window loses silently.
    window, _ = compute_window(NOW - 75, events_key_exists=True, now=NOW)
    assert window > POLL_WINDOW_SEC
    assert window >= 75


def test_a_huge_gap_is_capped_at_the_board_horizon():
    # The board only ever shows 10 minutes, so a 10-minute query fully
    # rebuilds it however long the outage was. No partial-recovery state.
    window, _ = compute_window(NOW - 86_400, events_key_exists=True, now=NOW)
    assert window == BOARD_WINDOW_SEC


def test_no_previous_poll_is_a_cold_start():
    window, _ = compute_window(None, events_key_exists=True, now=NOW)
    assert window == BOARD_WINDOW_SEC


def test_a_missing_events_key_forces_a_cold_start():
    # Redis restart or maxmemory eviction. Without this the next poll would
    # write 60 seconds of events plus a fresh heartbeat, producing an empty
    # board that claims to be live.
    window, _ = compute_window(NOW - 15, events_key_exists=False, now=NOW)
    assert window == BOARD_WINDOW_SEC


def test_covered_since_matches_the_window():
    window, covered_since = compute_window(NOW - 75, events_key_exists=True, now=NOW)
    assert covered_since == NOW - window
```

- [ ] **Step 2: Write the failing normalize tests**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_normalize.py`:

```python
from back_dev_home.ebeam.hitachi.live_alarm.writer.normalize import (
    canonical_json,
    to_events,
)


NOW = 1_753_000_000


def _row(alid="9006", eqp_id="MXCD101", utc9="2026-07-23 10:00:00"):
    return {
        "EQP_ID": eqp_id,
        "ALID": alid,
        "ALARM_NAME": "Align Fail",
        "UTC9": utc9,
        "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT",
        "LOT_TYPE_CD": "PROD",
    }


def test_maps_alid_to_kind():
    assert to_events([_row("9006")], now=NOW)[0]["kind"] == "align"
    assert to_events([_row("9100")], now=NOW)[0]["kind"] == "meas"


def test_drops_alarms_outside_the_two_target_alids():
    assert to_events([_row("1001")], now=NOW) == []


def test_tolerates_a_float_shaped_alid():
    # The in-house feed has been seen emitting "9006.0" via pandas.
    assert to_events([_row("9006.0")], now=NOW)[0]["kind"] == "align"


def test_builds_a_stable_id():
    event = to_events([_row()], now=NOW)[0]
    assert event["id"] == f"MXCD101|9006|{event['occurred_at']}"


def test_occurred_at_carries_an_explicit_offset():
    assert to_events([_row()], now=NOW)[0]["occurred_at"].endswith("+09:00")


def test_occurred_epoch_is_populated():
    assert isinstance(to_events([_row()], now=NOW)[0]["occurred_epoch"], int)


def test_drops_events_dated_far_in_the_future():
    # An upstream clock running fast would otherwise park an event above
    # the pruning boundary forever.
    far = "2099-01-01 00:00:00"
    assert to_events([_row(utc9=far)], now=NOW) == []


def test_drops_rows_with_an_unparseable_timestamp():
    assert to_events([_row(utc9="not a date")], now=NOW) == []


def test_canonical_json_is_key_order_independent():
    # ZSET dedupe is by exact member string, so serialization must be stable.
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_has_no_incidental_whitespace():
    assert " " not in canonical_json({"a": 1, "b": 2})
```

- [ ] **Step 3: Run both to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...live_alarm.writer'`

- [ ] **Step 4: Write `writer/window.py`**

```python
"""Adaptive backfill window.

Standalone by design: this module is copied to a scheduler service and
must not import anything from back_dev_home. The constants are duplicated
from contracts.py on purpose — the shared contract is the Redis layout,
not Python imports.
"""

from __future__ import annotations

BOARD_WINDOW_SEC = 600
POLL_WINDOW_SEC = 60
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
```

- [ ] **Step 5: Write `writer/normalize.py`**

```python
"""In-house alarm rows -> AlarmEvent, plus the canonical ZSET member form.

Standalone by design (see window.py). The AlarmEvent shape here must stay
in step with back_dev_home/.../live_alarm/contracts.py; the contract test
in test_writer_job.py is what enforces that.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any


KST = timezone(timedelta(hours=9))
ALID_KIND = {"9006": "align", "9100": "meas"}
FUTURE_TOLERANCE_SEC = 300

__all__ = ["to_events", "canonical_json", "ALID_KIND"]


def _text(row: Any, *names: str) -> str:
    for name in names:
        if isinstance(row, dict) and name in row and row[name] is not None:
            return str(row[name]).strip()
    return ""


def _alid(row: Any) -> str:
    """Normalize the alarm id to a bare integer string.

    The in-house feed reaches us through pandas in places, which turns an
    integer column into "9006.0". Both spellings mean the same alarm.
    """
    raw = _text(row, "ALID", "alarm_id", "alid")
    return raw[:-2] if raw.endswith(".0") else raw


def _parse(text: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    return None


def to_events(rows: list[dict], *, now: int) -> list[dict]:
    """Convert raw feed rows into AlarmEvents, discarding what we cannot use."""
    events: list[dict] = []
    for row in rows:
        alid = _alid(row)
        kind = ALID_KIND.get(alid)
        if kind is None:
            continue

        moment = _parse(_text(row, "UTC9", "TIMESTAMP", "timestamp"))
        if moment is None:
            continue

        occurred_epoch = int(moment.timestamp())
        if occurred_epoch > now + FUTURE_TOLERANCE_SEC:
            # An upstream clock running fast would park this above the
            # pruning boundary, where it would never age off the board.
            continue

        occurred_at = moment.isoformat(sep=" ")
        eqp_id = _text(row, "EQP_ID", "eqp_id")
        events.append({
            "id": f"{eqp_id}|{alid}|{occurred_at}",
            "eqp_id": eqp_id,
            "alid": alid,
            "kind": kind,
            "alarm_name": _text(row, "ALARM_NAME", "alarm_name"),
            "occurred_at": occurred_at,
            "occurred_epoch": occurred_epoch,
            "recipe_id": _text(row, "RECIPE_ID", "recipe_id"),
            "operation_desc": _text(row, "OPERATION_DESC", "operation_desc"),
            "lot_type_cd": _text(row, "LOT_TYPE_CD", "lot_type_cd"),
        })
    return events


def canonical_json(event: dict) -> str:
    """Stable serialization — ZSET dedupe compares member strings exactly."""
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

- [ ] **Step 6: Create `writer/__init__.py`**

```python
"""Portable writer job. Imports nothing from back_dev_home by design."""
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: 35 passed

- [ ] **Step 8: Verify the writer really is standalone**

Run: `grep -rn "back_dev_home" back_dev_home/ebeam/hitachi/live_alarm/writer/`
Expected: no output. Any hit breaks the portability requirement.

- [ ] **Step 9: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/writer/ back_dev_home/ebeam/hitachi/live_alarm/tests/
git commit -m "feat(live-alarm): add writer window and normalization logic

compute_window is the fix for the review's critical finding: a fixed 60s
poll window loses every alarm that occurs during an outage longer than
60s, and the fresh heartbeat written on recovery hides the loss. Deriving
the window from the last success and capping it at the board horizon
closes that, and because the board only shows 10 minutes, one capped
query fully rebuilds it however long the outage was.

A missing events key takes the same cold-start path, so an evicted key
cannot produce an empty board that reports itself live.

normalize drops far-future events (an upstream clock running fast would
otherwise park one above the pruning boundary permanently) and tolerates
the '9006.0' spelling the feed produces when it transits pandas.

Both modules import nothing from back_dev_home — they are copied to a
scheduler service verbatim."
```

---

### Task 8: The writer job

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/writer/job.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/fake_redis.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_job.py`

**Interfaces:**

- Consumes: `window.compute_window`, `normalize.to_events`, `normalize.canonical_json` (Task 7); `board.parse_members` (Task 1, for the contract test only).
- Produces:
  - `job.run_once(fetch=None, client=None) -> None` — injectable for tests, defaults resolve from `writer.office`
  - `job.keys(tool_slug: str, fab_name: str) -> tuple[str, str]` returning `(events_key, meta_key)`
  - `job.REGISTRY_KEY: str`

- [ ] **Step 1: Write the fake Redis**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/fake_redis.py`:

```python
"""Minimal in-memory stand-in for the Redis commands the writer uses.

Hand-rolled rather than pulled from a package: Phase 1 is fully offline,
so the test suite must not require a new dependency. Only the handful of
commands job.py issues are implemented.
"""

from __future__ import annotations


class FakePipeline:
    def __init__(self, store: "FakeRedis") -> None:
        self.store = store
        self.ops: list = []

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def zremrangebyscore(self, key, low, high):
        self.ops.append(("zremrangebyscore", key, low, high))
        return self

    def set(self, key, value, ex=None):
        self.ops.append(("set", key, value))
        return self

    def sadd(self, key, member):
        self.ops.append(("sadd", key, member))
        return self

    def expire(self, key, ttl):
        return self

    def execute(self):
        for op in self.ops:
            if op[0] == "zadd":
                self.store.zsets.setdefault(op[1], {}).update(op[2])
            elif op[0] == "zremrangebyscore":
                zset = self.store.zsets.get(op[1], {})
                high = float(op[3])
                self.store.zsets[op[1]] = {
                    m: s for m, s in zset.items() if float(s) > high
                }
            elif op[0] == "set":
                self.store.strings[op[1]] = op[2].encode()
            elif op[0] == "sadd":
                self.store.sets.setdefault(op[1], set()).add(op[2])
        self.ops = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeRedis:
    def __init__(self, now: int = 1_000_000) -> None:
        self.zsets: dict[str, dict[str, float]] = {}
        self.strings: dict[str, bytes] = {}
        self.sets: dict[str, set] = {}
        self._now = now

    def time(self):
        return (self._now, 0)

    def advance(self, seconds: int) -> None:
        self._now += seconds

    def exists(self, key) -> int:
        return int(key in self.zsets or key in self.strings)

    def get(self, key):
        return self.strings.get(key)

    def sismember(self, key, member) -> bool:
        return member in self.sets.get(key, set())

    def zrangebyscore(self, key, low, high):
        zset = self.store_zset(key)
        low_f = float("-inf") if low == "-inf" else float(low)
        high_f = float("inf") if high == "+inf" else float(high)
        chosen = [(m, s) for m, s in zset.items() if low_f <= float(s) <= high_f]
        return [m.encode() for m, _ in sorted(chosen, key=lambda pair: pair[1])]

    def store_zset(self, key):
        return self.zsets.get(key, {})

    def pipeline(self):
        return FakePipeline(self)
```

- [ ] **Step 2: Write the failing job tests**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_job.py`:

```python
"""The writer's behavioural contract.

The single most important test here is that a failed fetch leaves the
heartbeat alone. Everything about distinguishing "quiet fab" from "we
know nothing" rests on that.
"""

import json

import pytest

from back_dev_home.ebeam.hitachi.live_alarm import board
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis
from back_dev_home.ebeam.hitachi.live_alarm.writer import job


FABS = [("cd-sem", "R3"), ("cd-sem", "M16A")]


def _row(eqp_id="MXCD101", utc9="2026-07-23 10:00:00"):
    return {
        "EQP_ID": eqp_id, "ALID": "9006", "ALARM_NAME": "Align Fail",
        "UTC9": utc9, "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT", "LOT_TYPE_CD": "PROD",
    }


def _meta(client, tool_slug="cd-sem", fab_name="R3"):
    _, meta_key = job.keys(tool_slug, fab_name)
    raw = client.get(meta_key)
    return json.loads(raw.decode()) if raw else None


def _events(client, tool_slug="cd-sem", fab_name="R3"):
    events_key, _ = job.keys(tool_slug, fab_name)
    return client.store_zset(events_key)


def test_a_successful_poll_writes_events_and_meta():
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)
    assert len(_events(client)) == 1
    assert _meta(client)["polled_at"] == 1_000_000


def test_an_empty_window_still_advances_the_heartbeat():
    # "No alarms" is a successful poll, not a failure. Conflating the two
    # is what makes a quiet fab indistinguishable from a dead feed.
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)
    assert _events(client) == {}
    assert _meta(client)["polled_at"] == 1_000_000


def test_a_failed_fetch_leaves_the_heartbeat_untouched():
    # THE critical test. If a failure stamped the heartbeat, the screen
    # would report a healthy feed while knowing nothing.
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)
    before = _meta(client)["polled_at"]

    client.advance(300)

    def boom(tool_slug, fab_name, window):
        raise RuntimeError("in-house API down")

    with pytest.raises(RuntimeError):
        job.run_once(fetch=boom, client=client, fabs=FABS)

    assert _meta(client)["polled_at"] == before


def test_one_failing_fab_does_not_block_the_others():
    client = FakeRedis()

    def selective(tool_slug, fab_name, window):
        if fab_name == "R3":
            raise RuntimeError("this fab only")
        return [_row(eqp_id="MXCD204")]

    job.run_once(fetch=selective, client=client, fabs=FABS)

    assert _meta(client, fab_name="R3") is None
    assert _meta(client, fab_name="M16A")["polled_at"] == 1_000_000


def test_a_partial_failure_does_not_raise():
    client = FakeRedis()

    def selective(tool_slug, fab_name, window):
        if fab_name == "R3":
            raise RuntimeError("this fab only")
        return []

    job.run_once(fetch=selective, client=client, fabs=FABS)  # must not raise


def test_total_failure_raises_so_the_host_records_an_error():
    # Otherwise TaskLogger writes an 'end' record and the ops dashboard
    # shows green while every fab is dark.
    client = FakeRedis()

    def boom(tool_slug, fab_name, window):
        raise RuntimeError("all down")

    with pytest.raises(RuntimeError):
        job.run_once(fetch=boom, client=client, fabs=FABS)


def test_running_twice_on_the_same_response_is_idempotent():
    # This is the evidence for "safe on a scheduler with no distributed
    # lock". If it ever fails, that claim is void.
    client = FakeRedis()
    fetch = lambda t, f, w: [_row(), _row(eqp_id="MXCD204")]

    job.run_once(fetch=fetch, client=client, fabs=FABS)
    first = dict(_events(client))
    job.run_once(fetch=fetch, client=client, fabs=FABS)

    assert _events(client) == first


def test_events_past_the_retention_bound_are_pruned():
    client = FakeRedis()
    events_key, _ = job.keys("cd-sem", "R3")
    client.zsets[events_key] = {'{"id":"ancient"}': 1_000_000 - 5_000}

    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)

    assert '{"id":"ancient"}' not in _events(client)


def test_the_fab_is_recorded_in_the_registry():
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)
    assert client.sismember(job.REGISTRY_KEY, "cd-sem:R3")


def test_a_recovery_poll_widens_the_window():
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [], client=client, fabs=FABS)
    client.advance(300)

    seen: list[int] = []

    def record(tool_slug, fab_name, window):
        seen.append(window)
        return []

    job.run_once(fetch=record, client=client, fabs=FABS)
    assert all(w > 60 for w in seen)


def test_written_members_are_readable_by_the_reader():
    # The two services share no Python. This is the only thing standing
    # between them and silent schema drift.
    client = FakeRedis()
    job.run_once(fetch=lambda t, f, w: [_row()], client=client, fabs=FABS)

    events_key, _ = job.keys("cd-sem", "R3")
    raw = client.zrangebyscore(events_key, "-inf", "+inf")
    parsed = board.parse_members(raw)

    assert len(parsed) == 1
    assert parsed[0]["kind"] == "align"
    assert parsed[0]["id"] == parsed[0]["eqp_id"] + "|9006|" + parsed[0]["occurred_at"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_job.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...writer.job'`

- [ ] **Step 4: Write `writer/job.py`**

```python
"""run_once() — everything the host scheduler needs to call.

Portability is the governing constraint: this module must work on any
Flask + APScheduler server, so it asks the host for nothing but a periodic
call. No distributed lock, no app context, no framework logger. Duplicate
execution is safe because every Redis write here is idempotent.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from back_dev_home.ebeam.hitachi.live_alarm.writer.normalize import (
    canonical_json,
    to_events,
)
from back_dev_home.ebeam.hitachi.live_alarm.writer.window import compute_window


log = logging.getLogger(__name__)

KEY_PREFIX = "skewnono:live_alarm"
REGISTRY_KEY = f"{KEY_PREFIX}:registry"
TTL_SEC = 86_400
PRUNE_SEC = int(os.environ.get("LIVE_ALARM_PRUNE_SEC", "900"))
MAX_PARALLEL_FABS = 8

__all__ = ["run_once", "keys", "REGISTRY_KEY"]


def keys(tool_slug: str, fab_name: str) -> tuple[str, str]:
    base = f"{KEY_PREFIX}:{tool_slug}:{fab_name}"
    return f"{base}:events", f"{base}:meta"


def _last_polled_at(client, meta_key: str) -> int | None:
    raw = client.get(meta_key)
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return int(json.loads(text)["polled_at"])
    except (UnicodeDecodeError, ValueError, TypeError, KeyError):
        # Unreadable meta is indistinguishable from no meta: cold start.
        return None


def _poll_one(client, fetch, tool_slug: str, fab_name: str, now: int) -> None:
    events_key, meta_key = keys(tool_slug, fab_name)

    window, covered_since = compute_window(
        _last_polled_at(client, meta_key),
        events_key_exists=bool(client.exists(events_key)),
        now=now,
    )

    rows = fetch(tool_slug, fab_name, window)      # raises on failure
    events = to_events(rows, now=now)

    pipe = client.pipeline()
    if events:
        # redis-py rejects an empty mapping, and an empty window is normal.
        pipe.zadd(events_key, {canonical_json(e): e["occurred_epoch"] for e in events})
    pipe.zremrangebyscore(events_key, "-inf", now - PRUNE_SEC)
    pipe.expire(events_key, TTL_SEC)
    pipe.set(
        meta_key,
        json.dumps({"polled_at": now, "covered_since": covered_since}),
        ex=TTL_SEC,
    )
    pipe.sadd(REGISTRY_KEY, f"{tool_slug}:{fab_name}")
    pipe.expire(REGISTRY_KEY, TTL_SEC)
    pipe.execute()


def run_once(fetch=None, client=None, fabs=None) -> None:
    """One scheduler tick. Poll every configured fab and write the board.

    The heartbeat is only stamped on success — a failed poll must leave it
    ageing, because a fresh heartbeat over missing data is the one failure
    mode this whole design exists to prevent.

    Partial failure is swallowed so one dark fab cannot blind the rest.
    Total failure raises: the host's run log would otherwise record a
    successful execution while every fab is down.
    """
    if fetch is None or client is None or fabs is None:
        from back_dev_home.ebeam.hitachi.live_alarm.writer import office
        fetch = fetch or office.fetch_alarms
        client = client if client is not None else office.redis_client()
        fabs = fabs or office.configured_fabs()

    now = int(client.time()[0])   # Redis is the single clock authority
    failures: list[str] = []

    def attempt(target: tuple[str, str]) -> None:
        tool_slug, fab_name = target
        try:
            _poll_one(client, fetch, tool_slug, fab_name, now)
        except Exception:
            failures.append(f"{tool_slug}:{fab_name}")
            log.exception("live_alarm poll failed for %s/%s", tool_slug, fab_name)

    targets = list(fabs)
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FABS, max(1, len(targets)))) as pool:
        list(pool.map(attempt, targets))

    if targets and len(failures) == len(targets):
        raise RuntimeError(f"live_alarm: every fab failed ({', '.join(failures)})")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm -v`
Expected: 46 passed

- [ ] **Step 6: Re-verify writer independence**

Run: `grep -rn "back_dev_home" back_dev_home/ebeam/hitachi/live_alarm/writer/`
Expected: only the two intra-`writer` imports in `job.py`. When this directory is copied to the scheduler service those two lines become relative imports; note that in the MIGRATION doc in Task 9.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/writer/job.py back_dev_home/ebeam/hitachi/live_alarm/tests/
git commit -m "feat(live-alarm): add the writer job

run_once asks its host for one thing: a periodic call. No distributed
lock, no app context, no framework logger — every Redis write is
idempotent, which is what makes it safe to drop onto any scheduler.
test_running_twice_on_the_same_response_is_idempotent is the evidence for
that claim.

The heartbeat is stamped only on success. A failed poll must leave it
ageing, since a fresh heartbeat over missing data is precisely the
failure this design exists to prevent. Partial failure is swallowed so
one dark fab cannot blind the rest; total failure raises so the host's
run log does not record a green execution while every fab is down.

Redis TIME is the clock for pruning, the heartbeat, and the window, so
concurrent writers compute identical boundaries.

Tests use a hand-rolled fake Redis rather than a package, because Phase 1
is fully offline and must not need a new dependency."
```

---

### Task 9: Office adapters and migration doc

These are the tracked templates. `office.py` is gitignored and only ever created by `cp` at the office.

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/providers/office_example.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/writer/office_example.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md`
- Modify: `back_dev_home/.env.example`

**Interfaces:**

- Consumes: `board.parse_members`, `board.dedupe_by_id`, `board.feed_status_for` (Task 1); `job.keys`, `job.REGISTRY_KEY` (Task 8); `redis_client` from `back_dev_home._runtime.office_redis`.
- Produces: `providers/office.get_board(tool_type, fab_name) -> LiveAlarmPayload`; `writer/office.fetch_alarms(tool_slug, fab_name, window_sec) -> list[dict]`, `writer/office.configured_fabs() -> list[tuple[str, str]]`, `writer/office.redis_client()`.

- [ ] **Step 1: Write `providers/office_example.py`**

```python
"""[Office template] live_alarm reader. Copy to office.py to activate.

    cp office_example.py office.py

Reads only. Everything on the board was put there by the writer job (see
writer/office_example.py), so this file never touches the in-house alarm
API and never writes to Redis.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from back_dev_home._runtime.office_redis import load_env_file, redis_client
from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.hitachi.live_alarm import board
from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    BOARD_WINDOW_SEC,
    FUTURE_TOLERANCE_SEC,
    LiveAlarmPayload,
)


KST = timezone(timedelta(hours=9))

KEY_PREFIX = "skewnono:live_alarm"
REGISTRY_KEY = f"{KEY_PREFIX}:registry"

# The tool slug is what the writer put in the key, and it matches the URL
# segment the route already resolved.
_TOOL_SLUG: dict[str, str] = {"cd-sem": "cd-sem", "hv-sem": "hv-sem"}


def _iso(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), KST).isoformat(sep=" ")


def _decode(raw) -> dict | None:
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(text)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    client = redis_client()
    load_env_file("REDIS_HOST")

    tool_slug = _TOOL_SLUG[tool_type]
    base = f"{KEY_PREFIX}:{tool_slug}:{fab_name}"
    events_key, meta_key = f"{base}:events", f"{base}:meta"

    # Redis is the single clock authority — the writer prunes against this
    # same clock, so the two never disagree about the boundary.
    now = int(client.time()[0])

    raw_members = client.zrangebyscore(
        events_key,
        now - BOARD_WINDOW_SEC,
        # Not "+inf": an upstream clock running fast would otherwise leave
        # a far-future event pinned to the top of the board forever.
        now + FUTURE_TOLERANCE_SEC,
    )
    meta = _decode(client.get(meta_key))
    known = bool(client.sismember(REGISTRY_KEY, f"{tool_slug}:{fab_name}"))

    events = board.dedupe_by_id(board.parse_members(raw_members))
    events.sort(key=lambda e: e["occurred_epoch"], reverse=True)

    return {
        "fab_name": fab_name,
        "tool_type": tool_type,
        "feed_status": board.feed_status_for(meta, known, now=now),
        "polled_at": _iso(meta.get("polled_at")) if meta else None,
        "covered_since": _iso(meta.get("covered_since")) if meta else None,
        "server_now": _iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "events": events,
    }
```

- [ ] **Step 2: Write `writer/office_example.py`**

```python
"""[Office template] live_alarm writer I/O. Copy to office.py to activate.

    cp office_example.py office.py

This is the only file that knows the in-house alarm API addresses, which
is why office.py is gitignored. It is also deliberately free of any
back_dev_home import: the writer directory is copied wholesale onto a
scheduler service that does not have SKEWNONO on its path.

The fab list IS the address map's key set. Adding a fab and registering
its address are the same edit, so the two cannot drift apart.
"""

from __future__ import annotations

import os

import redis
import requests


# (tool_slug, fab_name) -> in-house alarm API base URL. Fill in at the office.
ALARM_API: dict[tuple[str, str], str] = {
    ("cd-sem", "R3"): "http://alarm-r3.example.internal/api/alarms",
    # ("cd-sem", "M11"): "...",
    # ("cd-sem", "M12"): "...",
    # ("cd-sem", "M14"): "...",
    # ("cd-sem", "M15"): "...",
    # ("cd-sem", "M16A"): "...",
}


def _timeout() -> tuple[float, float]:
    connect, _, read = os.environ.get("LIVE_ALARM_HTTP_TIMEOUT", "3,7").partition(",")
    return float(connect), float(read or 7)


def configured_fabs() -> list[tuple[str, str]]:
    return list(ALARM_API.keys())


def redis_client():
    """The Redis SKEWNONO's office adapters read.

    NOTE: db is left at redis-py's default of 0 on purpose.
    back_dev_home/_runtime/office_redis.py:73 passes no db either, so the
    reader sits on db 0. Changing one side without the other silently
    splits the writer and reader onto different databases.
    """
    return redis.Redis(
        host=os.environ["LIVE_ALARM_REDIS_HOST"],
        port=int(os.environ.get("LIVE_ALARM_REDIS_PORT", "6379")),
        password=os.environ.get("LIVE_ALARM_REDIS_PASSWORD") or None,
        db=int(os.environ.get("LIVE_ALARM_REDIS_DB", "0")),
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=10,
    )


def fetch_alarms(tool_slug: str, fab_name: str, window_sec: int) -> list[dict]:
    """Query one fab's alarm feed for the last `window_sec` seconds.

    Raise on any failure — run_once relies on the exception to decide NOT
    to stamp the heartbeat. Returning [] on error would report a healthy
    feed with no data, which is the exact failure this design prevents.

    `window_sec` is not always 60: after an outage the caller widens it so
    the gap gets backfilled. Honour whatever it passes.
    """
    url = ALARM_API[(tool_slug, fab_name)]
    response = requests.get(
        url,
        params={"range_sec": window_sec},   # adjust to the real API's contract
        timeout=_timeout(),
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else payload.get("rows", [])
```

- [ ] **Step 3: Add the env template entries**

Append to `back_dev_home/.env.example`:

```bash
# --- live_alarm writer (runs on the scheduler service, not on SKEWNONO) -----
# The writer targets the SAME Redis the office adapters read, at db 0.
# _runtime/office_redis.py passes no db, so REDIS_DB is ignored there —
# do not set LIVE_ALARM_REDIS_DB to anything else without changing both.
LIVE_ALARM_REDIS_HOST=
LIVE_ALARM_REDIS_PORT=6379
LIVE_ALARM_REDIS_PASSWORD=
LIVE_ALARM_REDIS_DB=0
LIVE_ALARM_PRUNE_SEC=900
LIVE_ALARM_HTTP_TIMEOUT=3,7
```

- [ ] **Step 4: Write `MIGRATION.md`**

Create `back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md`:

````markdown
# live_alarm — 오피스 전환 절차

이 기능은 다른 기능과 달리 **swap surface 가 둘** 입니다.

| 위치 | 역할 | 실행 주체 |
| --- | --- | --- |
| `providers/office.py` | Redis 를 읽어 화면에 내보냅니다 | SKEWNONO Flask |
| `writer/office.py` | 사내 알람 API 를 폴링해 Redis 에 씁니다 | 스케줄러 서비스 |

writer 가 먼저 돌아야 reader 가 보여줄 것이 생깁니다. 순서대로 진행합니다.

## 1. 스케줄러 플랫폼 준비

`flask_modules/api` 에 다음 두 가지가 반영되어 있어야 합니다.

- `extension.py` 의 `SCHEDULER_EXECUTORS` 에 `fast` executor
- `schedule.py` 의 `init_jobs` 가 `misfire_grace_time` / `executor` 를 전달

없으면 15초 잡이 긴 잡에 밀려 굶고, `misfire_grace_time` 은 60초가 적용됩니다.

## 2. writer 배치

1. `back_dev_home/ebeam/hitachi/live_alarm/writer/` 디렉터리를 스케줄러 서비스로
   복사합니다.
2. `job.py` 의 두 import 를 상대 경로로 바꿉니다 — 그 서비스에는 `back_dev_home`
   가 없습니다.

   ```python
   from .normalize import canonical_json, to_events
   from .window import compute_window
   ```

3. `cp office_example.py office.py` 후 `ALARM_API` 에 팹별 실제 주소를 채웁니다.
   **이 맵의 키 집합이 곧 감시 대상 팹 목록입니다.**
4. `job.py` 의 `office` import 도 상대 경로로 바꿉니다.
5. 환경 변수 `LIVE_ALARM_REDIS_*` 를 설정합니다. **db 는 0 이어야 합니다** —
   `_runtime/office_redis.py` 가 `db` 를 넘기지 않아 reader 가 0 번에 있습니다.
6. `JOB_FUNCTIONS` 에 등록합니다.

   ```python
   "live_alarm_board": {
       "fn": run_once,
       "trigger": IntervalTrigger(seconds=15),
       "executor": "fast",
       "misfire_grace_time": 10,
       "lock_ttl": 45,          # 기본 1200 을 반드시 덮어쓸 것
       "manual_dispatch": True,
   },
   ```

   `lock_ttl` 기본값 1200 초를 그대로 두면, 락을 쥔 채 워커가 재활용될 때 20분간
   잡이 skip 되고 화면은 내내 `stale` 입니다.

## 3. writer 동작 확인

```bash
redis-cli -n 0 --scan --pattern 'skewnono:live_alarm:*'
redis-cli -n 0 SMEMBERS skewnono:live_alarm:registry
redis-cli -n 0 GET skewnono:live_alarm:cd-sem:R3:meta
```

`meta` 의 `polled_at` 이 15초마다 올라가면 정상입니다. 올라가지 않으면
스케줄러의 `/jobs/logs` 에서 해당 잡의 `error` 레코드를 확인합니다.

## 4. reader 활성화

```bash
cd back_dev_home/ebeam/hitachi/live_alarm/providers
cp office_example.py office.py
```

`office.py` 의 존재 자체가 이 기능을 office 모드로 전환합니다. 별도 환경 변수는
필요 없습니다 (`_runtime/office_registry.py`).

## 5. 검증

```bash
SKEWNONO_LIVE_ALARM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
curl 'http://localhost:5000/api/health/providers' | grep live_alarm
curl 'http://localhost:5000/api/ebeam/cd-sem/live-alarm?fab_name=R3'
```

응답의 `feed_status` 를 확인합니다.

| 값 | 의미 | 조치 |
| --- | --- | --- |
| `live` | 정상 | — |
| `stale` | 레지스트리에는 있으나 갱신이 멈춤 | writer 잡 로그 확인 |
| `not_configured` | 이 팹이 `ALARM_API` 에 없음 | 주소 맵에 추가 |

## 주의

- writer 는 `back_dev_home` 를 import 하지 않습니다. 이식성이 이 기능의 설계
  제약이므로, 편의를 위해 import 를 추가하지 마십시오.
- writer 와 reader 는 Python 코드를 공유하지 않습니다. 유일한 계약은 Redis 키
  구조이며, `test_written_members_are_readable_by_the_reader` 가 그 계약을
  지킵니다. writer 를 고치면 이 테스트를 반드시 다시 돌리십시오.
````

- [ ] **Step 5: Verify the tracked templates are syntactically valid**

Run: `.venv/bin/python -m py_compile back_dev_home/ebeam/hitachi/live_alarm/providers/office_example.py back_dev_home/ebeam/hitachi/live_alarm/writer/office_example.py`
Expected: no output

- [ ] **Step 6: Confirm `office.py` stays untracked**

Run: `git check-ignore -v back_dev_home/ebeam/hitachi/live_alarm/providers/office.py`
Expected: a line naming the `.gitignore` rule that matches. If there is no output, add the pattern before continuing — office adapters must never reach git.

- [ ] **Step 7: Lint the migration doc**

Run: `npm run lint:md`
Expected: `Summary: 0 error(s)`

- [ ] **Step 8: Run the full backend suite**

Run: `.venv/bin/pytest back_dev_home -q`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/ back_dev_home/.env.example
git commit -m "feat(live-alarm): add office adapter templates and migration doc

Two swap surfaces, unlike other features: providers/office.py reads the
board for SKEWNONO, writer/office.py polls the in-house API from the
scheduler service. The migration doc orders them, because the reader has
nothing to show until the writer has run.

The reader caps its ZRANGEBYSCORE upper bound rather than using +inf, so
a fast upstream clock cannot pin an event to the top of the board
permanently. The writer's redis_client leaves db at 0 to match
office_redis.py, which passes no db at all — a mismatch there would put
writer and reader on different databases with no error.

fetch_alarms raises on failure by contract: returning [] would let
run_once stamp a heartbeat over missing data."
```

---

## Self-Review

**Spec coverage**

| Spec section | Task |
| --- | --- |
| §4 contracts, invariant assert | 1 |
| §5 ZSET/meta/registry keys, dedupe rule, db=0, bytes | 1, 8, 9 |
| §5 Redis TIME as single clock | 8 (writer), 9 (reader) |
| §6 adaptive backfill, cold start, EXISTS check | 7, 8 |
| §6 heartbeat only on success, partial vs total failure | 8 |
| §6 env config, standalone module | 7, 8, 9 |
| §7 reader, capped upper bound, lenient parse, feed_status | 1, 9 |
| §8 pages, composable, pure utils, jitter, clock offset | 3, 4, 5 |
| §9 no notifications/audio | 5 (nothing added) |
| §10 failure modes | 1, 8, 9 |
| §11 test list | 1, 3, 4, 7, 8 |
| §12 flask_modules changes | 6 |
| §15 constants | 1 (backend), 4 (frontend), 7 (writer copy) |

**Known gaps, deliberately left**

- `FeatureTabs.vue` (Task 5, Step 7) says to follow the file's existing entry shape rather than quoting code, because that file was not read while writing this plan. The implementer should open it and match the neighbouring `hardware` entry.
- `flask_modules`' `_app_with_config()` test helper (Task 6, Step 1) is likewise described rather than quoted, for the same reason.
- `fetch_alarms`' query parameter name (`range_sec`) is a placeholder for the real in-house API contract, flagged inline. It is only reachable at the office.

**Type consistency** — `get_board(tool_type, fab_name)` keeps the same signature in `data.py`, `providers/mock.py`, and `providers/office_example.py`. `job.keys()` returns `(events_key, meta_key)` in that order everywhere. `feed_status_for(meta, known, *, now)` is called identically in tests and in the office reader. `compute_window` returns `(window_sec, covered_since)` in that order in both its tests and `job._poll_one`.

**Ordering constraint** — Task 6 (`flask_modules`) must be deployed before the writer from Tasks 7–9 is registered; nothing else depends on it. Tasks 1–5 are independently shippable and give a working page at home.
