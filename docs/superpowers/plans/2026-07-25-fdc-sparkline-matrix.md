# FDC Sparkline Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small-multiples overview above the single-MSR sequence workbench so CD and every dynamic FDC param are visible at once, each in its native unit, ranked by relation to `cd_value`.

**Architecture:** A pure util (`paramMatrix.ts`) turns the `SequenceModel` the workbench already computes into a flat row/cell layout model, including per-param Pearson r against CD. A presentational component (`ParamMatrix.vue`) renders that model as an ECharts 6 `matrix` coordinate system where each cell is an ordinary `grid` + `xAxis` + `yAxis` + `line`. All judgement lives in the util and is unit-tested; the component only builds an ECharts option.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), Vue 3 `<script setup>`, ECharts 6.1 (full bundle), TypeScript, `node --test`.

## Global Constraints

- ECharts **6.1.0**, imported as the full bundle by `useEchart.ts:1`. The `matrix` coordinate system requires **>= 6.0.0**; no component registration needed.
- **No Pinia.** Shared state flows through the existing `SkewvoirAnalysis` composable.
- **`MAX_COLUMNS = 4`** and **`MAX_SUSPECTS = 4`**.
- **`connectNulls: false`** — gaps must read as gaps, matching `FdcSequenceTrend.vue:93`.
- Test files import **values** relatively with an explicit extension (`'./paramMatrix.ts'`) and **types** via the alias (`'~/composables/useMsrFileApi'`). A value import through `~/` breaks `node --test`.
- **Zero component tests exist in this repo** (72 util tests, 0 component tests). Do not add the first one.
- Korean UI copy, formal endings. The demo-data warning must reuse the existing wording verbatim: `데모 데이터 · 방법 검증 불가` (from `SequenceWorkbench.vue:84-86`).
- Every chart component in this repo exposes an `sr-only` aria-label (see `FdcSequenceTrend.vue:1-10`). Follow it.
- Verify commands, all run from `front-dev-home/`: `npm test`, `npm run lint`, `npm run typecheck`.

## File Structure

| File | Responsibility |
| --- | --- |
| Create `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts` | Pure layout+ranking model. No Vue, no ECharts. |
| Create `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts` | `node --test` coverage for that util. |
| Create `front-dev-home/app/components/ebeam/skewvoir/timeseries/ParamMatrix.vue` | Builds the ECharts matrix option. Presentational only. |
| Modify `front-dev-home/app/composables/useEchart.ts:20`, `:89-107` | Widen `onGridClick` to report `gridIndex`. |
| Modify `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue` | Mount the matrix, wire cursor + drill-down. |

---

### Task 1: Matrix model foundation — types, CD row, category rows

**Files:**
- Create: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts`

**Interfaces:**
- Consumes: `analyzeSequence(source, parameter, unit) → SequenceModel` from `./sequence.ts`; `SeqPoint`, `SequenceModel`, `FdcSeqSeries` types from the same file; `FdcParamSummary`, `FdcCategory`, `MsrFileRow` types from `~/composables/useMsrFileApi`.
- Produces: `MAX_COLUMNS`, `MAX_SUSPECTS`, `MatrixCell`, `MatrixRow`, `MatrixRowKind`, `ParamMatrixModel`, and `buildParamMatrix(model, rows, dynamicFdc, fdcParams, cdParam) → ParamMatrixModel`. Tasks 2, 3, 5 and 6 all depend on these exact names.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts`:

```ts
// front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
// Pure-logic tests for the FDC sparkline matrix layout model.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeSequence } from './sequence.ts'
import { buildParamMatrix } from './paramMatrix.ts'
import type { MsrFileRow, FdcParamSummary } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: 'img_0001.svg', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

const fdcParam = (over: Partial<FdcParamSummary>): FdcParamSummary => ({
  name: 'StigmaX', category: 'astigmatism', category_label: '비점수차', unit: '%',
  nominal: 0, mean: 1, std: 0.4, min: 0, max: 2, drift_sigma: 1.3, status: 'ok',
  ...over
})

// CD rises +2/sequence over 4 sequences. StigmaX tracks it exactly (r = 1),
// Brightness moves opposite (r = -1). Two categories, one param each.
const source = () => ({
  rows: [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 102 }),
    row({ sequence: 3, cd_value: 104 }),
    row({ sequence: 4, cd_value: 106 })
  ],
  dynamic_fdc: {
    1: { StigmaX: 10, Brightness: 40 },
    2: { StigmaX: 12, Brightness: 30 },
    3: { StigmaX: 14, Brightness: 20 },
    4: { StigmaX: 16, Brightness: 10 }
  } as unknown as Record<string, Record<string, number>>,
  fdc_params: [
    fdcParam({ name: 'StigmaX', category: 'astigmatism', category_label: '비점수차', unit: '%' }),
    fdcParam({ name: 'Brightness', category: 'image', category_label: '이미지 품질', unit: 'DN' })
  ]
})

const build = () => {
  const src = source()
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  return buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
}

test('row 0 is the CD reference row carrying the active CD parameter', () => {
  const m = build()
  assert.equal(m.rows[0]?.kind, 'cd')
  assert.equal(m.rows[0]?.cells.length, 1)
  assert.equal(m.rows[0]?.cells[0]?.param, 'CD_TOP')
  assert.equal(m.rows[0]?.cells[0]?.category, 'cd')
  assert.equal(m.rows[0]?.cells[0]?.nominal, null)
})

test('category rows use the Korean label resolved from fdc_params', () => {
  const m = build()
  const labels = m.rows.filter(r => r.kind === 'category').map(r => r.label)
  assert.ok(labels.includes('비점수차'))
  assert.ok(labels.includes('이미지 품질'))
})

test('cell values are aligned onto the shared sequence axis', () => {
  const m = build()
  const stigma = m.rows.flatMap(r => r.cells).find(c => c.param === 'StigmaX')
  assert.deepEqual(m.sequences, [1, 2, 3, 4])
  assert.deepEqual(stigma?.values, [10, 12, 14, 16])
})

test('every FDC param appears exactly once outside the suspects row', () => {
  const m = build()
  const names = m.rows
    .filter(r => r.kind === 'category')
    .flatMap(r => r.cells)
    .map(c => c.param)
  assert.deepEqual([...names].sort(), ['Brightness', 'StigmaX'])
})

test('row keys are unique so they can be used as ordinal matrix coords', () => {
  const m = build()
  const keys = m.rows.map(r => r.key)
  assert.equal(new Set(keys).size, keys.length)
})

test('a CD-only MSR with no dynamic FDC yields just the CD row', () => {
  const src = source()
  src.dynamic_fdc = {}
  src.fdc_params = []
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  const m = buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
  assert.equal(m.rows.length, 1)
  assert.equal(m.rows[0]?.kind, 'cd')
  assert.equal(m.columns, 1)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts`
