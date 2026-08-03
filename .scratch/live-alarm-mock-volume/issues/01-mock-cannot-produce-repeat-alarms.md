# live_alarm mock cannot produce a repeated (eqp_id, ppid)

Type: bug
Status: needs-triage

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
