// front-dev-home/app/utils/skewvoirAnalysis/features.test.ts
// Pure-logic tests — run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/features.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  featureRows,
  featureRegistry,
  type FeatureSource,
  type DerivedValue
} from './features.ts'
import type { MsrFileRow, MsrParamSummary, FdcParamSummary, ExeDetailInfo } from '~/composables/useMsrFileApi'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

const exe = (): ExeDetailInfo => ({
  class_name: 'C1', recipe_name: 'RCP_A', idp_name: '/Recipe/RCP_A.idp', lot_id: 'LOT1',
  process: 'P1', wafer_id: 'W1', idw_name: '/Recipe/RCP_A.idw', chip_array: '40,56',
  chip_pitch: '7500000,5357142', wafer_size: '300000000', map_offset: '0,0', map_origin: '20,28'
})

const paramSummary = (over: Partial<MsrParamSummary> = {}): MsrParamSummary => ({
  parameter: 'CD_TOP', count: 3, mean: 105, std: 5, min: 100, max: 110, unit: 'nm', ...over
})

const fdcParams = (): FdcParamSummary[] => [
  {
    name: 'StageTemp', category: 'stage_drift', category_label: '스테이지 드리프트', unit: 'degC',
    nominal: 23, mean: 23.5, std: 0.1, min: 23.4, max: 23.6, drift_sigma: 0.5, status: 'ok'
  },
  {
    name: 'StigmaX', category: 'astigmatism', category_label: '비점수차', unit: 'nm',
    nominal: 0.1, mean: 0.12, std: 0.02, min: 0.1, max: 0.14, drift_sigma: 0.2, status: 'ok'
  }
]

// A clean, exactly-linear fixture (values chosen so the arithmetic checks out
// by hand): 3 measured sites at radius 0/10/20mm with cd 100/105/110 (slope
// 0.5 nm/mm exactly), one failed site, one fixed FDC scalar, and dynamic FDC
// StigmaX rising 0.10 -> 0.12 -> 0.14 across sequences 1/2/3 (slope 0.02/seq).
const sourceM1 = (): FeatureSource => ({
  msr: 'M1',
  parameters: [paramSummary()],
  rows: [
    row({ sequence: 1, stage_coordinate: '150000000,150000000', cd_value: 100 }),
    row({ sequence: 2, stage_coordinate: '160000000,150000000', cd_value: 105 }),
    row({ sequence: 3, stage_coordinate: '170000000,150000000', cd_value: 110 }),
    row({ sequence: 4, cd_value: null, mp_number: -1, chip_number: '9, 9' })
  ],
  fixed_fdc: { StageTemp: 23.5 },
  dynamic_fdc: {
    1: { StigmaX: 0.10 },
    2: { StigmaX: 0.12 },
    3: { StigmaX: 0.14 }
  },
  fdc_params: fdcParams(),
  exe_detail_info: exe()
})

// A second source with a single measured site — too few points for a spatial
// fit (linearFit needs n >= 2).
const sourceM2 = (): FeatureSource => ({
  msr: 'M2',
  parameters: [paramSummary({ mean: 100, std: 0 })],
  rows: [row({ sequence: 1, msr: 'M2', stage_coordinate: '150000000,150000000', cd_value: 100 })],
  fixed_fdc: {},
  dynamic_fdc: {},
  fdc_params: [],
  exe_detail_info: exe()
})

// ---------------------------------------------------------------------------
// featureRegistry
// ---------------------------------------------------------------------------

test('featureRegistry lists level/spread/coverage/failure/spatial + fdc entries with correct units', () => {
  const defs = featureRegistry([sourceM1()], 'CD_TOP')
  const byId = new Map(defs.map(d => [d.id, d]))

  assert.equal(byId.get('level')?.unit, 'nm')
  assert.equal(byId.get('spread')?.unit, 'nm')
  assert.equal(byId.get('coverage')?.unit, 'ratio')
  assert.equal(byId.get('failure')?.unit, 'ratio')
  assert.equal(byId.get('spatial')?.unit, 'nm')
  assert.equal(byId.get('fixed_fdc.StageTemp')?.unit, 'degC')
  assert.equal(byId.get('dynamic_fdc.StigmaX')?.unit, 'nm')

  assert.equal(byId.get('level')?.family, 'level')
  assert.equal(byId.get('fixed_fdc.StageTemp')?.family, 'fixed_fdc')
  assert.equal(byId.get('dynamic_fdc.StigmaX')?.family, 'dynamic_fdc')
  for (const d of defs) assert.equal(d.grain, 'msr')
})

test('featureRegistry ids are unique and never auto-sum across units (no combined/total entry)', () => {
  const defs = featureRegistry([sourceM1()], 'CD_TOP')
  const ids = defs.map(d => d.id)
  assert.equal(new Set(ids).size, ids.length)
  assert.ok(!ids.some(id => /total|combined|sum/i.test(id)))
})

// ---------------------------------------------------------------------------
// featureRows: level / spread / coverage / failure
// ---------------------------------------------------------------------------

test('level is the mean of measured cd_value, spread is sample std', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  assert.equal(row1!.level.value, 105)
  assert.equal(row1!.level.unit, 'nm')
  assert.equal(row1!.level.n, 3)
  assert.equal(row1!.level.missing, 1)
  assert.equal(row1!.spread.value, 5)
  assert.equal(row1!.spread.n, 3)
})

