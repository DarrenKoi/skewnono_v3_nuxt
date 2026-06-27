# Anomaly Convention — Phase 2 Handoff

- **Date:** 2026-06-27
- **Prerequisite:** Phase 1 merged on `main` (through commit `68a2e73`), live-verified.
- **Spec:** `docs/superpowers/specs/2026-06-27-anomaly-convention-design.md` (read §2, §4.2, §7, §10)
- **Phase 1 journal:** `docs/superpowers/journals/2026-06-27-anomaly-convention-phase1-build.md`
- **How to start:** Phase 2 is a NEW plan. Run `superpowers:brainstorming` → `superpowers:writing-plans` → `superpowers:subagent-driven-development`. Do NOT extend the Phase 1 plan.

## The seam Phase 1 leaves you

Phase 1 shipped the **contract + two scoring methods + combine + visual layer**, all stable. Phase 2 adds **comparison bases (detectors)** only — the scoring and rendering are reused unchanged.

- A detector takes domain items, computes a **leave-one-out center** per item, and bands the distance with the active method via `scoreByRange` / `scoreByStddev`, returning `AnomalyVerdict[]`. The reference implementation is `app/utils/anomaly/peer.ts` — copy its shape for `sibling.ts` and `recentShift.ts`, then export via the `index.ts` barrel.
- `combineVerdicts` already does **worst-of severity + insufficient-preserved + multi-reason** aggregation, so a point carrying peer + sibling + shift verdicts becomes **one `SkAnomalyBadge` with N reason lines for free** — no new combine logic needed.
- **Live host is the Workspace path**, not `AnalyzePanel` (deleted in Phase 1). Attach new verdicts in `app/composables/useSkewvoirAnalysis.ts` and render through the existing badges/chart in `app/components/ebeam/skewvoir/views/*`. Shared scoring config is `useState('skewvoir-anomaly-cfg')`.

## Phase 2 scope (from spec §2 / §4.2 / §10)

| Item | What | Gate / prereq |
|---|---|---|
| `siblingDivergence(items, {groupKey, contrast, value, minGroup})` | Group by a control facet (`recipe·param·device`), score each member LOO vs the group's rest; reason names the deviating `contrast` (e.g. `eqp_id`). | **Measure group-size distribution on mock first** to set `minGroup`/`groupKey`. |
| `recentShift(series, {window, minN})` (was "drift") | **Step-change** detection on the focus param's time-ordered series vs the prior baseline mean. NOT slope/trend. Show the window boundary in the tooltip. | Introduce only **after** peer calibration is validated. `minN` default 8. |
| Calibration gate (Codex #6) | Before trusting defaults: measure expected **flag-rate** of 10/20% + 2/3σ on a known-good mock fixture; threshold-sweep screenshots; if over-alarming, consider per-metric presets. | Blocks Phase 2 entry. Recall the D22 `k=2` over-flag lesson. |
| Retrofit `device-statistics` (`outlierDetect.ts`) + `FdcAnalysis` (±2σ / ±3.5σ) | Adopt the convention on those surfaces. | Separate sub-plans. FDC's ±3.5σ → absorb as `abnormalK` config (decide 3 vs 3.5). |

## Decisions already locked — do not relitigate

- Leave-one-out centering is **mandatory** (masking fixtures in `peer.test.ts` prove it).
- **Range** is authoritative + default; **stddev** is the diagnostic lens.
- `status` (`evaluated`/`insufficient`) and `severity` are **separate axes**; `insufficient` must stay visually distinct from silent-normal.
- Effective N is **re-checked after dropping non-finite** values (drops below `minN` → all insufficient).
- Korean vocabulary only (평균/표준편차/범위/% 초과/σ); `z-score`/`modified z-score`/`MAD` are forbidden.
- Components under `app/components/sk/` are thin/render-only (no unit tests; verified by typecheck/lint + Playwright).

## Open questions for the brainstorm

- `siblingDivergence`: exact `groupKey` facets, `contrast` field, and `minGroup` (measure the real distribution before guessing).
- `recentShift`: window size, `minN`, and how to surface the baseline/window boundary in the tooltip.
- FDC retrofit: keep `abnormalK = 3` or set `3.5` to match the legacy band?
- Per-metric threshold presets: build in Phase 2, or defer until real flag-rate data exists?

## Concrete first steps

1. Write a one-off eval over the mock `MsrFile` data to get the `recipe·param·device` group-size distribution → informs `minGroup`/`groupKey`.
2. Run the calibration gate: flag-rate at defaults + a threshold sweep; capture screenshots.
3. `brainstorm` the sibling + recentShift detectors → write the Phase 2 plan → execute.

**Anticipated files:** `app/utils/anomaly/{sibling,recentShift}.ts` (+ `*.test.ts`), `index.ts` barrel, `useSkewvoirAnalysis.ts` (attach sibling/shift verdicts), `views/*` (badges where items render). Backend: none — all computed from data the views already load.
