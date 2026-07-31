# Skewvoir Multi-MSR Time-Series Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the skewvoir Time-Series view — reached by multi-selecting MSRs on the search page — into a real analysis page with three button-switched lenses (trend / distribution / tool skew), a true time axis, and a set-aware parameter selector.

**Architecture:** Every new calculation is a pure function in `app/utils/skewvoirAnalysis/`, unit-tested under raw `node --test`; the composable layer only wires those functions to reactive state, and the `.vue` files only render. The three lenses share one chart slot switched by a URL-carried `tsview` key, so an analysis screen stays reproducible from its link. No backend change: all data already sits in `setRows` and `setFiles`.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), NuxtUI, ECharts 6 via `useEchart`, `useState` composables (no Pinia), `node --test` with TypeScript type-stripping.

**Spec:** `docs/superpowers/specs/2026-08-01-skewvoir-time-series-multi-msr-design.md`

## Global Constraints

- All frontend commands run **from `front-dev-home/`**: `npm test`, `npm run typecheck`, `npm run lint`. Markdown lint runs from the repo root: `npm run lint:md`.
- `npm test` is `node --test "app/**/*.test.ts"`. To run one file: `node --test app/utils/skewvoirAnalysis/timeSeries.test.ts`.
- **Frontend baseline before this plan starts: 971 passed, 0 failed.** Never finish a task with fewer passing.
- `npm test` covers **pure functions only**. There is no component mounting harness and no E2E suite. Anything inside a `.vue` file is verified by hand via the `verify` skill, never by a unit test. Do not invent a component test.
- **Pure utils under `app/utils/` must run under raw `node --test`.** That means: value imports use a relative path **with an explicit `.ts` extension** (`import { quantileSorted } from '../stats.ts'`); only **type-only** imports may use the `~` alias (they are erased at runtime). A value import via `~` will fail at test time.
- Colors come from `--sk-*` CSS tokens or `app/utils/chartPalette.ts`. Never inline a hex value in a component. `DESIGN.md` is the source of truth for visual language.
- Korean UI copy uses formal endings. The baseline label is **`세트 기준`** — the word `consensus` must not appear in UI copy, comments, or identifiers.
- No Pinia. Shared client state is a `useState`-backed composable; anything surviving reload goes through `composables/usePersistedState.ts`.
- Commit only files you personally edited, with explicit pathspecs (`git commit -m "..." -- path/a path/b`). `git add -A`, `git add .`, and `git commit -a` are banned — other agent sessions share this working tree.
- This plan touches more than one file, so **work in a git worktree** (`git worktree add ../skewnono-timeseries -b work/timeseries`), then fast-forward merge to `main` and remove the worktree when done.

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `app/utils/skewvoirAnalysis/types.ts` | modify | Add `TsView`, `TsAxisMode`, `TsBaseline` union types |
| `app/utils/skewvoirAnalysis/routeQuery.ts` | modify | Parse/normalize the three new URL keys; dedupe `msrs` |
| `app/utils/skewvoirAnalysis/activeParam.ts` | create | Pure rule for which parameter is active (focus vs set pool) |
| `app/utils/skewvoirAnalysis/timeSeries.ts` | create | `TrendPoint`, trend/distribution/skew/coverage/integrity derivations |
| `app/composables/useSkewvoirRoute.ts` | modify | Expose the new URL keys and their setters |
| `app/composables/useSkewvoirAnalysis.ts` | modify | Wire the derivations; apply the set-scope parameter rule |
| `app/components/ebeam/skewvoir/TimeSeriesChart.vue` | modify | Time/order axis, per-tool series, residual band, `select` emit |
| `app/components/ebeam/skewvoir/DistributionChart.vue` | modify | Opt-in axis rotation + `dataZoom` props (defaults keep today's look) |
| `app/components/ebeam/skewvoir/timeseries/ParamCoverageSelect.vue` | create | Set-aware parameter selector with coverage |
| `app/components/ebeam/skewvoir/timeseries/ToolSkewPanel.vue` | create | Per-tool offset interval plot + numeric table |
| `app/components/ebeam/skewvoir/Workspace.vue` | modify | Pass `ws` to the Time-Series view (the new URL keys live on the workspace) |
| `app/components/ebeam/skewvoir/views/TimeSeries.vue` | rewrite | Lens buttons, integrity banner, chart slot, Sequence Trend |
| `app/composables/useEchart.ts` | modify | Add an `onDataIndex` click callback (existing callbacks untouched) |

Tasks 1–5 are pure and fully unit-tested. Task 6 is the wiring seam. Tasks 7–10 are rendering, verified in the browser.

---

### Task 1: URL contract for the three new keys

**Files:**

- Modify: `app/utils/skewvoirAnalysis/types.ts`
- Modify: `app/utils/skewvoirAnalysis/routeQuery.ts`
- Test: `app/utils/skewvoirAnalysis/routeQuery.test.ts`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `TsView`, `TsAxisMode`, `TsBaseline` types; `parseTsView(raw: unknown): TsView`, `parseTsAxis(raw: unknown): TsAxisMode`, `parseTsBaseline(raw: unknown): TsBaseline`; `parseMsrList` now deduplicates.

- [ ] **Step 1: Write the failing tests**

Append to `app/utils/skewvoirAnalysis/routeQuery.test.ts`:

```ts
import {
  parseTsView,
  parseTsAxis,
  parseTsBaseline
} from './routeQuery.ts'

test('parseTsView defaults to trend and corrects an unknown value', () => {
  assert.equal(parseTsView(undefined), 'trend')
  assert.equal(parseTsView('dist'), 'dist')
  assert.equal(parseTsView('skew'), 'skew')
  assert.equal(parseTsView('nonsense'), 'trend')
  assert.equal(parseTsView(''), 'trend')
  // An array query value collapses to its first element (qstr behaviour).
  assert.equal(parseTsView(['skew', 'dist']), 'skew')
})

test('parseTsAxis defaults to time; parseTsBaseline defaults to raw', () => {
  assert.equal(parseTsAxis(undefined), 'time')
  assert.equal(parseTsAxis('order'), 'order')
  assert.equal(parseTsAxis('bogus'), 'time')
  assert.equal(parseTsBaseline(undefined), 'raw')
  assert.equal(parseTsBaseline('resid'), 'resid')
  assert.equal(parseTsBaseline('bogus'), 'raw')
})

test('parseMsrList removes duplicate msr ids, keeping first occurrence order', () => {
  assert.deepEqual(
    parseMsrList({ msrs: 'a,b,a,c,b' }),
    ['a', 'b', 'c']
  )
})
```

If `parseMsrList` is not already imported at the top of the test file, add it to the existing import list from `'./routeQuery.ts'`.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `front-dev-home/`:

```bash
node --test app/utils/skewvoirAnalysis/routeQuery.test.ts
```

Expected: FAIL — `parseTsView is not a function` (and the dedupe assertion fails).

- [ ] **Step 3: Add the union types**

In `app/utils/skewvoirAnalysis/types.ts`, alongside the existing `AnalysisScope` / `SequenceAxisMode` declarations:

```ts
/** Time-Series lens: which of the three readings occupies the chart slot. */
export type TsView = 'trend' | 'dist' | 'skew'

/** Time-Series x-axis scaling. `time` is honest about cadence; `order` is the
 *  escape hatch when measurements bunch into an unreadable smear. */
export type TsAxisMode = 'time' | 'order'

/** Time-Series value baseline: plotted as measured, or as a delta from the
 *  set's median (`세트 기준`). */
export type TsBaseline = 'raw' | 'resid'
```

- [ ] **Step 4: Add the parsers and dedupe**

In `app/utils/skewvoirAnalysis/routeQuery.ts`, extend the type import from `./types.ts` to include `TsView`, `TsAxisMode`, `TsBaseline`, then add:

```ts
export const DEFAULT_TS_VIEW: TsView = 'trend'

const TS_VIEWS: readonly TsView[] = ['trend', 'dist', 'skew']
const TS_AXES: readonly TsAxisMode[] = ['time', 'order']
const TS_BASELINES: readonly TsBaseline[] = ['raw', 'resid']

/** Lens for the Time-Series view. An unknown value corrects to `trend` rather
 *  than rendering nothing, matching parseView's treatment of a hand-edited link. */
export const parseTsView = (raw: unknown): TsView => {
  const v = qstr(raw)
  return v && (TS_VIEWS as readonly string[]).includes(v) ? v as TsView : DEFAULT_TS_VIEW
}

export const parseTsAxis = (raw: unknown): TsAxisMode => {
  const v = qstr(raw)
  return v && (TS_AXES as readonly string[]).includes(v) ? v as TsAxisMode : 'time'
}

export const parseTsBaseline = (raw: unknown): TsBaseline => {
  const v = qstr(raw)
  return v && (TS_BASELINES as readonly string[]).includes(v) ? v as TsBaseline : 'raw'
}
```

Then make `parseMsrList` deduplicate. Find the existing function and wrap its result in a `Set` pass, preserving first-occurrence order:

```ts
// A duplicated msr would be counted twice by every aggregation (mean, n,
// coverage) and would also consume one of the TREND_LIMIT slots, so ids are
// unique from the moment they leave the URL.
  return [...new Set(parts)]
```

where `parts` is the existing filtered array the function currently returns. Keep the existing empty-value filtering ahead of the dedupe.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
node --test app/utils/skewvoirAnalysis/routeQuery.test.ts
```

Expected: PASS.

- [ ] **Step 6: Run the full suite and typecheck**

```bash
npm test
npm run typecheck
```

Expected: 971 + your new tests passing, 0 failures; typecheck clean.

- [ ] **Step 7: Commit**

```bash
git add app/utils/skewvoirAnalysis/types.ts app/utils/skewvoirAnalysis/routeQuery.ts app/utils/skewvoirAnalysis/routeQuery.test.ts
git commit -m "feat(skewvoir): parse tsview/tsx/tsb and dedupe the msrs list"
```

---

### Task 2: Set-aware active-parameter rule

The current rule validates the URL `mp` against the **focus file only**, and a watcher rewrites an unsupported `mp` back. That silently reverts any set-wide parameter the focus MSR happens to lack. This task extracts the rule as a pure function and widens the pool under `set` scope.

**Files:**

- Create: `app/utils/skewvoirAnalysis/activeParam.ts`
- Test: `app/utils/skewvoirAnalysis/activeParam.test.ts`

**Interfaces:**

- Consumes: `AnalysisScope` from `./types.ts`; `isNamedParam` from `./paramOrder.ts`.
- Produces: `resolveActiveParam(input: ActiveParamInput): string` and `activeParamPool(input: ActiveParamInput): string[]`.

- [ ] **Step 1: Write the failing test**

Create `app/utils/skewvoirAnalysis/activeParam.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolveActiveParam, activeParamPool } from './activeParam.ts'

