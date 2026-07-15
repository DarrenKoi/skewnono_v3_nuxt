// front-dev-home/app/utils/overview.test.ts
// Pure-logic tests — run: cd front-dev-home && node --test app/utils/overview.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { overviewSites } from './overview.ts'
import { DEFAULT_METHOD_CONFIG } from './anomaly/types.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

// 5 measured at 100, one at 160 (+60% off LOO mean → abnormal), one failure.
const sample = (): MsrFileRow[] => [
  row({ sequence: 1, cd_value: 100 }),
  row({ sequence: 2, cd_value: 100 }),
  row({ sequence: 3, cd_value: 100 }),
  row({ sequence: 4, cd_value: 100 }),
  row({ sequence: 5, cd_value: 100 }),
  row({ sequence: 6, cd_value: 160, chip_number: '9, 9' }),
  row({ sequence: 7, cd_value: null, mp_number: -1, chip_number: '7, 2' })
]

test('coverage counts measured vs total, failures excluded from measured', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.deepEqual(ov.coverage, { total: 7, measured: 6, failed: 1 })
})

test('outlierCount is abnormal+watch only, never failures or normals', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.outlierCount, 6) // 5 watch + 1 abnormal; the null failure is NOT counted
})

test('tableRows include flagged + failed, exclude normal sites', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  const kinds = ov.tableRows.map(r => r.kind)
  assert.ok(kinds.includes('abnormal'))
  assert.ok(kinds.includes('failed'))
  assert.equal(kinds.filter(k => k === 'abnormal' || k === 'watch').length, 6)
  assert.equal(ov.tableRows.length, 7) // 6 flagged (5 watch + 1 abnormal) + 1 failed
})

test('a failed row carries null cd/delta and kind failed', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  const failed = ov.tableRows.find(r => r.kind === 'failed')!
  assert.equal(failed.sequence, 7)
  assert.equal(failed.cd, null)
  assert.equal(failed.delta, null)
})

test('flagged sorts before failed, flagged by |delta| desc', () => {
  const ov = overviewSites(sample(), 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.tableRows[0]!.kind, 'abnormal')
  assert.equal(ov.tableRows.at(-1)!.kind, 'failed')
})

test('too few measured sites → status insufficient, outlierCount 0', () => {
  const rows = [row({ sequence: 1, cd_value: 100 }), row({ sequence: 2, cd_value: 100 })]
  const ov = overviewSites(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.status, 'insufficient')
  assert.equal(ov.outlierCount, 0)
})

test('other parameters are ignored', () => {
  const rows = [
    ...sample(),
    row({ sequence: 8, parameter: 'CD_BOTTOM', cd_value: 5 })
  ]
  const ov = overviewSites(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.coverage.total, 7)
})

test('normal sites are excluded from outlierCount and tableRows', () => {
  // 9 peers at 100 → each site's leave-one-out mean is ~106.7, a ~6% deviation
  // (< watchPct 10) → normal. The lone 160 site is +60% → abnormal. This is the
  // fixture that actually exercises normal-exclusion: dropping the severity
  // filter in overviewSites would make outlierCount 10 here, not 1.
  const rows = [
    ...Array.from({ length: 9 }, (_, i) => row({ sequence: i + 1, cd_value: 100 })),
    row({ sequence: 10, cd_value: 160, chip_number: '9, 9' })
  ]
  const ov = overviewSites(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.status, 'evaluated')
  assert.equal(ov.outlierCount, 1) // only the 160 site; the 9 normals are excluded
  assert.equal(ov.tableRows.length, 1)
  assert.equal(ov.tableRows[0]!.kind, 'abnormal')
})

test('empty rows and an unmatched parameter yield zero coverage + insufficient status', () => {
  assert.deepEqual(overviewSites([], 'CD_TOP', DEFAULT_METHOD_CONFIG).coverage, { total: 0, measured: 0, failed: 0 })
  const ov = overviewSites(sample(), 'NO_SUCH_PARAM', DEFAULT_METHOD_CONFIG)
  assert.equal(ov.coverage.total, 0)
  assert.equal(ov.status, 'insufficient')
  assert.deepEqual(ov.tableRows, [])
})

test('multiple failed rows sort by sequence', () => {
  const rows = [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 100 }),
    row({ sequence: 3, cd_value: 100 }),
    row({ sequence: 9, cd_value: null, mp_number: -1 }),
    row({ sequence: 5, cd_value: null, mp_number: -1 })
  ]
  const failed = overviewSites(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG).tableRows.filter(r => r.kind === 'failed')
  assert.deepEqual(failed.map(r => r.sequence), [5, 9])
})
