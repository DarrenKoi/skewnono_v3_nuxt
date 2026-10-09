# Review brief 4 — the /simplify pass over the 2026-10-09 skewvoir + AFM batch

You are the reviewer. Read-only: do not edit source, stage, commit, or run git
commands that change state. Do not start servers or a browser. Write your
findings to `.scratch/skewvoir-afm-batch-261009/codex-review-4.md` (that one
file is the only thing you create) and stop.

You are in a git worktree (`work/simplify-1009`). `CLAUDE.md` carries the
project rules. Your three earlier reviews of this batch are beside this file
(`codex-review.md`, `-2.md`, `-3.md`) — do not repeat what they settled.

To run the frontend tests: `cd frontend && PATH="$HOME/.nvm/versions/node/v24.13.0/bin:$PATH" npm test`
(2176 pass at HEAD; `npm run typecheck` and `npm run lint` are clean).

## Part A — are the two refactor commits behaviour-preserving?

`git diff 806c41c9..HEAD` (two commits, 19 files, +97 −96). Both claim **no
visible change**. Find any input where that is false. Give the input.

`57a9ca88 refactor(afm)`

- `blockRows` moved from `afmSiteGrid.ts` to `afmPoints.ts`; `prepareEntries`
  now calls it. Same grouping for every payload (empty Summary, rows with no
  `Site`)?
- `RecipeCentre.n = values.length` replaces the 조사 묶음's own count
  (`rows.filter(recipe === … && value !== null && (!pinned || role === 'baseline'))`).
  Equal in every case — pinned, unpinned, mixed recipes, a recipe with no values?
- `bundleSuspects(rows, health = healthSeries(rows.map(r => r.entry)))`: the
  page passes its `health` computed, which is `healthSeries(entries)`. Is
  `rows[i].entry === entries[i]` always, so the index pairing holds?
- `see-together.vue` `relationEntries` now filters `entries` by `pointRecipe`
  instead of mapping `pointRows`. Same entries, same order, in mixed and
  single-recipe groups?
- `naturalOrder.compare` vs the inline `localeCompare(…, { numeric, sensitivity: 'base' })`.

`85bc3dea refactor(skewvoir)`

- `useSkewvoirRoute.ts`: `anomalyCfg` parses `qstr(route.query.anom)` through
  an intermediate computed; `baseline` is `computed(old => …)` returning `old`
  when `old.join() === next.join()`. Can either go stale — return an old value
  when the URL really changed? (`AnomalyThresholds.vue` watches
  `props.modelValue`; it now fires only on a real change. Does anything rely
  on it firing on every URL patch?)
- `comparedMembers` computed; `PositionStack.vue` reads it instead of
  `manifest.included.filter(id => setFiles.has(id))`. `setComparedMembers`
  returns `included` unfiltered in single scope — PositionStack's set branch is
  `v-else` of `scope === 'single'`; confirm no single-scope path reads
  `includedIds` / `waferCount` / `sites`.
- `thresholdPair` (routeQuery.ts) in `encodeAnomalyCfg`, `receipt.ts`
  settings, and `AnomalyThresholds.vue` (three call shapes, one with an
  explicit other method).
- Receipt `generatedAt`: hand-rolled pad string → `formatDateTimeLocal(d.toISOString())`.
  Identical text for every Date, including local midnight and month ends?
  (`receiptFilename` slices its first 10 chars.)
- `paramTableStats` via `paramValues`; `ParamSummary.vue` rows are
  `{ ...summary, ...paramTableStats }` — the spread overwrites the server
  summary's `count/mean/std/min/max` with possibly-null values; `fmt` takes
  null. Any consumer of `rows` that needed the server numbers?
- `SpatialLayerMap.vue` optional `hint`/`why`; `WaferHeatChart.vue`
  `scaleLabel` computed (declared above `option` — setup-order matters here).

## Part B — behaviour questions the cleanup surfaced and I did NOT change

For each: is it a real defect (give the failing input), and what is the
smallest correct fix? Say "not a defect" plainly when it is not.

1. `useSkewvoirAnalysis.ts` `baselineGroups` narrows to `manifest.included`
   only, not to loaded files, while `comparedMembers` also requires the file.
   Claim: a focus dropped by the 30-member cap can sit in `target` with no
   file; `baselineCompare.ts` counts it in `requested` and `BaselineBlock.vue`
   then says "이 파라미터의 측정값이 없어 빠졌습니다", which is not why.
2. AFM colour scales do not use `utils/scaleLabel.ts`:
   `components/afm/detail/SiteGrid.vue` prints both ends with `fmt2`
   (a 0.004-wide range prints the same text twice), and
   `components/afm/detail/HeatmapChart.vue`'s `calculable` visualMap has no
   formatter (ECharts' integer default → "-0 … 0").
3. Symmetric colour range floor: `WaferHeatChart.vue` uses
   `Math.max(...abs) || 0.5`, `SpatialLayerMap.vue` uses `Math.max(0.5, …)`.
   A ±0.3 residual is ±0.3 on one map and ±0.5 on the other. Which is intended?
4. AFM repeat lap × invalid row: `afmTrend.ts` `pointValues(validOnly)`
   filters `isValidRow` then takes the last (last VALID lap);
   `afmSiteGrid.ts` `siteGrid` takes the last row then applies `isValidRow`
   (no value if the last lap FAILED). Same point, two readings across pages?
5. `afmBundle.ts` `round` vs `receipt.ts` `num`: `num` blanks non-finite and
   fixes −0, `round` does neither. Can a NaN or −0 reach an AFM sheet?
6. `AnomalyThresholds.vue` emits on every valid keystroke (typing `12.5`
   writes the URL 3–4 times and re-judges the set each time). And
   `ProfileOverlay.vue`'s module-level `profileCache` is never evicted
   (full-resolution lines, ~1 MB each by estimate). Worth changing, or fine at
   this app's sizes (≤ 20 measurements per group, FHD desktops)?

## Format

Per finding: severity (blocker / should / nit), `file:line`, the failing input
or state, the smallest fix. Part A first, then Part B numbered as above. End
with a one-line verdict on whether the two commits are safe to merge as they
stand.
