// front-dev-home/app/utils/skewvoirAnalysis/cdu.test.ts
// Pure-logic tests for the CDU metric card + failure decomposition.
// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/cdu.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cduMetrics, failureBreakdown, failureClustering } from './cdu.ts'
import type { SpatialFailureSite } from './spatial.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { MeasHistRow } from '~/composables/useMeasHistApi'

const close = (a: number, b: number, eps = 1e-9) =>
  assert.ok(Math.abs(a - b) < eps, `${a} !== ${b}`)

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '150000000,150000000',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

// Five measured CD_TOP sites (98/99/100/101/102), one unmeasured site
// (cd_value null, mp_number -1), and one site of ANOTHER parameter.
const rows = (): MsrFileRow[] => [
  row({ sequence: 1, cd_value: 98 }),
  row({ sequence: 2, cd_value: 99 }),
  row({ sequence: 3, cd_value: 100 }),
  row({ sequence: 4, cd_value: 101 }),
  row({ sequence: 5, cd_value: 102 }),
  row({ sequence: 6, cd_value: null, mp_number: -1 }),
  row({ sequence: 7, parameter: 'CD_BOTTOM', cd_value: 55 })
]

test('cduMetrics reports level and spread for the active parameter only', () => {
  const m = cduMetrics(rows(), 'CD_TOP', 'nm')
  assert.equal(m.parameter, 'CD_TOP')
  assert.equal(m.unit, 'nm')
  close(m.level!.mean, 100)
  close(m.level!.median, 100)
  // Known-good literals: sd of 98..102 is sqrt(10/4) = 1.5811388300841898.
  close(m.spread!.std, 1.5811388300841898)
  close(m.spread!.threeSigma, 3 * 1.5811388300841898)
  close(m.spread!.range, 4)
  // raw MAD of 98..102 is 1; scaled to a sigma it is 1.4826.
  close(m.spread!.madSigma, 1.4826)
})

test('cduMetrics counts valid N from measured rows and reports the missing ones', () => {
  const m = cduMetrics(rows(), 'CD_TOP', 'nm')
  assert.equal(m.n, 5)
  assert.equal(m.missing, 1)
  assert.equal(m.total, 6)
})

test('cduMetrics never substitutes 0 for a missing cd_value', () => {
  // If the null row were read as 0, the mean would collapse to ~83.
  const m = cduMetrics(rows(), 'CD_TOP', 'nm')
  close(m.level!.mean, 100)
})

test('cduMetrics returns null level/spread rather than a fabricated number when nothing measured', () => {
  const m = cduMetrics([row({ cd_value: null, mp_number: -1 })], 'CD_TOP', 'nm')
  assert.equal(m.level, null)
  assert.equal(m.spread, null)
  assert.equal(m.n, 0)
  assert.equal(m.missing, 1)
})

test('cduMetrics gives a level but no spread from a single measured site', () => {
  const m = cduMetrics([row({ cd_value: 100 })], 'CD_TOP', 'nm')
  close(m.level!.mean, 100)
  close(m.level!.median, 100)
  assert.equal(m.spread, null, 'one point has no spread — 0 would read as perfect uniformity')
})

test('cduMetrics median resists an outlier the mean follows', () => {
  const m = cduMetrics([
    row({ sequence: 1, cd_value: 99 }),
    row({ sequence: 2, cd_value: 100 }),
    row({ sequence: 3, cd_value: 101 }),
    row({ sequence: 4, cd_value: 900 })
  ], 'CD_TOP', 'nm')
  close(m.level!.median, 100.5)
  assert.ok(m.level!.mean > 290, 'mean is dragged by the wild reading')
  assert.ok(m.spread!.madSigma < m.spread!.std, 'MAD stays put while sigma inflates')
})

// ── failureBreakdown ─────────────────────────────────────────────────────

const meas = (over: Partial<MeasHistRow> = {}): MeasHistRow => ({
  id: 'r1', fac_id: 'M14', fab_name: 'M14', vendor_nm: 'HITACHI', eqp_id: 'EQ1', eqp_ip: '1.1.1.1',
  eqp_model_cd: 'CG5000', tool_type: 'cd-sem', lot_cd: 'L1', lot_id: 'L1.1', class_name: 'C1',
  recipe_name: 'RCP_A', full_name: 'RCP_A', timestamp: '2026-08-01 10:00', start_time: '2026-08-01 10:00',
  end_time: '2026-08-01 10:10', meastime: 600, msr: 'M1', msr_check: 'Yes', align_fail: 'Pass',
  total_images: 100, fail_images: 0, fail_ratio: 0, idp_name: 'a.idp', idw_name: 'a.idw',
  ...over
})

const reasonOf = (b: ReturnType<typeof failureBreakdown>, key: string) =>
  b.reasons.find(r => r.key === key)!

