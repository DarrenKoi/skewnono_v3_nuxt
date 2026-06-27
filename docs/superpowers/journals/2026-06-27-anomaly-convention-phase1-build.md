# Anomaly Convention (Phase 1) — Build Journal

- **Date:** 2026-06-27
- **Status:** Implemented, per-task + whole-branch reviewed, all fixes applied, **Playwright E2E-verified on the live UI**. **On `main`, commits `44a5e77..3473f8b`. NOT pushed.**
- **Spec:** `docs/superpowers/specs/2026-06-27-anomaly-convention-design.md`
- **Plan:** `docs/superpowers/plans/2026-06-27-anomaly-convention-phase1.md`
- **Tests:** 115 `node --test` cases pass · `nuxt typecheck` clean · `eslint` clean

## What was built (one paragraph)

A shared, app-wide abnormality-detection convention replacing three scattered notions (`outlierDetect.ts`, `madOutliers.ts`, FdcAnalysis σ-bands). Two orthogonal axes: a **comparison base** (Phase 1 ships `peer` — a leave-one-out center) and a user-selectable **scoring method** (`범위` ±% authoritative default 10/20, `표준편차` ±kσ diagnostic 2/3). Output is a graded, explained `AnomalyVerdict` with a separate `status` (`evaluated|insufficient`) axis. Pure framework-free utils under `app/utils/anomaly/` (`types`/`score`/`peer`/`combine`), render-only `SkAnomalyBadge`/`SkAnomalyLegend`, a `--sk-warn` amber token, and a method toggle + threshold controls. All user copy is Korean (평균/표준편차/범위/% 초과/σ); z-score/MAD are forbidden.

## The re-target (the thing to remember)

The plan piloted **`AnalyzePanel.vue`**, but during implementation it turned out to be **orphaned** — only `SkewvoirView.vue` rendered it, and no route mounts `SkewvoirView`. The live skewvoir analysis UI is the multi-view Workspace shell:

```text
pages/ebeam/{cd,hv}-sem/skewvoir/analysis.vue
  → Workspace.vue  (calls useSkewvoirAnalysis)
    → views/TimeSeries.vue
      → TimeSeriesChart.vue   (fed by analysis.trendPoints)
```

Per the user's decision, the convention was **re-targeted onto this live path** and the orphaned `AnalyzePanel.vue` + `SkewvoirView.vue` were **deleted**. Verdict computation now lives in the `useSkewvoirAnalysis` composable's `trendPoints` (peer verdicts on mean + spread `산포`, combined), reading a shared `useState('skewvoir-anomaly-cfg')`; the method/threshold controls, legend, summary, and focus badge live in `views/TimeSeries.vue`. The old `madOutliers.*` boolean recolor is gone.

**Gotcha banked:** binding a control to a `useState` ref that arrives *through a prop* trips `vue/no-mutating-props`. Aliasing it to a local `const` (`const anomalyCfg = props.analysis.anomalyCfg`) fixes the lint — but then the alias is auto-unwrapped in the template, so it must be used **without** `.value` (`anomalyCfg.method`, not `anomalyCfg.value.method`). The `.value` form compiles to `_unref(anomalyCfg).value` → `undefined` → render crash that typecheck/lint/unit cannot catch. A prop member that holds a ref (`analysis.trendPoints.value`) still needs `.value`; the local alias does not.

## File map

| Area | Files |
|---|---|
| Pure utils | `app/utils/anomaly/{types,score,peer,combine,index}.ts` + `*.test.ts` |
| Visual | `app/components/sk/{AnomalyBadge,AnomalyLegend}.vue`; `--sk-warn*` in `app/assets/css/main.css` |
| Live wiring | `app/composables/useSkewvoirAnalysis.ts`; `app/components/ebeam/skewvoir/views/TimeSeries.vue`; `.../skewvoir/TimeSeriesChart.vue` |
| Deleted | `app/utils/madOutliers.{ts,test.ts}`; `app/components/ebeam/SkewvoirView.vue`; `.../skewvoir/AnalyzePanel.vue` |
| Infra | `nuxt.config.ts` (`allowImportingTsExtensions` for the `.ts`-extension imports) |

## What remains / known items

- **Task 9 (Playwright E2E): done.** Verified on the live `Workspace → Time-Series` view: controls render with no crash (0 console errors), range legend ±10/±20 with watch+abnormal points, live threshold recompute (35/70 → all normal), method toggle to ±2σ/±3σ, `insufficient`(미평가) distinct (1 MSR, and stddev on 3 pts < minN 5 → grey), focus badge reflects verdict. Screenshots: `.playwright-mcp/screenshots/anomaly-pilot-{range,stddev}.png`.
- **Accepted minors (not bugs):** `SEV_HEX` canvas hexes are static (don't track dark-mode tokens — ECharts tradeoff); `--sk-warn-soft/-border` defined for token-family symmetry but currently unused; `trendSummary` reports watch/abnormal but not an insufficient count.
- **Phase 2 (separate plan):** `siblingDivergence`, `recentShift`, the flag-rate calibration gate, and retrofitting `device-statistics` + `FdcAnalysis`.
