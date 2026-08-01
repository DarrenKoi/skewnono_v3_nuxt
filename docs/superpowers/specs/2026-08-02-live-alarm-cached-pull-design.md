# live_alarm — demand-driven cached pull — Design

- **Date:** 2026-08-02
- **Status:** approved
- **Area:** `ebeam/hitachi/live_alarm` — provider, refresh core, contracts,
  Redis layout, `office_utils` seam; deletes the `writer/` package

## Problem

`live_alarm` was built as a **writer/reader split**: a separate scheduler
service polls the in-house alarm API every 15 seconds and writes a Redis board;
SKEWNONO only ever reads that board. That design does keep the alarm API safe
from page traffic, but it buys the safety at a price:

- it needs a **second deployment** (`writer/` copied onto the scheduler
  service, a `JOB_FUNCTIONS` entry, `lock_ttl` and `misfire_grace_time`
  overrides, its own `LIVE_ALARM_REDIS_*` env block);
- it polls the alarm API **24 hours a day** whether or not anyone has the page
  open; and
- its office template `writer/office_example.py` assumes an interface the
  office does not have.

That last point is what forces the redesign rather than merely motivating it.
The template assumes a per-fab HTTP endpoint:

```python
ALARM_API: dict[tuple[str, str], str]      # (tool_slug, fab_name) -> URL
def fetch_alarms(tool_slug, fab_name, window_sec) -> list[dict]: ...
```

The real office code, as established by the `auto_recipe_creator` POC
(`poc/workflow_3/monitor/alarm_source.py` and
`poc/workflow_3e/meas_alarm_source.py`), exposes no such thing. It exposes
argument-free functions that return **every** CD-SEM alarm at once:

```python
get_cdsem_alarms()             # ALL alarms. No fab, no window.
filter_align_fail(alarms)      # -> ALID 9006
get_measurement_fail_alarms()  # -> ALID 9100, also argument-free
```

So the per-fab map would issue one call per fab where the office API wants one
call per facility. The interface mismatch and the deployment cost point at the
same replacement: let the **page request** trigger the fetch, and put a short
Redis cache with a lock in front of it so that many viewers collapse into one
upstream call.

## Decision

Replace the scheduled writer with a **demand-driven cached pull** inside
SKEWNONO Flask.

```text
visitor A ──┐
visitor B ──┼─► GET /api/cdsem/live-alarm?fab_name=M16A
visitor C ──┘              │
                           ▼
                fac_id cache age < 20s ?
                  ├ yes ─► serve board            (office API untouched)
                  └ no  ─► SET NX lock
                            ├ won  ─► office_utils.get_live_alarms(fac_id)
                            │          └─► accumulate into ZSET, stamp meta
                            └ lost ─► serve previous board immediately
```

Office API load is bounded at **3 calls per minute per facility being viewed**,
and drops to **zero** when nobody has the page open — regardless of how many
viewers there are or how fast they poll.

## The office seam

`office_utils/` is gitignored in this repo (`.gitignore:139:/office_utils/`); it
is an office-only library directory, and `recipe_search` already imports from it
lazily inside functions with a diagnostic on `ImportError`. `live_alarm` follows
the same pattern.

The office writes **one merged function**, so SKEWNONO has one import, one call,
and one failure mode rather than two of each:

```python
# office_utils/live_alarm.py  — written at the office
def get_live_alarms(fac_id: str) -> pd.DataFrame:
    """All alarm rows for one facility, both ALIDs (9006 align, 9100 meas)."""
    align = filter_align_fail(get_cdsem_alarms(fac_id))
    meas = get_measurement_fail_alarms(fac_id)
    return pd.concat([align, meas], ignore_index=True)
```

Returned columns are the POC's standard alarm schema, already the shape
`normalize.to_events()` reads:

| Column | Required | Meaning |
| --- | --- | --- |
| `EQP_ID` | yes | equipment id; the roster join key |
| `ALID` | yes | `9006` align fail, `9100` measurement fail |
| `UTC9` | yes | `"%Y-%m-%d %H:%M:%S"` occurrence time |
| `RECIPE_ID` | no | `"<class>/<recipe>"` |
| `ALARM_NAME` | no | human-readable label |
| `OPERATION_DESC` | no | process/step description |
| `LOT_TYPE_CD` | no | lot type code |
| `TIMESTAMP` | no | fallback for `UTC9` |

## fac_id versus fab_name

`get_live_alarms` takes **`fac_id`**, the coarse facility key — not `fab_name`,
which is what the URL carries. The two must not be confused:

| Key | Granularity | Values |
| --- | --- | --- |
| `fab_name` | granular; the `[fab]` URL segment and sidebar | `M16A`, `M16B`, `M16C`, `R3`, `R4` |
| `fac_id` | coarse facility | `M16`, `R3` (`R3`+`R4` → `R3`, `M16A/B/C` → `M16`) |

**`R3` is the single value where the two coincide**, which is exactly why
development focused on R3 cannot surface the difference. Passing a `fab_name` of
`M16A` to a function expecting `M16` returns nothing and looks like a quiet fab
— the same class of defect that hit `storage` on 2026-07-21.

Caching at fac granularity is also strictly better than caching per fab, because
the coarse key is the one the upstream call is actually parameterized by:

```text
?fab_name=M16A ─┐
?fab_name=M16B ─┼─► fac_id M16 ─► one cache entry, one upstream call
?fab_name=M16C ─┘

?fab_name=R3   ─┐
?fab_name=R4   ─┴─► fac_id R3  ─► one cache entry, one upstream call
```

No `fabNameToFacId` table is reintroduced — that helper was deliberately deleted.
`sem_list` rows carry **both** `fac_id` and `fab_name`, and the roster is already
being loaded for the `eqp_id` join, so the mapping is read from data. A fab added
to `sem_list` therefore works with no code edit.

## Redis layout

One board per facility. Keys are `fac_id`-scoped:

```text
skewnono:live_alarm:{fac_id}:events   ZSET   member = canonical JSON,
                                             score  = occurred_epoch
skewnono:live_alarm:{fac_id}:meta     JSON   {"fetched_at": <epoch>}
skewnono:live_alarm:{fac_id}:lock     string SET NX EX — stampede guard
```

The `registry` SET is **removed**. It existed to distinguish "this fab was never
configured" from "configured and quiet", but with one call per facility there is
no per-fab configuration left to drift; the `sem_list` roster answers that
question directly and more accurately (see *feed_status* below).

### The ZSET stays — this is load-bearing

The events key remains an accumulating sorted set, pruned at `WRITER_PRUNE_SEC`
(900s) and displayed at `BOARD_WINDOW_SEC` (600s). It is **not** replaced by a
plain "cache the last response" value, for one reason:

`get_live_alarms(fac_id)` takes no window argument, so how far back it reaches is
the office API's choice, not ours. If it reports only *currently active* alarms,
a last-response cache would drop each alarm the moment it cleared, and a
10-minute board could never be assembled. Accumulating successive snapshots into
a ZSET reconstructs the board from whatever the upstream happens to report.

This is safe precisely because ZSET members are canonical JSON: re-adding an
event already present is a no-op. Idempotence is what allows the refresh cadence
to be irregular and viewer-driven rather than a fixed schedule.

## The refresh core

New module `live_alarm/refresh.py`, called by the office provider before every
read.

```python
CACHE_TTL_SEC = 20   # a fetch is "fresh" for this long
LOCK_TTL_SEC = 20    # in-flight guard AND failure backoff


def ensure_fresh(client, fac_id: str, *, now: int) -> None:
    meta = _read_meta(client, fac_id)
    if meta and now - int(meta["fetched_at"]) < CACHE_TTL_SEC:
        return                                    # fresh: office API untouched

    token = secrets.token_hex(8)
    if not client.set(_lock_key(fac_id), token, nx=True, ex=LOCK_TTL_SEC):
        return                                    # another request is fetching

    try:
        rows = _fetch(fac_id)                     # office_utils; raises on failure
        _write_board(client, fac_id, to_events(rows, now=now), now)
    except Exception:
        log.exception("live_alarm refresh failed for fac_id=%s", fac_id)
        # Lock deliberately NOT released: it expires in LOCK_TTL_SEC and acts
        # as the retry backoff, so an office API already in trouble is not
        # retried by every poll of every viewer.
        return
    _release(client, _lock_key(fac_id), token)    # released only on success
```

Four properties this must preserve, each of which a test asserts:

- **No request waits on another request.** The lock is non-blocking; the loser
  serves the previous board (stale-while-revalidate). A crowd arriving together
  produces exactly one upstream call and zero queued workers.
- **The lock is also the backoff.** Releasing only on success suppresses retries
  for `LOCK_TTL_SEC` after a failure. One mechanism, no second key.
- **`fetched_at` is stamped only on success.** A fresh heartbeat over missing
  data is the one failure mode this feature exists to prevent; a failed fetch
  must leave the timestamp ageing so the screen honestly reports `stale`.
