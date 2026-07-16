// front-dev-home/app/utils/skewvoirAnalysis/spatial.test.ts
// Pure-logic tests for the single-MSR spatial diagnosis.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/spatial.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeSpatial } from './spatial.ts'
import { parseWaferGeometry } from '../waferGeometry.ts'
import type { MsrFileRow, ExeDetailInfo } from '~/composables/useMsrFileApi'

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
  chip_pitch: '7500000,5357142', wafer_size: '300', map_offset: '0,0', map_origin: '150000000,150000000'
})

const geo = () => parseWaferGeometry(exe())

// A wafer whose CD rises exactly 0.5 nm/mm along +x: radii 0/10/20/30 mm,
// cd 100/105/110/115. Centre (150e6,150e6) nm for a 300 mm wafer. One failed
// site (cd null, mp -1) for the failure layer.
const linearRows = (): MsrFileRow[] => [
  row({ sequence: 1, chip_number: '0, 0', stage_coordinate: '150000000,150000000', cd_value: 100 }),
  row({ sequence: 2, chip_number: '1, 0', stage_coordinate: '160000000,150000000', cd_value: 105 }),
  row({ sequence: 3, chip_number: '2, 0', stage_coordinate: '170000000,150000000', cd_value: 110 }),
  row({ sequence: 4, chip_number: '3, 0', stage_coordinate: '180000000,150000000', cd_value: 115 }),
  row({ sequence: 5, chip_number: '9, 9', stage_coordinate: '150000000,150000000', cd_value: null, mp_number: -1 })
]

// Four sites, one per compass sector, distinct values so sector medians differ.
const sectorRows = (): MsrFileRow[] => [
  row({ sequence: 1, chip_number: '1, 0', stage_coordinate: '160000000,150000000', cd_value: 120 }), // E
  row({ sequence: 2, chip_number: '0, 1', stage_coordinate: '150000000,160000000', cd_value: 100 }), // N
  row({ sequence: 3, chip_number: '-1, 0', stage_coordinate: '140000000,150000000', cd_value: 118 }), // W
  row({ sequence: 4, chip_number: '0, -1', stage_coordinate: '150000000,140000000', cd_value: 102 }) // S
]

// ---------------------------------------------------------------------------

test('splits measured sites from the failure layer via the isMeasuredRow gate', () => {
  const r = analyzeSpatial(linearRows(), 'CD_TOP', geo())
  assert.equal(r.sites.length, 4)
  assert.equal(r.failures.length, 1)
  assert.equal(r.failures[0]!.sequence, 5)
  assert.deepEqual(r.sites.map(s => s.sequence), [1, 2, 3, 4])
})

test('median-centered layer subtracts the wafer median from each raw value', () => {
  const r = analyzeSpatial(linearRows(), 'CD_TOP', geo())
  assert.equal(r.waferMedian, 107.5) // median of 100,105,110,115
  const bySeq = new Map(r.sites.map(s => [s.sequence, s]))
  assert.equal(bySeq.get(1)!.raw, 100)
  assert.equal(bySeq.get(1)!.centered, 100 - 107.5)
  assert.equal(bySeq.get(4)!.centered, 115 - 107.5)
})

test('residual layer reuses the radial trend fit — a perfectly linear wafer leaves ~0 residuals', () => {
  const r = analyzeSpatial(linearRows(), 'CD_TOP', geo(), { model: 'linear' })
  assert.equal(r.readiness.radialTrend, 'ok')
  for (const s of r.sites) {
    assert.notEqual(s.residual, null)
    assert.ok(Math.abs(s.residual!) < 1e-8, `residual ${s.residual} not ~0`)
  }
})

test('radius bins carry median / spread / N and each site knows its radius', () => {
  const r = analyzeSpatial(linearRows(), 'CD_TOP', geo())
  assert.ok(r.radiusBins.length >= 1)
  const totalN = r.radiusBins.reduce((sum, b) => sum + b.count, 0)
  assert.equal(totalN, 4)
  for (const b of r.radiusBins) {
    assert.ok(Number.isFinite(b.median))
    assert.ok(b.spread >= 0)
    assert.equal(b.spread, b.q3 - b.q1)
  }
  const bySeq = new Map(r.sites.map(s => [s.sequence, s]))
  assert.equal(bySeq.get(1)!.radiusMm, 0)
  assert.equal(bySeq.get(4)!.radiusMm, 30)
})