test('single scope honours a URL mp the focus file has', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'GATE_CD', focusParams: ['WAFER', 'GATE_CD'], setParams: []
  }), 'GATE_CD')
})

test('single scope falls back to the first NAMED param when the focus lacks the URL mp', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'GATE_CD', focusParams: ['', 'WAFER'], setParams: []
  }), 'WAFER')
})

test('set scope accepts a param the focus lacks but another set member has', () => {
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), 'GATE_CD')
})

test('set scope with EMPTY setParams falls back to focus rules — the set files are not loaded yet', () => {
  // shouldLoadSet() excludes the dashboard view, so scope=set + view=dashboard
  // leaves setFiles empty. Judging against an empty pool would reject every
  // parameter and corrupt the URL.
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: []
  }), 'WAFER')
})

test('an explicit pick of the unnamed settling MP is honoured, but never defaulted to', () => {
  // The unnamed MP's name IS the empty string, so `urlMp != null` (not truthy).
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: '', focusParams: ['', 'WAFER'], setParams: ['', 'WAFER']
  }), '')
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: undefined, focusParams: ['', 'WAFER'], setParams: ['', 'WAFER']
  }), 'WAFER')
})

test('a file whose only parameter is the unnamed MP falls back to it', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: undefined, focusParams: [''], setParams: []
  }), '')
})

test('no parameters at all yields the URL mp, else the empty string', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'WAFER', focusParams: [], setParams: []
  }), 'WAFER')
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: undefined, focusParams: [], setParams: []
  }), '')
})

