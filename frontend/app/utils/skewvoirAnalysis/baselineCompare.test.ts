// Pure-logic tests for the hand-split baseline ↔ target comparison (S7).
// Run: cd frontend && node --test app/utils/skewvoirAnalysis/baselineCompare.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { baselineComparison, baselineDeltaMap, baselineSentence, compositeSiteMap, splitBaseline } from './baselineCompare.ts'
import type { MsrFileResponse, MsrFileRow } from '~/composables/useMsrFileApi'

const close = (a: number | null | undefined, b: number, eps = 1e-6) =>
  assert.ok(a != null && Math.abs(a - b) < eps, `${a} !== ${b}`)

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

// Only `rows` is read; the rest of MsrFileResponse is irrelevant to the maths.
const files = (spec: Record<string, MsrFileRow[]>) =>
  new Map(Object.entries(spec).map(([msr, rows]) => [msr, { msr, rows } as MsrFileResponse]))

const values = (...vs: number[]) => vs.map((cd_value, i) => row({ sequence: i + 1, cd_value }))

const SET = files({
  B1: values(10, 12),
  B2: [...values(14, 16, 18), row({ cd_value: null, mp_number: -1 }), row({ parameter: 'CD_BOTTOM', cd_value: 999 })],
  T1: values(15, 17, 19, 21)
})

test('splitBaseline: baseline and the rest, each narrowed to the manifest-included MSRs', () => {
  assert.deepEqual(
    splitBaseline(['a', 'b', 'c', 'd'], ['b'], ['a', 'b', 'c']),
    { base: ['b'], target: ['a', 'c'] }
  )
})

test('baselineComparison: pooled level and spread per side, and how far the target moved', () => {
  const r = baselineComparison(SET, ['B1', 'B2'], ['T1'], 'CD_TOP', 'nm')
  // base pool 10,12,14,16,18 → mean 14, median 14, s = √10, range 8
  assert.equal(r.base.msrs.length, 2)
  assert.equal(r.base.pooled.n, 5)
  close(r.base.pooled.level?.mean, 14)
  close(r.base.pooled.level?.median, 14)
  close(r.base.pooled.spread?.threeSigma, 9.486833)
  close(r.base.pooled.spread?.range, 8)
  // target pool 15,17,19,21 → mean 18, s = √(20/3), range 6
  assert.equal(r.target.pooled.n, 4)
  close(r.target.pooled.level?.mean, 18)
  close(r.target.pooled.spread?.threeSigma, 7.745967)
  assert.equal(r.reason, null)
  close(r.comparison?.shift, 4)
  close(r.comparison?.shiftInBaseSigma, 0.421637)
  close(r.comparison?.threeSigmaRatio, 0.816497)
  close(r.comparison?.rangeDelta, -2)
})

test('baselineComparison: a unit mismatch never arrives — the manifest excluded it before the split', () => {
  // The function pools whatever ids it is handed; it is splitBaseline's
  // `included` argument that keeps an incompatible MSR out of both sides.
  const { base, target } = splitBaseline(['B1', 'B2', 'T1'], ['B1', 'B2'], ['B1', 'T1'])
  const r = baselineComparison(SET, base, target, 'CD_TOP', 'nm')
  assert.deepEqual(r.base.msrs.map(m => m.msr), ['B1'])
  assert.equal(r.base.pooled.n, 2)
})

test('baselineComparison: an id with no loaded file or no points of the parameter is not a contributing MSR', () => {
  const r = baselineComparison(SET, ['B1', 'GONE'], ['T1'], 'CD_TOP', 'nm')
  assert.equal(r.base.requested, 2)
  assert.deepEqual(r.base.msrs.map(m => m.msr), ['B1'])
})

test('baselineComparison: fewer than two points on a side is 평가 불가, not a zero shift', () => {
  const thin = files({ B1: values(10), T1: values(15, 17) })
  const r = baselineComparison(thin, ['B1'], ['T1'], 'CD_TOP', 'nm')
  assert.equal(r.comparison, null)
  assert.match(r.reason ?? '', /기준/)

  const noTarget = baselineComparison(SET, ['B1', 'B2', 'T1'], [], 'CD_TOP', 'nm')
  assert.equal(noTarget.comparison, null)
  assert.match(noTarget.reason ?? '', /대상/)
})