test('sector summary uses the validated default notch (bottom) and reports per-sector median/N', () => {
  const r = analyzeSpatial(sectorRows(), 'CD_TOP', geo())
  assert.equal(r.sectors.status, 'ok')
  assert.equal(r.sectors.notch, 'bottom')
  const bySector = new Map(r.sectors.sectors.map(s => [s.key, s]))
  assert.equal(bySector.get('E')!.median, 120)
  assert.equal(bySector.get('N')!.median, 100)
  assert.equal(bySector.get('W')!.median, 118)
  assert.equal(bySector.get('S')!.median, 102)
  for (const s of r.sectors.sectors) assert.equal(s.count, 1)
})

test('the answer strip exposes four SEPARATE evidence values, never one merged score', () => {
  const r = analyzeSpatial(linearRows(), 'CD_TOP', geo(), { unit: 'nm' })
  const keys = Object.keys(r.evidence).sort()
  assert.deepEqual(keys, ['centerEdgeDelta', 'coverage', 'directionContrast', 'largestLocalResidual'])
  // Distinct values — not the same number copied into four chips.
  assert.equal(r.evidence.coverage.value, 4 / 5)
  assert.notEqual(r.evidence.centerEdgeDelta.value, r.evidence.coverage.value)
  // No merged "score"/"health" field masquerading as a single verdict.
  assert.ok(!('score' in r.evidence))
})

test('center→edge delta follows the radial trend across the measured span', () => {
  const r = analyzeSpatial(linearRows(), 'CD_TOP', geo(), { model: 'linear' })
  // slope 0.5 nm/mm over a 30 mm span → +15 nm from centre to edge.
  assert.equal(r.evidence.centerEdgeDelta.status, 'ok')
  assert.ok(Math.abs(r.evidence.centerEdgeDelta.value! - 15) < 1e-6)
})

test('coordinate readiness: stripping stage coordinates makes the sector summary 평가 불가, not fabricated', () => {
  const stripped = linearRows().map(rw => ({ ...rw, stage_coordinate: '' }))
  const r = analyzeSpatial(stripped, 'CD_TOP', geo())
  assert.equal(r.readiness.coordinates, 'unavailable')
  assert.equal(r.readiness.radialTrend, 'unavailable')
  assert.equal(r.sectors.status, 'unavailable')
  assert.equal(r.sectors.sectors.length, 0)
  assert.equal(r.radiusBins.length, 0)
  // Radial-dependent evidence is unavailable, not invented.
  assert.equal(r.evidence.centerEdgeDelta.status, 'unavailable')
  assert.equal(r.evidence.centerEdgeDelta.value, null)
  assert.equal(r.evidence.directionContrast.status, 'unavailable')
  assert.equal(r.evidence.largestLocalResidual.status, 'unavailable')
  // But the raw layer + coverage survive: values still centred against the wafer median.
  assert.equal(r.sites.length, 4)
  assert.equal(r.waferMedian, 107.5)
  assert.equal(r.sites[0]!.residual, null)
  assert.equal(r.evidence.coverage.status, 'ok')
  assert.equal(r.evidence.coverage.value, 4 / 5)
})

test('single-MSR path never derives a cross-wafer / cross-site σ', () => {
  // Every site identical → every WITHIN-wafer spread is exactly 0. A cross-wafer
  // sigma would be undefined here (there is only one wafer); the module must not
  // fabricate one. Spreads are IQRs of a single wafer's own sites.
  const flat = [
    row({ sequence: 1, stage_coordinate: '150000000,150000000', cd_value: 100 }),
    row({ sequence: 2, stage_coordinate: '160000000,150000000', cd_value: 100 }),
    row({ sequence: 3, stage_coordinate: '150000000,160000000', cd_value: 100 }),
    row({ sequence: 4, stage_coordinate: '140000000,150000000', cd_value: 100 })
  ]
  const r = analyzeSpatial(flat, 'CD_TOP', geo())
  for (const b of r.radiusBins) assert.equal(b.spread, 0)
  for (const s of r.sectors.sectors) assert.equal(s.spread, 0)
  // No field named like a wafer-to-wafer / site sigma may exist anywhere.
  assert.ok(!/sigma|crosswafer|wafertowafer/i.test(JSON.stringify(r)))
})