Expected: FAIL — cannot resolve `./paramMatrix.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts`:

```ts
// The layout + ranking model behind the single-MSR FDC sparkline matrix.
//
// Pure: no Vue, no ECharts. Everything the matrix decides — which row a param
// sits in, how cells are ordered, which params count as suspects, how wide the
// grid is — is decided here so it can be tested with `node --test`. The
// component that consumes this only turns the model into an ECharts option.
import type { FdcCategory, FdcParamSummary, MsrFileRow } from '~/composables/useMsrFileApi'
import type { SequenceModel } from './sequence.ts'
import { buildCdFdcRelationship, type RelationshipReadiness } from './relationships.ts'

/** Hard cap on matrix width. Rows are CATEGORIES, so their count is small and
 * fixed; letting the column count track the widest row would let one fat
 * category (the office catalog is not a closed set) dictate cell width for the
 * whole matrix and shrink every cell to illegibility. Oversized categories wrap
 * onto continuation rows instead — see `Task 3`. */
export const MAX_COLUMNS = 4
export const MAX_SUSPECTS = 4

export interface MatrixCell {
  /** Param name. For the CD cell, the active CD parameter. */
  param: string
  /** `'cd'` marks the reference cell; otherwise the FDC category code. */
  category: FdcCategory | 'cd'
  unit: string
  /** Reference line value. Always null for the CD cell — CD has no nominal. */
  nominal: number | null
  /** Values aligned onto `ParamMatrixModel.sequences`; null marks a gap. */
  values: (number | null)[]
  /** Pearson r against cd_value. Null when not evaluable, and always null for
   * the CD cell itself, where correlation is not applicable rather than
   * unavailable — consumers detect that via `category === 'cd'`. */
  r: number | null
  readiness: RelationshipReadiness
  /** Why r is unavailable; null when ready. */
  reason: string | null
  /** True for the copy that lives in the suspects row. */
  duplicated: boolean
}

export type MatrixRowKind = 'cd' | 'suspects' | 'category'

export interface MatrixRow {
  /** Unique ordinal key. Doubles as the matrix y-dimension value, so it must
   * never repeat — duplicate ordinal keys make `coord` lookups ambiguous. */
  key: string
  kind: MatrixRowKind
  /** Row header text. Continuation rows carry a ` (n)` suffix to stay unique. */
  label: string
  continuation: boolean
  cells: MatrixCell[]
}

export interface ParamMatrixModel {
  columns: number
  rows: MatrixRow[]
  /** The shared sequence axis every cell indexes. */
  sequences: number[]
  /** True when any r came from a demo-coupled join. Always true on home mock. */
  demoCoupled: boolean
}

/** category code → Korean label, taken from the backend's own labelling rather
 * than a hardcoded map, so a new office category needs no frontend change. */
const labelsByCategory = (fdcParams: FdcParamSummary[]): Map<string, string> => {
  const out = new Map<string, string>()
  for (const p of fdcParams) if (!out.has(p.category)) out.set(p.category, p.category_label)
  return out
}

export const buildParamMatrix = (
  model: SequenceModel,
  rows: MsrFileRow[],
  dynamicFdc: Record<string, Record<string, number>>,
  fdcParams: FdcParamSummary[],
  cdParam: string
): ParamMatrixModel => {
  const sequences = model.sequences
  const align = (points: { sequence: number, value: number | null, measured: boolean }[]): (number | null)[] => {
    const bySeq = new Map(points.map(p => [p.sequence, p.measured ? p.value : null]))
    return sequences.map(s => bySeq.get(s) ?? null)
  }

  const labels = labelsByCategory(fdcParams)

  const cdCell: MatrixCell = {
    param: cdParam,
    category: 'cd',
    unit: model.unit,
    nominal: null,
    values: align(model.cd.points),
    r: null,
    readiness: 'ready',
    reason: null,
    duplicated: false
  }

  let demoCoupled = false
  const fdcCells: MatrixCell[] = model.fdc.map((series) => {
    const rel = buildCdFdcRelationship(rows, cdParam, series.param, dynamicFdc)
    if (rel.demoCoupled) demoCoupled = true
    return {
      param: series.param,
      category: series.category,
      unit: series.unit,
      nominal: series.nominal,
      values: align(series.points),
      r: rel.readiness === 'ready' ? rel.pearson : null,
      readiness: rel.readiness,
      reason: rel.reason,
      duplicated: false
    }
  })

  const matrixRows: MatrixRow[] = [
    { key: 'cd', kind: 'cd', label: 'CD', continuation: false, cells: [cdCell] }
  ]

  // One row per category, in first-seen order from fdc_params.
  const seen: string[] = []
  for (const cell of fdcCells) if (!seen.includes(cell.category)) seen.push(cell.category)
  for (const category of seen) {
    matrixRows.push({
      key: category,
      kind: 'category',
      label: labels.get(category) ?? category,
      continuation: false,
      cells: fdcCells.filter(c => c.category === category)
    })
  }

  const widest = matrixRows
    .filter(r => r.kind !== 'cd')
    .reduce((max, r) => Math.max(max, r.cells.length), 0)

  return {
    columns: Math.max(1, Math.min(MAX_COLUMNS, widest)),
    rows: matrixRows,
    sequences,
    demoCoupled
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts`
Expected: PASS, 6 tests.