test('baselineComparison: a flat baseline has no σ to scale by — the ratios are null, the shift stands', () => {
  const flat = files({ B1: values(10, 10), T1: values(11, 13) })
  const r = baselineComparison(flat, ['B1'], ['T1'], 'CD_TOP', 'nm')
  close(r.comparison?.shift, 2)
  assert.equal(r.comparison?.shiftInBaseSigma, null)
  assert.equal(r.comparison?.threeSigmaRatio, null)
})

test('baselineComparison: dominance is the largest MSR\'s share of the pooled points', () => {
  // 3 of 5 points = 0.6 exactly: not OVER the line.
  const even = baselineComparison(SET, ['B1', 'B2'], ['T1'], 'CD_TOP', 'nm')
  close(even.base.dominance, 0.6)
  assert.equal(even.base.dominated, false)
  // A single-MSR side is 1.0 by construction — nothing is being drowned out.
  close(even.target.dominance, 1)
  assert.equal(even.target.dominated, false)

  // 7 of 9 points come from one MSR.
  const skewed = files({ B1: values(10, 12), B2: values(1, 2, 3, 4, 5, 6, 7), T1: values(15, 17) })
  const r = baselineComparison(skewed, ['B1', 'B2'], ['T1'], 'CD_TOP', 'nm')
  close(r.base.dominance, 0.777778)
  assert.equal(r.base.dominated, true)
})

test('baselineDeltaMap: per chip site, target mean minus baseline mean; a one-sided site is no-data', () => {
  const at = (chip_number: string, cd_value: number | null) =>
    row({ chip_number, cd_value, mp_number: cd_value == null ? -1 : 1 })
  const set = files({
    B1: [at('1,1', 10), at('2,2', 20), at('4,4', null)],
    B2: [at('1, 1', 12)],
    T1: [at('1,1', 15), at('3,3', 30), at('4,4', 40)]
  })
  const map = baselineDeltaMap(set, ['B1', 'B2'], ['T1'], 'CD_TOP')
  // (1,1): 15 − mean(10, 12) = +4. (2,2) is baseline-only, (3,3) target-only,
  // (4,4) unmeasured in the baseline: three sites with no pair, none drawn as 0.
  assert.deepEqual(map.points, [[1, 1, 4]])
  assert.equal(map.unpaired, 3)
})

// Codex review 2026-10-09, second pass: a chip can hold several measurement
// points (MP). Averaging every row of the chip turns a difference in WHICH MPs
// each group measured into a movement of the value.
test('baselineDeltaMap pairs the same MP of a chip, not everything measured on it', () => {
  const at = (chip_number: string, mp_number: number, cd_value: number) => row({ chip_number, mp_number, cd_value })
  const set = files({
    B: [at('1,1', 1, 10), at('1,1', 2, 100)],
    T: [at('1,1', 1, 20), at('2,2', 3, 30)]
  })
  const map = baselineDeltaMap(set, ['B'], ['T'], 'CD_TOP')
  // Chip (1,1): only MP1 is in both groups → 20 − 10 = +10, never
  // 20 − mean(10, 100) = −35. Chip (2,2) is target-only.
  assert.deepEqual(map.points, [[1, 1, 10]])
  assert.equal(map.unpaired, 1)
})

test('baselineDeltaMap: a chip both groups measured, but at different MPs, has no pair', () => {
  const at = (mp_number: number, cd_value: number) => row({ chip_number: '1,1', mp_number, cd_value })
  const map = baselineDeltaMap(files({ B: [at(1, 10)], T: [at(2, 20)] }), ['B'], ['T'], 'CD_TOP')
  assert.deepEqual(map.points, [])
  assert.equal(map.unpaired, 1)
})

test('baselineSentence: one sentence, the difference and its sample sizes — no verdict word', () => {
  const r = baselineComparison(SET, ['B1', 'B2'], ['T1'], 'CD_TOP', 'nm')
  assert.equal(
    baselineSentence(r),
    '기준 2건보다 대상 1건의 평균이 +4.00 nm(기준 3σ 의 0.4배) 이동했고 3σ 는 0.8배입니다.'
  )
  const flat = baselineComparison(files({ B1: values(10, 10), T1: values(9, 7) }), ['B1'], ['T1'], 'CD_TOP', 'nm')
  assert.equal(
    baselineSentence(flat),
    '기준 1건보다 대상 1건의 평균이 -2.00 nm 이동했습니다. 기준 3σ 가 0 이라 배율은 계산하지 않습니다.'
  )
  const none = baselineComparison(SET, ['B1', 'B2', 'T1'], [], 'CD_TOP', 'nm')
  assert.equal(baselineSentence(none), '평가 불가 — 대상으로 남은 측정이 없습니다. 세트의 일부만 기준으로 지정하세요.')
})

