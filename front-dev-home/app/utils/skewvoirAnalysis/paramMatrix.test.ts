// front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
// Pure-logic tests for the FDC sparkline matrix layout model.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeSequence, type SequenceSource } from './sequence.ts'
import { buildParamMatrix, MAX_COLUMNS, MAX_EVIDENCE } from './paramMatrix.ts'
import type { MsrFileRow, FdcParamSummary } from '~/composables/useMsrFileApi'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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

const cdRows = () => [
  row({ sequence: 1, cd_value: 100 }),
  row({ sequence: 2, cd_value: 102 }),
  row({ sequence: 3, cd_value: 104 }),
  row({ sequence: 4, cd_value: 106 })
]

/** Params sharing one category, so ordering within a row is observable. */
const oneCategory = (names: string[]) =>
  names.map(n => fdcParam({ name: n, category: 'defocus', category_label: 'defocus' }))

const build = (src: SequenceSource) =>
  buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src)

// CD rises +2/sequence. StigmaX tracks it exactly, Brightness inverts it.
// Two categories, one param each.
const source = (): SequenceSource => ({
  rows: cdRows(),
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

// ---------------------------------------------------------------------------
// Foundation: CD row, category rows, alignment
// ---------------------------------------------------------------------------

test('row 0 is the CD reference row carrying the active CD parameter', () => {
  const m = build(source())
  assert.equal(m.rows[0]?.kind, 'cd')
  assert.equal(m.rows[0]?.cells.length, 1)
  assert.equal(m.rows[0]?.cells[0]?.param, 'CD_TOP')
  assert.equal(m.rows[0]?.cells[0]?.category, 'cd')
  assert.equal(m.rows[0]?.cells[0]?.nominal, null)
})

test('the CD cell is a reference, not an unavailable relation', () => {
  const cd = build(source()).rows[0]?.cells[0]
  assert.equal(cd?.rState, 'reference')
  assert.equal(cd?.r, null)
})

test('category rows use the Korean label resolved from fdc_params', () => {
  const labels = build(source()).rows.filter(r => r.kind === 'category').map(r => r.label)
  assert.ok(labels.includes('비점수차'))
  assert.ok(labels.includes('이미지 품질'))
})

test('cell values are aligned onto the shared sequence axis', () => {
  const m = build(source())
  const stigma = m.rows.flatMap(r => r.cells).find(c => c.param === 'StigmaX')
  assert.deepEqual(m.sequences, [1, 2, 3, 4])
  assert.deepEqual(stigma?.values, [10, 12, 14, 16])
})

test('a sequence with no CD measurement becomes a gap, not an interpolation', () => {
  const src = source()
  src.rows = [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: null, mp_number: -1 }),
    row({ sequence: 3, cd_value: 104 }),
    row({ sequence: 4, cd_value: 106 })
  ]
  const cd = build(src).rows[0]?.cells[0]
  assert.deepEqual(cd?.values, [100, null, 104, 106])
})

test('every FDC param appears exactly once outside the evidence row', () => {
  const names = build(source()).rows
    .filter(r => r.kind === 'category')
    .flatMap(r => r.cells)
    .map(c => c.param)
  assert.deepEqual([...names].sort(), ['Brightness', 'StigmaX'])
})

test('row labels are unique so they can be used as ordinal matrix coords', () => {
  const labels = build(source()).rows.map(r => r.label)
  assert.equal(new Set(labels).size, labels.length)
})

test('a CD-only MSR with no dynamic FDC yields just the CD row', () => {
  const src = source()
  src.dynamic_fdc = {}
  src.fdc_params = []
  const m = build(src)
  assert.equal(m.rows.length, 1)
  assert.equal(m.rows[0]?.kind, 'cd')
  assert.equal(m.columns, 1)
})

// ---------------------------------------------------------------------------
// Ranking: ordering by |r| to CD, and the evidence row
// ---------------------------------------------------------------------------

// Up tracks CD exactly (r = +1.000); Down inverts it imperfectly (r ≈ -0.981);
// Flat is constant, so it has zero variance → 평가 불가, never rankable.
const orderedSource = (): SequenceSource => ({
  rows: cdRows(),
  dynamic_fdc: {
    1: { Up: 1, Down: 40, Flat: 5 },
    2: { Up: 2, Down: 30, Flat: 5 },
    3: { Up: 3, Down: 25, Flat: 5 },
    4: { Up: 4, Down: 10, Flat: 5 }
  } as unknown as Record<string, Record<string, number>>,
  fdc_params: oneCategory(['Up', 'Down', 'Flat'])
})