- [ ] **Step 5: Lint and typecheck**

Run: `cd front-dev-home && npm run lint && npm run typecheck`
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
git commit -m "feat(skewvoir): add the FDC matrix layout model foundation

Turns the SequenceModel the workbench already computes into a flat row/cell
layout: a CD reference row plus one row per FDC category, with values aligned
onto the shared sequence axis and Korean row labels resolved from the backend's
own category_label rather than a hardcoded map."
```

---

### Task 2: CD correlation ordering and the suspects row

**Files:**
- Modify: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts`

**Interfaces:**
- Consumes: everything Task 1 produced, plus `buildCdFdcRelationship` and `RelationshipReadiness` from `./relationships.ts`.
- Produces: no new exported names. `MatrixRow` with `kind: 'suspects'` now appears at index 1 when at least one param is evaluable, and `cells` within every `kind: 'category'` row are ordered by `|r|` descending.

- [ ] **Step 1: Write the failing test**

Append to `paramMatrix.test.ts`:

```ts
// Three params in ONE category with distinct |r| so ordering is observable:
// Up tracks CD exactly (r=+1), Down inverts it (r=-1), Flat is constant
// (zero variance → 평가 불가, never rankable).
const orderedSource = () => ({
  rows: [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 102 }),
    row({ sequence: 3, cd_value: 104 }),
    row({ sequence: 4, cd_value: 106 })
  ],
  dynamic_fdc: {
    1: { Up: 1, Down: 40, Flat: 5 },
    2: { Up: 2, Down: 30, Flat: 5 },
    3: { Up: 3, Down: 20, Flat: 5 },
    4: { Up: 4, Down: 10, Flat: 5 }
  } as unknown as Record<string, Record<string, number>>,
  fdc_params: [
    fdcParam({ name: 'Up', category: 'defocus', category_label: 'defocus' }),
    fdcParam({ name: 'Down', category: 'defocus', category_label: 'defocus' }),
    fdcParam({ name: 'Flat', category: 'defocus', category_label: 'defocus' })
  ]
})

const buildOrdered = () => {
  const src = orderedSource()
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  return buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
}

test('a constant param is 평가 불가 and carries no r', () => {
  const m = buildOrdered()
  const flat = m.rows.flatMap(r => r.cells).find(c => c.param === 'Flat')
  assert.equal(flat?.readiness, 'unavailable')
  assert.equal(flat?.r, null)
  assert.ok(flat?.reason)
})

test('unevaluable params sort last within their category row', () => {
  const m = buildOrdered()
  const catRow = m.rows.find(r => r.kind === 'category')
  assert.equal(catRow?.cells.at(-1)?.param, 'Flat')
})

test('the suspects row sits at index 1 and holds only evaluable params', () => {
  const m = buildOrdered()
  assert.equal(m.rows[1]?.kind, 'suspects')
  const names = m.rows[1]!.cells.map(c => c.param)
  assert.ok(!names.includes('Flat'))
  assert.deepEqual([...names].sort(), ['Down', 'Up'])
})

test('suspects are copies, flagged duplicated, and originals stay in place', () => {
  const m = buildOrdered()
  assert.ok(m.rows[1]!.cells.every(c => c.duplicated))
  const catRow = m.rows.find(r => r.kind === 'category')
  assert.ok(catRow!.cells.every(c => !c.duplicated))
  assert.equal(catRow!.cells.length, 3)
})

test('the suspects row is omitted entirely when nothing is evaluable', () => {
  const src = orderedSource()
  src.dynamic_fdc = {
    1: { Flat: 5 }, 2: { Flat: 5 }, 3: { Flat: 5 }, 4: { Flat: 5 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = [fdcParam({ name: 'Flat', category: 'defocus', category_label: 'defocus' })]
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  const m = buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
  assert.ok(!m.rows.some(r => r.kind === 'suspects'))
})

test('the suspects row caps at MAX_SUSPECTS', () => {
  const src = orderedSource()
  src.dynamic_fdc = {
    1: { A: 1, B: 2, C: 3, D: 4, E: 5 },
    2: { A: 2, B: 4, C: 6, D: 8, E: 10 },
    3: { A: 4, B: 7, C: 9, D: 11, E: 14 },
    4: { A: 8, B: 9, C: 13, D: 15, E: 21 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = ['A', 'B', 'C', 'D', 'E'].map(n =>
    fdcParam({ name: n, category: 'defocus', category_label: 'defocus' }))
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  const m = buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
  assert.equal(m.rows.find(r => r.kind === 'suspects')!.cells.length, MAX_SUSPECTS)
})

test('equal |r| breaks by param name so order is stable', () => {
  const src = orderedSource()
  // Zeta and Alpha both track CD exactly → identical |r| = 1.
  src.dynamic_fdc = {
    1: { Zeta: 1, Alpha: 1 }, 2: { Zeta: 2, Alpha: 2 },
    3: { Zeta: 3, Alpha: 3 }, 4: { Zeta: 4, Alpha: 4 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = [
    fdcParam({ name: 'Zeta', category: 'defocus', category_label: 'defocus' }),
    fdcParam({ name: 'Alpha', category: 'defocus', category_label: 'defocus' })
  ]
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  const m = buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
  const catRow = m.rows.find(r => r.kind === 'category')
  assert.deepEqual(catRow!.cells.map(c => c.param), ['Alpha', 'Zeta'])
})
```

