# Anomaly Convention — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared abnormality-detection convention (verdict model, two scoring methods, peer detector, combine, badge/legend/tokens) and prove it on the skewvoir `AnalyzePanel` time-series chart.

**Architecture:** Two orthogonal axes — a *comparison base* (this plan ships `peer`) that produces a leave-one-out center, and a user-selectable *scoring method* (`range` = ±% band, authoritative; `stddev` = ±kσ, diagnostic) that bands the distance. Pure framework-free utils under `app/utils/anomaly/` (node --test), thin render-only components under `app/components/sk/`. Replaces the existing `madOutliers.ts` boolean recolor.

**Tech Stack:** Nuxt 4 + NuxtUI, TypeScript, ECharts (via `useEchart`), `node --test` (Node 24 native TS strip).

Spec: `docs/superpowers/specs/2026-06-27-anomaly-convention-design.md`.

## Global Constraints

- **Package manager: npm** (`npm --prefix front-dev-home <script>`). Never bun.
- **Test runner:** `npm --prefix front-dev-home test` runs `node --test "app/**/*.test.ts"`. Single file: `cd front-dev-home && node --test app/utils/anomaly/<name>.test.ts`. Test files import siblings with the **`.ts` extension** (e.g. `./types.ts`).
- **Vocabulary:** all user-facing strings (reason/legend/labels) use Korean **평균 / 표준편차 / 범위 / % 초과 / σ**. The terms **z-score / modified z-score / MAD are forbidden** in code and copy.
- **Range is authoritative**; stddev is a diagnostic lens. Badge/summary/triage always reflect the active method but range is the default.
- **Leave-one-out (LOO)**: peer/sibling centers exclude the judged point — this is mandatory (prevents masking).
- **Component auto-import prefixes the folder**: `app/components/sk/AnomalyBadge.vue` registers as `SkAnomalyBadge`. Do not prefix the filename.
- **`<template>` before `<script setup>`**; Composition API only.
- **Tailwind v4 canonical tokens**; muted text uses `--sk-ink-*` semantic vars, not raw `text-zinc-*`.
- Out of scope (Phase 2 / later): `siblingDivergence`, `recentShift`, retrofitting device-statistics + FdcAnalysis, calibration automation.

---

### Task 1: Verdict contract + defaults (`types.ts`)

**Files:**
- Create: `front-dev-home/app/utils/anomaly/types.ts`
- Create: `front-dev-home/app/utils/anomaly/index.ts`
- Test: `front-dev-home/app/utils/anomaly/types.test.ts`

**Interfaces:**
- Produces: `EvalStatus`, `Severity`, `ScoringMethod`, `AnomalySignal`, `AnomalyVerdict`, `CombinedVerdict`, `RangeConfig`, `StddevConfig`, `MethodConfig`, `DEFAULT_RANGE`, `DEFAULT_STDDEV`, `DEFAULT_METHOD_CONFIG`, `PEER_MIN_N`.

- [ ] **Step 1: Write the failing test**

```ts
// front-dev-home/app/utils/anomaly/types.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_RANGE, DEFAULT_STDDEV, DEFAULT_METHOD_CONFIG, PEER_MIN_N
} from './types.ts'

test('range defaults: 10/20% with a div-by-zero guard', () => {
  assert.equal(DEFAULT_RANGE.watchPct, 10)
  assert.equal(DEFAULT_RANGE.abnormalPct, 20)
  assert.ok(DEFAULT_RANGE.minAbsCenter > 0)
})

test('stddev defaults: 2/3 sigma', () => {
  assert.equal(DEFAULT_STDDEV.watchK, 2)
  assert.equal(DEFAULT_STDDEV.abnormalK, 3)
})

test('default method is range (authoritative)', () => {
  assert.equal(DEFAULT_METHOD_CONFIG.method, 'range')
})

test('peer minN: looser for range than stddev', () => {
  assert.equal(PEER_MIN_N.range, 3)
  assert.equal(PEER_MIN_N.stddev, 5)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/anomaly/types.test.ts`
Expected: FAIL — cannot find module `./types.ts`.

- [ ] **Step 3: Write the types + defaults**

```ts
// front-dev-home/app/utils/anomaly/types.ts
// Shared abnormality-detection contract. Pure types + defaults, no framework deps.
// status and severity are SEPARATE axes: status = "did detection run?",
// severity = "how abnormal?" (only meaningful when evaluated).

export type EvalStatus = 'evaluated' | 'insufficient'
export type Severity = 'normal' | 'watch' | 'abnormal'
export type ScoringMethod = 'range' | 'stddev'
export type AnomalySignal = 'peer' | 'sibling' | 'recent-shift'

export interface AnomalyVerdict {
  status: EvalStatus
  severity: Severity      // valid only when status === 'evaluated'
  method: ScoringMethod   // decides the unit of `score`
  score: number           // range → signed % deviation; stddev → signed σ (NaN when insufficient)
  reason: string          // Korean, value-bearing
  metric: string          // 'mean' | 'spread' | ...
  signal: AnomalySignal
}

export interface CombinedVerdict {
  status: EvalStatus
  severity: Severity
  verdicts: AnomalyVerdict[]
}

export interface RangeConfig {
  watchPct: number
  abnormalPct: number
  minAbsCenter: number    // |center| below this → insufficient (zero-centred metric guard)
}
export interface StddevConfig {
  watchK: number
  abnormalK: number
}
export interface MethodConfig {
  method: ScoringMethod
  range: RangeConfig
  stddev: StddevConfig
}

export const DEFAULT_RANGE: RangeConfig = { watchPct: 10, abnormalPct: 20, minAbsCenter: 1e-6 }
export const DEFAULT_STDDEV: StddevConfig = { watchK: 2, abnormalK: 3 }
export const DEFAULT_METHOD_CONFIG: MethodConfig = {
  method: 'range',
  range: DEFAULT_RANGE,
  stddev: DEFAULT_STDDEV
}

// Effective minimum sample size per method (stddev needs more to estimate spread).
export const PEER_MIN_N: Record<ScoringMethod, number> = { range: 3, stddev: 5 }
```