test('failureBreakdown splits the four causes instead of one success rate', () => {
  const b = failureBreakdown(rows(), 'CD_TOP', meas())
  assert.deepEqual(b.reasons.map(r => r.key), ['msr_check', 'align_fail', 'image', 'cd_missing'])
})

test('failureBreakdown reads msr_check=No as a failure and Yes as a pass', () => {
  assert.equal(reasonOf(failureBreakdown(rows(), 'CD_TOP', meas({ msr_check: 'No' })), 'msr_check').status, 'fail')
  assert.equal(reasonOf(failureBreakdown(rows(), 'CD_TOP', meas()), 'msr_check').status, 'pass')
})

test('align_fail=NA is unknown, not a failure', () => {
  const b = failureBreakdown(rows(), 'CD_TOP', meas({ align_fail: 'NA' }))
  const align = reasonOf(b, 'align_fail')
  assert.equal(align.status, 'unknown')
  assert.deepEqual(
    b.reasons.filter(r => r.status === 'fail').map(r => r.key),
    ['cd_missing'],
    'NA must not be counted among the failures — only the real missing-CD site is'
  )
  assert.equal(reasonOf(failureBreakdown(rows(), 'CD_TOP', meas({ align_fail: 'Fail' })), 'align_fail').status, 'fail')
})

test('fail_ratio is already a percent — it is carried through untouched', () => {
  const image = reasonOf(failureBreakdown(rows(), 'CD_TOP', meas({ total_images: 350, fail_images: 16, fail_ratio: 4.57 })), 'image')
  assert.equal(image.status, 'fail')
  assert.equal(image.count, 16)
  assert.equal(image.total, 350)
  close(image.percent!, 4.57)
})

test('image failure is 평가 불가 when there are no images to be the denominator', () => {
  const image = reasonOf(failureBreakdown(rows(), 'CD_TOP', meas({ total_images: 0, fail_images: 0, fail_ratio: 0 })), 'image')
  assert.equal(image.status, 'unknown')
  assert.equal(image.percent, null)
})

test('cd_missing counts the unmeasured sites of the active parameter', () => {
  const b = failureBreakdown(rows(), 'CD_TOP', meas())
  const missing = reasonOf(b, 'cd_missing')
  assert.equal(missing.status, 'fail')
  assert.equal(missing.count, 1)
  assert.equal(missing.total, 6, 'the CD_BOTTOM row is another parameter and is not in this denominator')
  close(missing.percent!, 100 / 6)
  assert.deepEqual(b.sites, { total: 6, measured: 5, missing: 1 })
})

test('failureBreakdown without a meas-hist row reports 평가 불가, never a pass', () => {
  const b = failureBreakdown(rows(), 'CD_TOP', null)
  for (const key of ['msr_check', 'align_fail', 'image']) {
    assert.equal(reasonOf(b, key).status, 'unknown', key)
  }
  assert.equal(reasonOf(b, 'cd_missing').status, 'fail', 'the site-level cause needs no meas-hist row')
  assert.equal(b.unknownCount, 3)
})

// ── failureClustering ────────────────────────────────────────────────────

const fail = (sequence: number, sector: string | null): SpatialFailureSite => ({
  sequence,
  chip: `${sequence}, 0`,
  chipXY: [sequence, 0],
  posMm: sector ? [10, 10] : null,
  sector
})

test('failureClustering calls one crowded sector clustered', () => {
  const c = failureClustering([fail(1, 'S'), fail(2, 'S'), fail(3, 'S'), fail(4, 'E')])
  assert.equal(c.status, 'ok')
  assert.equal(c.placed, 4)
  assert.equal(c.verdict, 'clustered')
  assert.equal(c.sectors[0]!.key, 'S')
  assert.equal(c.sectors[0]!.count, 3)
  assert.equal(c.sectors[0]!.label, '하단(S·노치)', 'the label comes from spatial.ts, not a second table')
  close(c.topShare!, 0.75)
})

test('failureClustering calls evenly spread failures scattered', () => {
  const c = failureClustering([fail(1, 'S'), fail(2, 'E'), fail(3, 'N'), fail(4, 'W')])
  assert.equal(c.verdict, 'scattered')
  close(c.topShare!, 0.25)
})

test('failureClustering refuses a verdict on too few placed failures', () => {
  const c = failureClustering([fail(1, 'S'), fail(2, 'S')])
  assert.equal(c.status, 'unavailable')
  assert.equal(c.verdict, null)
  assert.ok(c.reason)
})

test('failureClustering keeps unplaceable failures out of the denominator', () => {
  const c = failureClustering([fail(1, 'S'), fail(2, 'S'), fail(3, 'S'), fail(4, null)])
  assert.equal(c.placed, 3)
  assert.equal(c.unplaced, 1)
  close(c.topShare!, 1)
})

test('failureClustering on no failures at all is unavailable, not clustered', () => {
  const c = failureClustering([])
  assert.equal(c.status, 'unavailable')
  assert.equal(c.verdict, null)
  assert.deepEqual(c.sectors, [])
})