Add `MAX_SUSPECTS` to the import at the top of the test file:

```ts
import { buildParamMatrix, MAX_SUSPECTS } from './paramMatrix.ts'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts`
Expected: FAIL — no suspects row exists and cells are in `fdc_params` order, not `|r|` order.

- [ ] **Step 3: Write minimal implementation**

In `paramMatrix.ts`, add the comparator above `buildParamMatrix`:

```ts
/** Strongest CD relation first; unevaluable cells last; name as a stable
 * tie-break so identical |r| never reorders between renders. */
const byCdRelation = (a: MatrixCell, b: MatrixCell): number => {
  const ra = a.r == null ? -1 : Math.abs(a.r)
  const rb = b.r == null ? -1 : Math.abs(b.r)
  if (ra !== rb) return rb - ra
  return a.param.localeCompare(b.param)
}
```

Replace the category-row loop and the return block with:

```ts
  for (const category of seen) {
    matrixRows.push({
      key: category,
      kind: 'category',
      label: labels.get(category) ?? category,
      continuation: false,
      cells: fdcCells.filter(c => c.category === category).sort(byCdRelation)
    })
  }

  // Suspects are COPIES. Ranking on an unevaluable param would mean ranking on
  // a number `assess()` already refused to produce, so they are excluded.
  const suspects = fdcCells
    .filter(c => c.readiness === 'ready' && c.r != null)
    .sort(byCdRelation)
    .slice(0, MAX_SUSPECTS)
    .map(c => ({ ...c, duplicated: true }))

  if (suspects.length) {
    matrixRows.splice(1, 0, {
      key: 'suspects',
      kind: 'suspects',
      label: '주요 용의자',
      continuation: false,
      cells: suspects
    })
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts`
Expected: PASS, 13 tests.

- [ ] **Step 5: Lint and typecheck**

Run: `cd front-dev-home && npm run lint && npm run typecheck`
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
git commit -m "feat(skewvoir): rank FDC matrix cells by relation to cd_value

Orders cells within each category row by |r| descending with name as a stable
tie-break, and adds a 주요 용의자 row of duplicated copies so the strongest
suspects surface without scrambling the category rows.

Params whose relationship is 평가 불가 (no pairs, n<3, or a constant axis) are
sorted last and excluded from the suspects row — ranking them would mean ranking
on a number assess() explicitly refused to produce. The row is omitted entirely
when nothing is evaluable."
```

---

### Task 3: Column cap and continuation-row wrapping

**Files:**
- Modify: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts`

**Interfaces:**
- Consumes: Task 1 and Task 2 output.
- Produces: no new exported names. Category rows holding more than `MAX_COLUMNS` params now split into multiple `MatrixRow`s with `continuation: true` on every row after the first, and `columns` never exceeds `MAX_COLUMNS`.

- [ ] **Step 1: Write the failing test**

Append to `paramMatrix.test.ts`:

```ts
// Six params in ONE category — two rows past MAX_COLUMNS = 4.
const wideSource = () => {
  const names = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']
  const dynamic_fdc: Record<string, Record<string, number>> = {}
  for (let seq = 1; seq <= 4; seq++) {
    dynamic_fdc[String(seq)] = {}
    names.forEach((n, i) => { dynamic_fdc[String(seq)]![n] = seq * (i + 1) })
  }
  return {
    rows: [
      row({ sequence: 1, cd_value: 100 }),
      row({ sequence: 2, cd_value: 102 }),
      row({ sequence: 3, cd_value: 104 }),
      row({ sequence: 4, cd_value: 106 })
    ],
    dynamic_fdc,
    fdc_params: names.map(n =>
      fdcParam({ name: n, category: 'stage_drift', category_label: '스테이지 드리프트' }))
  }
}

const buildWide = () => {
  const src = wideSource()
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  return buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
}

test('columns never exceed MAX_COLUMNS however many params a category has', () => {
  assert.equal(buildWide().columns, MAX_COLUMNS)
})

test('an oversized category wraps onto continuation rows', () => {
  const m = buildWide()
  const catRows = m.rows.filter(r => r.kind === 'category')
  assert.equal(catRows.length, 2)
  assert.equal(catRows[0]?.cells.length, 4)
  assert.equal(catRows[1]?.cells.length, 2)
  assert.equal(catRows[0]?.continuation, false)
  assert.equal(catRows[1]?.continuation, true)
})

test('wrapping loses no param and duplicates none', () => {
  const names = buildWide().rows
    .filter(r => r.kind === 'category')
    .flatMap(r => r.cells)
    .map(c => c.param)
  assert.equal(names.length, 6)
  assert.equal(new Set(names).size, 6)
})

test('continuation row labels stay unique for use as ordinal coords', () => {
  const m = buildWide()
  const labels = m.rows.map(r => r.label)
  assert.equal(new Set(labels).size, labels.length)
  const catRows = m.rows.filter(r => r.kind === 'category')
  assert.equal(catRows[0]?.label, '스테이지 드리프트')
  assert.equal(catRows[1]?.label, '스테이지 드리프트 (2)')
})

test('continuation row keys stay unique too', () => {
  const keys = buildWide().rows.map(r => r.key)
  assert.equal(new Set(keys).size, keys.length)
})
```

Add `MAX_COLUMNS` to the test file import:

```ts
import { buildParamMatrix, MAX_COLUMNS, MAX_SUSPECTS } from './paramMatrix.ts'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts`
Expected: FAIL — one category row holds all 6 cells and `columns` is 4 while a row is 6 wide.

- [ ] **Step 3: Write minimal implementation**

In `paramMatrix.ts`, add above `buildParamMatrix`:

```ts
/** Split one category's cells into rows of at most MAX_COLUMNS. Continuation
 * rows carry a ` (n)` suffix on BOTH label and key: those double as the matrix
 * y-dimension ordinal values, and duplicates would make `coord` ambiguous. */
const wrapCategory = (category: string, label: string, cells: MatrixCell[]): MatrixRow[] => {
  const out: MatrixRow[] = []
  for (let start = 0; start < cells.length; start += MAX_COLUMNS) {
    const part = start / MAX_COLUMNS
    out.push({
      key: part === 0 ? category : `${category}#${part + 1}`,
      kind: 'category',
      label: part === 0 ? label : `${label} (${part + 1})`,
      continuation: part > 0,
      cells: cells.slice(start, start + MAX_COLUMNS)
    })
  }
  return out
}
```

Replace the category-row loop with:

```ts
  for (const category of seen) {
    const cells = fdcCells.filter(c => c.category === category).sort(byCdRelation)
    matrixRows.push(...wrapCategory(category, labels.get(category) ?? category, cells))
  }
```

The existing `columns` calculation already clamps with `Math.min(MAX_COLUMNS, widest)`, and no row can now exceed `MAX_COLUMNS`, so it needs no change.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts`
Expected: PASS, 18 tests.

- [ ] **Step 5: Run the whole suite, lint, typecheck**

Run: `cd front-dev-home && npm test && npm run lint && npm run typecheck`
Expected: all green, no regression in the other 72 util test files.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.ts front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
git commit -m "feat(skewvoir): cap matrix columns and wrap oversized categories

Rows are categories, so their count is small and fixed. Letting the column count
track the widest row means one fat category dictates cell width for the entire
matrix — at office param counts every cell would shrink to roughly 60px. Columns
are capped at 4 and a larger category wraps onto continuation rows.

Continuation labels and keys carry a ' (n)' suffix because both double as matrix
y-dimension ordinal values, where duplicates make coord lookups ambiguous."
```

---

### Task 4: Report `gridIndex` from `useEchart`'s grid-click handler

**Files:**
- Modify: `front-dev-home/app/composables/useEchart.ts:20`, `:89-107`

**Interfaces:**
- Consumes: nothing new.
- Produces: `onGridClick?: (xValue: number, gridIndex: number) => void`. Task 5 relies on the second argument to map a click to a matrix cell.

**Why this is safe:** the loop at `useEchart.ts:99-105` already computes `gridIndex` and discards it. Every current caller declares a one-parameter arrow function, and JavaScript ignores extra arguments, so widening the signature cannot break them.

- [ ] **Step 1: Confirm no caller destructures or arity-checks the callback**

Run: `cd front-dev-home && grep -rn "onGridClick" app/`
Expected: the definition plus call sites that all pass a single-parameter arrow function. If any caller passes a named function used elsewhere, stop and reassess.

- [ ] **Step 2: Widen the type**

In `front-dev-home/app/composables/useEchart.ts`, replace the `onGridClick` declaration (line 20) and keep the surrounding comment:

```ts
  // Receives the x-axis value under the cursor and the index of the grid that
  // was hit. `gridIndex` matters for multi-grid charts (small multiples, matrix
  // cells) where the same x value means a different series per grid; callers
  // with a single grid can ignore it.
  onGridClick?: (xValue: number, gridIndex: number) => void