test('activeParamPool widens to the set only under set scope with a loaded set', () => {
  assert.deepEqual(activeParamPool({
    scope: 'set', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), ['WAFER', 'GATE_CD'])
  assert.deepEqual(activeParamPool({
    scope: 'single', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), ['WAFER'])
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
node --test app/utils/skewvoirAnalysis/activeParam.test.ts
```

Expected: FAIL — cannot find module `./activeParam.ts`.

- [ ] **Step 3: Write the implementation**

Create `app/utils/skewvoirAnalysis/activeParam.ts`:

```ts
// Which parameter the analysis screen is showing.
//
// The URL `mp` is the user's stated pick, but a pick is only meaningful if some
// loaded measurement actually carries that parameter. Which measurements get a
// vote is the whole question:
//
//   • single scope — the focus file alone. Historic behaviour, unchanged.
//   • set scope    — ANY measurement in the curated set. A set spans recipes,
//                    so a parameter 22 of 30 measurements share is a legitimate
//                    pick even when the focus measurement is one of the 8.
//
// The set pool applies only once the set files are loaded. shouldLoadSet()
// excludes the dashboard view, so a scope=set + view=dashboard screen holds an
// EMPTY setFiles; judging against that empty pool would reject every parameter
// and let the caller's write-back watcher corrupt the URL.
//
// Pure and framework-free so it runs under raw `node --test`.
import type { AnalysisScope } from './types.ts'
import { isNamedParam } from './paramOrder.ts'

export interface ActiveParamInput {
  scope: AnalysisScope
  /** The URL `mp`. `undefined` when absent; `''` is the unnamed settling MP. */
  urlMp: string | undefined
  /** Parameters of the focus measurement's file. */
  focusParams: string[]
  /** Parameters across the curated set. Empty when the set is not loaded. */
  setParams: string[]
}

/** Which parameters get a vote on whether the URL `mp` is valid. */
export const activeParamPool = (input: ActiveParamInput): string[] =>
  input.scope === 'set' && input.setParams.length > 0
    ? input.setParams
    : input.focusParams

export const resolveActiveParam = (input: ActiveParamInput): string => {
  const pool = activeParamPool(input)
  // `!= null` rather than a truthy test: the unnamed MP's name is '', and a
  // truthy check would reject that explicit pick and bounce elsewhere.
  if (input.urlMp != null && pool.includes(input.urlMp)) return input.urlMp
  const named = pool.filter(isNamedParam)
  return named[0] ?? pool[0] ?? input.urlMp ?? ''
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
node --test app/utils/skewvoirAnalysis/activeParam.test.ts
```

Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add app/utils/skewvoirAnalysis/activeParam.ts app/utils/skewvoirAnalysis/activeParam.test.ts
git commit -m "feat(skewvoir): widen the active-parameter pool under set scope"
```

---

### Task 3: Trend derivations — `TrendPoint`, baseline, series

**Files:**

- Create: `app/utils/skewvoirAnalysis/timeSeries.ts`
- Test: `app/utils/skewvoirAnalysis/timeSeries.test.ts`

**Interfaces:**

- Consumes: `TsBaseline` from `./types.ts`; `quantileSorted` from `../stats.ts`; `peerVerdicts` / `combineVerdicts` / `MethodConfig` / `CombinedVerdict` from `../anomaly/index.ts`; `isNamedParam` from `./paramOrder.ts`.
- Produces: `TrendPoint`, `TrendRowInput`, `TrendFileInput`, `setBaseline(means: number[]): number`, `buildTrendSeries(rows, files, parameter, opts): TrendPoint[]`.

**Critical design note for the implementer:** `TrendPoint` carries **both** raw statistics and display values. `mean` / `min` / `max` are always as measured; `value` / `bandLo` / `bandHi` are what the chart plots after the baseline is applied. Everything that does math downstream (tool skew, anomaly verdicts) reads the raw fields. This is not redundancy — the `range` scoring method divides by the leave-one-out center, so scoring shifted values would silently change every percentage.

- [ ] **Step 1: Write the failing test**

Create `app/utils/skewvoirAnalysis/timeSeries.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { setBaseline, buildTrendSeries, type TrendRowInput, type TrendFileInput } from './timeSeries.ts'
import { DEFAULT_METHOD_CONFIG } from '../anomaly/types.ts'

const row = (msr: string, eqpId: string, timestamp: string): TrendRowInput =>
  ({ msr, label: `${eqpId} · ${timestamp}`, eqpId, timestamp })

const file = (parameter: string, mean: number, min: number, max: number, std: number): TrendFileInput =>
  ({ parameters: [{ parameter, count: 9, mean, std, min, max, unit: 'nm' }] })

test('setBaseline returns the median and does NOT require pre-sorted input', () => {
  // quantileSorted indexes without sorting — an unsorted caller silently gets
  // a wrong "median", so setBaseline must sort defensively.
  assert.equal(setBaseline([5, 1, 3]), 3)
  assert.equal(setBaseline([10, 2, 8, 4]), 6) // even count → midpoint of 4 and 8
  assert.equal(setBaseline([7]), 7)
  assert.ok(Number.isNaN(setBaseline([])))
})

test('buildTrendSeries sorts by timestamp, not by authored order', () => {
  const rows = [
    row('m1', 'TP01', '2026-07-03T10:00:00'),
    row('m2', 'TP02', '2026-07-01T10:00:00'),
    row('m3', 'TP03', '2026-07-02T10:00:00')
  ]
  const files = new Map<string, TrendFileInput>([
    ['m1', file('WAFER', 30, 28, 32, 1)],
    ['m2', file('WAFER', 10, 9, 11, 1)],
    ['m3', file('WAFER', 20, 19, 21, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(out.map(p => p.msr), ['m2', 'm3', 'm1'])
})

test('raw baseline leaves value and band equal to the measured statistics', () => {
  const rows = [row('m1', 'TP01', '2026-07-01T10:00:00')]
  const files = new Map([['m1', file('WAFER', 20, 18, 24, 2)]])
  const [p] = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.equal(p!.mean, 20)
  assert.equal(p!.value, 20)
  assert.equal(p!.bandLo, 18)
  assert.equal(p!.bandHi, 24)
})

test('residual baseline shifts value AND both band edges by the same amount', () => {
  const rows = [
    row('m1', 'TP01', '2026-07-01T10:00:00'),
    row('m2', 'TP02', '2026-07-02T10:00:00'),
    row('m3', 'TP03', '2026-07-03T10:00:00')
  ]
  const files = new Map([
    ['m1', file('WAFER', 10, 8, 12, 1)],
    ['m2', file('WAFER', 20, 18, 24, 2)],
    ['m3', file('WAFER', 30, 28, 32, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'resid', config: DEFAULT_METHOD_CONFIG })
  const mid = out.find(p => p.msr === 'm2')!
  assert.equal(mid.mean, 20)      // raw statistic preserved
  assert.equal(mid.value, 0)      // 20 - median(10,20,30) = 0
  assert.equal(mid.bandLo, -2)    // 18 - 20
  assert.equal(mid.bandHi, 4)     // 24 - 20
})

test('measurements whose file lacks the parameter are dropped', () => {
  const rows = [
    row('m1', 'TP01', '2026-07-01T10:00:00'),
    row('m2', 'TP02', '2026-07-02T10:00:00')
  ]
  const files = new Map([
    ['m1', file('WAFER', 10, 9, 11, 1)],
    ['m2', file('GATE_CD', 50, 48, 52, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(out.map(p => p.msr), ['m1'])
})

test('an unparseable timestamp yields ts null and sorts to the end, still plotted', () => {
  const rows = [
    row('bad', 'TP09', 'not-a-date'),
    row('m1', 'TP01', '2026-07-01T10:00:00')
  ]
  const files = new Map([
    ['bad', file('WAFER', 15, 14, 16, 1)],
    ['m1', file('WAFER', 10, 9, 11, 1)]
  ])
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(out.map(p => p.msr), ['m1', 'bad'])
  assert.equal(out[1]!.ts, null)
})

test('an unnamed settling MP gets no verdicts — no peer judgement on a warm-up shot', () => {
  const rows = Array.from({ length: 6 }, (_, i) =>
    row(`m${i}`, 'TP01', `2026-07-0${i + 1}T10:00:00`))
  const files = new Map(rows.map((r, i) => [r.msr, file('', 10 + i, 9 + i, 11 + i, 1)]))
  const out = buildTrendSeries(rows, files, '', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.equal(out.length, 6)
  assert.ok(out.every(p => p.verdict === undefined))
})

test('a named parameter DOES get verdicts once there are enough peers', () => {
  const rows = Array.from({ length: 6 }, (_, i) =>
    row(`m${i}`, 'TP01', `2026-07-0${i + 1}T10:00:00`))
  const files = new Map(rows.map((r, i) => [r.msr, file('WAFER', 10 + i, 9 + i, 11 + i, 1)]))
  const out = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  assert.ok(out.every(p => p.verdict !== undefined))
})

test('verdicts are computed from RAW means, so residual mode cannot change them', () => {
  const rows = Array.from({ length: 6 }, (_, i) =>
    row(`m${i}`, 'TP01', `2026-07-0${i + 1}T10:00:00`))
  const files = new Map(rows.map((r, i) => [r.msr, file('WAFER', 100 + i, 99 + i, 101 + i, 1)]))
  const raw = buildTrendSeries(rows, files, 'WAFER', { baseline: 'raw', config: DEFAULT_METHOD_CONFIG })
  const resid = buildTrendSeries(rows, files, 'WAFER', { baseline: 'resid', config: DEFAULT_METHOD_CONFIG })
  assert.deepEqual(
    raw.map(p => p.verdict?.severity),
    resid.map(p => p.verdict?.severity)
  )
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
node --test app/utils/skewvoirAnalysis/timeSeries.test.ts
```

Expected: FAIL — cannot find module `./timeSeries.ts`.

- [ ] **Step 3: Write the implementation**

Create `app/utils/skewvoirAnalysis/timeSeries.ts`:

```ts
// Skewvoir Time-Series — derivations for the multi-measurement (set) lenses.
//
// Every function here is pure so it runs under raw `node --test`; the composable
// only wires them to reactive state and the .vue files only render.
//
// A TrendPoint carries BOTH raw statistics and display values:
//   mean / min / max   — always as measured
//   value / bandLo/Hi  — what the chart plots, after the baseline is applied
//
// That split is load-bearing, not redundancy. The `range` scoring method divides
// by the leave-one-out center, so judging baseline-shifted values would change
// every percentage. Anomaly verdicts and tool skew read the RAW fields.
import type { TsBaseline } from './types.ts'
import type { MsrParamSummary } from '~/composables/useMsrFileApi'
import { quantileSorted } from '../stats.ts'
import { peerVerdicts, combineVerdicts, type MethodConfig, type CombinedVerdict } from '../anomaly/index.ts'
import { isNamedParam } from './paramOrder.ts'

/** The meas_hist facts a trend point needs. Structural (not MeasHistRow) so the
 *  tests can build one without a 25-field fixture. */
export interface TrendRowInput {
  msr: string
  /** Presentation label, built by the caller (`eqp_id · timestamp`). */
  label: string
  eqpId: string
  timestamp: string
}

/** The MsrFile facts a trend point needs. */
export interface TrendFileInput {
  parameters: MsrParamSummary[]
}

export interface TrendPoint {
  msr: string
  label: string
  eqpId: string
  /** Epoch ms, or null when the timestamp could not be parsed. */
  ts: number | null
  // Raw statistics — never baseline-shifted.
  mean: number
  min: number
  max: number
  std: number
  // Display values — baseline applied.
  value: number
  bandLo: number
  bandHi: number
  /** Absent ONLY for an unnamed settling MP. With too few peers the verdict is
   *  still present, carrying status 'insufficient' — peerVerdicts returns an
   *  insufficient verdict rather than nothing, and the chart renders that as
   *  the grey 판정 불가 tone. */
  verdict?: CombinedVerdict
}

export interface BuildTrendOptions {
  baseline: TsBaseline
  config: MethodConfig
}

/** Median of the set's measurement means — the `세트 기준`.
 *
 *  Sorts defensively: quantileSorted indexes without sorting (its contract says
 *  "caller pre-sorts"), so an unsorted caller gets a confident wrong number. */
export const setBaseline = (means: number[]): number => {
  const sorted = means.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return Number.NaN
  return quantileSorted(sorted, 0.5)
}

const parseTs = (timestamp: string): number | null => {
  const t = new Date(timestamp).getTime()
  return Number.isFinite(t) ? t : null
}

export const buildTrendSeries = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, TrendFileInput>,
  parameter: string,
  opts: BuildTrendOptions
): TrendPoint[] => {
  const raw: TrendPoint[] = []
  for (const row of rows) {
    const summary = files.get(row.msr)?.parameters.find(p => p.parameter === parameter)
    if (!summary) continue
    raw.push({
      msr: row.msr,
      label: row.label,
      eqpId: row.eqpId,
      ts: parseTs(row.timestamp),
      mean: summary.mean,
      min: summary.min,
      max: summary.max,
      std: summary.std,
      // Overwritten below once the baseline is known.
      value: summary.mean,
      bandLo: summary.min,
      bandHi: summary.max
    })
  }

  // Chronological, with unparseable timestamps held at the end in authored
  // order rather than dropped — they are still real measurements, and the
  // `order` axis can show them honestly.
  raw.sort((a, b) => {
    if (a.ts == null && b.ts == null) return 0
    if (a.ts == null) return 1
    if (b.ts == null) return -1
    return a.ts - b.ts
  })

  const base = opts.baseline === 'resid' ? setBaseline(raw.map(p => p.mean)) : 0
  const shift = Number.isFinite(base) ? base : 0
  const points = raw.map(p => ({
    ...p,
    value: p.mean - shift,
    bandLo: p.min - shift,
    bandHi: p.max - shift
  }))

  // No peer judgement on an unnamed settling MP: comparing one measurement's
  // warm-up shot against another's says nothing about either wafer.
  if (!isNamedParam(parameter)) return points

  // Judged on RAW means, so the verdicts are identical in raw and residual mode.
  const meanV = peerVerdicts(points.map(p => p.mean), { config: opts.config, metric: 'mean' })
  const spreadV = peerVerdicts(points.map(p => p.std), { config: opts.config, metric: 'spread', tag: '산포' })
  return points.map((p, i) => ({ ...p, verdict: combineVerdicts([meanV[i]!, spreadV[i]!]) }))
}
```

**Note on the anomaly import path:** `app/utils/anomaly/index.ts` exists, so `'../anomaly/index.ts'` is correct — with the explicit `.ts`. A bare `'../anomaly'` directory import will fail under `node --test`.

- [ ] **Step 4: Run the test to verify it passes**

```bash
node --test app/utils/skewvoirAnalysis/timeSeries.test.ts
```

Expected: PASS (9 tests). If the verdict tests fail with all-undefined verdicts, check `PEER_MIN_N` — `range` needs 3 peers and `stddev` needs 5; the fixtures use 6 measurements to clear both.

- [ ] **Step 5: Commit**

```bash
git add app/utils/skewvoirAnalysis/timeSeries.ts app/utils/skewvoirAnalysis/timeSeries.test.ts
git commit -m "feat(skewvoir): derive the multi-measurement trend series"
```

---

### Task 4: Distribution groups and tool skew

**Files:**

- Modify: `app/utils/skewvoirAnalysis/timeSeries.ts`
- Modify: `app/utils/skewvoirAnalysis/timeSeries.test.ts`

**Interfaces:**

- Consumes: `TrendPoint`, `TrendRowInput` from Task 3; `isMeasuredRow` from `../msrRows.ts`; `mean`, `sampleStd` from `../stats.ts`.
- Produces: `SetDistributionGroup`, `ToolSkewRow`, `buildSetDistributionGroups(rows, files, parameter): SetDistributionGroup[]`, `buildToolSkew(points, baseline): ToolSkewRow[]`.

- [ ] **Step 1: Write the failing test**

Append to `app/utils/skewvoirAnalysis/timeSeries.test.ts`:

```ts
import { buildSetDistributionGroups, buildToolSkew, distinctToolCount, type DistFileInput } from './timeSeries.ts'

const siteRow = (parameter: string, mp_number: number, cd_value: number | null) =>
  ({ parameter, mp_number, cd_value })

test('buildSetDistributionGroups makes one group per measurement, measured sites only', () => {
  const rows = [row('m1', 'TP01', '2026-07-01T10:00:00'), row('m2', 'TP02', '2026-07-02T10:00:00')]
  const files = new Map<string, DistFileInput>([
    ['m1', { rows: [siteRow('WAFER', 0, 10), siteRow('WAFER', 1, 12), siteRow('GATE_CD', 2, 99)] }],
    ['m2', { rows: [siteRow('WAFER', 0, 20), siteRow('WAFER', -1, null)] }]
  ])
  const out = buildSetDistributionGroups(rows, files, 'WAFER')
  assert.deepEqual(out.map(g => g.label), ['TP01 · 2026-07-01T10:00:00', 'TP02 · 2026-07-02T10:00:00'])
  assert.deepEqual(out[0]!.values, [10, 12])
  assert.deepEqual(out[1]!.values, [20]) // the mp_number -1 / null site is excluded
})

test('buildSetDistributionGroups drops a measurement with no measured site', () => {
  const rows = [row('m1', 'TP01', '2026-07-01T10:00:00'), row('m2', 'TP02', '2026-07-02T10:00:00')]
  const files = new Map<string, DistFileInput>([
    ['m1', { rows: [siteRow('WAFER', 0, 10)] }],
    ['m2', { rows: [siteRow('WAFER', -1, null)] }]
  ])
  const out = buildSetDistributionGroups(rows, files, 'WAFER')
  assert.deepEqual(out.map(g => g.label), ['TP01 · 2026-07-01T10:00:00'])
})

test('buildToolSkew groups by equipment, offsets against the set baseline', () => {
  const points = [
    { eqpId: 'TP01', mean: 10 }, { eqpId: 'TP01', mean: 12 },
    { eqpId: 'TP02', mean: 30 }
  ] as TrendPoint[]
  const out = buildToolSkew(points, 20)
  const tp01 = out.find(r => r.eqpId === 'TP01')!
  assert.equal(tp01.n, 2)
  assert.equal(tp01.mean, 11)
  assert.equal(tp01.offset, -9)
  assert.equal(tp01.sigma, Math.sqrt(2)) // sample std of [10, 12]
})

test('buildToolSkew reports sigma null for a single-measurement tool', () => {
  // sampleStd returns 0 for n<2; rendering that reads as "no variation" when
  // the truth is "not estimable".
  const points = [{ eqpId: 'TP01', mean: 10 }, { eqpId: 'TP02', mean: 30 }] as TrendPoint[]
  const out = buildToolSkew(points, 20)
  assert.ok(out.every(r => r.n === 1))
  assert.ok(out.every(r => r.sigma === null))
})

test('buildToolSkew sorts by absolute offset, most-skewed tool first', () => {
  const points = [
    { eqpId: 'NEAR', mean: 21 }, { eqpId: 'FAR', mean: 40 }, { eqpId: 'MID', mean: 14 }
  ] as TrendPoint[]
  assert.deepEqual(buildToolSkew(points, 20).map(r => r.eqpId), ['FAR', 'MID', 'NEAR'])
})

test('buildToolSkew produces NO rows for a single-tool set', () => {
  // An offset against a baseline the tool itself defines is not a comparison.
  // The spec requires no row at all — the panel says 단일 장비 instead.
  const points = [{ eqpId: 'TP01', mean: 10 }, { eqpId: 'TP01', mean: 20 }] as TrendPoint[]
  assert.deepEqual(buildToolSkew(points, 15), [])
})

test('buildToolSkew on an empty set returns no rows', () => {
  assert.deepEqual(buildToolSkew([], Number.NaN), [])
})

test('distinctToolCount lets the panel tell "one tool" apart from "no data"', () => {
  // Both cases give buildToolSkew an empty array, but they need different copy.
  assert.equal(distinctToolCount([{ eqpId: 'TP01', mean: 10 }] as TrendPoint[]), 1)
  assert.equal(distinctToolCount([]), 0)
  assert.equal(distinctToolCount([
    { eqpId: 'TP01', mean: 10 }, { eqpId: 'TP02', mean: 20 }
  ] as TrendPoint[]), 2)
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
node --test app/utils/skewvoirAnalysis/timeSeries.test.ts
```

Expected: FAIL — `buildSetDistributionGroups is not a function`.

- [ ] **Step 3: Write the implementation**

Append to `app/utils/skewvoirAnalysis/timeSeries.ts`. Add to the existing imports:

```ts
import { mean as meanOf, sampleStd } from '../stats.ts'
```

Then:

```ts
/** The site facts the distribution lens needs.
 *
 *  Deliberately a MINIMAL structural type, not `MsrFileRow`. `MsrFileRow` has
 *  ~20 required fields (coordinates, image names, measurement conditions,
 *  scores); demanding it here would force every test fixture to invent all of
 *  them. `nuxt typecheck` covers `app/**` INCLUDING `*.test.ts`, so a shortcut
 *  fixture would not merely be untidy — it would fail the build. A real
 *  MsrFileRow still satisfies this shape structurally. */
export interface DistSiteInput {
  parameter: string
  mp_number: number
  cd_value: number | null
}

export interface DistFileInput {
  rows: DistSiteInput[]
}

/** Local mirror of utils/msrRows.ts's isMeasuredRow, narrowed to DistSiteInput.
 *  Same rule — mp_number < 0 is a metadata-only point with no measurement, and
 *  a null cd_value is the contract for "no data" — but it does not demand a
 *  full MsrFileRow. Keep the two in sync. */
const isMeasuredSite = (r: DistSiteInput): r is DistSiteInput & { cd_value: number } =>
  r.mp_number >= 0 && r.cd_value != null && Number.isFinite(r.cd_value)

/** Matches DistributionChart.vue's `DistributionGroup` prop shape. */
export interface SetDistributionGroup {
  label: string
  values: number[]
}

/** One box per measurement, from the site rows already in setFiles.
 *
 *  A measurement with no measured site is dropped rather than contributed as an
 *  empty box — the caller reports the count in the panel meta. */
export const buildSetDistributionGroups = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, DistFileInput>,
  parameter: string
): SetDistributionGroup[] => {
  const groups: SetDistributionGroup[] = []
  for (const row of rows) {
    const file = files.get(row.msr)
    if (!file) continue
    const values: number[] = []
    for (const site of file.rows) {
      if (site.parameter === parameter && isMeasuredSite(site)) values.push(site.cd_value)
    }
    if (values.length === 0) continue
    groups.push({ label: row.label, values })
  }
  return groups
}

export interface ToolSkewRow {
  eqpId: string
  /** Measurements this tool contributed to the set. */
  n: number
  /** Mean of this tool's measurement means (raw). */
  mean: number
  /** mean - 세트 기준. */
  offset: number
  /** Sample std across this tool's means; null when n < 2 (not estimable). */
  sigma: number | null
}

/** Distinct equipment in the set. The panel needs this to tell "one tool"
 *  (say 단일 장비) apart from "no data" (say nothing) — buildToolSkew returns an
 *  empty array for both. */
export const distinctToolCount = (points: readonly TrendPoint[]): number =>
  new Set(points.map(p => p.eqpId)).size

/** Per-equipment offset from the set baseline.
 *
 *  Reads the RAW `mean`, so the rows are identical in raw and residual mode —
 *  an offset is already a delta. No verdict or status is produced: with a
 *  hand-picked set spanning recipes, an offset is not attributable enough to
 *  grade.
 *
 *  A single-tool set yields NO rows. Its baseline is that tool's own median, so
 *  the "offset" would be a number about nothing — a row reading ≈0 invites the
 *  conclusion that the tool agrees with its peers when it has none. */
export const buildToolSkew = (
  points: readonly TrendPoint[],
  baseline: number
): ToolSkewRow[] => {
  if (distinctToolCount(points) < 2) return []

  const byTool = new Map<string, number[]>()
  for (const p of points) {
    const list = byTool.get(p.eqpId)
    if (list) list.push(p.mean)
    else byTool.set(p.eqpId, [p.mean])
  }

  const rows: ToolSkewRow[] = []
  for (const [eqpId, means] of byTool) {
    const m = meanOf(means)
    rows.push({
      eqpId,
      n: means.length,
      mean: m,
      offset: m - baseline,
      sigma: means.length > 1 ? sampleStd(means) : null
    })
  }

  rows.sort((a, b) => Math.abs(b.offset) - Math.abs(a.offset))
  return rows
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
node --test app/utils/skewvoirAnalysis/timeSeries.test.ts
```

Expected: PASS (17 tests — 9 from Task 3 plus 8 here). If `mean` collides with the imported `mean` from `../stats.ts`, keep the `meanOf` alias shown above.

- [ ] **Step 5: Commit**

```bash
git add app/utils/skewvoirAnalysis/timeSeries.ts app/utils/skewvoirAnalysis/timeSeries.test.ts
git commit -m "feat(skewvoir): derive distribution groups and per-tool skew rows"
```

---

### Task 5: Set parameter options and set integrity

**Files:**

- Modify: `app/utils/skewvoirAnalysis/timeSeries.ts`
- Modify: `app/utils/skewvoirAnalysis/timeSeries.test.ts`

**Interfaces:**

- Consumes: `TrendRowInput` from Task 3.
- Produces: `SetParamOption`, `SetIntegrity`, `setParamOptions(rows, files): SetParamOption[]`, `setIntegrity(msrList, resolvedRows, files): SetIntegrity`.

**Naming note:** do **not** call this `ParamCoverage`. `app/utils/overview.ts` already exports a `ParamCoverage` meaning something else entirely (attempted/measured/failed **sites within one measurement**). Reusing the name would make two unrelated concepts look like one.

- [ ] **Step 1: Write the failing test**

Append to `app/utils/skewvoirAnalysis/timeSeries.test.ts`:

```ts
import { setParamOptions, setIntegrity, type OptionFileInput } from './timeSeries.ts'

const optFile = (params: string[], mpRows: { parameter: string, mp_number: number, sequence: number }[]): OptionFileInput =>
  ({ parameters: params.map(p => ({ parameter: p, count: 1, mean: 0, std: 0, min: 0, max: 0, unit: 'nm' })), rows: mpRows })

test('setParamOptions counts how many LOADED measurements carry each parameter', () => {
  const rows = [row('m1', 'TP01', 't1'), row('m2', 'TP02', 't2'), row('m3', 'TP03', 't3')]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['WAFER', 'GATE_CD'], [{ parameter: 'WAFER', mp_number: 1, sequence: 1 }, { parameter: 'GATE_CD', mp_number: 2, sequence: 2 }])],
    ['m2', optFile(['WAFER'], [{ parameter: 'WAFER', mp_number: 1, sequence: 1 }])]
    // m3 has no file — it was never loaded, so it is not in the denominator
  ])
  const out = setParamOptions(rows, files)
  assert.equal(out.find(o => o.parameter === 'WAFER')!.covered, 2)
  assert.equal(out.find(o => o.parameter === 'GATE_CD')!.covered, 1)
  assert.ok(out.every(o => o.loaded === 2))
})

test('setParamOptions sorts by coverage, then MP order, then name', () => {
  const rows = [row('m1', 'TP01', 't1'), row('m2', 'TP02', 't2')]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['B_LATE', 'A_EARLY', 'RARE'], [
      { parameter: 'A_EARLY', mp_number: 1, sequence: 1 },
      { parameter: 'B_LATE', mp_number: 5, sequence: 5 },
      { parameter: 'RARE', mp_number: 9, sequence: 9 }
    ])],
    ['m2', optFile(['B_LATE', 'A_EARLY'], [
      { parameter: 'A_EARLY', mp_number: 1, sequence: 1 },
      { parameter: 'B_LATE', mp_number: 5, sequence: 5 }
    ])]
  ])
  // A_EARLY and B_LATE both cover 2; A_EARLY has the lower mp_number.
  // RARE covers 1, so it sorts last regardless of anything else.
  assert.deepEqual(setParamOptions(rows, files).map(o => o.parameter), ['A_EARLY', 'B_LATE', 'RARE'])
})