// ── Set-scope composite maps: a site is (chip, MP) ───────────────────────
const mpAt = (chip_number: string, mp_number: number, cd_value: number | null) =>
  row({ chip_number, mp_number, cd_value })

test('compositeSiteMap: per chip, the mean over its MPs of each MP\'s wafer mean and wafer-to-wafer σ', () => {
  const set = files({
    W1: [mpAt('0,0', 1, 10), mpAt('0,0', 2, 20)],
    W2: [mpAt('0,0', 1, 14), mpAt('0,0', 2, 24)],
    W3: [mpAt('0, 0', 1, 12)]
  })
  // MP1: 10, 14, 12 → mean 12, s = √((4+4+0)/2) = 2.
  // MP2: 20, 24     → mean 22, s = √((4+4)/1)   = 2.828427.
  // chip (0,0): mean (12 + 22)/2 = 17, σ (2 + 2.828427)/2 = 2.414214.
  // Pooling the five rows instead would give mean 16 and s 5.83.
  const [site, ...rest] = compositeSiteMap(set, ['W1', 'W2', 'W3'], 'CD_TOP')
  assert.equal(rest.length, 0)
  assert.deepEqual([site!.x, site!.y, site!.mps, site!.wafers], [0, 0, 2, 3])
  close(site!.mean, 17)
  close(site!.sigma, 2.414214)
})

test('compositeSiteMap: an MP only one wafer measured has a mean and no σ — it is left out of the chip σ, never a 0', () => {
  const set = files({
    W1: [mpAt('1,1', 1, 10), mpAt('1,1', 2, 100), mpAt('2,2', 1, 30)],
    W2: [mpAt('1,1', 1, 14)]
  })
  const sites = compositeSiteMap(set, ['W1', 'W2'], 'CD_TOP')
  // (1,1): MP1 10,14 → mean 12, s = √8 = 2.828427; MP2 100 alone → mean 100, no s.
  //        chip mean (12 + 100)/2 = 56; chip σ = 2.828427 (MP1 only).
  // (2,2): one wafer → mean 30, σ absent.
  assert.deepEqual(sites.map(s => [s.x, s.y, s.mps, s.wafers]), [[1, 1, 2, 2], [2, 2, 1, 1]])
  close(sites[0]!.mean, 56)
  close(sites[0]!.sigma, 2.828427)
  close(sites[1]!.mean, 30)
  assert.equal(sites[1]!.sigma, null)
})

test('compositeSiteMap: one wafer measuring a site twice is still one wafer at that site', () => {
  const set = files({
    W1: [mpAt('3,3', 1, 10), row({ sequence: 2, chip_number: '3,3', mp_number: 1, cd_value: 12 })],
    W2: [mpAt('3,3', 1, 15)]
  })
  // W1's site value is mean(10, 12) = 11; with W2's 15 → mean 13, s = √((4+4)/1) = 2.828427.
  // Treating the three rows as three wafers would give mean 12.33, s 2.52.
  const [site] = compositeSiteMap(set, ['W1', 'W2'], 'CD_TOP')
  close(site!.mean, 13)
  close(site!.sigma, 2.828427)
  assert.equal(site!.wafers, 2)
})

test('compositeSiteMap: only the ids handed in, only measured rows of the parameter', () => {
  const set = files({
    W1: [mpAt('1,1', 1, 10), mpAt('1,1', -1, null), row({ chip_number: '1,1', parameter: 'CD_BOTTOM', cd_value: 999 }), mpAt('??', 1, 5)],
    W2: [mpAt('1,1', 1, 14)],
    OUT: [mpAt('1,1', 1, 500)]
  })
  const sites = compositeSiteMap(set, ['W1', 'W2', 'GONE'], 'CD_TOP')
  assert.equal(sites.length, 1)
  close(sites[0]!.mean, 12)
  assert.equal(sites[0]!.wafers, 2)
})