```

- [ ] **Step 3: Pass the index through**

In the same file, change the call inside `bindGridClick` (line 103) from `callback(xValue)` to:

```ts
        if (Number.isFinite(xValue)) callback(xValue, gridIndex)
```

- [ ] **Step 4: Verify nothing broke**

Run: `cd front-dev-home && npm run lint && npm run typecheck && npm test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useEchart.ts
git commit -m "feat(charts): report gridIndex from useEchart's grid-click handler

bindGridClick already iterates every grid and uses containPixel to find the one
the click landed in, then threw that index away. Multi-grid charts need it: in a
small-multiples or matrix layout the same x value means a different series
depending on which cell was hit.

Purely additive — every existing caller passes a one-parameter arrow function and
JavaScript ignores extra arguments."
```

---

### Task 5: `ParamMatrix.vue` — render the model as an ECharts matrix

**Files:**
- Create: `front-dev-home/app/components/ebeam/skewvoir/timeseries/ParamMatrix.vue`

**Interfaces:**
- Consumes: `ParamMatrixModel`, `MatrixCell`, `MatrixRow` from `~/utils/skewvoirAnalysis/paramMatrix`; `useEchart(elRef, option, opts)` with the Task 4 signature; `useChartPalette()` and `useEchartsTheme()` as used in `SequenceWorkbench.vue:162-168`.
- Produces: component auto-imported as `EbeamSkewvoirTimeseriesParamMatrix`, props `model: ParamMatrixModel` and `focused: number | null`, emits `select: [sequence: number]` and `drill: [param: string]`. Task 6 consumes both events.

**Placement mechanics.** Each cell is an ordinary cartesian grid positioned into a matrix cell with `coordinateSystem: 'matrix'` and `coord: [columnIndex, rowIndex]`. The CD row spans the full width with a range coord, `coord: [[0, columns - 1], 0]` — verified supported: `Grid.js:152` → `layout.js:357-361` → `Matrix.js:151-173`, where `dataToLayout` runs the coord through the same `parseCoordRangeOption` that handles matrix body-cell ranges. Grids, axes and series are pushed in one flat pass so `gridIndex` equals the position in a parallel `cellByGrid` array.

- [ ] **Step 1: Create the component**

```vue
<template>
  <div
    ref="chartEl"
    role="img"
    tabindex="0"
    class="w-full"
    :style="{ height: `${height}px` }"
    :aria-label="ariaLabel"
  />
  <span class="sr-only">{{ ariaLabel }}</span>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { MatrixCell, ParamMatrixModel } from '~/utils/skewvoirAnalysis/paramMatrix'

// The FDC sparkline matrix: one mini line chart per param, laid out by the
// ECharts 6 `matrix` coordinate system. Each cell is a full cartesian grid with
// its OWN scaled y-axis, so every param keeps its native unit — the reason this
// exists rather than reusing the σ-normalised multi-MSR trend chart.
//
// Presentational only. Row composition, ordering, suspects and the column cap
// are all decided in utils/skewvoirAnalysis/paramMatrix.ts.
const props = defineProps<{
  model: ParamMatrixModel
  focused?: number | null
}>()

const emit = defineEmits<{ select: [sequence: number], drill: [param: string] }>()

const ROW_HEIGHT = 78
const HEADER = 26
const ZOOM = 44

const height = computed(() => HEADER + props.model.rows.length * ROW_HEIGHT + ZOOM)

const categories = computed(() => props.model.sequences.map(String))

const sk = useChartPalette()
const { palette } = useEchartsTheme()

// Distinct accent per row so neighbouring cells never read as one series. Index
// 0 is reserved for CD, matching the CD pane below the matrix.
const colorFor = (rowIdx: number, kind: string): string => {
  if (kind === 'cd') return sk.value.series
  if (palette.value.length < 2) return sk.value.series
  return palette.value[1 + (rowIdx % (palette.value.length - 1))]!
}

const rBadge = (cell: MatrixCell): string => {
  if (cell.category === 'cd') return 'ref'
  if (cell.readiness !== 'ready' || cell.r == null) return '평가 불가'
  return `r ${cell.r >= 0 ? '+' : '−'}${Math.abs(cell.r).toFixed(2)}`
}

// Flat, index-parallel cell list. `gridIndex` from useEchart's grid click maps
// straight into this array, which is why grids/axes/series are built in lockstep.
const cellByGrid = computed<MatrixCell[]>(() =>
  props.model.rows.flatMap(r => r.cells)
)

