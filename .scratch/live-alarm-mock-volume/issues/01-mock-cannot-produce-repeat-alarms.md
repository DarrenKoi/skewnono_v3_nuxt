# live_alarm mock cannot produce a repeated (eqp_id, ppid)

Type: bug
Status: done

Fixed 2026-08-03 — see "How it was fixed" at the bottom.

## Background

The 라이브 알람 board gained a 측정 실패 grouping mode on 2026-08-03
(`docs/superpowers/specs/2026-08-03-live-alarm-grouped-triage-design.md`).
It groups measurement failures by `(eqp_id, ppid)` and sorts by 건수, so a PPID
failing repeatedly on one tool reads as one loud row instead of scattering
across a chronological list.

The mock cannot produce that situation.

`back_dev_home/ebeam/hitachi/live_alarm/providers/mock.py` emits

```python
count = (now // 60) % 4
```

— **0 to 3 events per board**, spread across several tools and recipes. Two
alarms sharing an `(eqp_id, ppid)` pair essentially never occur.

## Why this is a correctness problem, not a convenience one

Two separate consequences:

1. **The feature is invisible at home.** A developer opening the page against
   the stock mock sees a flat list of singleton rows and no group headers at
   all. Every behaviour the grouping adds — the count ranking, the
   collapse/expand, the `(PPID 없음)` bucket, the header highlight lifted from
   the row — is unreachable. Verifying the feature required a temporary local
   patch to this file, which was reverted (see
   `.superpowers/sdd/2026-08-03-live-alarm-grouped-triage/task-5-report.md`).

2. **The mock is asserting something false.** Per `CLAUDE.md`, mock data is the
   only carrier of what we know about the office DB. A board that can never
   contain two alarms sharing `(eqp_id, ppid)` is a mock claiming repeats do
   not happen — and repeats are the entire premise the grouping feature was
   built on. This is the mock's value domain being narrower than the real
   thing, which is the failure mode `CLAUDE.md` warns about.

The final whole-branch reviewer rated this the stronger of the two: "raising
the count is a correctness fix to the mock's value domain, not a cosmetic
bump."

## Shape of the fix

Task 5 proved the mechanism works. It made `count` env-overridable:

```python
count = int(os.environ.get('SKEWNONO_LIVE_ALARM_MOCK_COUNT') or ((now // 60) % 4))
```

That was a verification scaffold, not the proposed fix. The real change should
make the DEFAULT board carry repeats, so the feature is visible without anyone
setting an env var. Observed shapes while testing:

| count | meas events | groups | singletons | max 건수 |
| --- | --- | --- | --- | --- |
| 3 (current max) | ~2 | ~2 | all | 1 |
| 23 | 15 | 8 | 1 | 2 |
| 30 | 20 | 8 | 0 | 3 |

A default in the low-to-mid twenties gives a board with a mix of multi-event
groups, at least one singleton, and a `(PPID 없음)` bucket — i.e. every path the
screen has.

## Constraints to respect

- Keep the minute-derived determinism: the same minute must rebuild the same
  board, or the existing tests go flaky.
- `back_dev_home/ebeam/hitachi/live_alarm/tests/` has 91 tests over this
  feature; several assert on board contents.
- Per `CLAUDE.md`, a change to what the mock stands for belongs in the
  docstring too, and any new office fact belongs in
  `docs/datatables/live_alarm_board.txt` as well.
- **Do not invent office values.** Whether the office feed actually shows one
  PPID failing many times in ten minutes is `OFFICE-VERIFY`. The mock should
  be able to REPRESENT repeats because the screen is built for them; it should
  not claim a specific real-world rate.

## Why it was not fixed in the originating branch

The 2026-08-03 grouping work was scoped frontend-only, and its plan's Global
Constraints forbade touching `back_dev_home/`. Reaching across would have
turned a frontend branch into a backend one mid-review. Recorded here instead.

## How it was fixed

Three changes in
`back_dev_home/ebeam/hitachi/live_alarm/providers/mock.py`:

1. **Volume cycle.** `count = (now // 60) % 4` became
   `_COUNTS = (0, 11, 19, 27)` indexed by the minute. The `0` keeps the quiet
   board reachable — raising the volume must not cost the
   "최근 10분간 알람이 없습니다." screen.
2. **A deliberate repeat burst.** `_HOT_BURST = 6` events pinned to one
   `eqp_id` and one recipe, alternating 9007/9035 so they land in one `meas`
   group and prove the view groups by kind rather than by alid. Placed
   explicitly rather than left to index cycling, which produced a pile of 3 at
   best, only by coincidence, and would move whenever the roster size did.
   Marked in the code as a FABRICATED CORRELATION: the shape is what the
   screen was built for, the rate is `OFFICE-VERIFY`.
3. **Wider id spacing.** `(now // 60 % 1000) * 10` became `* 100`. At `*10` the
   per-minute id blocks overlapped once boards exceeded 10 events — minute
   N's index 12 collided with minute N+1's index 2. The frontend decides "new
   since the last poll" by id and polls straddle minute boundaries constantly,
   so that collision would have made a genuinely new alarm fail to highlight,
   looking like a bug in the highlight code.

Resulting boards per fab, across one turn of the cycle:

| slot | total | meas | groups | group counts | unmatched |
| --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | — | 0 |
| 1 | 17 | 13 | 8 | 6,1,1,1,1,1,1,1 | 0 |
| 2 | 25 | 18 | 9 | 6,2,2,2,2,1,1,1,1 | 0 |
| 3 | 33 | 24 | 9 | 6,3,3,2,2,2,2,2,2 | 1 |

## One thing the fix nearly broke

`unmatched_count` — the roster-gap screen — was keyed on `count == 3`. The new
cycle never produces a 3, so that path became unreachable the moment the volume
changed, **and not one existing test would have failed.** It is now keyed on the
cycle slot, and `test_the_roster_gap_path_stays_reachable` pins it.

This is the same class of defect as the original bug: a capability lost with no
assertion watching. `tests/test_mock.py` (8 tests) now guards the mock's value
domain — volume, the repeat, its prominence, the quiet board, id uniqueness
within and across minutes, the blank ppid, and the roster gap.