- [ ] **Step 4: Create the barrel re-export**

```ts
// front-dev-home/app/utils/anomaly/index.ts
export * from './types.ts'
export * from './score.ts'
export * from './peer.ts'
export * from './combine.ts'
```

> Note: `score.ts`, `peer.ts`, `combine.ts` arrive in Tasks 2–4. Nuxt's auto-import resolves `~/utils/anomaly` to this barrel; the missing siblings only matter once imported, which happens in Task 7.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/anomaly/types.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/anomaly/types.ts front-dev-home/app/utils/anomaly/index.ts front-dev-home/app/utils/anomaly/types.test.ts
git commit -m "feat(anomaly): verdict contract types + method defaults"
```

---

### Task 2: Scoring methods (`score.ts`)

**Files:**
- Create: `front-dev-home/app/utils/anomaly/score.ts`
- Test: `front-dev-home/app/utils/anomaly/score.test.ts`

**Interfaces:**
- Consumes: `RangeConfig`, `StddevConfig`, `Severity` from `./types.ts`.
- Produces: `ScorePart` (`{ status, severity, score, reason }`), `bandRange(absDevPct, cfg)`, `bandStddev(absK, cfg)`, `scoreByRange(value, center, cfg, tag?)`, `scoreByStddev(value, mean, std, cfg, tag?)`.

- [ ] **Step 1: Write the failing test**

```ts
// front-dev-home/app/utils/anomaly/score.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { scoreByRange, scoreByStddev, bandRange, bandStddev } from './score.ts'
import { DEFAULT_RANGE, DEFAULT_STDDEV } from './types.ts'

test('range bands: normal < 10%, watch 10–20%, abnormal ≥ 20%', () => {
  assert.equal(bandRange(5, DEFAULT_RANGE), 'normal')
  assert.equal(bandRange(10, DEFAULT_RANGE), 'watch')
  assert.equal(bandRange(15, DEFAULT_RANGE), 'watch')
  assert.equal(bandRange(20, DEFAULT_RANGE), 'abnormal')
})

test('range: +14% over center 10 → watch, score is signed %', () => {
  const r = scoreByRange(11.4, 10, DEFAULT_RANGE)
  assert.equal(r.status, 'evaluated')
  assert.equal(r.severity, 'watch')
  assert.ok(Math.abs(r.score - 14) < 1e-6)
  assert.match(r.reason, /\+14/)
  assert.match(r.reason, /실측 11.4/)
})

test('range: |center| below minAbsCenter → insufficient', () => {
  const r = scoreByRange(0.001, 0, DEFAULT_RANGE)
  assert.equal(r.status, 'insufficient')
})

test('range: negative deviation keeps the sign', () => {
  const r = scoreByRange(8, 10, DEFAULT_RANGE) // -20%
  assert.equal(r.severity, 'abnormal')
  assert.ok(r.score < 0)
})

test('stddev bands: normal < 2σ, watch 2–3σ, abnormal ≥ 3σ', () => {
  assert.equal(bandStddev(1.5, DEFAULT_STDDEV), 'normal')
  assert.equal(bandStddev(2, DEFAULT_STDDEV), 'watch')
  assert.equal(bandStddev(3, DEFAULT_STDDEV), 'abnormal')
})

test('stddev: std=0 and equal value → normal, score 0', () => {
  const r = scoreByStddev(10, 10, 0, DEFAULT_STDDEV)
  assert.equal(r.severity, 'normal')
  assert.equal(r.score, 0)
})

test('stddev: std=0 with a different value → abnormal, score is absolute delta', () => {
  const r = scoreByStddev(12, 10, 0, DEFAULT_STDDEV)
  assert.equal(r.severity, 'abnormal')
  assert.equal(r.score, 2)
  assert.match(r.reason, /표준편차 0/)
})

test('non-finite input → insufficient', () => {
  assert.equal(scoreByRange(NaN, 10, DEFAULT_RANGE).status, 'insufficient')
  assert.equal(scoreByStddev(10, NaN, 1, DEFAULT_STDDEV).status, 'insufficient')
})

