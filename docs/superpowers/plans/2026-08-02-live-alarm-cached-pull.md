# live_alarm demand-driven cached pull — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `live_alarm`'s separate scheduler writer with an on-demand
fetch inside SKEWNONO Flask, guarded by a 20-second Redis cache and a
non-blocking lock, so any number of viewers collapse into at most one call to
the office alarm API per facility per 20 seconds.

**Architecture:** The page request triggers the refresh. `providers/office.py`
resolves `fab_name → fac_id` through the `sem_list` roster, calls
`refresh.ensure_fresh(client, fac_id)`, then reads the accumulated ZSET and
filters it to the requested fab. `ensure_fresh` returns immediately when the
cache is younger than 20s; otherwise it takes a `SET NX EX` lock, and the
loser serves the previous board rather than waiting. The office seam is a
single lazily-imported `office_utils.live_alarm.get_live_alarms(fac_id)`.

**Tech Stack:** Python 3.14, Flask blueprints, redis-py, pytest; Nuxt 4 +
TypeScript with `node --test` for the frontend pure functions.

**Spec:** `docs/superpowers/specs/2026-08-02-live-alarm-cached-pull-design.md`

## Global Constraints

- Run backend tests as `.venv/bin/python -m pytest ... -q` **from the repo
  root**. The `-m` form is what puts the root on `sys.path`.
- **No new dependencies.** Phase 1 is fully offline; the test suite must not
  require a package that is not already installed.
- `office_utils` is **gitignored and absent at home**. Import it lazily inside
  a function and raise a `RuntimeError` naming it on `ImportError`. Never
  import it at module scope.
- **Never parse an `eqp_id`.** Resolve a tool through the `sem_list` roster and
  classify with `model_to_tool_type()`. `_tool_specs.py` documents an outage
  caused by treating `eqp_prefixes`/`eqp_models` as classifiers.
- `fac_id` is the coarse facility key (`M16`, `R3`); `fab_name` is granular
  (`M16A`, `R3`, `R4`). Cache keys use **`fac_id`**. `R3` is the one value where
  they coincide, so no test may use `R3` alone to prove the mapping works.
- Commit with **explicit pathspecs only**. `git add -A`, `git add .`, and
  `git commit -a` are banned — other agent sessions share this working tree.
- Run `npm run lint:md` from the repo root after any Markdown edit.
- Markdown tables use markdownlint `MD060` `compact` style.

## Worktree Setup

This plan touches many files, so it runs in an isolated worktree.

```bash
git worktree add ../skewnono-live-alarm-pull -b work/live-alarm-pull
cd ../skewnono-live-alarm-pull
```