test('a constant param is 평가 불가 and carries no r, with a reason', () => {
  const flat = build(orderedSource()).rows.flatMap(r => r.cells).find(c => c.param === 'Flat')
  assert.equal(flat?.rState, 'unavailable')
  assert.equal(flat?.r, null)
  assert.ok(flat?.reason)
})

test('category cells order by |r| descending with unevaluable last', () => {
  const catRow = build(orderedSource()).rows.find(r => r.kind === 'category')
  assert.deepEqual(catRow?.cells.map(c => c.param), ['Up', 'Down', 'Flat'])
})

test('the evidence row sits at index 1 and holds only evaluable params', () => {
  const m = build(orderedSource())
  assert.equal(m.rows[1]?.kind, 'evidence')
  assert.deepEqual(m.rows[1]?.cells.map(c => c.param), ['Up', 'Down'])
})

test('evidence cells are copies, flagged duplicated, and originals stay in place', () => {
  const m = build(orderedSource())
  assert.ok(m.rows[1]!.cells.every(c => c.duplicated))
  const catRow = m.rows.find(r => r.kind === 'category')
  assert.ok(catRow!.cells.every(c => !c.duplicated))
  assert.equal(catRow!.cells.length, 3)
})

test('the evidence row is omitted entirely when nothing is evaluable', () => {
  const src = orderedSource()
  src.dynamic_fdc = {
    1: { Flat: 5 }, 2: { Flat: 5 }, 3: { Flat: 5 }, 4: { Flat: 5 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = oneCategory(['Flat'])
  assert.ok(!build(src).rows.some(r => r.kind === 'evidence'))
})

test('the evidence row caps at MAX_EVIDENCE', () => {
  const src = orderedSource()
  src.dynamic_fdc = {
    1: { A: 1, B: 2, C: 3, D: 4, E: 5 },
    2: { A: 2, B: 4, C: 6, D: 8, E: 10 },
    3: { A: 4, B: 7, C: 9, D: 11, E: 14 },
    4: { A: 8, B: 9, C: 13, D: 15, E: 21 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = oneCategory(['A', 'B', 'C', 'D', 'E'])
  assert.equal(build(src).rows.find(r => r.kind === 'evidence')!.cells.length, MAX_EVIDENCE)
})

test('equal |r| breaks by param name so order is stable', () => {
  const src = orderedSource()
  // Zeta and Alpha both track CD exactly → identical |r| = 1.
  src.dynamic_fdc = {
    1: { Zeta: 1, Alpha: 1 }, 2: { Zeta: 2, Alpha: 2 },
    3: { Zeta: 3, Alpha: 3 }, 4: { Zeta: 4, Alpha: 4 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = oneCategory(['Zeta', 'Alpha'])
  const catRow = build(src).rows.find(r => r.kind === 'category')
  assert.deepEqual(catRow!.cells.map(c => c.param), ['Alpha', 'Zeta'])
})

// ---------------------------------------------------------------------------
// Column cap and continuation-row wrapping
// ---------------------------------------------------------------------------

// Six params in ONE category — two past MAX_COLUMNS = 4.
const wideSource = (): SequenceSource => {
  const names = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']
  const dynamic_fdc: Record<string, Record<string, number>> = {}
  for (let seq = 1; seq <= 4; seq++) {
    const channels: Record<string, number> = {}
    for (const [i, n] of names.entries()) channels[n] = seq * (i + 1)
    dynamic_fdc[String(seq)] = channels
  }
  return {
    rows: cdRows(),
    dynamic_fdc,
    fdc_params: names.map(n =>
      fdcParam({ name: n, category: 'stage_drift', category_label: '스테이지 드리프트' }))
  }
}

test('columns never exceed MAX_COLUMNS however many params a category has', () => {
  assert.equal(build(wideSource()).columns, MAX_COLUMNS)
})

test('an oversized category wraps onto continuation rows', () => {
  const catRows = build(wideSource()).rows.filter(r => r.kind === 'category')
  assert.equal(catRows.length, 2)
  assert.equal(catRows[0]?.cells.length, 4)
  assert.equal(catRows[1]?.cells.length, 2)
  // The continuation is visible in the label suffix, which is what the matrix
  // renders and what keeps the ordinal coord unique.
  assert.ok(!catRows[0]?.label.endsWith('(2)'))
  assert.ok(catRows[1]?.label.endsWith('(2)'))
})

test('wrapping loses no param and duplicates none', () => {
  const names = build(wideSource()).rows
    .filter(r => r.kind === 'category')
    .flatMap(r => r.cells)
    .map(c => c.param)
  assert.equal(names.length, 6)
  assert.equal(new Set(names).size, 6)
})

test('continuation row labels stay unique for use as ordinal coords', () => {
  const m = build(wideSource())
  const labels = m.rows.map(r => r.label)
  assert.equal(new Set(labels).size, labels.length)
  const catRows = m.rows.filter(r => r.kind === 'category')
  assert.equal(catRows[0]?.label, '스테이지 드리프트')
  assert.equal(catRows[1]?.label, '스테이지 드리프트 (2)')
})

// ---------------------------------------------------------------------------
// The matrix inherits the scoped axis (Task 1). Before that fix the CD row was
// mostly null while every FDC row was dense, so the picture and the r badge
// printed beside it were computed on different samples.
// ---------------------------------------------------------------------------

const interleavedSource = (): SequenceSource => ({
  rows: [
    row({ sequence: 1, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, parameter: 'SPACE', cd_value: 50 }),
    row({ sequence: 3, parameter: 'CD_TOP', cd_value: 104 }),
    row({ sequence: 4, parameter: 'SPACE', cd_value: 52 }),
    row({ sequence: 5, parameter: 'CD_TOP', cd_value: 108 }),
    row({ sequence: 6, parameter: 'SPACE', cd_value: 54 })
  ],
  dynamic_fdc: {
    1: { StigmaX: 10 }, 2: { StigmaX: 11 }, 3: { StigmaX: 12 },
    4: { StigmaX: 13 }, 5: { StigmaX: 14 }, 6: { StigmaX: 15 }
  },
  fdc_params: [fdcParam({})]
})

test('matrix cells span the active parameter axis, not the whole MSR', () => {
  const src = interleavedSource()
  const matrix = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src)
  assert.deepEqual(matrix.sequences, [1, 3, 5])
  for (const r of matrix.rows) {
    for (const c of r.cells) {
      assert.equal(c.values.length, 3, `${c.param} has ${c.values.length} values for a 3-sequence axis`)
    }
  }
})

test('the CD row has no manufactured gaps once the axis is scoped', () => {
  const src = interleavedSource()
  const matrix = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src)
  const cd = matrix.rows.find(r => r.kind === 'cd')!.cells[0]!
  assert.deepEqual(cd.values, [100, 104, 108])
})

// ---------------------------------------------------------------------------
// hideUnavailable: the tooltip-declutter toggle
// ---------------------------------------------------------------------------

test('hideUnavailable drops 평가 불가 cells and counts what it hid', () => {
  const src = orderedSource()
  const m = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src, { hideUnavailable: true })
  const names = m.rows.filter(r => r.kind === 'category').flatMap(r => r.cells).map(c => c.param)
  assert.deepEqual(names, ['Up', 'Down'])
  assert.equal(m.hiddenUnavailable, 1)
})

test('hideUnavailable defaults off: 평가 불가 cells stay and nothing is counted hidden', () => {
  const m = build(orderedSource())
  assert.equal(m.hiddenUnavailable, 0)
  assert.ok(m.rows.flatMap(r => r.cells).some(c => c.rState === 'unavailable'))
})

test('hiding every FDC cell degrades to the CD row, never an empty matrix', () => {
  const src = orderedSource()
  src.dynamic_fdc = {
    1: { Flat: 5 }, 2: { Flat: 5 }, 3: { Flat: 5 }, 4: { Flat: 5 }
  } as unknown as Record<string, Record<string, number>>
  src.fdc_params = oneCategory(['Flat'])
  const m = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src, { hideUnavailable: true })
  assert.equal(m.rows.length, 1)
  assert.equal(m.rows[0]?.kind, 'cd')
  assert.equal(m.columns, 1)
  assert.equal(m.hiddenUnavailable, 1)
})

test('hideUnavailable leaves the evidence ranking untouched', () => {
  const src = orderedSource()
  const shown = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src)
  const hidden = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src, { hideUnavailable: true })
  assert.deepEqual(
    shown.rows.find(r => r.kind === 'evidence')?.cells.map(c => c.param),
    hidden.rows.find(r => r.kind === 'evidence')?.cells.map(c => c.param)
  )
})