test('setIntegrity separates unresolved ids from unloaded files and counts recipes', () => {
  const resolved = [
    { ...row('m1', 'TP01', 't1'), recipeName: 'RCP_A' },
    { ...row('m2', 'TP02', 't2'), recipeName: 'RCP_B' }
  ]
  const files = new Map<string, OptionFileInput>([['m1', optFile(['WAFER'], [])]])
  const out = setIntegrity(['m1', 'm2', 'ghost'], resolved, files)
  assert.equal(out.requested, 3)
  assert.equal(out.resolved, 2)
  assert.equal(out.loaded, 1)
  assert.deepEqual(out.unresolvedMsrs, ['ghost'])
  assert.equal(out.recipeCount, 2)
})

test('setIntegrity on a clean single-recipe set reports nothing to warn about', () => {
  const resolved = [
    { ...row('m1', 'TP01', 't1'), recipeName: 'RCP_A' },
    { ...row('m2', 'TP02', 't2'), recipeName: 'RCP_A' }
  ]
  const files = new Map<string, OptionFileInput>([
    ['m1', optFile(['WAFER'], [])], ['m2', optFile(['WAFER'], [])]
  ])
  const out = setIntegrity(['m1', 'm2'], resolved, files)
  assert.deepEqual(out.unresolvedMsrs, [])
  assert.equal(out.recipeCount, 1)
  assert.equal(out.loaded, 2)
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
node --test app/utils/skewvoirAnalysis/timeSeries.test.ts
```

Expected: FAIL — `setParamOptions is not a function`.

- [ ] **Step 3: Write the implementation**

Append to `app/utils/skewvoirAnalysis/timeSeries.ts`:

```ts
/** The MsrFile facts the parameter selector needs: which parameters exist, and
 *  the MP order rows that break coverage ties. */
export interface OptionFileInput {
  parameters: MsrParamSummary[]
  rows: { parameter: string, mp_number: number, sequence: number }[]
}

export interface SetParamOption {
  parameter: string
  /** Measurements in the set whose file carries this parameter. */
  covered: number
  /** Measurements whose file loaded at all — the coverage denominator. */
  loaded: number
}

/** Set-aware parameter list with coverage.
 *
 *  NOT `ParamCoverage` — utils/overview.ts already owns that name for
 *  attempted/measured/failed SITES within one measurement.
 *
 *  Ordering must be deterministic across a heterogeneous set. sortByRowMpOrder
 *  answers "what order are one measurement's parameters in", and recipes can
 *  disagree, so the set uses: coverage desc → lowest (mp_number, sequence) in
 *  the set → name. */
export const setParamOptions = (
  rows: readonly TrendRowInput[],
  files: ReadonlyMap<string, OptionFileInput>
): SetParamOption[] => {
  const covered = new Map<string, number>()
  const rank = new Map<string, [number, number]>()
  let loaded = 0

  for (const row of rows) {
    const file = files.get(row.msr)
    if (!file) continue
    loaded++
    for (const p of file.parameters) {
      covered.set(p.parameter, (covered.get(p.parameter) ?? 0) + 1)
    }
    for (const r of file.rows) {
      if (r.mp_number < 0) continue
      const current = rank.get(r.parameter)
      if (!current || r.mp_number < current[0] || (r.mp_number === current[0] && r.sequence < current[1])) {
        rank.set(r.parameter, [r.mp_number, r.sequence])
      }
    }
  }

  const options = [...covered].map(([parameter, n]) => ({ parameter, covered: n, loaded }))
  const NO_RANK: [number, number] = [Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY]
  options.sort((a, b) => {
    if (b.covered !== a.covered) return b.covered - a.covered
    const ra = rank.get(a.parameter) ?? NO_RANK
    const rb = rank.get(b.parameter) ?? NO_RANK
    if (ra[0] !== rb[0]) return ra[0] - rb[0]
    if (ra[1] !== rb[1]) return ra[1] - rb[1]
    return a.parameter.localeCompare(b.parameter)
  })
  return options
}

/** A resolved set row plus the recipe, for the confounding badge. */
export interface IntegrityRowInput extends TrendRowInput {
  recipeName: string
}

export interface SetIntegrity {
  /** Ids in the URL `msrs`. */
  requested: number
  /** Ids that matched a measurement-history row. */
  resolved: number
  /** Resolved measurements whose MsrFile actually came back. */
  loaded: number
  /** Ids the history could not resolve — most often a cross-family selection,
   *  since search spans both SEM families but analysis loads one tool type. */
  unresolvedMsrs: string[]
  /** Distinct recipes in the set. >1 means tool skew is confounded. */
  recipeCount: number
}

export const setIntegrity = (
  msrList: readonly string[],
  resolvedRows: readonly IntegrityRowInput[],
  files: ReadonlyMap<string, unknown>
): SetIntegrity => {
  const resolvedIds = new Set(resolvedRows.map(r => r.msr))
  return {
    requested: msrList.length,
    resolved: resolvedRows.length,
    loaded: resolvedRows.filter(r => files.has(r.msr)).length,
    unresolvedMsrs: msrList.filter(id => !resolvedIds.has(id)),
    recipeCount: new Set(resolvedRows.map(r => r.recipeName)).size
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
node --test app/utils/skewvoirAnalysis/timeSeries.test.ts
npm test
npm run typecheck
```

Expected: all `timeSeries.test.ts` tests pass; full suite ≥ 971 + new; typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add app/utils/skewvoirAnalysis/timeSeries.ts app/utils/skewvoirAnalysis/timeSeries.test.ts
git commit -m "feat(skewvoir): derive set parameter options and set integrity"
```

---

### Task 6: Wire the derivations into the composables

This is the seam. No new unit tests — the rules are already tested in Tasks 1–5, and composables cannot be tested here (no mounting harness). Correctness is carried by typecheck plus the browser check in Task 10.

**Files:**

- Modify: `app/composables/useSkewvoirRoute.ts`
- Modify: `app/composables/useSkewvoirAnalysis.ts`
- Modify: `app/components/ebeam/skewvoir/TimeSeriesChart.vue` (type import only)

**Interfaces:**

- Consumes: everything produced by Tasks 1–5.
- Produces on `useSkewvoirRoute`: `tsView`, `tsAxis`, `tsBaseline` refs and `setTsView(v: TsView)`, `setTsAxis(v: TsAxisMode)`, `setTsBaseline(v: TsBaseline)`.
- Produces on `useSkewvoirAnalysis`: `trendPoints: ComputedRef<TrendPoint[]>` (replacing the old shape), `setBaselineValue: ComputedRef<number>`, `distributionGroups`, `toolSkewRows`, `paramOptions`, `integrity`.

- [ ] **Step 1: Expose the new URL keys**

In `app/composables/useSkewvoirRoute.ts`, next to the existing `fdcAxis` block:

```ts
  const tsView = computed<TsView>(() => parseTsView(route.query.tsview))
  const tsAxis = computed<TsAxisMode>(() => parseTsAxis(route.query.tsx))
  const tsBaseline = computed<TsBaseline>(() => parseTsBaseline(route.query.tsb))

  // In-place (no history entry), same pattern as setView/setFdcAxis.
  const setTsView = (v: TsView) =>
    router.replace({ path: analysisPath, query: { ...route.query, tsview: v } })
  const setTsAxis = (v: TsAxisMode) =>
    router.replace({ path: analysisPath, query: { ...route.query, tsx: v } })
  const setTsBaseline = (v: TsBaseline) =>
    router.replace({ path: analysisPath, query: { ...route.query, tsb: v } })
```

Add all six to the returned object, and import the parsers and types.

Then re-export them from `app/composables/useSkewvoirWorkspace.ts`'s returned object (it wraps `skRoute`), following how `fdcAxis` / `setFdcAxis` are already re-exported.

- [ ] **Step 2: Switch the trend point type**

In `app/components/ebeam/skewvoir/TimeSeriesChart.vue`, delete the local `TimeSeriesPoint` interface and replace it with a re-export so no other importer breaks:

```ts
import type { TrendPoint } from '~/utils/skewvoirAnalysis/timeSeries'

/** @deprecated Use TrendPoint from utils/skewvoirAnalysis/timeSeries. Kept so
 *  existing importers of this name keep compiling. */
export type TimeSeriesPoint = TrendPoint
```

Change the component's `points` prop type to `TrendPoint[]`. Leave the rendering alone in this task — Task 7 rewrites it.

- [ ] **Step 3: Apply the set-scope parameter rule**

In `app/composables/useSkewvoirAnalysis.ts`, import `resolveActiveParam` and `activeParamPool` from `~/utils/skewvoirAnalysis/activeParam`, then add a set-parameter list and rewrite `activeParam`:

```ts
  // Parameters carried by ANY loaded measurement in the curated set. Empty
  // until the set files land, which is what keeps the dashboard case safe.
  const setParams = computed<string[]>(() => {
    const names = new Set<string>()
    for (const file of setFiles.value.values()) {
      for (const p of file.parameters) names.add(p.parameter)
    }
    return [...names]
  })

  const paramInput = computed(() => ({
    scope: ws.scope.value,
    urlMp: ws.selection.value?.mp,
    focusParams: availableParams.value,
    setParams: setParams.value
  }))

  const activeParam = computed(() => resolveActiveParam(paramInput.value))
```

Then update the write-back watcher (currently around line 334) so it judges against the same pool, not `availableParams`:

```ts
  watch([() => activeParamPool(paramInput.value), () => ws.selection.value?.mp], ([pool, mp]) => {
    if (pool.length === 0) return
    if (mp != null && pool.includes(mp)) return
    if (activeParam.value !== mp) ws.setParam(activeParam.value)
  })
```

Note the `mp != null` change from the existing truthy `mp &&`: an explicit pick of the unnamed MP (`''`) must not be treated as absent and rewritten away.

- [ ] **Step 4: Replace `trendPoints` and add the new derivations**

Still in `app/composables/useSkewvoirAnalysis.ts`, replace the existing `trendPoints` computed with calls into the new util. `trendRowInputs` centralises the label so the trend and distribution lenses always agree on it:

```ts
  const trendRowInputs = computed(() => setRows.value.map(r => ({
    msr: r.msr,
    label: msrLabel(r.msr),
    eqpId: r.eqp_id,
    timestamp: r.timestamp,
    recipeName: r.recipe_name
  })))

  const trendPoints = computed<TrendPoint[]>(() => buildTrendSeries(
    trendRowInputs.value,
    setFiles.value,
    activeParam.value,
    { baseline: ws.tsBaseline.value, config: anomalyCfg.value }
  ))

  const setBaselineValue = computed(() => setBaseline(trendPoints.value.map(p => p.mean)))

  const distributionGroups = computed(() => buildSetDistributionGroups(
    trendRowInputs.value, setFiles.value, activeParam.value
  ))

  const toolSkewRows = computed(() => buildToolSkew(trendPoints.value, setBaselineValue.value))

  const paramOptions = computed(() => setParamOptions(trendRowInputs.value, setFiles.value))

  const integrity = computed(() => setIntegrity(ws.msrList.value, trendRowInputs.value, setFiles.value))

  const toolCount = computed(() => distinctToolCount(trendPoints.value))
```

Add `setBaselineValue`, `distributionGroups`, `toolSkewRows`, `toolCount`, `paramOptions`, and `integrity` to the returned object. `trendSummary` and `focusVerdict` already read `trendPoints` and keep working unchanged.

- [ ] **Step 4b: Make `activeUnit` set-aware too**

Widening the parameter without widening the unit leaves a hole: `activeSummary` searches `paramSummaries`, which derives from the **focus file only**, and `activeUnit` falls back to `''`. So the exact case Task 2 unlocks — a parameter the focus measurement lacks — would render every axis and table with no unit.

Find the existing `activeUnit` computed (around line 216) and give it a set fallback:

```ts
  // Focus first (unchanged for single scope); then any loaded set measurement
  // that carries the parameter. Without this, widening activeParam to the set
  // would strip the unit off the very parameters the widening exists to reach.
  const activeUnit = computed(() => {
    const focusUnit = activeSummary.value?.unit
    if (focusUnit) return focusUnit
    for (const file of setFiles.value.values()) {
      const hit = file.parameters.find(p => p.parameter === activeParam.value)
      if (hit?.unit) return hit.unit
    }
    return ''
  })
```

Keep whatever the current declaration returns for the focus case so single-scope screens are untouched.

- [ ] **Step 5: Verify the wiring compiles and nothing regressed**

```bash
npm run typecheck
npm test
npm run lint
```

Expected: typecheck clean, tests ≥ baseline, lint clean. If typecheck complains that `setFiles.value` (a `Map<string, MsrFileResponse>`) does not satisfy `ReadonlyMap<string, TrendFileInput>`, that is a real structural mismatch — confirm `MsrFileResponse` carries both `parameters` and `rows`; it does, so the map should be assignable.

- [ ] **Step 6: Commit**

```bash
git add app/composables/useSkewvoirRoute.ts app/composables/useSkewvoirWorkspace.ts app/composables/useSkewvoirAnalysis.ts app/components/ebeam/skewvoir/TimeSeriesChart.vue
git commit -m "feat(skewvoir): wire the time-series derivations and set-scope param rule"
```

---

### Task 7: Trend chart — time axis, per-tool color, residual band, click-to-focus

**Files:**

- Modify: `app/components/ebeam/skewvoir/TimeSeriesChart.vue`

**Interfaces:**

- Consumes: `TrendPoint` from Task 3; `SK_SITE` / `SK_SITE_OVERFLOW` from `~/utils/chartPalette`.
- Produces: props `points: TrendPoint[]`, `parameter: string`, `unit: string`, `axisMode: TsAxisMode`, `baseline: TsBaseline`; emit `select(msr: string)`.

- [ ] **Step 1: Add the props and emit**

```ts
const props = defineProps<{
  points: TrendPoint[]
  parameter: string
  unit: string
  axisMode: TsAxisMode
  baseline: TsBaseline
}>()

const emit = defineEmits<{ select: [msr: string] }>()
```

- [ ] **Step 2: Assign per-tool colors with an explicit overflow bucket**

`SK_SITE` holds exactly 10 identity colors and `SK_SITE_OVERFLOW` is one shared gray. Handing every tool past the 10th the same gray makes distinct tools look like one series, so cap the distinct colors at 9 and name the remainder honestly:

```ts
// Tools ranked by how many measurements they contributed; the top 9 get an
// identity color, everything else collapses into one labelled 기타 bucket.
// A shared gray silently spread across many tools would read as one series.
const TOOL_COLOR_LIMIT = 9
const OTHER_LABEL = '기타'

const toolColor = computed<Map<string, string>>(() => {
  const counts = new Map<string, number>()
  for (const p of props.points) counts.set(p.eqpId, (counts.get(p.eqpId) ?? 0) + 1)
  const ranked = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([eqpId]) => eqpId)
  const map = new Map<string, string>()
  ranked.forEach((eqpId, i) => {
    map.set(eqpId, i < TOOL_COLOR_LIMIT ? SK_SITE[i]! : SK_SITE_OVERFLOW)
  })
  return map
})

const overflowTools = computed(() => {
  const ranked = [...toolColor.value.entries()].filter(([, c]) => c === SK_SITE_OVERFLOW)
  return ranked.map(([eqpId]) => eqpId)
})
```

Render the legend from `toolColor`, replacing the overflow entries with a single `기타 (n)` chip using `overflowTools.value.length`.

- [ ] **Step 3: Split one series per tool, keeping verdict color on the points**

**Two channels, two meanings — do not collapse them.** The line's color says *which tool*; the point's color says *how the anomaly rule judged that measurement*. Recoloring the existing single point series by tool would destroy the verdict signal (`sevHex`, already in this file) and still leave every tool joined by one continuous line, which draws a trend across measurements that never belonged to the same series.

So: one line series per `eqp_id`, colored by tool; each datum keeps its verdict `itemStyle`.

```ts
// `time` is the honest default; `order` is the escape hatch when measurements
// bunch. Under `order` the x value is the index, so spacing is uniform.
// A point with an unparseable ts has no position on a time axis, so the time
// branch drops it; the view reports the count in the panel meta.
const placed = computed(() =>
  props.points
    .map((p, i) => ({ p, x: props.axisMode === 'time' ? p.ts : i }))
    .filter((e): e is { p: TrendPoint, x: number } => e.x != null)
)

const symbolFor = (key: string): number =>
  key === 'abnormal' ? 10 : key === 'watch' ? 9 : key === 'insufficient' ? 7 : 6

// One series per tool. The LINE carries tool identity; each POINT keeps the
// severity color the existing sevHex table produces, so a red dot still means
// "this measurement was judged abnormal", never "this is tool 3".
const toolSeries = computed(() => {
  const byTool = new Map<string, { value: [number, number], itemStyle: { color: string }, symbolSize: number }[]>()
  for (const { p, x } of placed.value) {
    const key = sevKey(p)
    const datum = {
      value: [x, p.value] as [number, number],
      itemStyle: { color: sevHex.value[key]! },
      symbolSize: symbolFor(key)
    }
    const list = byTool.get(p.eqpId)
    if (list) list.push(datum)
    else byTool.set(p.eqpId, [datum])
  }
  return [...byTool].map(([eqpId, data]) => ({
    name: eqpId,
    type: 'line' as const,
    data,
    smooth: false,
    showSymbol: true,
    lineStyle: { width: 2, color: toolColor.value.get(eqpId) ?? sk.value.series },
    itemStyle: { color: toolColor.value.get(eqpId) ?? sk.value.series },
    z: 3
  }))
})

// The band spans the whole set, not one tool, so it stays two global silent
// series behind everything. bandLo/bandHi are already baseline-shifted (Task 3).
const floorData = computed(() => placed.value.map(({ p, x }) => [x, p.bandLo]))
const bandData = computed(() => placed.value.map(({ p, x }) => [x, p.bandHi - p.bandLo]))
```

Build `series` as `[floorSeries, bandSeries, ...toolSeries.value]`, keeping the existing `stack: 'band'`, `silent: true`, `symbol: 'none'`, `z: 1` settings on the two band series unchanged.

**Set `hidden` count for the meta:** expose `placed.value.length` against `props.points.length` so Task 10 can report how many measurements the time axis could not place.

Axis:

```ts
xAxis: props.axisMode === 'time'
  ? { type: 'time' as const, axisLabel: { fontSize: 10, hideOverlap: true } }
  : { type: 'category' as const, data: props.points.map(p => p.label), axisLabel: { fontSize: 10, rotate: 35, hideOverlap: true }, boundaryGap: true },
```

Under `category` the datum x is the index, which lines up with `data` positionally.

The tooltip's existing `formatter` indexes `props.points[dataIndex]`. That is no longer correct — `dataIndex` is now an index into one tool's filtered array. Rebuild the tooltip from the datum instead, or carry the `msr` on each datum and look it up. Do not leave the existing index lookup in place; it will show the wrong measurement's numbers.

Set `xAxis` to `{ type: 'time' }` when `axisMode === 'time'`, else `{ type: 'category', data: labels }`. Under `time`, points whose `ts` is `null` cannot be placed — filter them out of the series and let Task 10's panel meta report the count.

Y-axis name switches with the baseline:

```ts
const yName = computed(() => {
  const base = props.unit ? `${props.parameter} (${props.unit})` : props.parameter
  return props.baseline === 'resid'
    ? `Δ vs 세트 기준${props.unit ? ` (${props.unit})` : ''}`
    : base
})
```

- [ ] **Step 4: Emit the clicked MSR**

`useEchart`'s `onClick` forwards only a category **name**, and these labels are `eqp_id · timestamp`, not MSR ids. Resolve through the series index instead:

Because Step 3 split the points across one series per tool, `dataIndex` alone is no longer an index into `props.points` — it is an index within **one tool's** array, and the two band series sit at series 0 and 1 ahead of them. Keep an msr lookup with the same shape as the series list:

```ts
// Parallel to the series array: msrGrid[seriesIndex - BAND_SERIES][dataIndex].
// Built from the same grouping pass as toolSeries so the two cannot drift.
const BAND_SERIES = 2

const msrGrid = computed<string[][]>(() => {
  const byTool = new Map<string, string[]>()
  for (const { p } of placed.value) {
    const list = byTool.get(p.eqpId)
    if (list) list.push(p.msr)
    else byTool.set(p.eqpId, [p.msr])
  }
  return [...byTool.values()]
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, option, {
  onDataIndex: (dataIndex: number, seriesIndex: number) => {
    const msr = msrGrid.value[seriesIndex - BAND_SERIES]?.[dataIndex]
    if (msr) emit('select', msr)
  }
})
```

The `?.` is the guard: the band series are `silent: true` so they should not fire at all, but an out-of-range index resolves to `undefined` and emits nothing rather than selecting the wrong measurement.

**`toolSeries` and `msrGrid` must iterate the same Map insertion order.** Both build their map by walking `placed.value` in order, so a tool's index is the same in both — if you refactor one, refactor both together, or merge them into a single computed returning `{ series, msrGrid }`.

`useEchart` currently exposes exactly two click callbacks — `onClick(name)` and `onGridClick(xValue, gridIndex)` — and **neither forwards a data index**, so you must add `onDataIndex` to `UseEchartOptions`. Add it beside the existing two, leaving both untouched so no other chart changes behaviour:

```ts
  // Fired when a series element is clicked, carrying the datum's index within
  // its series. `onClick` forwards the category NAME, which is not an identity
  // for charts whose labels are display strings rather than ids — the caller
  // maps the index back to its own data array. All supplied callbacks fire.
  onDataIndex?: (dataIndex: number, seriesIndex: number) => void
```

and bind it next to `bindClick`:

```ts
  const bindDataIndex = () => {
    const callback = options.onDataIndex
    if (!chart || !callback) return
    chart.on('click', (params) => {
      if (params.componentType !== 'series') return
      if (typeof params.dataIndex !== 'number') return
      callback(params.dataIndex, params.seriesIndex ?? 0)
    })
  }
```

Call `bindDataIndex()` wherever `bindClick()` is already called. **Guard on `seriesIndex` in the consumer:** the trend chart draws three series (band floor, band height, mean), so only clicks on the mean series should move focus. The band series are already `silent: true`, which suppresses their events — confirm that still holds after your Task 7 edits, and if not, filter on `seriesIndex` in the handler.

- [ ] **Step 5: Verify**

```bash
npm run typecheck
npm run lint
```

Expected: clean. There is no unit test for this file — it is a component.

- [ ] **Step 6: Commit**

```bash
git add app/components/ebeam/skewvoir/TimeSeriesChart.vue app/composables/useEchart.ts
git commit -m "feat(skewvoir): time axis, per-tool color, and click-to-focus on the trend chart"
```

---

### Task 8: Opt-in axis readability props on `DistributionChart`

30 groups with dozens of raw points each will overrun an axis that currently pins `interval: 0` with no rotation and no zoom. The existing callers (`dashboard/Distribution.vue`, `views/Correlation.vue`) pass few groups and must keep their current look, so the new behaviour is opt-in.

**Files:**

- Modify: `app/components/ebeam/skewvoir/DistributionChart.vue`

**Interfaces:**

- Produces: new optional props `rotateLabels?: boolean` (default `false`), `zoomable?: boolean` (default `false`).

- [ ] **Step 1: Add the props**

```ts
  // Box mode with many groups (the Time-Series set lens passes up to 30) needs
  // room the existing callers do not: they pass a handful of groups and must
  // keep today's flat labels, so both default OFF.
  rotateLabels?: boolean
  zoomable?: boolean
```

Add to `withDefaults`: `rotateLabels: false, zoomable: false`.

- [ ] **Step 2: Apply them in `boxOption` only**

In the `boxOption` computed, replace the category axis label config and add the zoom:

```ts
    xAxis: {
      type: 'category',
      data: cats.map(c => `${c.label} (${c.values.length})`),
      axisLabel: props.rotateLabels
        ? { fontSize: 10, rotate: 35, hideOverlap: true }
        : { fontSize: 10, interval: 0 }
    },
    dataZoom: props.zoomable
      ? [{ type: 'slider', height: 14, bottom: 4 }, { type: 'inside' }]
      : undefined,
```

Keep every other shape (`Hist`, `ECDF`, `Violin`) untouched — this task changes only the box branch, and only when the new props are set.

- [ ] **Step 3: Verify existing callers are unaffected**

```bash
npm run typecheck
npm run lint
```

Then confirm by reading `dashboard/Distribution.vue` and `views/Correlation.vue` that neither passes the new props, so both keep `interval: 0` and no zoom.

- [ ] **Step 4: Commit**

```bash
git add app/components/ebeam/skewvoir/DistributionChart.vue
git commit -m "feat(skewvoir): opt-in label rotation and zoom for many-group box plots"
```

---

### Task 9: `ParamCoverageSelect` and `ToolSkewPanel`

**Files:**

- Create: `app/components/ebeam/skewvoir/timeseries/ParamCoverageSelect.vue`
- Create: `app/components/ebeam/skewvoir/timeseries/ToolSkewPanel.vue`

**Interfaces:**

- Consumes: `SetParamOption`, `ToolSkewRow` from Task 5 / Task 4; `paramLabel` from `~/utils/skewvoirAnalysis/paramOrder`.
- Produces: `ParamCoverageSelect` props `options: SetParamOption[]`, `modelValue: string`; emit `update:modelValue(parameter: string)`. `ToolSkewPanel` props `rows: ToolSkewRow[]`, `toolCount: number`, `unit: string`.

- [ ] **Step 1: Write `ParamCoverageSelect.vue`**

```vue
<template>
  <USelectMenu
    :model-value="selected"
    :items="items"
    value-key="value"
    size="sm"
    class="min-w-64"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script setup lang="ts">
import type { SetParamOption } from '~/utils/skewvoirAnalysis/timeSeries'
import { paramLabel } from '~/utils/skewvoirAnalysis/paramOrder'

const props = defineProps<{
  options: SetParamOption[]
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [parameter: string] }>()

// Coverage is shown on every option so a silent drop becomes a visible one:
// picking a parameter 22 of 30 measurements carry should look different from
// picking one they all share.
const items = computed(() => props.options.map(o => ({
  label: `${paramLabel(o.parameter)} · ${o.covered}/${o.loaded}`,
  value: o.parameter
})))

const selected = computed(() => props.modelValue)
</script>
```

Confirm the NuxtUI `USelectMenu` prop names against another call site in this repo (for example `search/FacetSelect.vue`) before finalising — match whatever that file uses for `items` / `value-key`.

- [ ] **Step 2: Write `ToolSkewPanel.vue`**

Render one row per tool: the label, a horizontal offset bar against a zero line, and the numbers. `σ` renders as `—` when `sigma` is `null`.

```vue
<template>
  <!-- buildToolSkew returns [] for BOTH "one tool" and "no data", so the copy
       is chosen by toolCount, not by rows.length. -->
  <div
    v-if="!rows.length"
    class="flex h-56 items-center justify-center sk-body"
  >
    {{ toolCount === 1 ? '단일 장비 · 비교 대상 없습니다.' : '비교할 측정을 추가하세요.' }}
  </div>
  <table
    v-else
    class="w-full text-left"
  >
    <thead>
      <tr class="sk-meta">
        <th class="py-1">장비</th>
        <th class="py-1 text-right">n</th>
        <th class="py-1 text-right">평균</th>
        <th class="py-1 text-right">세트 기준 대비</th>
        <th class="py-1 text-right">σ</th>
        <th class="py-1 pl-3">편차</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="r in rows"
        :key="r.eqpId"
        class="border-t border-(--sk-border-soft)"
      >
        <td class="py-1 font-mono text-xs text-(--sk-ink)">{{ r.eqpId }}</td>
        <td class="py-1 text-right tabular-nums sk-body">{{ r.n }}</td>
        <td class="py-1 text-right tabular-nums sk-body">{{ r.mean.toFixed(3) }}</td>
        <td class="py-1 text-right tabular-nums sk-body">{{ signed(r.offset) }}</td>
        <td class="py-1 text-right tabular-nums sk-body">{{ r.sigma == null ? '—' : r.sigma.toFixed(3) }}</td>
        <td class="py-1 pl-3">
          <!-- Offset POINT with a ±σ interval around it — not a bar from zero.
               A filled bar reads as a magnitude; this reads as an estimate and
               its uncertainty, which is what the numbers actually are. -->
          <div class="relative h-4 w-full">
            <span class="absolute inset-y-0 left-1/2 w-px bg-(--sk-border)" />
            <span
              v-if="r.sigma != null"
              class="absolute top-1/2 h-px -translate-y-1/2 bg-(--sk-brand)/50"
              :style="intervalStyle(r)"
            />
            <span
              class="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-(--sk-brand)"
              :style="{ left: `${pos(r.offset)}%` }"
            />
          </div>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script setup lang="ts">
import type { ToolSkewRow } from '~/utils/skewvoirAnalysis/timeSeries'

const props = defineProps<{
  rows: ToolSkewRow[]
  /** Distinct equipment in the set — distinguishes "one tool" from "no data". */
  toolCount: number
  unit: string
}>()

const signed = (v: number): string => `${v >= 0 ? '+' : ''}${v.toFixed(3)}`

// The track is scaled so the widest reach in the set — offset plus its sigma
// whisker — just fits. Scaling on offset alone would push a noisy tool's
// interval off the end of its row.
const maxAbs = computed(() =>
  props.rows.reduce((m, r) => Math.max(m, Math.abs(r.offset) + (r.sigma ?? 0)), 0) || 1)

/** Percent position across the track, 50% = 세트 기준 (zero). */
const pos = (value: number): number => 50 + (value / maxAbs.value) * 50

const intervalStyle = (r: ToolSkewRow) => {
  const lo = pos(r.offset - (r.sigma ?? 0))
  const hi = pos(r.offset + (r.sigma ?? 0))
  return { left: `${lo}%`, width: `${hi - lo}%` }
}
</script>
```

`σ = —` for a single-measurement tool is the whole point of `sigma: number | null` — do not substitute `0`.

- [ ] **Step 3: Verify**

```bash
npm run typecheck
npm run lint
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/components/ebeam/skewvoir/timeseries/ParamCoverageSelect.vue app/components/ebeam/skewvoir/timeseries/ToolSkewPanel.vue
git commit -m "feat(skewvoir): add the set param selector and tool skew panel"
```

---

### Task 10: Assemble the Time-Series view and verify in the browser

**Files:**

- Modify: `app/components/ebeam/skewvoir/Workspace.vue`
- Rewrite: `app/components/ebeam/skewvoir/views/TimeSeries.vue`

**Interfaces:**

- Consumes: everything from Tasks 6–9.
- Produces: the finished page. Nothing downstream depends on it.

- [ ] **Step 1: Pass the workspace into the view**

`views/TimeSeries.vue` needs `tsView` / `tsAxis` / `tsBaseline` and their setters, which Task 6 put on the **workspace**, not on `analysis`. But `Workspace.vue` currently renders the view with only `:analysis="analysis"` (line 57–60), and `ws` is local to `Workspace.vue`. Without this step the whole template fails to compile.

In `Workspace.vue`, pass `ws` to the Time-Series view only:

```vue
            <EbeamSkewvoirViewsTimeSeries
              v-else-if="ws.activeKind.value === 'time-series'"
              :analysis="analysis"
              :ws="ws"
            />
```

and in `views/TimeSeries.vue`:

```ts
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{
  analysis: SkewvoirAnalysis
  ws: SkewvoirWorkspace
}>()
```

Leave the other five view components untouched — none of them needs `ws`, and widening them all would be churn for nothing.

- [ ] **Step 2: Compose the view**

Reading order is `integrity banner → parameter selector → lens buttons → active chart → Sequence Trend`. Keep the existing `scope !== 'set'` empty state exactly as it is today.

Structure:

```vue
<template>
  <div v-if="analysis.scope.value === 'set'" class="space-y-3">
    <!-- Integrity: what silently fell out of the set, and whether tool skew is
         interpretable at all. Reports; never blocks. -->
    <UAlert
      v-if="integrity.unresolvedMsrs.length"
      color="warning"
      variant="soft"
      :title="`${integrity.unresolvedMsrs.length}개 측정이 이 장비군 검색 결과에 없어 제외되었습니다.`"
    />
    <!-- Resolved but never loaded: POST /api/msr-files silently skips MSRs it
         cannot find, so without this the miss would masquerade as "this
         parameter is absent" and quietly shrink every denominator. -->
    <UAlert
      v-if="integrity.resolved > integrity.loaded"
      color="warning"
      variant="soft"
      :title="`${integrity.resolved - integrity.loaded}개 측정의 파일을 불러오지 못했습니다.`"
    />

    <div class="flex flex-wrap items-center gap-2">
      <EbeamSkewvoirTimeseriesParamCoverageSelect
        :options="analysis.paramOptions.value"
        :model-value="analysis.activeParam.value"
        @update:model-value="ws.setParam($event)"
      />
      <span
        v-if="integrity.recipeCount > 1"
        class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-2 py-1 sk-meta"
      >recipe {{ integrity.recipeCount }}종 혼재 · 장비 차이로 해석하기 어렵습니다</span>
    </div>

    <!-- Lens switch. NOTE: there is no `UButtonGroup` in NuxtUI 4.10 — the
         registry has UFieldGroup and UTabs. This repo's own precedent for
         exactly this control is a hand-rolled tablist with native buttons and
         a roving tabindex; see fdc/SequenceWorkbench.vue. Copy that pattern,
         including its keydown handler, rather than introducing a third idiom.

         Hidden while loading and while there is nothing to show, per the spec:
         an empty tab strip over a spinner offers a choice that does nothing. -->
    <div
      v-if="!analysis.setPending.value && hasAnySetData"
      role="tablist"
      aria-label="Time-Series 보기"
      class="inline-flex w-fit items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
      @keydown="onLensKeydown"
    >
      <button
        v-for="lens in LENSES"
        :key="lens.value"
        type="button"
        role="tab"
        :tabindex="ws.tsView.value === lens.value ? 0 : -1"
        :aria-selected="ws.tsView.value === lens.value"
        @click="ws.setTsView(lens.value)"
      >
        {{ lens.label }}
      </button>
    </div>

    <EbeamSkewvoirPanelFrame :title="activeTitle" :meta="activeMeta" :icon="activeIcon">
      <template v-if="ws.tsView.value === 'trend'" #actions>
        <!-- 시간/순서 + 원시/잔차 + the existing anomaly method controls -->
      </template>

      <div v-if="analysis.setPending.value" class="flex h-72 items-center justify-center gap-2 sk-body">
        <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
        추이 데이터를 불러오는 중…
      </div>

      <EbeamSkewvoirTimeSeriesChart
        v-else-if="ws.tsView.value === 'trend' && analysis.trendPoints.value.length"
        :points="analysis.trendPoints.value"
        :parameter="analysis.activeParam.value"
        :unit="analysis.activeUnit.value"
        :axis-mode="ws.tsAxis.value"
        :baseline="ws.tsBaseline.value"
        @select="analysis.setFocusedMsr($event)"
      />

      <EbeamSkewvoirDistributionChart
        v-else-if="ws.tsView.value === 'dist' && analysis.distributionGroups.value.length"
        :groups="analysis.distributionGroups.value"
        :unit="analysis.activeUnit.value"
        mode="Box"
        rotate-labels
        zoomable
      />

      <EbeamSkewvoirTimeseriesToolSkewPanel
        v-else-if="ws.tsView.value === 'skew'"
        :rows="analysis.toolSkewRows.value"
        :tool-count="analysis.toolCount.value"
        :unit="analysis.activeUnit.value"
      />

      <div v-else class="flex h-72 items-center justify-center sk-body">
        비교할 측정을 추가하세요.
      </div>
    </EbeamSkewvoirPanelFrame>

    <!-- Sequence Trend: measurement-INTERNAL order, a different axis from the
         three lenses above, so it stays put rather than joining the switch. -->
    <EbeamSkewvoirPanelFrame title="Sequence Trend" :meta="`focus · ${analysis.focusRow.value?.lot_id ?? '—'}`" icon="i-lucide-activity">
      <!-- unchanged from the current file -->
    </EbeamSkewvoirPanelFrame>
  </div>

  <div v-else class="dashboard-surface flex h-72 flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 text-center">
    <p class="sk-title">Time-Series</p>
    <p class="sk-body">MSR을 2개 이상 선택하면 측정 간 추이를 비교합니다.</p>
  </div>
</template>
```

The trend panel's `#actions` slot keeps the existing anomaly method `USelect` and threshold `UInput`s from the current file — move them, do not rewrite them — and adds two small toggles bound to `ws.tsAxis` / `ws.tsBaseline`. Use plain `UButton`s (`variant="soft"` when active, `variant="ghost"` when not), matching how `SequenceWorkbench.vue` renders its inline controls.

The script block needs:

```ts
const LENSES = [
  { value: 'trend' as const, label: '추이' },
  { value: 'dist' as const, label: '분포' },
  { value: 'skew' as const, label: '장비 skew' }
]

// Whether ANY lens has something to draw. Gates the tab strip so a set that
// resolved to nothing does not offer three empty choices.
const hasAnySetData = computed(() =>
  props.analysis.trendPoints.value.length > 0
  || props.analysis.distributionGroups.value.length > 0
)
```

plus `activeTitle` / `activeMeta` / `activeIcon` computeds switching on `ws.tsView.value`, and an `onLensKeydown` roving-focus handler copied from `fdc/SequenceWorkbench.vue`.

Panel meta strings must report what was dropped, per the spec: `n/총` for measurements missing the parameter, the count of measurements with fewer than 4 measured sites (distribution lens), and — for the trend lens in `time` mode only — the count of measurements the time axis could not place because their timestamp would not parse (the `points.length - placed.length` figure Task 7 exposes).

- [ ] **Step 3: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: clean.

- [ ] **Step 4: Run the backend suite to confirm no backend impact**

From the repo root:

```bash
.venv/bin/python -m pytest -q
```

Expected: passing at the pre-existing baseline. This plan changes no Python; run it to confirm that claim rather than assert it.

- [ ] **Step 5: Verify in the browser**

Use the `verify` skill to start Flask on :5050 and Nuxt on :3000, then walk the real path:

1. Open `/ebeam/cd-sem/skewvoir`, search, and check **4+ measurements** across at least two different `eqp_id`s.
2. Click **Time-Series** in 측정 작업 세트. Confirm you land on `view=time-series&scope=set` with the trend lens active.
3. Confirm the parameter selector shows coverage (`WAFER · n/m`) and that switching to a parameter the focus measurement lacks **sticks** — this is the Task 2 rule; before the change the URL would snap back.
4. Toggle 시간 ↔ 순서. Confirm point spacing changes and the axis type changes with it.
5. Toggle 원시값 ↔ 잔차. Confirm the y-axis name becomes `Δ vs 세트 기준` and the min/max band moves with the mean rather than staying behind.
6. Confirm each `eqp_id` draws its **own line** (measurements from different tools are not joined), while individual points still carry verdict colors — a flagged measurement stays red/amber regardless of which tool it came from.
7. Click a point. Confirm the focus moves to that MSR (left rail identity updates), and that the point you clicked is the measurement you land on.
8. Switch to 분포. Confirm one box per measurement, raw points overlaid, labels rotated and zoom present.
9. Switch to 장비 skew. Confirm tools are sorted most-skewed first, that each row shows an offset **point with a ±σ interval** (not a bar from zero), and that a single-measurement tool shows `σ = —`.
10. Select measurements from **one** tool only and confirm the skew lens says 단일 장비 · 비교 대상 없습니다.
11. Deep-link a URL with an `msrs` id that does not exist, and confirm the integrity banner counts it rather than the set silently shrinking.
12. Copy the URL, open it in a new tab, and confirm the lens, axis mode, baseline, and parameter all come back.

Save screenshots under `.playwright-mcp/screenshots/`.

- [ ] **Step 6: Commit**

```bash
git add app/components/ebeam/skewvoir/Workspace.vue app/components/ebeam/skewvoir/views/TimeSeries.vue
git commit -m "feat(skewvoir): assemble the three-lens Time-Series page"
```

- [ ] **Step 7: Land the work and tear down the worktree**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/timeseries && git push
git worktree remove ../skewnono-timeseries && git branch -d work/timeseries
git worktree list   # must show the main tree alone
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: lens buttons + `tsview` (1, 10), set-scope parameter rule (2, 6), trend with time/order axis and raw/residual (3, 6, 7), no control limits (3 — they are simply never built), distribution lens (4, 8, 10), tool skew with `σ = —` (4, 9), set-aware selector with coverage (5, 9), integrity banner and recipe badge (5, 10), `msrs` dedupe (1), verification limits (10 step 4 exercises what home can actually show).

**Known gaps carried deliberately.** The spec's 알려진 선행 이슈 — the set loader's missing request-generation guard — is not fixed here and no task claims to. The 검증 한계 stand: the mock gives CD values no equipment dependence, so step 4.8 verifies the skew lens's *wiring*, not its reading.

**Type consistency.** `TrendPoint` is defined once in Task 3 and consumed by Tasks 4, 6, 7. `SetParamOption` (Task 5) is deliberately *not* named `ParamCoverage`, which `utils/overview.ts` already owns. `TrendRowInput` gains `recipeName` in Task 5 via `IntegrityRowInput`; Task 6 builds one `trendRowInputs` array carrying `recipeName`, which satisfies both. `sigma: number | null` is null-for-n<2 in Task 4 and rendered `—` in Task 9.

**All API assumptions were checked against this checkout before the plan was finalised**, so no task starts on a guess:

- `app/utils/anomaly/index.ts` exists → Task 3 imports `'../anomaly/index.ts'`.
- `useEchart` exposes only `onClick(name)` and `onGridClick(xValue, gridIndex)`, neither carrying a data index → Task 7 adds `onDataIndex` with the exact code to write.
- **`UButtonGroup` does not exist in NuxtUI 4.10** (the registry has `UFieldGroup` and `UTabs`). This repo's own precedent for a lens switch is a hand-rolled `role="tablist"` with native buttons in `fdc/SequenceWorkbench.vue` → Task 10 copies that, including the roving-tabindex keydown handler.
- `nuxt typecheck` includes `../app/**/*`, which covers `*.test.ts` → fixtures must satisfy their declared types. That is why `DistFileInput.rows` is a minimal `DistSiteInput[]` rather than `MsrFileRow[]`: a 20-field row type would make every fixture a liability.

**One assumption left for the implementer to confirm at the keyboard**, called out inline in Task 9: the NuxtUI `USelectMenu` prop names (`items` / `value-key`) should be matched against a working call site such as `search/FacetSelect.vue` rather than trusted from this plan.

**Two places where the plan deliberately makes a pure function stricter than "just return the data".** `buildToolSkew` returns `[]` for a single-tool set rather than one ≈0 row, because an offset against a baseline the tool itself defines reads as "this tool agrees with its peers" when it has none — the spec requires a unit test proving no row is produced. `distinctToolCount` exists solely so the panel can tell that case apart from "no data", since both hand it an empty array.

**One cross-task hazard worth re-reading before Task 7.** Splitting the trend into one series per tool changes what `dataIndex` means, which breaks both the click handler and the existing tooltip `formatter` — Task 7 fixes the first with `msrGrid` and explicitly flags the second. Neither is optional; leaving the old index lookup shows the wrong measurement's numbers.
