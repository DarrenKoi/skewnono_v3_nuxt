// frontend/app/utils/skewvoirAnalysis/features.test.ts
// Pure-logic tests — run: cd frontend && node --test app/utils/skewvoirAnalysis/features.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  featureRows,
  featureRegistry,
  type FeatureSource,
  type DerivedValue
} from './features.ts'
import type { MsrFileRow, MsrParamSummary, FdcParamSummary, ExeDetailInfo } from '~/composables/useMsrFileApi'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { overviewSites } from '../overview.ts'
import { DEFAULT_METHOD_CONFIG } from '../anomaly/types.ts'

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

// ---------------------------------------------------------------------------
// Measurement-quality / execution signals — DISPLAY-ONLY axes (2026-10-09)
// ---------------------------------------------------------------------------

// Scores chosen so every median is readable by hand. The FAILED row (seq 4)
// carries a measurement_score on purpose: a failed measurement's score is the
// interesting one, so it must be counted, not dropped with the cd_value gate.
const qualitySource = (): FeatureSource => ({
  ...sourceM1(),
  rows: [
    row({ sequence: 1, cd_value: 100, measurement_score: 100, addressing1_score: 868, addressing2_score: null }),
    row({ sequence: 2, cd_value: 105, measurement_score: 200, addressing1_score: null, addressing2_score: null }),
    row({ sequence: 3, cd_value: 110, measurement_score: 400, addressing1_score: 870, addressing2_score: null }),
    row({ sequence: 4, cd_value: null, mp_number: -1, measurement_score: 900, addressing1_score: null, addressing2_score: null }),
    // Another parameter's row never enters the active parameter's median.
    row({ sequence: 1, parameter: 'CD_BOT', measurement_score: 5, addressing1_score: 5 })
  ],
  alignment: {
    offset: {
      1: ['OM', '3', '4'],
      2: ['SEM', 'abc', '5'],
      3: ['SEM', '', '7']
    }
  }
})

test('score axes are the median over the active parameter rows that carry a score, failed rows included', () => {
  const [r] = featureRows([qualitySource()], 'CD_TOP')
  const ms = r!.quality.measurement_score!
  assert.equal(ms.value, 300) // median of 100, 200, 400, 900 (the 900 is the failed row)
  assert.equal(ms.n, 4)
  assert.equal(ms.missing, 0)
  assert.equal(ms.unit, '')

  const a1 = r!.quality.addressing1_score!
  assert.equal(a1.value, 869) // median of 868, 870
  assert.equal(a1.n, 2)
  assert.equal(a1.missing, 2)
})

test('a score nobody recorded yields no figure, never a zero', () => {
  const [r] = featureRows([qualitySource()], 'CD_TOP')
  assert.equal(r!.quality.addressing2_score, undefined)
})

test('alignment offset magnitude exists only where both components are numeric', () => {
  const [r] = featureRows([qualitySource()], 'CD_TOP')
  assert.equal(r!.quality['alignment_offset.1']!.value, 5) // hypot(3, 4)
  assert.equal(r!.quality['alignment_offset.1']!.unit, '')
  assert.equal(r!.quality['alignment_offset.2'], undefined) // 'abc'
  assert.equal(r!.quality['alignment_offset.3'], undefined) // '' must not parse as 0
})

test('seconds per point is meastime over the distinct sequences, and absent when either is missing or zero', () => {
  const hist = (meastime: number) => new Map([['M1', { meastime }]])
  const [r] = featureRows([qualitySource()], 'CD_TOP', undefined, hist(120))
  assert.equal(r!.quality.sec_per_point!.value, 30) // 120 s / 4 sequences
  assert.equal(r!.quality.sec_per_point!.unit, 's')

  assert.equal(featureRows([qualitySource()], 'CD_TOP', undefined, hist(0))[0]!.quality.sec_per_point, undefined)
  assert.equal(featureRows([qualitySource()], 'CD_TOP')[0]!.quality.sec_per_point, undefined)
  const noRows = { ...qualitySource(), rows: [] }
  assert.equal(featureRows([noRows], 'CD_TOP', undefined, hist(120))[0]!.quality.sec_per_point, undefined)
})

test('featureRegistry lists the quality axes last, unitless where the schema states no unit', () => {
  const defs = featureRegistry([qualitySource()], 'CD_TOP')
  const quality = defs.filter(d => d.family === 'quality')
  assert.deepEqual(quality.map(d => [d.id, d.label, d.unit]), [
    ['quality.measurement_score', 'measurement_score 중앙값', ''],
    ['quality.addressing1_score', 'addressing1_score 중앙값', ''],
    ['quality.addressing2_score', 'addressing2_score 중앙값', ''],
    ['quality.sec_per_point', '측정점당 소요 시간', 's'],
    ['quality.alignment_offset.1', 'alignment offset 1 크기', ''],
    ['quality.alignment_offset.2', 'alignment offset 2 크기', ''],
    ['quality.alignment_offset.3', 'alignment offset 3 크기', '']
  ])
  assert.deepEqual(defs.slice(-7), quality)
  for (const d of Object.values(featureRows([qualitySource()], 'CD_TOP')[0]!.quality)) assertDerivedValue(d)
})

// The research note excluded vendor scores from the JUDGEMENT path
// (docs/issues/skewvoir/wafer-analysis-method-research.md §2, P0). Two proofs:
// the judgement functions return the same answer whatever the scores say, and
// no judgement module so much as names one of these fields.
test('quality axes are display-only: no verdict moves with a score, and no judgement module reads one', () => {
  const rescored = (score: number | null): FeatureSource => ({
    ...qualitySource(),
    rows: qualitySource().rows.map(r => ({
      ...r, measurement_score: score, addressing1_score: score, addressing2_score: score
    }))
  })
  for (const score of [1, 999999, null]) {
    assert.deepEqual(
      overviewSites(rescored(score).rows, 'CD_TOP'),
      overviewSites(qualitySource().rows, 'CD_TOP')
    )
    const { quality: _q, ...judged } = featureRows([rescored(score)], 'CD_TOP')[0]!
    const { quality: _q0, ...baseline } = featureRows([qualitySource()], 'CD_TOP')[0]!
    assert.deepEqual(judged, baseline)
  }

  // The anomaly thresholds reach featureRows only for the coverage counts;
  // tightening them to the floor must leave every quality figure untouched.
  const strict = {
    ...DEFAULT_METHOD_CONFIG,
    range: { watchPct: 0.0001, abnormalPct: 0.0002, minAbsCenter: 1e-6 },
    stddev: { watchK: 0.0001, abnormalK: 0.0002 }
  }
  assert.deepEqual(
    featureRows([qualitySource()], 'CD_TOP', strict)[0]!.quality,
    featureRows([qualitySource()], 'CD_TOP')[0]!.quality
  )

  const here = dirname(fileURLToPath(import.meta.url))
  const judgement = [
    ...readdirSync(join(here, '../anomaly')).filter(f => f.endsWith('.ts') && !f.endsWith('.test.ts')).map(f => join(here, '../anomaly', f)),
    join(here, 'verdict.ts'),
    join(here, 'timeSeries.ts'),
    join(here, 'baselineCompare.ts'),
    join(here, '../overview.ts')
  ]
  assert.ok(judgement.length > 4)
  for (const file of judgement) {
    assert.doesNotMatch(
      readFileSync(file, 'utf8'),
      /measurement_score|addressing[12]_score|meastime|sec_per_point|alignment_offset|\.quality\b|features\.ts/,
      file
    )
  }
})
