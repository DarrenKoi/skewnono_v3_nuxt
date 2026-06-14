# Device-Statistics D22 — Implementation Plans (index)

Decision record: `docs/issues/ground_rules/grilling-log.md` **D22** (supersedes D15/D14/D16).
Design summary: device-statistics is a **descriptive** view for all fabs (within-device point-count outliers); **measurement-rules** is the **prescriptive** R3-only page (cap matrix + compliance). R3 appears in both; M-fab only in device-statistics. M-fab has no rule.

## Execute in order

1. **[Plan 1 — Data + Logic Foundation](2026-06-13-device-statistics-d22-plan1-data-foundation.md)**
   `recipe-params` mock endpoint + composable + `detectDeviceOutliers` util. No UI. Prerequisite for 2 & 3.
2. **[Plan 2 — Descriptive View (all fabs)](2026-06-13-device-statistics-d22-plan2-descriptive-view.md)**
   Shared `DrillDevice` view-model + `DrillSlideover` + `profile.vue` outlier table (selected device set).
3. **[Plan 3 — R3 Rule Page (prescriptive)](2026-06-13-device-statistics-d22-plan3-r3-rule-page.md)**
   `toViolationDrill` adapter + R3 compliance table on `measurement-rules`; remove M-fab caps from `rules.py`.

## ⚠️ Confirm before coding (each plan's "Key decisions" section)

- **Scope = selected device cart**, not the full 2000-row table (Plans 2 & 3). Phase 2/3 alt: a summary endpoint.
- **Placement:** descriptive view = new `device-statistics/profile.vue` reached from the cart; compliance = a section on `measurement-rules`.
- **Device-row units:** outlier = count of outlier *parameters*; compliance = count of violated *recipes* (count, not ratio — D22).
- **Multiplier `k` = 2** (median×k) default; **no health color** on the compliance row yet.

## Pre-flight (each task is TDD where logic exists)

- Frontend tests: `cd front-dev-home && npm run test` (`node --test "app/**/*.test.ts"`). Typecheck: `npm run typecheck`. Lint: `npm run lint`.
- Backend: no pytest — verify via module `__main__` preview / `python -c` / `curl` (Flask :5050).
- Use **superpowers:subagent-driven-development** or **superpowers:executing-plans** to run a plan.
