// front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
// Pure-logic tests for the FDC sparkline matrix layout model.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/paramMatrix.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeSequence } from './sequence.ts'
import { buildParamMatrix } from './paramMatrix.ts'
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

// CD rises +2/sequence. StigmaX tracks it exactly, Brightness inverts it.
// Two categories, one param each.
const source = () => ({
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

const build = () => {
  const src = source()
  const model = analyzeSequence(src, 'CD_TOP', 'nm')
  return buildParamMatrix(model, src.rows, src.dynamic_fdc, src.fdc_params, 'CD_TOP')
}

// ---------------------------------------------------------------------------
// Foundation: CD row, category rows, alignment
// ---------------------------------------------------------------------------

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