const option = computed<EChartsOption>(() => {
  const grids: Record<string, unknown>[] = []
  const xAxis: Record<string, unknown>[] = []
  const yAxis: Record<string, unknown>[] = []
  const series: Record<string, unknown>[] = []

  const cols = props.model.columns
  const focusIdx = props.focused == null
    ? -1
    : props.model.sequences.indexOf(props.focused)

  props.model.rows.forEach((row, rowIdx) => {
    row.cells.forEach((cell, colIdx) => {
      const id = `${rowIdx}|${colIdx}`
      const color = colorFor(rowIdx, row.kind)

      grids.push({
        id,
        coordinateSystem: 'matrix',
        // The CD row spans every column; all other cells occupy one.
        coord: row.kind === 'cd' ? [[0, cols - 1], rowIdx] : [colIdx, rowIdx],
        left: 4,
        right: 4,
        top: 16,
        bottom: 6,
        containLabel: true
      })

      xAxis.push({
        id,
        gridId: id,
        type: 'category',
        data: categories.value,
        boundaryGap: false,
        axisTick: { show: false },
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: false }
      })

      yAxis.push({
        id,
        gridId: id,
        type: 'value',
        scale: true,
        // One label only — the max. A tiny cell cannot carry a full scale.
        interval: Number.MAX_SAFE_INTEGER,
        axisLabel: { showMaxLabel: true, fontSize: 8, opacity: 0.55 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      })

      const marks: Record<string, unknown>[] = []
      if (cell.nominal != null) {
        marks.push({ yAxis: cell.nominal, lineStyle: { color: '#94a3b8', type: 'dashed', opacity: 0.5 } })
      }
      if (focusIdx >= 0) {
        marks.push({ xAxis: focusIdx, lineStyle: { color, type: 'solid', opacity: 0.45 } })
      }

      series.push({
        id,
        name: `${cell.param} · ${rBadge(cell)}`,
        xAxisId: id,
        yAxisId: id,
        type: 'line',
        symbol: 'none',
        // Gaps must read as gaps, never as interpolated measurements.
        connectNulls: false,
        lineStyle: { width: 1.15, color },
        itemStyle: { color },
        data: cell.values,
        markLine: marks.length
          ? { silent: true, symbol: 'none', label: { show: false }, data: marks }
          : undefined
      })
    })
  })

  return {
    matrix: {
      x: {
        data: Array.from({ length: cols }, (_, i) => String(i + 1)),
        levelSize: 2,
        label: { show: false }
      },
      y: {
        // Row keys are unique by construction; labels are what the user reads.
        data: props.model.rows.map(r => ({ value: r.label })),
        levelSize: 86,
        label: { fontSize: 10 }
      },
      corner: { data: [{ coord: [-1, -1], value: 'param' }], label: { fontSize: 9 } },
      left: 6,
      right: 6,
      top: HEADER,
      bottom: ZOOM
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params]
        const first = list[0] as { seriesId?: string, dataIndex: number, value: unknown } | undefined
        if (!first) return ''
        const seq = props.model.sequences[first.dataIndex]
        const cell = cellByGrid.value.find(c => `${c.param}` === String(first.seriesId).split(' · ')[0])
        const lines = [`sequence ${seq ?? '—'}`]
        for (const item of list as { seriesName: string, value: number | null }[]) {
          lines.push(`${item.seriesName}: <b>${item.value == null ? '결측' : item.value}</b>`)
        }
        if (cell?.reason) lines.push(`<span style="opacity:.7">${cell.reason}</span>`)
        return lines.join('<br/>')
      }
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      { type: 'inside', xAxisIndex: 'all', throttle: 120 },
      { type: 'slider', xAxisIndex: 'all', bottom: 8, height: 18, throttle: 120 }
    ],
    grid: grids,
    xAxis,
    yAxis,
    series
  } as EChartsOption
})

const ariaLabel = computed(() => {
  const n = cellByGrid.value.length
  const suspects = props.model.rows.find(r => r.kind === 'suspects')
  const top = suspects?.cells.map(c => c.param).join(', ')
  return `FDC 파라미터 매트릭스: ${n}개 셀, ${props.model.sequences.length}개 측정 순서`
    + (top ? `. 주요 용의자: ${top}` : '')
})

const chartEl = ref<HTMLDivElement | null>(null)

useEchart(chartEl, option, {
  exportName: 'fdc-param-matrix',
  onGridClick: (xValue, gridIndex) => {
    const seq = props.model.sequences[Math.round(xValue)]
    if (seq != null) emit('select', seq)
    const cell = cellByGrid.value[gridIndex]
    if (cell && cell.category !== 'cd') emit('drill', cell.param)
  }
})
</script>
```

- [ ] **Step 2: Lint and typecheck**

Run: `cd front-dev-home && npm run lint && npm run typecheck`
Expected: no errors. If `vue-tsc` rejects `coord` or `coordinateSystem` on a grid entry, do **not** cast the whole option — narrow the `grids` array element type instead and report the exact error.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/timeseries/ParamMatrix.vue
git commit -m "feat(skewvoir): render the FDC sparkline matrix

One mini line chart per param, laid out by the ECharts 6 matrix coordinate
system. Each cell is a full cartesian grid with its own scaled y-axis, so every
param keeps its native unit instead of being normalised to sigma-drift as the
multi-MSR trend chart has to do.

The CD row spans every column via a range coord. One shared dataZoom over
xAxisIndex 'all' means a single brush reframes every cell, and axisPointer.link
tracks the hover crosshair across cells."
```

---

### Task 6: Wire the matrix into the workbench with cursor and drill-down

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue`

**Interfaces:**
- Consumes: `buildParamMatrix` from `~/utils/skewvoirAnalysis/paramMatrix`; `EbeamSkewvoirTimeseriesParamMatrix` with props `model`/`focused` and events `select`/`drill`.
- Produces: nothing further depends on this task.

- [ ] **Step 1: Add the model computed**

In the `<script setup>` block of `SequenceWorkbench.vue`, after the existing `model` computed, add:

```ts
import { buildParamMatrix } from '~/utils/skewvoirAnalysis/paramMatrix'