- **Release is token-compared.** `_release` deletes the lock only if its value
  is still this caller's token (Lua `CAS`), so a slow fetch whose lock already
  expired cannot delete a successor's lock.

The lone-visitor case reads well: a single viewer arriving after an idle night
**wins** the lock, fetches synchronously, and receives a fresh board on that same
request. Only a lock loser sees a stale board, and their next poll is 15s away.

## Read path

```python
def get_board(tool_type: ToolType, fab_name: str) -> LiveAlarmPayload:
    roster = _roster_index()                  # sem_list, one pass
    fac_id = roster.fac_id_for(fab_name)
    if fac_id is None:
        return _not_configured(tool_type, fab_name)

    client = redis_client()
    now = int(client.time()[0])               # Redis is the clock authority
    ensure_fresh(client, fac_id, now=now)

    raw = client.zrangebyscore(
        _events_key(fac_id),
        now - BOARD_WINDOW_SEC,
        now + FUTURE_TOLERANCE_SEC,           # not +inf: a fast upstream clock
    )                                         # would otherwise pin an event
    events = board.dedupe_by_id(board.parse_members(raw))
    mine, unmatched = _split_by_roster(events, roster, tool_type, fab_name)
    mine.sort(key=lambda e: e["occurred_epoch"], reverse=True)
    ...
```

`_split_by_roster` resolves each event's `eqp_id` through the `sem_list` roster
to `(fac_id, fab_name, eqp_model_cd)` and classifies the tool family with
`model_to_tool_type()`. This mirrors `lateral_recipe._roster()`.

**An `eqp_id` is never parsed.** `_tool_specs.py` records why: `eqp_prefixes` and
`eqp_models` are mock fodder, not classifiers, and treating them as classifiers
silently emptied the office "PPID 미접속 장비" panel for 8 tools on 2026-07-24.

### Unmatched equipment

An alarm whose `eqp_id` is absent from `sem_list` — a tool still firewalled, so
it sits in the pending-tools list — matches no fab. Those events are **dropped
from the board but counted**, so the condition is visible rather than silent:

```json
{
  "fab_name": "M16A",
  "events": [],
  "unmatched_count": 2
}
```

Dropping silently was rejected: a roster gap and a genuinely quiet fab would
render identically, which is the failure mode `_tool_specs.py` already documents.

## feed_status

`board.feed_status_for()` keeps its three states, but `known` acquires a better
definition and `polled_at` is renamed to reflect what it now measures.

| Status | Old meaning | New meaning |
| --- | --- | --- |
| `not_configured` | fab absent from the writer's `ALARM_API` map | **no tools of this `tool_type` in this `fab_name`, per `sem_list`** |
| `live` | writer heartbeat ≤ 90s old | last **successful** fetch ≤ 90s old |
| `stale` | heartbeat older than that | last successful fetch older, or never |

`STALE_AFTER_SEC` stays at 90. Under the new cadence a single viewer polling at
15s against a 20s TTL refreshes roughly every 30s, so 90s still means about three
missed refreshes; with several viewers the cache refills close to every 20s.

A cold cache whose lock was lost returns an empty board marked `stale`. That is
honest — no successful fetch has happened — and self-corrects on the next poll.

## Contract changes

`contracts.py`:

- **add** `unmatched_count: int` to `LiveAlarmPayload`
- **add** `CACHE_TTL_SEC = 20`, `LOCK_TTL_SEC = 20`
- **rename** `polled_at` → `fetched_at` in `LiveAlarmPayload` (and the frontend
  `LiveAlarmPayload` type, `applyPoll`, and `useLiveAlarmFeed`'s `polledAt`)
- **remove** `POLL_WINDOW_SEC` and `WRITER_INTERVAL_SEC` — neither exists once
  the writer is gone and the upstream takes no window
- **keep** `BOARD_WINDOW_SEC`, `WRITER_PRUNE_SEC` (renamed `PRUNE_SEC`),
  `STALE_AFTER_SEC`, `FUTURE_TOLERANCE_SEC`, `ALID_KIND`, and the assert that
  the prune horizon is not shorter than the board window
- **keep** `covered_since`, but change how it is produced. It was written by
  the writer's adaptive backfill window, which is being deleted. Under this
  design the board always covers exactly `now - BOARD_WINDOW_SEC`, so it is
  derived from the board window — which is already what `mock.py` does. Keeping
  it avoids a needless `LiveAlarmPayload` change in `utils/liveAlarm.ts`.

## Error handling

| Failure | Behavior |
| --- | --- |
| `office_utils` not importable | `RuntimeError` naming the missing module → JSON 503, per the `recipe_search` pattern |
| Office fetch raises | Cached board still served; `fetched_at` unchanged so it ages into `stale`; lock held for `LOCK_TTL_SEC` as backoff |
| Redis unreachable | `STORE_ERRORS` → `unreachable()` → JSON 503; the frontend keeps the last board on screen and only surfaces an error after 3 consecutive failures |
| Unparseable ZSET member | Dropped with a log line; `parse_members` already does this |
| Cold cache and lock lost | Empty board, `feed_status: "stale"`; corrects on the next 15s poll |
| `fab_name` unknown to `sem_list` | `feed_status: "not_configured"`, no office call attempted |

## What is deleted

| Path | Reason |
| --- | --- |
| `writer/job.py` | replaced by `refresh.py` |
| `writer/window.py` | `get_live_alarms` takes no window; nothing to compute |
| `writer/office_example.py` | per-fab URL map is the wrong interface |
| `writer/__init__.py` | package emptied |
| `tests/test_writer_job.py`, `test_writer_window.py` | subjects deleted |
| `providers/office_example.py` | rewritten around `ensure_fresh` |

Two **repo-level** tests name the writer as an office adapter and must be
updated in the same change, or the suite fails on a path that no longer exists:

| File | Reference to remove |
| --- | --- |
| `tests/test_office_adapter_scripts.py` | `".../live_alarm/writer/office.py"` in its adapter list |
| `tests/test_office_adapter_parity.py` | `NO_MOCK_SIBLING = {"ebeam/hitachi/live_alarm/writer"}` — the carve-out exists only because the writer had no mock sibling |

`writer/normalize.py` is **moved**, not deleted: `to_events()` and
`canonical_json()` are still the row→event conversion and the ZSET member form.
It becomes `live_alarm/normalize.py`, and its constants stop being duplicated
from `contracts.py` — the duplication existed only because the writer was copied
to a service that could not import `back_dev_home`.

`live_alarm` consequently drops from **two swap surfaces to one**. Its
`MIGRATION.md` is rewritten, and the multi-surface note in
`docs/back-end/provider-selection.md` no longer applies to it.

## Frontend

`useLiveAlarmFeed.ts` needs **no behavioral change**. It already polls at 15s ±
3s jitter, suspends entirely on `visibilitychange`, clears timers on unmount, and
replaces rather than accumulates board state. Two edits only:

- `polledAt` → `fetchedAt`, following the contract rename
- render `unmatched_count` when non-zero, as a quiet line beneath the board
  rather than a badge or an error

## Testing

`tests/fake_redis.py` already exists, so lock and TTL behavior is testable
without a live Redis. New or rewritten coverage:

- a second call within `CACHE_TTL_SEC` performs **zero** office calls
- concurrent callers produce exactly one fetch; the loser receives the previous
  board rather than blocking
- a failed fetch does not advance `fetched_at`, and suppresses retries until the
  lock expires
- `_release` does not delete a lock whose token has been replaced
- two successive overlapping snapshots accumulate into one deduped board
- roster join: events route to the correct `fab_name`; unmatched events are
  counted and not shown
- `M16A`/`M16B`/`M16C` share one `fac_id` cache entry and issue one upstream call
- `not_configured` when the roster holds no tools of that type in that fab
- `to_events` round-trips every column in the POC alarm schema

## Office verification items

Marked `OFFICE-VERIFY` in `mock.py` and `docs/datatables/live_alarm_board.txt`:

- **How far back `get_live_alarms(fac_id)` reaches.** If it returns ≥10 minutes
  of history the board self-heals after any outage; if it returns only active
  alarms, an outage longer than the upstream's retention leaves a permanent hole.
  The accumulate-and-prune design is robust either way, but the answer decides
  whether an outage is fully recoverable.
- **Whether HV-SEM alarms are present in the feed.** The POC function was named
  `get_cdsem_alarms`. If HV-SEM has no source, `/api/hvsem/live-alarm` should
  report `not_configured` explicitly rather than render as a quiet fab.
- **The real `fac_id` value set**, confirming `R3`/`M16` and whether any facility
  exists that `sem_list` does not cover.

## Out of scope

- Any change to the alarm UI beyond the two edits listed under *Frontend*.
- Server-Sent Events or WebSocket push. Polling at 15s with a 20s shared cache
  already bounds office API load at 3 calls/minute/facility; a push transport
  would change the browser contract without reducing that number.
- A pre-warming scheduler job. It was considered and rejected: it reintroduces
  the 24/7 polling this design removes, to save one visitor one fetch.