test('reason never contains forbidden vocabulary', () => {
  const r = scoreByStddev(13, 10, 1, DEFAULT_STDDEV)
  assert.doesNotMatch(r.reason, /z-score|MAD/i)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/anomaly/score.test.ts`
Expected: FAIL — cannot find module `./score.ts`.

- [ ] **Step 3: Write the implementation**

```ts
// front-dev-home/app/utils/anomaly/score.ts
// Two interchangeable scoring methods that band a value's distance from a center.
// Both return the same ScorePart shape so any comparison base can use either.
import type { RangeConfig, Severity, StddevConfig } from './types.ts'

export interface ScorePart {
  status: 'evaluated' | 'insufficient'
  severity: Severity
  score: number
  reason: string
}

const r = (n: number, d = 2): number => Number(n.toFixed(d))
const sgn = (n: number): string => (n >= 0 ? '+' : '')

const INSUFFICIENT: ScorePart = {
  status: 'insufficient', severity: 'normal', score: NaN, reason: '표본 부족 — 미평가'
}

export const bandRange = (absDevPct: number, cfg: RangeConfig): Severity =>
  absDevPct < cfg.watchPct ? 'normal' : absDevPct < cfg.abnormalPct ? 'watch' : 'abnormal'

export const bandStddev = (absK: number, cfg: StddevConfig): Severity =>
  absK < cfg.watchK ? 'normal' : absK < cfg.abnormalK ? 'watch' : 'abnormal'

// Range (authoritative): % deviation from a LOO center. `tag` is a Korean prefix
// for the reason (e.g. '산포' for the spread metric); empty for the mean metric.
export const scoreByRange = (
  value: number, center: number, cfg: RangeConfig, tag = ''
): ScorePart => {
  if (!Number.isFinite(value) || !Number.isFinite(center) || Math.abs(center) < cfg.minAbsCenter) {
    return INSUFFICIENT
  }
  const devPct = ((value - center) / Math.abs(center)) * 100
  const severity = bandRange(Math.abs(devPct), cfg)
  const pre = tag ? `${tag} ` : ''
  const exceed = severity === 'normal' ? '' : ' 초과'
  const reason = `${pre}나머지 평균 ${r(center)} 대비 ${sgn(devPct)}${r(devPct, 1)}% (실측 ${r(value)}) · 허용 ±${cfg.watchPct}%${exceed}`
  return { status: 'evaluated', severity, score: devPct, reason }
}

// Stddev (diagnostic): classic (value − mean) / std against a LOO center.
export const scoreByStddev = (
  value: number, mean: number, std: number, cfg: StddevConfig, tag = ''
): ScorePart => {
  if (!Number.isFinite(value) || !Number.isFinite(mean) || !Number.isFinite(std)) {
    return INSUFFICIENT
  }
  const pre = tag ? `${tag} ` : ''
  if (std === 0) {
    if (value === mean) {
      return { status: 'evaluated', severity: 'normal', score: 0, reason: `${pre}나머지 동일값, 편차 없음` }
    }
    const delta = value - mean
    return {
      status: 'evaluated', severity: 'abnormal', score: delta,
      reason: `${pre}표준편차 0 기준에서 이탈, Δ ${sgn(delta)}${r(delta)}`
    }
  }
  const k = (value - mean) / std
  const severity = bandStddev(Math.abs(k), cfg)
  const exceed = severity === 'normal' ? '' : ` · ±${cfg.abnormalK}σ 초과`
  const reason = `${pre}나머지 평균 ${r(mean)}, 표준편차 ${r(std)} · ${sgn(k)}${r(k)}σ (실측 ${r(value)})${exceed}`
  return { status: 'evaluated', severity, score: k, reason }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/anomaly/score.test.ts`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/anomaly/score.ts front-dev-home/app/utils/anomaly/score.test.ts
git commit -m "feat(anomaly): range + stddev scoring methods with banding"
```

---

### Task 3: Peer detector with LOO + masking fixtures (`peer.ts`)

**Files:**
- Create: `front-dev-home/app/utils/anomaly/peer.ts`
- Test: `front-dev-home/app/utils/anomaly/peer.test.ts`

**Interfaces:**
- Consumes: `AnomalyVerdict`, `MethodConfig`, `PEER_MIN_N` from `./types.ts`; `scoreByRange`, `scoreByStddev` from `./score.ts`.
- Produces: `PeerOptions` (`{ config: MethodConfig, metric: string, tag?: string, minN?: number }`), `peerVerdicts(values: number[], opts: PeerOptions): AnomalyVerdict[]`.

- [ ] **Step 1: Write the failing test (includes the required masking fixtures)**

```ts
// front-dev-home/app/utils/anomaly/peer.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { peerVerdicts } from './peer.ts'
import { DEFAULT_METHOD_CONFIG, type MethodConfig } from './types.ts'

const rangeCfg: MethodConfig = DEFAULT_METHOD_CONFIG
const stddevCfg: MethodConfig = { ...DEFAULT_METHOD_CONFIG, method: 'stddev' }

test('below minN → all insufficient (length preserved)', () => {
  const v = peerVerdicts([10, 11], { config: rangeCfg, metric: 'mean' })
  assert.equal(v.length, 2)
  assert.ok(v.every(x => x.status === 'insufficient'))
})

test('clean series → all normal', () => {
  const v = peerVerdicts([10, 10, 10, 10, 10], { config: rangeCfg, metric: 'mean' })
  assert.ok(v.every(x => x.status === 'evaluated' && x.severity === 'normal'))
})

test('MASKING N=5: a true +20% outlier is abnormal thanks to LOO', () => {
  // Non-LOO (center includes the point) would show only +15.4% → missed.
  const v = peerVerdicts([10, 10, 10, 10, 12], { config: rangeCfg, metric: 'mean' })
  assert.equal(v[4]!.severity, 'abnormal')
  assert.ok(v.slice(0, 4).every(x => x.severity === 'normal'))
})

test('MASKING N=15: lone outlier still abnormal under LOO', () => {
  const vals = Array(14).fill(10).concat([12])
  const v = peerVerdicts(vals, { config: rangeCfg, metric: 'mean' })
  assert.equal(v[14]!.severity, 'abnormal')
})

test('MASKING: two co-directional outliers both flagged (LOO)', () => {
  const v = peerVerdicts([10, 10, 10, 10, 10, 12.5, 12.5], { config: rangeCfg, metric: 'mean' })
  assert.equal(v[5]!.severity, 'abnormal')
  assert.equal(v[6]!.severity, 'abnormal')
})

test('stddev method: lone extreme is flagged under LOO at N=7', () => {
  const v = peerVerdicts([50, 51, 49, 50, 52, 48, 90], { config: stddevCfg, metric: 'mean' })
  assert.equal(v[6]!.severity, 'abnormal')
  assert.equal(v[6]!.method, 'stddev')
})

test('verdict carries metric, signal=peer, and active method', () => {
  const v = peerVerdicts([10, 10, 10, 20], { config: rangeCfg, metric: 'spread', tag: '산포' })
  assert.equal(v[3]!.metric, 'spread')
  assert.equal(v[3]!.signal, 'peer')
  assert.equal(v[3]!.method, 'range')
  assert.match(v[3]!.reason, /산포/)
})

test('non-finite entries → that item insufficient, others evaluated', () => {
  const v = peerVerdicts([10, 10, 10, 10, NaN], { config: rangeCfg, metric: 'mean' })
  assert.equal(v[4]!.status, 'insufficient')
  assert.ok(v.slice(0, 4).every(x => x.status === 'evaluated'))
})

test('effective N after excluding missing drops below minN → all insufficient', () => {
  const v = peerVerdicts([10, 10, NaN, NaN], { config: rangeCfg, metric: 'mean' })
  assert.ok(v.every(x => x.status === 'insufficient'))
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/anomaly/peer.test.ts`
Expected: FAIL — cannot find module `./peer.ts`.

- [ ] **Step 3: Write the implementation**

```ts
// front-dev-home/app/utils/anomaly/peer.ts
// Peer comparison base: judge each value against the LEAVE-ONE-OUT mean of the
// others (and, for stddev, their LOO sample std). LOO is what prevents an
// outlier from inflating its own band and masking itself.
import type { AnomalyVerdict, MethodConfig } from './types.ts'
import { PEER_MIN_N } from './types.ts'
import { scoreByRange, scoreByStddev } from './score.ts'

export interface PeerOptions {
  config: MethodConfig
  metric: string          // 'mean' | 'spread'
  tag?: string            // Korean reason prefix, e.g. '산포'
  minN?: number
}

// Mean + sample std (n-1) of all finite entries except index `skip`.
const looStats = (values: number[], skip: number): { mean: number, std: number } | null => {
  const others: number[] = []
  for (let i = 0; i < values.length; i++) {
    if (i === skip) continue
    const v = values[i]!
    if (Number.isFinite(v)) others.push(v)
  }
  if (others.length < 1) return null
  const mean = others.reduce((s, v) => s + v, 0) / others.length
  const std = others.length > 1
    ? Math.sqrt(others.reduce((s, v) => s + (v - mean) ** 2, 0) / (others.length - 1))
    : 0
  return { mean, std }
}

export const peerVerdicts = (values: number[], opts: PeerOptions): AnomalyVerdict[] => {
  const { config, metric, tag = '' } = opts
  const method = config.method
  const minN = opts.minN ?? PEER_MIN_N[method]

  const insufficient = (): AnomalyVerdict => ({
    status: 'insufficient', severity: 'normal', method, score: NaN,
    reason: '표본 부족 — 미평가', metric, signal: 'peer'
  })

  // Re-check N after dropping non-finite values (Codex #8): too few real points → none evaluated.
  const finiteCount = values.filter(Number.isFinite).length
  if (finiteCount < minN) return values.map(insufficient)

  return values.map((value, i) => {
    if (!Number.isFinite(value)) return insufficient()
    const stats = looStats(values, i)
    if (!stats) return insufficient()
    const part = method === 'range'
      ? scoreByRange(value, stats.mean, config.range, tag)
      : scoreByStddev(value, stats.mean, stats.std, config.stddev, tag)
    return { ...part, method, metric, signal: 'peer' as const }
  })
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/anomaly/peer.test.ts`
Expected: PASS (9 tests). If any masking test fails, the LOO exclusion is wrong — do **not** relax the assertion.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/anomaly/peer.ts front-dev-home/app/utils/anomaly/peer.test.ts
git commit -m "feat(anomaly): peer detector with leave-one-out centering + masking fixtures"
```

---

### Task 4: Combine verdicts (`combine.ts`)

**Files:**
- Create: `front-dev-home/app/utils/anomaly/combine.ts`
- Test: `front-dev-home/app/utils/anomaly/combine.test.ts`

**Interfaces:**
- Consumes: `AnomalyVerdict`, `CombinedVerdict`, `Severity` from `./types.ts`.
- Produces: `combineVerdicts(verdicts: AnomalyVerdict[]): CombinedVerdict`.

- [ ] **Step 1: Write the failing test**

```ts
// front-dev-home/app/utils/anomaly/combine.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { combineVerdicts } from './combine.ts'
import type { AnomalyVerdict } from './types.ts'

const mk = (over: Partial<AnomalyVerdict>): AnomalyVerdict => ({
  status: 'evaluated', severity: 'normal', method: 'range', score: 0,
  reason: 'r', metric: 'mean', signal: 'peer', ...over
})

test('worst-of severity wins among evaluated', () => {
  const c = combineVerdicts([mk({ severity: 'normal' }), mk({ severity: 'abnormal', score: 25 })])
  assert.equal(c.status, 'evaluated')
  assert.equal(c.severity, 'abnormal')
})

test('insufficient is ignored for severity but preserved in the array', () => {
  const c = combineVerdicts([mk({ severity: 'normal' }), mk({ status: 'insufficient', score: NaN })])
  assert.equal(c.severity, 'normal')           // NOT hidden under insufficient
  assert.equal(c.verdicts.length, 2)           // the insufficient one survives
})

test('all insufficient → combined insufficient', () => {
  const c = combineVerdicts([mk({ status: 'insufficient' }), mk({ status: 'insufficient' })])
  assert.equal(c.status, 'insufficient')
})

test('evaluated sorted before insufficient; ties broken by |score|', () => {
  const c = combineVerdicts([
    mk({ status: 'insufficient', score: NaN }),
    mk({ severity: 'watch', score: 12 }),
    mk({ severity: 'watch', score: 18 })
  ])
  assert.equal(c.verdicts[0]!.score, 18)       // larger |score| first
  assert.equal(c.verdicts[2]!.status, 'insufficient')
})

test('empty input → insufficient', () => {
  assert.equal(combineVerdicts([]).status, 'insufficient')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/anomaly/combine.test.ts`
Expected: FAIL — cannot find module `./combine.ts`.

- [ ] **Step 3: Write the implementation**

```ts
// front-dev-home/app/utils/anomaly/combine.ts
// Reduce several signals on one item to a single CombinedVerdict.
// worst-of severity over EVALUATED verdicts only; insufficient ones are kept in
// the array (so "a detector couldn't run" survives, not buried under normal).
import type { AnomalyVerdict, CombinedVerdict, Severity } from './types.ts'

const RANK: Record<Severity, number> = { normal: 0, watch: 1, abnormal: 2 }

export const combineVerdicts = (verdicts: AnomalyVerdict[]): CombinedVerdict => {
  const sorted = [...verdicts].sort((a, b) => {
    if (a.status !== b.status) return a.status === 'evaluated' ? -1 : 1
    const dr = RANK[b.severity] - RANK[a.severity]
    if (dr !== 0) return dr
    const sa = Number.isFinite(a.score) ? Math.abs(a.score) : -1
    const sb = Number.isFinite(b.score) ? Math.abs(b.score) : -1
    return sb - sa
  })

  const evaluated = verdicts.filter(v => v.status === 'evaluated')
  if (evaluated.length === 0) {
    return { status: 'insufficient', severity: 'normal', verdicts: sorted }
  }
  const severity = evaluated.reduce<Severity>(
    (worst, v) => (RANK[v.severity] > RANK[worst] ? v.severity : worst),
    'normal'
  )
  return { status: 'evaluated', severity, verdicts: sorted }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/anomaly/combine.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the whole anomaly suite + typecheck**

Run: `npm --prefix front-dev-home test` then `npm --prefix front-dev-home run typecheck`
Expected: all anomaly tests PASS; typecheck clean.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/anomaly/combine.ts front-dev-home/app/utils/anomaly/combine.test.ts
git commit -m "feat(anomaly): combineVerdicts worst-of with insufficient preserved"
```

---

### Task 5: `--sk-warn` token + `SkAnomalyBadge`

**Files:**
- Modify: `front-dev-home/app/assets/css/main.css` (light block after `:114`, dark block after `:172`)
- Create: `front-dev-home/app/components/sk/AnomalyBadge.vue`

**Interfaces:**
- Consumes: `AnomalyVerdict`, `CombinedVerdict` from `~/utils/anomaly`.
- Produces: `<SkAnomalyBadge :verdict :compact />` — renders nothing for null/evaluated-normal; grey dot for insufficient; amber/red dot (+ optional Korean label + reason tooltip) otherwise.

- [ ] **Step 1: Add the amber token (light mode)**

In `main.css`, immediately after the `--sk-bad-border: …;` line in the `:root` block (currently line 114), add:

```css
  --sk-warn: oklch(0.70 0.15 75);
  --sk-warn-soft: oklch(0.94 0.06 85);
  --sk-warn-border: oklch(0.70 0.15 75 / 0.32);
```

- [ ] **Step 2: Add the amber token (dark mode)**

In `main.css`, immediately after the dark-block `--sk-bad-border: …;` line (currently line 172), add:

```css
  --sk-warn: oklch(0.80 0.15 78);
  --sk-warn-soft: oklch(0.34 0.06 78);
  --sk-warn-border: oklch(0.80 0.15 78 / 0.32);
```

- [ ] **Step 3: Write the badge component**

```vue
<!-- front-dev-home/app/components/sk/AnomalyBadge.vue -->
<template>
  <UTooltip
    v-if="show"
    :text="tooltip"
  >
    <span class="inline-flex items-center gap-1 align-middle">
      <span
        class="inline-block rounded-full"
        :class="compact ? 'h-2 w-2' : 'h-2.5 w-2.5'"
        :style="{ backgroundColor: colorVar }"
      />
      <span
        v-if="!compact && label"
        class="text-[10.5px] font-medium"
        :style="{ color: colorVar }"
      >{{ label }}</span>
    </span>
  </UTooltip>
</template>

<script setup lang="ts">
import type { AnomalyVerdict, CombinedVerdict } from '~/utils/anomaly'

const props = withDefaults(defineProps<{
  verdict: CombinedVerdict | AnomalyVerdict | null
  compact?: boolean
}>(), { compact: false })

const isCombined = (v: CombinedVerdict | AnomalyVerdict): v is CombinedVerdict => 'verdicts' in v

const status = computed(() => props.verdict?.status ?? 'evaluated')
const severity = computed(() => props.verdict?.severity ?? 'normal')

// status first, then severity. Silence (render nothing) for evaluated-normal.
const show = computed(() =>
  !!props.verdict && (status.value === 'insufficient' || severity.value !== 'normal')
)

const reasons = computed<string[]>(() => {
  const v = props.verdict
  if (!v) return []
  return isCombined(v) ? v.verdicts.map(x => x.reason) : [v.reason]
})
const tooltip = computed(() => reasons.value.join(' · '))

const label = computed(() =>
  status.value === 'insufficient'
    ? '미평가'
    : severity.value === 'abnormal' ? '이상' : severity.value === 'watch' ? '주의' : ''
)

const colorVar = computed(() =>
  status.value === 'insufficient'
    ? 'var(--sk-ink-subtle)'
    : severity.value === 'abnormal' ? 'var(--sk-bad)' : severity.value === 'watch' ? 'var(--sk-warn)' : 'transparent'
)
</script>
```

- [ ] **Step 4: Verify it compiles (typecheck + lint)**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: no errors referencing `AnomalyBadge.vue` or `main.css`.

> Per the spec, render-only components carry no unit test — they're verified by typecheck/lint here and Playwright in Task 9.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/assets/css/main.css front-dev-home/app/components/sk/AnomalyBadge.vue
git commit -m "feat(anomaly): --sk-warn token + SkAnomalyBadge"
```

---

### Task 6: `SkAnomalyLegend`

**Files:**
- Create: `front-dev-home/app/components/sk/AnomalyLegend.vue`

**Interfaces:**
- Consumes: `RangeConfig`, `StddevConfig`, `ScoringMethod` from `~/utils/anomaly`.
- Produces: `<SkAnomalyLegend :method :range :stddev />` — shows the scale + active thresholds in the active method's vocabulary.

- [ ] **Step 1: Write the legend component**

```vue
<!-- front-dev-home/app/components/sk/AnomalyLegend.vue -->
<template>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-(--sk-ink-muted)">
    <span class="inline-flex items-center gap-1">
      <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: 'var(--sk-warn)' }" />
      주의 {{ watchLabel }}
    </span>
    <span class="inline-flex items-center gap-1">
      <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: 'var(--sk-bad)' }" />
      이상 {{ abnormalLabel }}
    </span>
    <span class="inline-flex items-center gap-1">
      <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: 'var(--sk-ink-subtle)' }" />
      미평가
    </span>
    <span class="text-(--sk-ink-subtle)">· 사용자 허용범위 ({{ methodLabel }})</span>
  </div>
</template>

<script setup lang="ts">
import type { RangeConfig, ScoringMethod, StddevConfig } from '~/utils/anomaly'

const props = defineProps<{
  method: ScoringMethod
  range: RangeConfig
  stddev: StddevConfig
}>()

const methodLabel = computed(() => (props.method === 'range' ? '범위' : '표준편차 · 진단'))
const watchLabel = computed(() =>
  props.method === 'range' ? `±${props.range.watchPct}%` : `±${props.stddev.watchK}σ`
)
const abnormalLabel = computed(() =>
  props.method === 'range' ? `±${props.range.abnormalPct}% 초과` : `±${props.stddev.abnormalK}σ 초과`
)
</script>
```

- [ ] **Step 2: Verify it compiles**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: no errors referencing `AnomalyLegend.vue`.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/sk/AnomalyLegend.vue
git commit -m "feat(anomaly): SkAnomalyLegend showing active method + thresholds"
```

---

### Task 7: Wire `AnalyzePanel` — method state, peer verdicts, controls

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/AnalyzePanel.vue`

**Interfaces:**
- Consumes: `peerVerdicts`, `combineVerdicts`, `DEFAULT_RANGE`, `DEFAULT_STDDEV`, types from `~/utils/anomaly`; `SkAnomalyLegend`, `SkAnomalyBadge`; the updated `TimeSeriesPoint` from Task 8 (`verdict?: CombinedVerdict`).
- Produces: each `timeSeriesPoints` item carries `verdict: CombinedVerdict`; an `anomalyCfg` view-state object; an `anomalySummary` count; a `focusVerdict` for the focused MSR.

> The `TimeSeriesPoint` shape gains `verdict` and loses `outlier`; Task 8 makes the matching change in `TimeSeriesChart.vue`. Between this task and Task 8 the chart's per-point color is stale but the panel typechecks because the field is optional. Run both before the final verification.

- [ ] **Step 1: Replace the madOutliers import with the anomaly API**

In `<script setup>`, replace line `import { detectMadOutliers } from '~/utils/madOutliers'` with:

```ts
import {
  peerVerdicts, combineVerdicts, DEFAULT_RANGE, DEFAULT_STDDEV,
  type CombinedVerdict, type MethodConfig
} from '~/utils/anomaly'
```

- [ ] **Step 2: Add view-state config + summary (after the `selectedUnit` computed, ~line 240)**

```ts
// Active scoring method + thresholds. Range is the authoritative default;
// stddev is a diagnostic lens. Persisted across remounts via useState.
const anomalyCfg = useState<MethodConfig>('skewvoir-anomaly-cfg', () => ({
  method: 'range',
  range: { ...DEFAULT_RANGE },
  stddev: { ...DEFAULT_STDDEV }
}))
```

- [ ] **Step 3: Replace the outlier block inside `timeSeriesPoints`**

Replace the block from `// Outlier flags are relative…` through the `return points.map(…)` (currently lines 262–270) with:

```ts
  // Peer verdicts under the active method: level (mean) and spread (std),
  // each judged leave-one-out against the rest of the selection.
  const meanV = peerVerdicts(points.map(p => p.mean), { config: anomalyCfg.value, metric: 'mean' })
  const spreadV = peerVerdicts(points.map(p => p.std), { config: anomalyCfg.value, metric: 'spread', tag: '산포' })

  return points.map(({ ts: _ts, ...rest }, i) => ({
    ...rest,
    verdict: combineVerdicts([meanV[i]!, spreadV[i]!]) as CombinedVerdict
  }))
```

- [ ] **Step 4: Add the summary computed (after `timeSeriesPoints`)**

```ts
const anomalySummary = computed(() => {
  let watch = 0, abnormal = 0
  for (const p of timeSeriesPoints.value) {
    if (p.verdict?.severity === 'abnormal') abnormal++
    else if (p.verdict?.severity === 'watch') watch++
  }
  return { watch, abnormal }
})

// Verdict for the currently-focused MSR, for the SkAnomalyBadge in the detail card.
const focusVerdict = computed<CombinedVerdict | null>(() =>
  timeSeriesPoints.value.find(p => p.msr === focusMsrLocal.value)?.verdict ?? null
)
```

- [ ] **Step 5: Replace the time-series card header (template lines 42–49)**

```vue
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              시계열 추이 · {{ selectedParam || '—' }}
            </p>
            <span class="font-mono text-[10.5px] text-(--sk-ink-muted)">
              주의 {{ anomalySummary.watch }} · 이상 {{ anomalySummary.abnormal }} / {{ timeSeriesPoints.length }} MSR
            </span>
          </div>
        </template>
```

- [ ] **Step 6: Add the method/threshold controls + legend (template, immediately before `<EbeamSkewvoirTimeSeriesChart …>` at line 50)**

```vue
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <USelect
            v-model="anomalyCfg.method"
            size="xs"
            :items="[{ label: '범위(%)', value: 'range' }, { label: '표준편차(σ) · 진단', value: 'stddev' }]"
            class="min-w-[11rem]"
          />
          <template v-if="anomalyCfg.method === 'range'">
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              주의 ±<UInput v-model.number="anomalyCfg.range.watchPct" type="number" size="xs" class="w-14" />%
            </label>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              이상 ±<UInput v-model.number="anomalyCfg.range.abnormalPct" type="number" size="xs" class="w-14" />%
            </label>
          </template>
          <template v-else>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              주의 ±<UInput v-model.number="anomalyCfg.stddev.watchK" type="number" size="xs" class="w-14" />σ
            </label>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              이상 ±<UInput v-model.number="anomalyCfg.stddev.abnormalK" type="number" size="xs" class="w-14" />σ
            </label>
          </template>
          <SkAnomalyLegend
            class="ml-auto"
            :method="anomalyCfg.method"
            :range="anomalyCfg.range"
            :stddev="anomalyCfg.stddev"
          />
        </div>
```

- [ ] **Step 7: Show the focused MSR's badge in the detail card header**

In the `단일 MSR 상세` card header (template lines 79–91), add the badge beside the title. Replace the header's title `<p>` line with:

```vue
            <div class="flex items-center gap-2">
              <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
                단일 MSR 상세
              </p>
              <SkAnomalyBadge :verdict="focusVerdict" />
            </div>
```

- [ ] **Step 8: Verify typecheck + lint**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: clean. (If typecheck complains that `verdict` is missing on `TimeSeriesPoint`, that field is added in Task 8 — proceed to Task 8, then re-run.)

- [ ] **Step 9: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/AnalyzePanel.vue
git commit -m "feat(skewvoir): wire AnalyzePanel to anomaly convention (peer + method toggle)"
```

---

### Task 8: Render verdicts in `TimeSeriesChart` + remove `madOutliers`

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/TimeSeriesChart.vue`
- Delete: `front-dev-home/app/utils/madOutliers.ts`, `front-dev-home/app/utils/madOutliers.test.ts`

**Interfaces:**
- Consumes: `CombinedVerdict` from `~/utils/anomaly`.
- Produces: `TimeSeriesPoint` now has `verdict?: CombinedVerdict` (replaces `outlier`).

- [ ] **Step 1: Update the `TimeSeriesPoint` interface (lines 11–21)**

Replace the trailing comment + `outlier?` field with:

```ts
  std: number
  // Set by AnalyzePanel via combineVerdicts; absent ⇒ treated as normal.
  verdict?: import('~/utils/anomaly').CombinedVerdict
}
```

- [ ] **Step 2: Replace the per-datum styling (lines 35–45)**

```ts
// Per-datum styling by severity (status first): insufficient grey, watch amber,
// abnormal red, normal blue. Hexes mirror the --sk-warn/--sk-bad tokens for canvas.
const SEV_HEX: Record<string, string> = {
  abnormal: '#dc2626', watch: '#d97706', insufficient: '#9ca3af', normal: '#2563eb'
}
const sevKey = (p: TimeSeriesPoint): string =>
  !p.verdict ? 'normal' : p.verdict.status === 'insufficient' ? 'insufficient' : p.verdict.severity
const meanData = computed(() =>
  props.points.map((p) => {
    const key = sevKey(p)
    const symbolSize = key === 'abnormal' ? 10 : key === 'watch' ? 9 : key === 'insufficient' ? 7 : 6
    return { value: p.mean, itemStyle: { color: SEV_HEX[key] }, symbolSize }
  })
)
```

- [ ] **Step 3: Replace the tooltip outlier block (lines 62–66)**

```ts
      const v = p.verdict
      if (v && (v.status === 'insufficient' || v.severity !== 'normal')) {
        const color = v.severity === 'abnormal' ? '#dc2626' : v.severity === 'watch' ? '#d97706' : '#9ca3af'
        for (const x of v.verdicts) {
          if (x.status === 'evaluated' && x.severity === 'normal') continue
          lines.push(`<span style="color:${color}">⚠ ${x.reason}</span>`)
        }
      }
```

- [ ] **Step 4: Delete the obsolete madOutliers files**

```bash
git rm front-dev-home/app/utils/madOutliers.ts front-dev-home/app/utils/madOutliers.test.ts
```

- [ ] **Step 5: Verify nothing else references madOutliers**

Run: `cd front-dev-home && node --test "app/**/*.test.ts" && grep -rn "madOutliers" app || echo "no refs"`
Expected: tests PASS; grep prints `no refs`.

- [ ] **Step 6: Full gate — typecheck + lint + tests**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint && npm --prefix front-dev-home test`
Expected: all clean/PASS.

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/TimeSeriesChart.vue
git commit -m "feat(skewvoir): render anomaly verdicts on time-series, drop madOutliers"
```

---

### Task 9: End-to-end verification (Playwright)

**Files:** none (verification only).

- [ ] **Step 1: Confirm dev servers are up**

Flask (`:5050`) + Nuxt (`:3000`) run in PyCharm. If `http://localhost:3000` is unreachable, ask the user to start them rather than launching your own.

- [ ] **Step 2: Drive the pilot to the time-series chart**

Navigate to a skewvoir tool page → search/select ≥5 measurements → open the analysis workspace so `AnalyzePanel`'s `시계열 추이` chart renders with the new controls row.

- [ ] **Step 3: Verify the four states + method toggle**

- With **범위(%)** selected: confirm the legend reads `주의 ±10% · 이상 ±20% 초과`, the summary shows `주의 N · 이상 N`, and at least one point renders amber or red (hover → Korean reason tooltip with `% 초과`, no `z-score`/`MAD`).
- Lower 주의 to e.g. `3`%: more points turn amber (live recompute) — confirms thresholds are live.
- Switch to **표준편차(σ) · 진단**: legend switches to `±2σ / ±3σ`, tooltips now read `…σ`.
- Select <5 measurements (or a param missing on most): points render grey with `미평가` tooltip — confirms `insufficient` is distinct from silent-normal.
- In the `단일 MSR 상세` card: focus an abnormal/watch MSR → `SkAnomalyBadge` shows the matching colored dot + `이상`/`주의` label with the reason on hover; focus a normal MSR → badge is absent (silence).

- [ ] **Step 4: Screenshot for the record**

Save to `.playwright-mcp/screenshots/anomaly-pilot-range.png` and `…-stddev.png` (pass the `.playwright-mcp/screenshots/` prefix in `filename`).

- [ ] **Step 5: Final commit (if any verification tweaks were needed)**

```bash
git add -A
git commit -m "test(skewvoir): verify anomaly pilot renders range/stddev + insufficient"
```

---

## Phase 2 (separate plan, after the calibration gate)

Not in this plan: `siblingDivergence` (groupKey `recipe·param·device`, contrast `eqp_id`), `recentShift` (step-change on the focused param's series), the flag-rate calibration gate, and retrofitting `device-statistics` + `FdcAnalysis`. Write that plan once Phase 1's defaults are validated on mock data.