test('coverage/failure reuse overview.ts counts (measured/total, failed/total)', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  assert.equal(row1!.coverage.n, 4) // total attempted
  assert.equal(row1!.coverage.missing, 1) // failed
  assert.ok(Math.abs(row1!.coverage.value - 0.75) < 1e-9) // 3/4 measured
  assert.ok(Math.abs(row1!.failure.value - 0.25) < 1e-9) // 1/4 failed
})

// ---------------------------------------------------------------------------
// featureRows: spatial (centre -> edge)
// ---------------------------------------------------------------------------

test('spatial is the OLS slope * radius span across measured sites', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  assert.ok(row1!.spatial !== null)
  // slope 0.5 nm/mm over a 20mm span (0mm..20mm) = 10 nm delta.
  assert.ok(Math.abs(row1!.spatial!.value - 10) < 1e-9)
  assert.equal(row1!.spatial!.unit, 'nm')
  assert.equal(row1!.spatial!.n, 3)
})

test('spatial is null when fewer than 2 measured sites are available', () => {
  const [row2] = featureRows([sourceM2()], 'CD_TOP')
  assert.equal(row2!.spatial, null)
})

// ---------------------------------------------------------------------------
// featureRows: fixed FDC (already MSR grain)
// ---------------------------------------------------------------------------

test('fixed FDC carries the raw scalar with its own unit, n=1', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  const temp = row1!.fixedFdc.StageTemp!
  assert.equal(temp.value, 23.5)
  assert.equal(temp.unit, 'degC')
  assert.equal(temp.n, 1)
  assert.equal(temp.missing, 0)
  assert.equal(temp.reference, 'fixed_fdc.StageTemp')
})

// ---------------------------------------------------------------------------
// featureRows: dynamic FDC — grain safety
// ---------------------------------------------------------------------------

test('dynamic FDC reduces per-sequence values to ONE MSR-level entry per param (grain-safe)', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  // 3 sequences carried StigmaX, but the row holds exactly one dynamicFdc entry
  // for it — never one per sequence.
  assert.equal(Object.keys(row1!.dynamicFdc).length, 1)
  const stigma = row1!.dynamicFdc.StigmaX!
  assert.ok(Math.abs(stigma.value.mean - 0.12) < 1e-9)
  assert.ok(Math.abs(stigma.value.std - 0.02) < 1e-9)
  assert.ok(Math.abs(stigma.value.range - 0.04) < 1e-9)
  assert.ok(Math.abs(stigma.value.slope - 0.02) < 1e-9) // OLS slope of value vs seq index
  assert.equal(stigma.unit, 'nm')
  assert.equal(stigma.n, 3)
  assert.equal(stigma.missing, 0)
  assert.equal(stigma.reference, 'dynamic_fdc.*.StigmaX')
})

test('a sequence missing the dynamic param is excluded from n and counted in missing', () => {
  const src = sourceM1()
  src.dynamic_fdc = { 1: { StigmaX: 0.10 }, 2: {}, 3: { StigmaX: 0.14 } }
  const [row1] = featureRows([src], 'CD_TOP')
  const stigma = row1!.dynamicFdc.StigmaX!
  assert.equal(stigma.n, 2)
  assert.equal(stigma.missing, 1)
})

// ---------------------------------------------------------------------------
// featureRows: one row per loaded file, deduped by msr
// ---------------------------------------------------------------------------

test('featureRows produces one row per source, deduped by msr (first wins)', () => {
  const rows = featureRows([sourceM1(), sourceM1(), sourceM2()], 'CD_TOP')
  assert.equal(rows.length, 2)
  assert.deepEqual(rows.map(r => r.msr), ['M1', 'M2'])
})

// ---------------------------------------------------------------------------
// Provenance completeness — every exportable derived value is traceable.
// ---------------------------------------------------------------------------

const assertDerivedValue = (d: DerivedValue<unknown>) => {
  assert.equal(typeof d.unit, 'string')
  assert.equal(typeof d.n, 'number')
  assert.equal(typeof d.missing, 'number')
  assert.ok(d.transform.length > 0)
  assert.ok(d.reference.length > 0)
  assert.ok(d.version.length > 0)
}

test('every derived value in a row carries value/unit/n/missing/transform/reference/version', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  assertDerivedValue(row1!.level)
  assertDerivedValue(row1!.spread)
  assertDerivedValue(row1!.coverage)
  assertDerivedValue(row1!.failure)
  assertDerivedValue(row1!.spatial!)
  for (const d of Object.values(row1!.fixedFdc)) assertDerivedValue(d)
  for (const d of Object.values(row1!.dynamicFdc)) assertDerivedValue(d)
})

// ---------------------------------------------------------------------------
// health & spm_dict are BANNED from the feature registry — demo/placeholder
// scalars, never a source for a real feature.
// ---------------------------------------------------------------------------

test('health and spm_dict never appear in featureRegistry ids/sources/labels', () => {
  const defs = featureRegistry([sourceM1()], 'CD_TOP')
  for (const d of defs) {
    assert.ok(!/health/i.test(d.id))
    assert.ok(!/health/i.test(d.source))
    assert.ok(!/spm_dict/i.test(d.id))
    assert.ok(!/spm_dict/i.test(d.source))
  }
})

test('health and spm_dict never appear as fields on a feature row', () => {
  const [row1] = featureRows([sourceM1()], 'CD_TOP')
  const keys = Object.keys(row1!)
  assert.ok(!keys.includes('health'))
  assert.ok(!keys.includes('spm_dict'))
})