Do all work there. After the final task:

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/live-alarm-pull && git push
git worktree remove ../skewnono-live-alarm-pull
git branch -d work/live-alarm-pull
```

**Note:** a worktree has no gitignored `office*.py` files, so provider tests
that skip without them legitimately show different skip counts than the main
checkout. Compare `passed + skipped` totals, not `passed` alone.

## File Structure

| Path | Responsibility | Task |
| --- | --- | --- |
| `live_alarm/tests/fake_redis.py` | in-memory Redis double; gains lock + TTL commands | 1 |
| `live_alarm/contracts.py` | payload shape and tuning constants | 2 |
| `live_alarm/board.py` | pure board logic; `feed_status_for` | 2 |
| `live_alarm/roster.py` | **new** — `sem_list` join: `fab_name → fac_id`, `eqp_id → placement` | 3 |
| `live_alarm/normalize.py` | **new** — raw rows → `AlarmEvent`; moved out of `writer/` | 4 |
| `live_alarm/refresh.py` | **new** — cache freshness, lock, board write | 5 |
| `live_alarm/providers/office_example.py` | reader: roster → refresh → filter | 6 |
| `live_alarm/writer/**` | **deleted** | 7 |
| `live_alarm/providers/mock.py` | home stand-in; gains `fetched_at`, `unmatched_count` | 8 |
| `front-dev-home/app/utils/liveAlarm.ts` | payload type | 9 |
| `front-dev-home/app/composables/useLiveAlarmFeed.ts` | poll loop and reducer | 9 |
| `front-dev-home/app/components/ebeam/LiveAlarmView.vue` | board UI | 9 |
| `live_alarm/MIGRATION.md`, `docs/datatables/live_alarm_board.txt`, `back_dev_home/.env.example` | office-facing docs | 10 |

**Ordering constraint:** `tests/test_office_adapter_parity.py` imports every
office template through `importlib`. `providers/office_example.py` must
therefore stop importing `writer.job` (Task 6) **before** `writer/` is deleted
(Task 7). Task 4 creates `live_alarm/normalize.py` while `writer/normalize.py`
still exists; that duplication is deliberate and ends in Task 7.

---

### Task 1: Give FakeRedis the lock primitives

`FakeRedis` currently has no `set(nx=)`, no `delete`, no `eval`, and ignores
`ex=`. The lock needs all four, and the backoff test needs TTLs that actually
expire when the fake clock advances.

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/live_alarm/tests/fake_redis.py`
- Test: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_fake_redis.py` (create)

**Interfaces:**

- Consumes: nothing.
- Produces: `FakeRedis.set(key, value, nx=False, ex=None) -> True | None`,
  `FakeRedis.delete(*keys) -> int`,
  `FakeRedis.eval(script, numkeys, *args) -> int`,
  `FakeRedis.advance(seconds)` now evicts expired keys.

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_fake_redis.py`:

```python
"""The fake's own contract. A double that lies about NX or TTL would make
every lock test below it green for the wrong reason."""

from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis


RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"


def test_set_nx_succeeds_once_then_fails():
    client = FakeRedis()
    assert client.set("k", "first", nx=True, ex=20) is True
    assert client.set("k", "second", nx=True, ex=20) is None
    assert client.get("k") == b"first"


def test_expiry_releases_the_key_when_the_clock_advances():
    client = FakeRedis()
    client.set("k", "v", nx=True, ex=20)
    client.advance(19)
    assert client.set("k", "other", nx=True, ex=20) is None
    client.advance(1)
    assert client.set("k", "other", nx=True, ex=20) is True


def test_eval_deletes_only_when_the_token_matches():
    client = FakeRedis()
    client.set("k", "mine", nx=True, ex=20)
    assert client.eval(RELEASE, 1, "k", "theirs") == 0
    assert client.get("k") == b"mine"
    assert client.eval(RELEASE, 1, "k", "mine") == 1
    assert client.get("k") is None


def test_set_without_nx_overwrites_and_clears_any_ttl():
    client = FakeRedis()
    client.set("k", "v", nx=True, ex=5)
    client.set("k", "w")
    client.advance(10)
    assert client.get("k") == b"w"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_fake_redis.py -q
```

Expected: FAIL — `TypeError: set() got an unexpected keyword argument 'nx'`.

- [ ] **Step 3: Implement the new commands**

In `fake_redis.py`, replace the `FakeRedis` class body's `__init__`, `advance`,
`get`, and `exists`, and add the four new methods:

```python
class FakeRedis:
    def __init__(self, now: int = 1_000_000) -> None:
        self.zsets: dict[str, dict[str, float]] = {}
        self.strings: dict[str, bytes] = {}
        self.sets: dict[str, set] = {}
        # Expiry is modelled because the lock's TTL is the feature's retry
        # backoff: a fake that ignored `ex` would make the backoff test pass
        # while the real lock never expired.
        self._expires: dict[str, int] = {}
        self._now = now

    def time(self):
        return (self._now, 0)

    def advance(self, seconds: int) -> None:
        self._now += seconds
        self._evict()

    def _evict(self) -> None:
        for key in [k for k, at in self._expires.items() if at <= self._now]:
            self._expires.pop(key, None)
            self.strings.pop(key, None)
            self.zsets.pop(key, None)
            self.sets.pop(key, None)

    def exists(self, key) -> int:
        self._evict()
        return int(key in self.zsets or key in self.strings)

    def get(self, key):
        self._evict()
        return self.strings.get(key)

    def set(self, key, value, nx: bool = False, ex: int | None = None):
        """redis-py returns True on a write and None when NX declined."""
        self._evict()
        if nx and key in self.strings:
            return None
        self.strings[key] = value.encode() if isinstance(value, str) else value
        if ex is None:
            self._expires.pop(key, None)
        else:
            self._expires[key] = self._now + int(ex)
        return True

    def delete(self, *keys) -> int:
        removed = 0
        for key in keys:
            self._expires.pop(key, None)
            if self.strings.pop(key, None) is not None:
                removed += 1
        return removed

    def eval(self, script, numkeys: int, *args) -> int:
        """The ONE script this feature uses: compare-and-delete.

        The script text is accepted and ignored — this fake implements the
        semantics of refresh._RELEASE_LUA, not a Lua interpreter. If a second
        script is ever added, this must branch rather than silently apply
        compare-and-delete to it.
        """
        self._evict()
        keys, argv = list(args[:numkeys]), list(args[numkeys:])
        expected = argv[0].encode() if isinstance(argv[0], str) else argv[0]
        if self.strings.get(keys[0]) == expected:
            self.delete(keys[0])
            return 1
        return 0
```

Also update the module docstring's first line to:

```python
"""Minimal in-memory stand-in for the Redis commands live_alarm uses.
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm -q
```

Expected: the four new tests PASS and every pre-existing `live_alarm` test
still passes.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/tests/fake_redis.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_fake_redis.py
git commit -m "test(live-alarm): give FakeRedis NX, TTL, delete and eval

The demand-driven refresh needs a real SET NX EX lock and a token-compared
release. Expiry is modelled because the lock's TTL is the retry backoff, so a
fake that ignored ex would make the backoff test green while the real lock
never expired."
```

---

### Task 2: Reshape the contract and the feed-status rule

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/live_alarm/contracts.py`
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/board.py:25-37`
- Test: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `CACHE_TTL_SEC = 20`, `LOCK_TTL_SEC = 20`, `PRUNE_SEC = 900`;
  `LiveAlarmPayload` with `fetched_at: str | None` and `unmatched_count: int`;
  `board.feed_status_for(meta, known, *, now)` reading `meta["fetched_at"]`.

- [ ] **Step 1: Write the failing test**

Replace the `_meta` helper at the top of `tests/test_board.py` and add one test:

```python
def _meta(fetched_at: int, covered_since: int = 0) -> dict:
    return {"fetched_at": fetched_at, "covered_since": covered_since}


def test_feed_status_reads_fetched_at_not_polled_at():
    # The writer's heartbeat was polled_at; the cached pull stamps fetched_at
    # only on a SUCCESSFUL office call. A meta blob carrying the old key must
    # read as stale rather than being silently accepted.
    assert board.feed_status_for({"polled_at": 1_000_000}, True, now=1_000_000) == "stale"
    assert board.feed_status_for(_meta(1_000_000), True, now=1_000_000) == "live"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py -q
```

Expected: FAIL — the second assertion returns `"stale"` because
`feed_status_for` still looks for `polled_at`.

- [ ] **Step 3: Update `contracts.py`**

Replace lines 15–69 of `contracts.py` with:

```python
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
    "ALID_KIND",
]


Kind = Literal["align", "meas"]
FeedStatus = Literal["live", "stale", "not_configured"]

BOARD_WINDOW_SEC = 600      # what the reader cuts to — the screen's horizon
PRUNE_SEC = 900             # how much history the ZSET keeps
STALE_AFTER_SEC = 90        # ~3 missed refreshes at the viewer-driven cadence
FUTURE_TOLERANCE_SEC = 300  # events dated further ahead than this are dropped

# How long one successful office call is reused. The office API is called at
# most once per facility per this many seconds, no matter how many viewers
# are polling or how fast they poll.
CACHE_TTL_SEC = 20
# In-flight guard AND failure backoff: the lock is released on success but
# left to expire on failure, so an office API already in trouble is not
# retried by every poll of every viewer.
LOCK_TTL_SEC = 20

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
```

Also replace the module docstring (lines 1–6) with:

```python
"""Stable response contracts for the live_alarm endpoint.

The board is refreshed on demand by refresh.py, behind a short cache and a
lock, rather than by a separate writer service. These constants are the whole
tuning surface: the cache TTL bounds office API load, the board window bounds
what the screen shows, and PRUNE_SEC bounds what Redis keeps.
"""
```

- [ ] **Step 4: Update `board.feed_status_for`**

Replace `board.py:25-37` with:

```python
def feed_status_for(meta: dict[str, Any] | None, known: bool, *, now: int) -> FeedStatus:
    """Which of the three empty states is this?

    "No alarms" is ambiguous on its own: a healthy quiet fab, a dead feed, and
    a fab with no tools all render as an empty list. `known` (does the
    sem_list roster hold any tool of this type in this fab?) separates the
    third; the age of the last SUCCESSFUL fetch separates the first two.

    `fetched_at` is stamped only after the office call returns, so a failing
    feed ages into "stale" instead of reporting a fresh heartbeat over data
    that was never refreshed.
    """
    if not known:
        return "not_configured"
    if not meta or "fetched_at" not in meta:
        return "stale"
    return "live" if now - int(meta["fetched_at"]) <= STALE_AFTER_SEC else "stale"
```

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py -q
```

Expected: PASS. Other `live_alarm` tests fail at this point (they reference
`polled_at` and the deleted constants); Tasks 6–8 restore them.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/contracts.py \
        back_dev_home/ebeam/hitachi/live_alarm/board.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py
git commit -m "feat(live-alarm): recontract around fetched_at and unmatched_count

polled_at named a writer heartbeat that no longer exists; fetched_at names the
last successful office call and is stamped only on success. Adds the cache and
lock TTLs, unmatched_count, and drops POLL_WINDOW_SEC/WRITER_INTERVAL_SEC,
which described a scheduled writer and a windowed query the office API does
not accept."
```

---

### Task 3: Roster index — `fab_name → fac_id` and `eqp_id → placement`

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/roster.py`
- Test: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_roster.py` (create)

**Interfaces:**

- Consumes: `sem_list.data.get_sem_list()`, `_tool_specs.model_to_tool_type`.
- Produces: `roster.build_index(rows) -> RosterIndex`, `roster.load_index()`,
  and on `RosterIndex`: `.fac_id_for(fab_name) -> str | None`,
  `.has_tools(tool_type, fab_name) -> bool`,
  `.placement_of(eqp_id) -> tuple[str, ToolType] | None` returning
  `(fab_name, tool_type)`. All inputs are upper-cased and stripped.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_roster.py`:

```python
"""The roster is the only thing that knows which fab an alarm belongs to.

Every case here uses M16, never R3 alone: R3 is the single value where fac_id
and fab_name coincide, so an R3-only test proves nothing about the mapping.
"""

from back_dev_home.ebeam.hitachi.live_alarm import roster


def _row(eqp_id, fab_name, fac_id, model="CG6300"):
    return {"eqp_id": eqp_id, "fab_name": fab_name, "fac_id": fac_id, "eqp_model_cd": model}


ROWS = [
    _row("MCD101", "M16A", "M16"),
    _row("MCD102", "M16B", "M16"),
    _row("MCD103", "R3", "R3"),
    _row("MCD104", "R4", "R3"),
    _row("TP0421", "M16A", "M16", model="TP3000"),
    _row("VS9001", "M16A", "M16", model="VERITYSEM_5"),  # AMAT: not our tool
]


def test_sibling_fabs_share_one_fac_id():
    index = roster.build_index(ROWS)
    assert index.fac_id_for("M16A") == "M16"
    assert index.fac_id_for("M16B") == "M16"
    # R3 and R4 are different fabs in ONE facility — this is the pairing that
    # makes the cache key coarse enough to matter.
    assert index.fac_id_for("R4") == "R3"


def test_fab_name_is_normalized():
    index = roster.build_index(ROWS)
    assert index.fac_id_for(" m16a ") == "M16"


def test_unknown_fab_has_no_fac_id():
    assert roster.build_index(ROWS).fac_id_for("ZZZ") is None


def test_placement_carries_fab_and_tool_family():
    index = roster.build_index(ROWS)
    assert index.placement_of("MCD101") == ("M16A", "cd-sem")
    assert index.placement_of("TP0421") == ("M16A", "hv-sem")


def test_unrostered_equipment_has_no_placement():
    assert roster.build_index(ROWS).placement_of("MCD999") is None


def test_amat_tools_are_not_placed():
    # model_to_tool_type returns None for VeritySEM/Provision. Placing them
    # would put an AMAT alarm on a Hitachi board.
    assert roster.build_index(ROWS).placement_of("VS9001") is None


def test_has_tools_is_per_fab_and_per_family():
    index = roster.build_index(ROWS)
    assert index.has_tools("cd-sem", "M16A") is True
    assert index.has_tools("hv-sem", "M16A") is True
    assert index.has_tools("hv-sem", "M16B") is False   # only a CD-SEM there
    assert index.has_tools("cd-sem", "ZZZ") is False
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_roster.py -q
```

Expected: FAIL — `ModuleNotFoundError: ... live_alarm.roster`.

- [ ] **Step 3: Implement `roster.py`**

```python
"""Which fab an alarm belongs to, answered by the sem_list roster.

The office alarm feed is keyed by EQP_ID and carries no fab column, so fab
attribution is ours to compute. It is computed by LOOKUP, never by parsing the
id: `_tool_specs.py` records an outage where treating eqp prefixes as a
classifier silently dropped 8 real tools from a panel.

The roster is also where `fab_name -> fac_id` comes from. No mapping table is
hardcoded — SemListRow carries both columns, so a fab added at the office
works here the day it lands in sem_list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.sem_list.contracts import SemListRow


__all__ = ["RosterIndex", "build_index", "load_index"]


def _norm(value) -> str:
    """Roster text arrives from parquet/Redis cells carrying case and spaces."""
    return str(value or "").strip().upper()


@dataclass(frozen=True)
class RosterIndex:
    fac_id_by_fab: dict[str, str]
    placement_by_eqp: dict[str, tuple[str, ToolType]]

    def fac_id_for(self, fab_name: str) -> str | None:
        return self.fac_id_by_fab.get(_norm(fab_name))

    def placement_of(self, eqp_id: str) -> tuple[str, ToolType] | None:
        return self.placement_by_eqp.get(_norm(eqp_id))

    def has_tools(self, tool_type: ToolType, fab_name: str) -> bool:
        fab = _norm(fab_name)
        return any(
            placed_fab == fab and placed_type == tool_type
            for placed_fab, placed_type in self.placement_by_eqp.values()
        )


def build_index(rows: Iterable[SemListRow]) -> RosterIndex:
    fac_id_by_fab: dict[str, str] = {}
    placement_by_eqp: dict[str, tuple[str, ToolType]] = {}

    for row in rows:
        fab = _norm(row.get("fab_name"))
        fac = _norm(row.get("fac_id"))
        if fab and fac:
            fac_id_by_fab.setdefault(fab, fac)

        # None for AMAT VeritySEM/Provision, which are not on this board.
        tool_type = model_to_tool_type(row.get("eqp_model_cd", ""))
        eqp = _norm(row.get("eqp_id"))
        if eqp and fab and tool_type is not None:
            placement_by_eqp[eqp] = (fab, tool_type)

    return RosterIndex(fac_id_by_fab, placement_by_eqp)


def load_index() -> RosterIndex:
    from back_dev_home.sem_list.data import get_sem_list

    return build_index(get_sem_list())
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_roster.py -q
```

Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/roster.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_roster.py
git commit -m "feat(live-alarm): resolve fab and fac_id through the sem_list roster

The alarm feed carries EQP_ID and no fab column, so fab attribution is a
lookup against sem_list — never a parse of the id. The same roster supplies
fab_name -> fac_id, so M16A/B/C collapse onto one cache key with no hardcoded
mapping table."
```

---

### Task 4: Move `normalize` up to the feature, with a NaN guard

`writer/normalize.py` duplicates its constants because the writer was copied
to a service that could not import `back_dev_home`. Inside SKEWNONO it can
import `contracts`. It also needs a guard the writer never needed: the office
returns a **pandas DataFrame**, and `to_dict()` leaves `NaN` in optional
columns, which `str()` renders as the literal text `"nan"`.

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/normalize.py`
- Create: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_normalize.py`
- Leave `writer/normalize.py` in place — Task 7 deletes the package.

**Interfaces:**

- Consumes: `contracts.ALID_KIND`, `contracts.FUTURE_TOLERANCE_SEC`.
- Produces: `normalize.to_events(rows: list[dict], *, now: int) -> list[dict]`,
  `normalize.canonical_json(event: dict) -> str`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_normalize.py`:

```python
from back_dev_home.ebeam.hitachi.live_alarm.normalize import canonical_json, to_events


NOW = 1_000_000_000


def _row(**over):
    row = {
        "EQP_ID": "MCD101",
        "ALID": "9006",
        "UTC9": "2001-09-09 10:46:40",
        "ALARM_NAME": "Align Fail",
        "RECIPE_ID": "MONITOR/CD_TOP_01",
        "OPERATION_DESC": "CD MEASUREMENT",
        "LOT_TYPE_CD": "PROD",
    }
    row.update(over)
    return row


def test_every_documented_column_round_trips():
    event = to_events([_row()], now=NOW)[0]
    assert event["eqp_id"] == "MCD101"
    assert event["alid"] == "9006"
    assert event["kind"] == "align"
    assert event["alarm_name"] == "Align Fail"
    assert event["recipe_id"] == "MONITOR/CD_TOP_01"
    assert event["operation_desc"] == "CD MEASUREMENT"
    assert event["lot_type_cd"] == "PROD"
    assert event["id"] == f"MCD101|9006|{event['occurred_at']}"


def test_pandas_float_alid_is_normalized():
    # A DataFrame integer column reaches us as "9006.0"; both spellings are
    # the same alarm and an unnormalized one has no kind and is dropped.
    assert to_events([_row(ALID="9006.0")], now=NOW)[0]["alid"] == "9006"


def test_nan_optional_fields_become_empty_not_the_text_nan():
    # DataFrame.to_dict leaves NaN in place. str(nan) is "nan", which would
    # render literally in the UI — the office-only null path that home mocks
    # never produce.
    event = to_events([_row(RECIPE_ID=float("nan"), OPERATION_DESC=None)], now=NOW)[0]
    assert event["recipe_id"] == ""
    assert event["operation_desc"] == ""


def test_timestamp_is_the_fallback_for_utc9():
    row = _row()
    del row["UTC9"]
    row["TIMESTAMP"] = "2001-09-09 10:46:40"
    assert to_events([row], now=NOW)[0]["occurred_epoch"] > 0


def test_unknown_alid_is_dropped():
    assert to_events([_row(ALID="1001")], now=NOW) == []


def test_undated_row_is_dropped():
    assert to_events([_row(UTC9="not a time")], now=NOW) == []


def test_far_future_row_is_dropped():
    # A fast upstream clock would otherwise park the event above the prune
    # boundary, where it never ages off the board.
    assert to_events([_row(UTC9="2035-01-01 00:00:00")], now=NOW) == []


def test_canonical_json_is_stable_regardless_of_key_order():
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_normalize.py -q
```

Expected: FAIL — `ModuleNotFoundError: ... live_alarm.normalize`.

- [ ] **Step 3: Implement `normalize.py`**

```python
"""Office alarm rows -> AlarmEvent, plus the canonical ZSET member form.

Moved out of writer/ when the scheduled writer was replaced by the on-demand
refresh. It no longer duplicates ALID_KIND and FUTURE_TOLERANCE_SEC: that
duplication existed only because the writer was copied onto a service without
back_dev_home on its path.

Deliberately free of pandas. refresh.py converts the office DataFrame to dict
rows before calling in, so this module stays testable with plain literals.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    ALID_KIND,
    FUTURE_TOLERANCE_SEC,
)


KST = timezone(timedelta(hours=9))

__all__ = ["to_events", "canonical_json"]

# What DataFrame.to_dict leaves behind in an empty optional cell. str() turns
# each of these into text that would render literally on the board.
_NULLISH = {"nan", "nat", "none", "<na>"}


def _text(row: Any, *names: str) -> str:
    for name in names:
        if not isinstance(row, dict) or name not in row:
            continue
        value = row[name]
        if value is None:
            continue
        if isinstance(value, float) and value != value:   # NaN is never equal to itself
            continue
        text = str(value).strip()
        if not text or text.lower() in _NULLISH:
            continue
        return text
    return ""


def _alid(row: Any) -> str:
    """Normalize the alarm id to a bare integer string.

    The feed reaches us through pandas, which turns an integer column into
    "9006.0". Both spellings mean the same alarm.
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
            # An upstream clock running fast would park this above the prune
            # boundary, where it would never age off the board.
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

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_normalize.py -q
```

Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/normalize.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_normalize.py
git commit -m "feat(live-alarm): move normalize into the feature, guard pandas nulls

Inside SKEWNONO this can import contracts, so ALID_KIND and
FUTURE_TOLERANCE_SEC stop being duplicated. Adds the guard the writer never
needed: the office returns a DataFrame, and to_dict leaves NaN in optional
columns, which str() would render as the literal text 'nan' on the board."
```

---

### Task 5: The refresh core — cache, lock, backoff

**Files:**

- Create: `back_dev_home/ebeam/hitachi/live_alarm/refresh.py`
- Test: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_refresh.py` (create)

**Interfaces:**

- Consumes: `contracts.{CACHE_TTL_SEC,LOCK_TTL_SEC,PRUNE_SEC}`,
  `normalize.{to_events,canonical_json}`, `FakeRedis` in tests.
- Produces: `refresh.keys(fac_id) -> (events_key, meta_key, lock_key)`,
  `refresh.read_meta(client, fac_id) -> dict | None`,
  `refresh.ensure_fresh(client, fac_id, *, now, fetch=None) -> None`.
  `fetch` is a `(fac_id) -> list[dict]` injection point used only by tests.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_refresh.py`:

```python
"""The cache and the lock — the whole reason this feature was redesigned.

Every assertion here is about how often the OFFICE is called, not about what
the board contains. The board's content is normalize.py's contract.
"""

import pytest

from back_dev_home.ebeam.hitachi.live_alarm import refresh
from back_dev_home.ebeam.hitachi.live_alarm.contracts import CACHE_TTL_SEC, LOCK_TTL_SEC
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis


FAC = "M16"


class Spy:
    """A fetch that records its calls and can be told to fail."""

    def __init__(self, rows=None, fail=False):
        self.rows = rows if rows is not None else []
        self.fail = fail
        self.calls: list[str] = []

    def __call__(self, fac_id):
        self.calls.append(fac_id)
        if self.fail:
            raise RuntimeError("office alarm API is down")
        return self.rows


def _row(eqp_id="MCD101", utc9="2001-09-09 10:46:40", alid="9006"):
    return {"EQP_ID": eqp_id, "ALID": alid, "UTC9": utc9, "ALARM_NAME": "Align Fail"}


def _fresh(client, spy, now):
    refresh.ensure_fresh(client, FAC, now=now, fetch=spy)


def test_cold_cache_fetches_once():
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, 1_000_000_000)
    assert spy.calls == [FAC]


def test_second_call_inside_the_ttl_does_not_touch_the_office():
    # THE core claim: N viewers, one upstream call.
    client, spy = FakeRedis(), Spy([_row()])
    now = 1_000_000_000
    _fresh(client, spy, now)
    for offset in range(1, CACHE_TTL_SEC):
        _fresh(client, spy, now + offset)
    assert spy.calls == [FAC]


def test_the_office_is_called_again_once_the_ttl_lapses():
    client, spy = FakeRedis(), Spy([_row()])
    now = 1_000_000_000
    _fresh(client, spy, now)
    client.advance(CACHE_TTL_SEC)
    _fresh(client, spy, now + CACHE_TTL_SEC)
    assert spy.calls == [FAC, FAC]


def test_a_concurrent_caller_serves_the_old_board_instead_of_fetching():
    # Simulates the lock being held by another request already in flight.
    client, spy = FakeRedis(), Spy([_row()])
    now = 1_000_000_000
    _, _, lock_key = refresh.keys(FAC)
    client.set(lock_key, "someone-elses-token", nx=True, ex=LOCK_TTL_SEC)
    _fresh(client, spy, now)
    assert spy.calls == []


def test_a_failed_fetch_does_not_stamp_the_cache():
    # A fresh timestamp over data that never arrived is the one failure mode
    # this design exists to prevent.
    client, spy = FakeRedis(), Spy(fail=True)
    _fresh(client, spy, 1_000_000_000)
    assert refresh.read_meta(client, FAC) is None


def test_a_failed_fetch_backs_off_until_the_lock_expires():
    client, spy = FakeRedis(), Spy(fail=True)
    now = 1_000_000_000
    _fresh(client, spy, now)
    client.advance(LOCK_TTL_SEC - 1)
    _fresh(client, spy, now + LOCK_TTL_SEC - 1)
    assert spy.calls == [FAC], "retried while the office was still failing"
    client.advance(1)
    _fresh(client, spy, now + LOCK_TTL_SEC)
    assert spy.calls == [FAC, FAC], "never retried after the backoff lapsed"


def test_a_successful_fetch_releases_the_lock_immediately():
    client, spy = FakeRedis(), Spy([_row()])
    _fresh(client, spy, 1_000_000_000)
    _, _, lock_key = refresh.keys(FAC)
    assert client.get(lock_key) is None


def test_overlapping_snapshots_accumulate_into_one_deduped_board():
    # The office takes no window argument, so successive snapshots overlap.
    # Re-adding an event already present must be a no-op.
    client = FakeRedis()
    now = 1_000_000_000
    first = Spy([_row(utc9="2001-09-09 10:46:40")])
    second = Spy([_row(utc9="2001-09-09 10:46:40"), _row(eqp_id="MCD102")])
    _fresh(client, first, now)
    client.advance(CACHE_TTL_SEC)
    _fresh(client, second, now + CACHE_TTL_SEC)
    events_key, _, _ = refresh.keys(FAC)
    assert len(client.store_zset(events_key)) == 2


def test_each_facility_has_its_own_cache_and_lock():
    client, spy = FakeRedis(), Spy([_row()])
    now = 1_000_000_000
    refresh.ensure_fresh(client, "M16", now=now, fetch=spy)
    refresh.ensure_fresh(client, "R3", now=now, fetch=spy)
    assert spy.calls == ["M16", "R3"]


def test_missing_office_utils_raises_rather_than_serving_a_silent_empty_board():
    # office_utils is absent at home, so the real fetch path is exercised here.
    client = FakeRedis()
    with pytest.raises(RuntimeError, match="office_utils"):
        refresh.ensure_fresh(client, FAC, now=1_000_000_000)


def test_a_missing_office_utils_does_not_leave_a_lock_behind():
    # Resolved before the lock is taken: a deployment fault must not wedge
    # the feature for LOCK_TTL_SEC on top of failing.
    client = FakeRedis()
    with pytest.raises(RuntimeError):
        refresh.ensure_fresh(client, FAC, now=1_000_000_000)
    _, _, lock_key = refresh.keys(FAC)
    assert client.get(lock_key) is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_refresh.py -q
```

Expected: FAIL — `ModuleNotFoundError: ... live_alarm.refresh`.

- [ ] **Step 3: Implement `refresh.py`**

```python
"""On-demand board refresh: a 20-second cache in front of the office API.

The page request is the trigger. Freshness is checked first, so the common
case makes no office call at all; when the cache has lapsed, exactly one
request wins a lock and fetches while every other request serves the board
already in Redis.

Three rules hold this together:

* the lock is NON-BLOCKING — a loser never waits, it serves what is there;
* `fetched_at` is stamped ONLY on success, so a failing feed ages into
  "stale" rather than reporting a fresh heartbeat over missing data;
* the lock is released only on success, so its TTL doubles as the retry
  backoff and an office API already in trouble is not retried by every poll
  of every viewer.

The events key stays an ACCUMULATING ZSET rather than a last-response cache.
`get_live_alarms` takes no window argument, so how far back it reaches is the
office's choice; if it reports only currently-active alarms, a last-response
cache could never hold the 10-minute board. Accumulation is safe because ZSET
members are canonical JSON, making a repeated event a no-op.
"""

from __future__ import annotations

import json
import logging
import secrets

from back_dev_home.ebeam.hitachi.live_alarm.contracts import (
    CACHE_TTL_SEC,
    LOCK_TTL_SEC,
    PRUNE_SEC,
)
from back_dev_home.ebeam.hitachi.live_alarm.normalize import canonical_json, to_events


log = logging.getLogger(__name__)

KEY_PREFIX = "skewnono:live_alarm"
TTL_SEC = 86_400

__all__ = ["keys", "read_meta", "ensure_fresh"]

# Compare-and-delete. A fetch that outlived its own lock TTL must not delete
# the SUCCESSOR's lock, which is what an unconditional DEL would do.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def keys(fac_id: str) -> tuple[str, str, str]:
    """events, meta, lock — all scoped to the FACILITY, not the fab.

    fac_id is the granularity the office call is parameterized by, so M16A,
    M16B and M16C share one entry and issue one upstream call between them.
    """
    base = f"{KEY_PREFIX}:{fac_id}"
    return f"{base}:events", f"{base}:meta", f"{base}:lock"


def read_meta(client, fac_id: str) -> dict | None:
    _, meta_key, _ = keys(fac_id)
    raw = client.get(meta_key)
    if not raw:
        return None
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        payload = json.loads(text)
    except (UnicodeDecodeError, ValueError, TypeError):
        # Unreadable meta is indistinguishable from no meta: treat as cold.
        return None
    if not isinstance(payload, dict) or "fetched_at" not in payload:
        return None
    return payload


def _office_fetch():
    """Bind the office callable, or explain why it is missing.

    Imported inside the function because office_utils is gitignored and does
    not exist at home; a module-scope import would break the whole app
    factory's discovery sweep on any developer machine.
    """
    try:
        from office_utils.live_alarm import get_live_alarms
    except ImportError as exc:
        raise RuntimeError(
            "office_utils.live_alarm is not importable — live_alarm's office "
            "provider needs the office-only office_utils package on sys.path. "
            "Copy it onto this host, or run with "
            "SKEWNONO_LIVE_ALARM_PROVIDER=mock."
        ) from exc

    def fetch(fac_id: str) -> list[dict]:
        frame = get_live_alarms(fac_id)
        # DataFrame -> dict rows (CLAUDE.md's dataframe-dict convention).
        # NaN survives to_dict; normalize._text is what guards it.
        if hasattr(frame, "to_dict"):
            return frame.to_dict(orient="records")
        return list(frame)

    return fetch


def _write_board(client, fac_id: str, events: list[dict], now: int) -> None:
    events_key, meta_key, _ = keys(fac_id)
    pipe = client.pipeline()
    if events:
        # redis-py rejects an empty mapping, and a quiet facility is normal.
        pipe.zadd(events_key, {canonical_json(e): e["occurred_epoch"] for e in events})
    pipe.zremrangebyscore(events_key, "-inf", now - PRUNE_SEC)
    pipe.expire(events_key, TTL_SEC)
    pipe.set(meta_key, json.dumps({"fetched_at": now}), ex=TTL_SEC)
    pipe.execute()


def ensure_fresh(client, fac_id: str, *, now: int, fetch=None) -> None:
    """Refresh this facility's board if the cache has lapsed. Never blocks."""
    meta = read_meta(client, fac_id)
    if meta and now - int(meta["fetched_at"]) < CACHE_TTL_SEC:
        return

    # Bound BEFORE the lock is taken. A missing office_utils is a deployment
    # fault that must surface as a 503 — not be swallowed as a transient
    # failure, and not hold a lock for LOCK_TTL_SEC on the way out.
    fetcher = fetch or _office_fetch()

    _, _, lock_key = keys(fac_id)
    token = secrets.token_hex(8)
    if not client.set(lock_key, token, nx=True, ex=LOCK_TTL_SEC):
        return   # another request is fetching; serve the board already here

    try:
        rows = fetcher(fac_id)
        _write_board(client, fac_id, to_events(rows, now=now), now)
    except Exception:
        log.exception("live_alarm refresh failed for fac_id=%s", fac_id)
        # The lock is deliberately NOT released: it expires in LOCK_TTL_SEC
        # and is the retry backoff.
        return

    client.eval(_RELEASE_LUA, 1, lock_key, token)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_refresh.py -q
```

Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/refresh.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_refresh.py
git commit -m "feat(live-alarm): add the cached, lock-guarded on-demand refresh

Bounds office API load at one call per facility per CACHE_TTL_SEC no matter
how many viewers poll. The lock is non-blocking so no request ever waits on
another, and is released only on success so its TTL doubles as the retry
backoff. fetched_at is stamped only on success, so a failing feed ages into
stale instead of reporting a fresh heartbeat over data that never arrived."
```

---

### Task 6: Rewrite the office reader

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/live_alarm/providers/office_example.py` (full rewrite)
- Test: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_office_reader.py` (create)

**Interfaces:**

- Consumes: `roster.load_index`, `refresh.ensure_fresh`, `refresh.keys`,
  `refresh.read_meta`, `board.{parse_members,dedupe_by_id,feed_status_for}`,
  `office_redis.{redis_client,STORE_ERRORS,unreachable}`.
- Produces: `get_board(tool_type, fab_name) -> LiveAlarmPayload`, and the
  internal seams the test injects: `_build_board(client, index, tool_type,
  fab_name, *, now)`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/hitachi/live_alarm/tests/test_office_reader.py`:

```python
"""The reader: roster attribution, unmatched counting, and the three states.

Exercises _build_board directly so no Redis connection or office_utils import
is needed — get_board is a thin wrapper that supplies the client and index.
"""

from back_dev_home.ebeam.hitachi.live_alarm import refresh, roster
from back_dev_home.ebeam.hitachi.live_alarm.providers import office_example as reader
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis


NOW = 1_000_000_000
FAC = "M16"

ROWS = [
    {"eqp_id": "MCD101", "fab_name": "M16A", "fac_id": "M16", "eqp_model_cd": "CG6300"},
    {"eqp_id": "MCD102", "fab_name": "M16B", "fac_id": "M16", "eqp_model_cd": "CG6300"},
    {"eqp_id": "TP0421", "fab_name": "M16A", "fac_id": "M16", "eqp_model_cd": "TP3000"},
]


def _seed(client, *eqp_ids, now=NOW):
    """Put one align alarm per eqp_id on M16's board."""
    events = [
        {
            "id": f"{eqp}|9006|x", "eqp_id": eqp, "alid": "9006", "kind": "align",
            "alarm_name": "Align Fail", "occurred_at": "2001-09-09 10:46:40",
            "occurred_epoch": now - 60, "recipe_id": "", "operation_desc": "",
            "lot_type_cd": "",
        }
        for eqp in eqp_ids
    ]
    refresh._write_board(client, FAC, events, now)


def _board(client, tool_type="cd-sem", fab_name="M16A"):
    return reader._build_board(client, roster.build_index(ROWS), tool_type, fab_name, now=NOW)


def test_events_are_attributed_to_the_right_fab():
    client = FakeRedis()
    _seed(client, "MCD101", "MCD102")
    assert [e["eqp_id"] for e in _board(client, fab_name="M16A")["events"]] == ["MCD101"]
    assert [e["eqp_id"] for e in _board(client, fab_name="M16B")["events"]] == ["MCD102"]


def test_events_are_attributed_to_the_right_tool_family():
    client = FakeRedis()
    _seed(client, "MCD101", "TP0421")
    assert [e["eqp_id"] for e in _board(client, "cd-sem", "M16A")["events"]] == ["MCD101"]
    assert [e["eqp_id"] for e in _board(client, "hv-sem", "M16A")["events"]] == ["TP0421"]


def test_unrostered_equipment_is_counted_not_shown():
    client = FakeRedis()
    _seed(client, "MCD101", "MCD999")
    result = _board(client)
    assert [e["eqp_id"] for e in result["events"]] == ["MCD101"]
    assert result["unmatched_count"] == 1


def test_a_fab_with_no_tools_of_this_family_is_not_configured():
    client = FakeRedis()
    _seed(client, "MCD102")
    result = _board(client, "hv-sem", "M16B")   # M16B holds only a CD-SEM
    assert result["feed_status"] == "not_configured"
    assert result["events"] == []
    assert result["fetched_at"] is None


def test_a_configured_fab_with_a_recent_fetch_is_live():
    client = FakeRedis()
    _seed(client, "MCD101")
    result = _board(client)
    assert result["feed_status"] == "live"
    assert result["fetched_at"] is not None


def test_events_outside_the_board_window_are_not_shown():
    client = FakeRedis()
    _seed(client, "MCD101", now=NOW - 5000)
    # The seed also stamped fetched_at at NOW - 5000, so the feed reads stale.
    assert _board(client)["events"] == []


def test_covered_since_is_derived_from_the_board_window():
    client = FakeRedis()
    _seed(client, "MCD101")
    assert _board(client)["covered_since"] is not None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_office_reader.py -q
```

Expected: FAIL — `AttributeError: module ... has no attribute '_build_board'`.

- [ ] **Step 3: Rewrite `providers/office_example.py`**

Replace the file entirely:

```python
"""[Office template] live_alarm reader. Copy to office.py to activate.

    cp office_example.py office.py

Unlike most office adapters this one both reads and writes: the board it reads
is refreshed on demand by refresh.py, behind a 20-second cache and a lock, so
opening the page calls the in-house alarm API at most once per facility per 20
seconds no matter how many people are watching.

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


def _empty(tool_type: ToolType, fab_name: str, *, now: int) -> LiveAlarmPayload:
    """A fab the roster holds no tools for: no feed, and none expected."""
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
    """Read one fab's board out of its facility's ZSET. Assumes fresh."""
    fac_id = index.fac_id_for(fab_name)
    events_key, _, _ = refresh.keys(fac_id)

    raw = client.zrangebyscore(
        events_key,
        now - BOARD_WINDOW_SEC,
        # Not "+inf": a fast upstream clock would otherwise pin a far-future
        # event to the top of the board forever.
        now + FUTURE_TOLERANCE_SEC,
    )
    everything = board.dedupe_by_id(board.parse_members(raw))

    mine = []
    unmatched = 0
    for event in everything:
        placement = index.placement_of(event.get("eqp_id", ""))
        if placement is None:
            # In the facility's feed but in no fab: a tool the roster does not
            # carry yet (still firewalled). Counted, so a roster gap does not
            # look like a quiet fab.
            unmatched += 1
        elif placement == (fab_name.strip().upper(), tool_type):
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
        return _empty(tool_type, fab_name, now=int(time.time()))

    try:
        client = redis_client()
        # Redis is the single clock authority — the refresh prunes against
        # this same clock, so the two never disagree about the boundary.
        now = int(client.time()[0])
        refresh.ensure_fresh(client, index.fac_id_for(fab_name), now=now)
        return _build_board(client, index, tool_type, fab_name, now=now)
    except STORE_ERRORS as exc:
        raise unreachable("live_alarm board is unreachable", exc) from exc
```

- [ ] **Step 4: Run the tests**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_office_reader.py -q
```

Expected: PASS (7 tests).

- [ ] **Step 5: Confirm the office template still imports cleanly**

```bash
.venv/bin/python -m pytest tests/test_office_adapter_parity.py -q
```

Expected: PASS. This suite imports every office template, and is the gate that
proves the reader no longer depends on `writer.job` — which Task 7 deletes.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/providers/office_example.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_office_reader.py
git commit -m "feat(live-alarm): rewrite the office reader around the cached pull

The reader now triggers its own refresh instead of reading a board a
scheduler service filled. Fab attribution goes through the sem_list roster,
and alarms from equipment the roster does not carry are counted into
unmatched_count rather than dropped silently, so a roster gap cannot look
like a quiet fab. Drops the last import of writer.job."
```

---

### Task 7: Delete the writer package and its stale references

**Files:**

- Delete: `back_dev_home/ebeam/hitachi/live_alarm/writer/` (whole directory)
- Delete: `live_alarm/tests/test_writer_job.py`, `test_writer_window.py`,
  `test_writer_normalize.py`
- Modify: `tests/test_office_adapter_parity.py:95`
- Modify: `tests/test_office_adapter_scripts.py:408-412`

**Interfaces:**

- Consumes: nothing. Task 6 removed the last importer.
- Produces: nothing.

- [ ] **Step 1: Confirm nothing still imports the writer**

```bash
grep -rn "live_alarm.writer\|live_alarm import writer" --include="*.py" . | grep -v node_modules
```

Expected: only the two repo-level test files and the writer's own files. If
`providers/office_example.py` appears, Task 6 is incomplete — stop and finish it.

- [ ] **Step 2: Delete the package and its tests**

```bash
git rm -r back_dev_home/ebeam/hitachi/live_alarm/writer
git rm back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_job.py \
       back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_window.py \
       back_dev_home/ebeam/hitachi/live_alarm/tests/test_writer_normalize.py
```

- [ ] **Step 3: Remove the parity carve-out**

In `tests/test_office_adapter_parity.py`, delete lines 91–95 — the comment
block and the `NO_MOCK_SIBLING` assignment:

```python
# The writer directory is copied wholesale onto a scheduler service and has no
# providers/ layout and no mock.py at all — its caller is its own job.py, not a
# data.py. Importability is still asserted; parity has no second side to check.
NO_MOCK_SIBLING = {"ebeam/hitachi/live_alarm/writer"}
```

Then remove every remaining reference to `NO_MOCK_SIBLING` in that file:

```bash
grep -n "NO_MOCK_SIBLING" tests/test_office_adapter_parity.py
```

Each hit is a guard of the form `if adapter.slug in NO_MOCK_SIBLING: ...` or a
set subtraction; delete the guard so every discovered adapter takes the normal
parity path. `live_alarm` now has an ordinary `providers/{mock,office}.py`
layout, so there is no longer an adapter without a mock sibling.

- [ ] **Step 4: Drop the stale gitignore parameter**

In `tests/test_office_adapter_scripts.py`, remove this line from the
`@pytest.mark.parametrize` list at line ~412:

```python
    "back_dev_home/ebeam/hitachi/live_alarm/writer/office.py",
```

This test asserts a `.gitignore` rule and `git check-ignore` answers for paths
that do not exist, so leaving it would stay green — but it would assert a rule
about a file nobody can ever create.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. Compare `passed + skipped` against the pre-change total, not
`passed` alone — a worktree has no gitignored `office*.py`, so skip counts
legitimately differ from the main checkout.

- [ ] **Step 6: Commit**

```bash
git add -u tests/test_office_adapter_parity.py tests/test_office_adapter_scripts.py
git commit -m "refactor(live-alarm): delete the scheduler writer package

The writer existed to keep the alarm API off the request path; the cached
pull does that with a 20s TTL and no second deployment. Its office template
also assumed a per-fab URL map and a windowed query the office API does not
offer. live_alarm drops from two swap surfaces to one, so the parity suite's
no-mock-sibling carve-out and the scripts suite's writer/office.py parameter
both go with it."
```

---

### Task 8: Update the mock provider

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/live_alarm/providers/mock.py`
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_contract.py`

**Interfaces:**

- Consumes: `contracts.LiveAlarmPayload`.
- Produces: a mock payload carrying `fetched_at` and `unmatched_count`.

- [ ] **Step 1: Update the contract test**

In `tests/test_contract.py`, replace `polled_at` with `fetched_at` at lines 85
and 99, and add one test:

```python
def test_unmatched_count_is_always_present_and_non_negative():
    # A roster gap must be reportable on every board, including an empty one:
    # the field is what keeps "no alarms" distinguishable from "alarms we
    # could not attribute".
    for fab in (CONFIGURED_FAB, UNKNOWN_FAB):
        board = data.get_board(TOOL_TYPE, fab)
        assert isinstance(board["unmatched_count"], int)
        assert board["unmatched_count"] >= 0
```

Also update the module docstring's line 11 from

```text
returns whatever the writer job last pushed into Redis — which for a healthy,
```

to

```text
returns whatever the last successful office fetch put in Redis — which for a
healthy,
```

and line 36's comment from `the office writer's Redis registry` to
`the office roster`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm/tests/test_contract.py -q
```

Expected: FAIL — `KeyError: 'unmatched_count'`.

- [ ] **Step 3: Update `mock.py`**

Replace the module docstring's lines 8–37 with:

```python
Office counterpart — schema of record: `docs/datatables/live_alarm_board.txt`.
The office read source is refreshed by the SAME request that reads it: a page
view calls `refresh.ensure_fresh`, which fetches from the in-house alarm API
only when the facility's cache is older than CACHE_TTL_SEC and only after
winning a lock. Opening the page therefore costs at most one office call per
facility per 20 seconds, shared by every viewer:

    page --(cache miss + lock)--> 사내 alarm API --> Redis board --> page
    page --(cache hit)---------------------------> Redis board --> page

    skewnono:live_alarm:{fac_id}:events   ZSET, score = occurred_epoch
    skewnono:live_alarm:{fac_id}:meta     JSON, fetched_at
    skewnono:live_alarm:{fac_id}:lock     stampede guard

Keys are scoped by fac_id (the coarse facility: M16, R3), NOT by fab_name
(M16A, R3, R4) — one office call covers a whole facility, and the reader
filters it down to the requested fab through the sem_list roster.

Windows come from `contracts.py` and are shared with this mock, so home and
office cut the board the same way: BOARD_WINDOW_SEC (600) back, and only
FUTURE_TOLERANCE_SEC (300) forward — not +inf, because one upstream clock
running fast would otherwise pin a far-future alarm to the top of the board
permanently.

OFFICE-VERIFY: how far back `get_live_alarms(fac_id)` reaches is unknown. The
ZSET accumulates successive snapshots and prunes at PRUNE_SEC, so the board is
rebuilt correctly whether the office returns a rolling history or only the
alarms active right now.

Office reads take `now` from REDIS's clock, not the app server's, because the
refresh prunes against that same clock. This mock uses the local clock, which
is the honest home equivalent and the reason its output shifts by the minute.
```

Then replace `get_board` (lines 100–133) with:

```python
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
        # reachable at home. A mock that always reported 0 would leave that
        # UI path unexercised until it first appeared at the office.
        "unmatched_count": 1 if count == 3 else 0,
        "events": sorted(events, key=lambda e: e["occurred_epoch"], reverse=True),
    }
```

- [ ] **Step 4: Run the feature suite**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm -q
```

Expected: PASS, all files.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/providers/mock.py \
        back_dev_home/ebeam/hitachi/live_alarm/tests/test_contract.py
git commit -m "feat(live-alarm): teach the mock fetched_at and unmatched_count

Also rewrites the docstring's description of the office counterpart: keys are
fac_id-scoped now, and the board is refreshed by the request that reads it
rather than by a scheduler. Emits a non-zero unmatched_count one minute in
four so the roster-gap UI is reachable at home instead of first appearing at
the office."
```

---

### Task 9: Frontend rename and the roster-gap line

**Files:**

- Modify: `front-dev-home/app/utils/liveAlarm.ts:20-29`
- Modify: `front-dev-home/app/composables/useLiveAlarmFeed.ts`
- Modify: `front-dev-home/app/composables/useLiveAlarmFeed.test.ts`
- Modify: `front-dev-home/app/components/ebeam/LiveAlarmView.vue`

**Interfaces:**

- Consumes: the backend payload's `fetched_at` and `unmatched_count`.
- Produces: `useLiveAlarmFeed(...)` returning `fetchedAt` (was `polledAt`) and
  a new `unmatchedCount`.

- [ ] **Step 1: Update the payload type**

In `app/utils/liveAlarm.ts`, replace the `LiveAlarmPayload` interface:

```typescript
export interface LiveAlarmPayload {
  fab_name: string
  tool_type: string
  feed_status: FeedStatus
  // Last SUCCESSFUL office fetch — null when there has never been one.
  fetched_at: string | null
  covered_since: string | null
  server_now: string
  board_window_sec: number
  // Alarms in this facility's feed whose equipment is absent from the
  // sem_list roster, so they belong to no fab. Shown as a count, never as
  // rows: they cannot be attributed to the fab being viewed.
  unmatched_count: number
  events: LiveAlarmEvent[]
}
```

- [ ] **Step 2: Update the composable**

In `app/composables/useLiveAlarmFeed.ts`:

1. In the `FeedState` interface, replace `polledAt: string | null` with:

```typescript
  fetchedAt: string | null
  unmatchedCount: number
```

1. In `applyPoll`'s returned object, replace `polledAt: payload.polled_at` with:

```typescript
    fetchedAt: payload.fetched_at,
    unmatchedCount: payload.unmatched_count,
```

1. In the `useState` initializer, replace `polledAt: null` with
   `fetchedAt: null, unmatchedCount: 0`.

1. In the returned object, replace the `polledAt` computed with:

```typescript
    fetchedAt: computed(() => state.value.fetchedAt),
    // Non-zero means the feed carried alarms this build could not attribute
    // to any fab — a roster gap, not a quiet board.
    unmatchedCount: computed(() => state.value.unmatchedCount),
```

- [ ] **Step 3: Update the composable's test fixture**

In `app/composables/useLiveAlarmFeed.test.ts`, in the payload fixture, replace
`polled_at` with `fetched_at` and add `unmatched_count: 0`. Then update any
assertion referencing `polledAt` to `fetchedAt`.

- [ ] **Step 4: Update the view**

In `app/components/ebeam/LiveAlarmView.vue`:

1. Line 15 — replace `polledAt` with `fetchedAt` and add `unmatchedCount` to
   the destructured bindings.

1. Lines 26–29 — replace `sinceLastPoll`:

```typescript
const sinceLastPoll = computed(() => {
  if (!fetchedAt.value) return '갱신 기록 없음'
  return `${formatElapsed(Date.now() + serverOffsetMs.value - Date.parse(fetchedAt.value))} 갱신`
})
```

1. In the template, immediately after the element rendering the alarm rows,
   add the roster-gap line:

```vue
<p
  v-if="unmatchedCount > 0"
  class="mt-2 text-xs text-[--sk-ink-muted]"
>
  장비 목록에 없는 알람 {{ unmatchedCount }}건은 표시하지 않았습니다.
</p>
```

Use the `--sk-*` token that the surrounding muted text already uses — read the
file's existing classes and match them rather than introducing a new colour.
`DESIGN.md` is the source of truth and inline hex is never allowed.

- [ ] **Step 5: Run the frontend checks**

```bash
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/liveAlarm.ts \
        front-dev-home/app/composables/useLiveAlarmFeed.ts \
        front-dev-home/app/composables/useLiveAlarmFeed.test.ts \
        front-dev-home/app/components/ebeam/LiveAlarmView.vue
git commit -m "feat(live-alarm): follow the fetched_at rename, surface roster gaps

polled_at named a writer heartbeat that no longer exists. unmatched_count
renders as a quiet line rather than a badge: it reports that the feed carried
alarms from equipment the roster does not know, which is an operator's cue to
check the tool list, not an alarm in its own right."
```

---

### Task 10: Rewrite the office-facing docs

CLAUDE.md's rule: office-DB knowledge lands in **both** `docs/datatables/` and
the feature's `mock.py`. Task 8 did the mock; this task does the rest.

**Files:**

- Rewrite: `back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md`
- Rewrite: `docs/datatables/live_alarm_board.txt`
- Modify: `back_dev_home/.env.example:193-203`

- [ ] **Step 1: Rewrite `MIGRATION.md`**

Replace the whole file. It is written in Korean with `~입니다./~합니다.`
endings, per CLAUDE.md, because it is read by teammates at the office.

````markdown
# live_alarm — 오피스 전환 절차

swap surface 는 **하나**입니다. `providers/office.py` 를 만들면 이 기능이
office 모드로 전환됩니다. 별도의 스케줄러 서비스나 writer 배포는 필요하지
않습니다.

## 1. office_utils 에 알람 조회 함수를 둡니다

`office_utils/live_alarm.py` 에 아래 한 함수를 구현합니다. SKEWNONO 는 이
함수 하나만 호출합니다.

```python
def get_live_alarms(fac_id: str) -> pd.DataFrame:
    """한 fac_id 의 알람 rows 를 ALID 구분 없이 모두 돌려줍니다."""
    align = filter_align_fail(get_cdsem_alarms(fac_id))
    meas = get_measurement_fail_alarms(fac_id)
    return pd.concat([align, meas], ignore_index=True)
```

반환 컬럼은 workflow_3 알람 표준 스키마와 같습니다.

| 컬럼 | 필수 | 의미 |
| --- | --- | --- |
| `EQP_ID` | 예 | 장비 ID. 이 값으로 sem_list 에서 fab 을 찾습니다 |
| `ALID` | 예 | `9006` align fail, `9100` 측정 연속 실패 |
| `UTC9` | 예 | `"%Y-%m-%d %H:%M:%S"` 발생 시각 |
| `RECIPE_ID` | 아니오 | `"<class>/<recipe>"` |
| `ALARM_NAME` | 아니오 | 사람이 읽는 라벨 |
| `OPERATION_DESC` | 아니오 | 공정/스텝 설명 |
| `LOT_TYPE_CD` | 아니오 | lot 종류 코드 |
| `TIMESTAMP` | 아니오 | `UTC9` 가 없을 때의 대체 값 |

**인자는 `fac_id` 입니다** (`M16`, `R3`). 화면 URL 이 나르는 `fab_name`
(`M16A`, `R3`, `R4`) 이 아닙니다. `R3` 은 두 값이 같아지는 유일한 값이라
`R3` 만으로는 이 구분이 드러나지 않습니다.

## 2. reader 활성화

```bash
cd back_dev_home/ebeam/hitachi/live_alarm/providers
cp office_example.py office.py
```

`office.py` 파일이 존재한다는 사실 자체가 이 기능을 office 모드로
전환합니다. 별도의 환경 변수 설정은 필요하지 않습니다.

## 3. 동작 확인

```bash
curl 'http://localhost:5000/api/health/providers' | grep live_alarm
curl 'http://localhost:5000/api/cdsem/live-alarm?fab_name=M16A'
redis-cli -n 0 --scan --pattern 'skewnono:live_alarm:*'
```

응답의 `feed_status` 값을 확인합니다.

| 값 | 의미 | 조치 |
| --- | --- | --- |
| `live` | 마지막 성공 조회가 90초 이내입니다 | 없음 |
| `stale` | 마지막 성공 조회가 오래됐습니다 | Flask 로그에서 `live_alarm refresh failed` 를 확인합니다 |
| `not_configured` | sem_list 에 이 fab 의 해당 tool 이 없습니다 | sem_list roster 를 확인합니다 |

`unmatched_count` 가 0 이 아니면, 알람은 왔는데 그 `EQP_ID` 가 sem_list 에
없다는 뜻입니다. 방화벽 미개방 장비일 가능성이 높습니다.

## 4. 부하 확인

사내 alarm API 호출은 **fac_id 당 20초에 한 번**이 상한입니다. 보는 사람이
몇 명이든, 얼마나 자주 새로고침하든 이 상한은 변하지 않습니다. 아무도 페이지를
열지 않으면 호출은 0 입니다.

호출이 이보다 잦다면 `CACHE_TTL_SEC` 이 아니라 락을 의심합니다. Redis 가
여러 대로 분리돼 있으면 `SET NX` 가 인스턴스마다 따로 걸려 상한이 인스턴스
수만큼 늘어납니다.

## 주의

- 캐시 키는 `fac_id` 단위입니다. `M16A`/`M16B`/`M16C` 는 하나의 항목을
  공유하고, `R3`/`R4` 도 하나를 공유합니다.
- 조회 실패 시 `fetched_at` 을 갱신하지 않습니다. 데이터가 오지 않았는데
  최신인 것처럼 보이는 상태를 만들지 않기 위한 것이므로, 편의를 위해서라도
  실패 경로에서 타임스탬프를 찍지 않습니다.
- 조회 실패 시 락을 풀지 않고 TTL 로 만료시킵니다. 이것이 재시도 backoff
  입니다.
````

- [ ] **Step 2: Rewrite `docs/datatables/live_alarm_board.txt`**

Replace the file's header and key-structure sections (through the `events
ZSET` heading) with:

```text
사무실(Office) Redis — 실시간 알람 보드

장비 실시간 알람입니다. Redis 는 원천이 아니라 사내 alarm API 앞에 놓인
짧은 캐시입니다. 화면을 여는 요청이 곧 갱신 트리거이며, 해당 fac_id 의
캐시가 CACHE_TTL_SEC(20초)보다 오래됐을 때만, 그리고 락을 잡은 요청 하나만
사내 API 를 호출합니다.

  page --(캐시 만료 + 락 획득)--> 사내 alarm API --> Redis 보드 --> 화면
  page --(캐시 유효)--------------------------------> Redis 보드 --> 화면

보는 사람이 몇 명이든 사내 API 호출은 fac_id 당 20초에 한 번이 상한입니다.
아무도 페이지를 열지 않으면 호출은 0 입니다.

Key 구조

  prefix : skewnono:live_alarm
  events : skewnono:live_alarm:{fac_id}:events   (ZSET)
  meta   : skewnono:live_alarm:{fac_id}:meta     (string, JSON)
  lock   : skewnono:live_alarm:{fac_id}:lock     (string, SET NX EX)

  fac_id -> "M16", "R3" 등 대문자 표기의 **fac 단위** 코드입니다.
            fab_name("M16A", "R4")이 아닙니다 — 사내 API 가 fac 단위로
            받기 때문에 캐시도 같은 단위로 잡습니다. M16A/M16B/M16C 는
            하나의 항목을 공유하고, R3/R4 도 하나를 공유합니다.
  meta   -> {"fetched_at": <epoch>}. **조회에 성공했을 때만** 기록합니다.
            실패했는데 시각을 갱신하면 데이터가 없는데도 최신으로 보입니다.
  lock   -> 값은 요청마다 만드는 임의 토큰입니다. 성공하면 토큰이 일치할
            때만 지우고(다른 요청의 락을 지우지 않기 위함), 실패하면 풀지
            않고 TTL 로 만료시켜 재시도 backoff 로 씁니다.

fab 귀속은 Redis 가 아니라 sem_list roster 가 정합니다. 알람 row 에는 fab
컬럼이 없고 EQP_ID 만 있으므로, reader 가 sem_list 에서 EQP_ID -> (fab_name,
tool_type) 을 찾습니다. EQP_ID 문자열을 파싱하지 않습니다.

OFFICE-VERIFY: get_live_alarms(fac_id) 가 과거 몇 분까지 돌려주는지는 아직
확인되지 않았습니다. events 는 ZSET 에 누적되고 PRUNE_SEC(900초)로 잘리므로,
사내 API 가 이력을 주든 '현재 발생 중'만 주든 보드는 동일하게 만들어집니다.
```

Leave the rest of the file (the `events ZSET` member schema onward) unchanged,
but delete any surviving mention of `registry` — that key no longer exists.

- [ ] **Step 3: Remove the writer env block**

In `back_dev_home/.env.example`, delete lines 193–203 (the
`── live_alarm writer ──` block and all `LIVE_ALARM_*` variables). The cached
pull uses the shared `REDIS_*` connection, and its TTLs are constants in
`contracts.py` rather than env knobs — one fewer thing to configure, and no
way for the writer and reader to end up on different databases.

- [ ] **Step 4: Verify nothing still references the removed variables**

```bash
grep -rn "LIVE_ALARM_" --include="*.py" --include="*.md" --include="*.example" . | grep -v node_modules
```

Expected: no hits except `SKEWNONO_LIVE_ALARM_PROVIDER` (the per-feature
provider override, which is unrelated and stays).

- [ ] **Step 5: Lint the Markdown**

```bash
npm run lint:md
```

Expected: `Summary: 0 error(s)`.

- [ ] **Step 6: Run the whole suite one last time**

```bash
.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md \
        docs/datatables/live_alarm_board.txt \
        back_dev_home/.env.example
git commit -m "docs(live-alarm): document the cached pull for the office

MIGRATION.md drops to one swap surface and specifies get_live_alarms(fac_id),
including the fac_id-vs-fab_name trap that R3-only development hides. The
datatables entry records the new key layout, that fetched_at is stamped only
on success, and the OFFICE-VERIFY question of how far back the feed reaches.
Removes the LIVE_ALARM_* env block, which configured a writer that is gone."
```

---

## Verification

After Task 10, drive the running app once — there is no automated E2E suite.

```bash
.venv/bin/python index.py                      # Flask on :5050
cd front-dev-home && npm run dev               # Nuxt on :3000
```

Check, at `/ebeam/cd-sem/R3/live-alarm`:

1. The board renders and the "N초 전 갱신" line advances.
1. `SKEWNONO_LIVE_ALARM_MOCK_STALE=1` flips the badge to `피드 지연`.
1. A fab outside `_CONFIGURED_FABS` (e.g. `/ebeam/cd-sem/ZZZ/live-alarm`)
   shows `미설정`.
1. Within a 4-minute window, one minute shows the roster-gap line.
1. Hiding the tab stops the polling (Network panel), and showing it resumes.

Save screenshots under `.playwright-mcp/screenshots/`.

## Self-Review Notes

Checked against the spec:

- Every spec section maps to a task: office seam → 5, fac_id/fab_name → 3,
  Redis layout → 5, refresh core → 5, read path → 6, feed_status → 2,
  contract changes → 2, error handling → 5 and 6, deletions → 7, frontend → 9,
  testing → spread across 1–9, office verification → 8 and 10.
- Names are consistent across tasks: `fetched_at` (payload) / `fetchedAt`
  (frontend), `unmatched_count` / `unmatchedCount`, `ensure_fresh`, `keys`,
  `read_meta`, `build_index`, `load_index`, `fac_id_for`, `placement_of`,
  `has_tools`, `_build_board`.
- `covered_since` is retained and derived (spec §Contract changes), so
  `utils/liveAlarm.ts` keeps the field.
- One deliberate transient: `live_alarm/normalize.py` (Task 4) coexists with
  `writer/normalize.py` until Task 7. Reviewers should not flag it before then.