// The matrix reads the SAME SequenceModel the panes below already use, so the
// overview and the detail can never disagree about what was measured.
const matrix = computed(() =>
  buildParamMatrix(
    model.value,
    props.analysis.siteRows.value,
    props.analysis.focusFile.value?.dynamic_fdc ?? {},
    props.analysis.focusFile.value?.fdc_params ?? [],
    props.analysis.activeParam.value
  )
)

// Drill-down: bring the clicked param's full-size pane into view. `nearest` is
// deliberate — it is a no-op when the pane is already on screen, so a click
// meant only to move the cursor does not yank the page around.
const drillTo = (param: string): void => {
  if (!import.meta.client) return
  document.getElementById(`fdc-pane-${param}`)?.scrollIntoView({
    block: 'nearest',
    behavior: 'smooth'
  })
}
```

- [ ] **Step 2: Mount the matrix above the CD pane**

Immediately after the `</EbeamSkewvoirPanelFrame>` that closes the 측정 순서 (Sequence) event-lane panel, insert:

```vue
      <!-- Overview: every param at once, each in its own unit. The panes below
           stay the detailed reading; this is the scan layer. -->
      <EbeamSkewvoirPanelFrame
        title="파라미터 매트릭스"
        :meta="`${matrix.rows.length} rows · ${matrix.columns} cols · CD 대비 상관`"
        icon="i-lucide-grid-3x3"
      >
        <template #actions>
          <span
            v-if="matrix.demoCoupled"
            class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-0.5 font-mono text-[10px] text-(--sk-warn)"
          >
            데모 데이터 · 방법 검증 불가
          </span>
        </template>
        <EbeamSkewvoirTimeseriesParamMatrix
          :model="matrix"
          :focused="analysis.focusedSequence.value"
          @select="onSelect"
          @drill="drillTo"
        />
      </EbeamSkewvoirPanelFrame>
```

- [ ] **Step 3: Give each FDC pane a drill target id**

Wrap the existing dynamic-FDC `v-for` panel so the scroll target exists. Replace the opening tag of that `EbeamSkewvoirPanelFrame` (currently carrying `v-for="(series, i) in model.fdc"`) with a wrapper div that owns the key and id:

```vue
        <div
          v-for="(series, i) in model.fdc"
          :id="`fdc-pane-${series.param}`"
          :key="series.param"
        >
          <EbeamSkewvoirPanelFrame
            :title="`Dynamic FDC · ${series.param}`"
            :meta="fdcMeta(series)"
            icon="i-lucide-waves"
          >
```

and close the wrapper with `</div>` after that panel's `</EbeamSkewvoirPanelFrame>`. Remove the now-duplicated `v-for`/`:key` from the panel itself.

- [ ] **Step 4: Verify in the running app**

Start the stack per the project's `/verify` skill (Flask on `:5050`, Nuxt with `NUXT_API_TARGET=http://localhost:5050`), open a single MSR in Skewvoir's TimeSeries tab, and confirm:

- the matrix renders above the CD pane with a CD row spanning the full width
- the 주요 용의자 row appears with the demo-data chip
- dragging the dataZoom slider reframes every cell together
- clicking a cell moves the cursor in the CD pane *and* scrolls that param's pane into view
- a browser console with no ECharts warnings

Screenshot to `.playwright-mcp/screenshots/fdc-param-matrix.png`.

- [ ] **Step 5: Lint, typecheck, full suite**

Run: `cd front-dev-home && npm run lint && npm run typecheck && npm test`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue
git commit -m "feat(skewvoir): mount the FDC matrix in the sequence workbench

The matrix reads the same SequenceModel the panes below already use, so the
overview and the detail cannot disagree about what was measured.

One click does both jobs: it moves the shared sequence cursor exactly as every
other pane's click does, and scrolls the clicked param's full-size pane into
view with block 'nearest' — a no-op when that pane is already visible, so a
click meant only to move the cursor does not yank the page around."
```

---

## Self-Review

**Spec coverage.** Approach → Task 5. Layout model incl. column cap and wrapping → Tasks 1, 3. Suspects row and ordering → Task 2. `paramMatrix.ts` → Tasks 1-3. `ParamMatrix.vue` → Task 5. `useEchart` widening → Task 4. `SequenceWorkbench` changes → Task 6. Interaction (one gesture, shared zoom, axisPointer link, focus markLine) → Tasks 5, 6. Honesty constraints (demo chip verbatim, 평가 불가, suspects omitted) → Tasks 2, 5, 6. Failure states (`hasFdc` false, gaps) → Tasks 1, 5. Testing → Tasks 1-3. Grid-span resolution → Task 5 placement note.

**Type consistency.** `MatrixCell.values` (not `points`) is used in Tasks 1, 3 and 5. `MatrixRow.kind` values `'cd' | 'suspects' | 'category'` are used consistently. `buildParamMatrix`'s five-argument order is identical in Tasks 1, 2, 3 and 6. `onGridClick(xValue, gridIndex)` is defined in Task 4 and consumed in Task 5.

**Known follow-up, not a placeholder.** Task 5 sets `matrix.x.label.show: false` with `levelSize: 2` to suppress the meaningless numeric column header. If that combination still reserves visible space, the fix is a layout tweak found during Task 6's Step 4 verification, not a design change.
