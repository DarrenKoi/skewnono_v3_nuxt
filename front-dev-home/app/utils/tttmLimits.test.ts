// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  actionLimitNm,
  fractionOfLimit,
  resolveNominalCd,
  MONITOR_WAFER_CD_NM,
  PM_BM_ACTION_LIMIT_RATIO
} from './tttmLimits.ts'

test('actionLimitNm: the ratio reproduces the ±0.15 nm the fab quoted', () => {
  // The anchor for everything here. If this fails, the ratio has drifted from
  // the number the rule was actually stated as (±0.15 nm at the 15 nm monitor
  // wafer, user-confirmed 2026-08-16) and every drawn limit is wrong with it.
  assert.equal(actionLimitNm(MONITOR_WAFER_CD_NM), 0.15)
  assert.equal(PM_BM_ACTION_LIMIT_RATIO, 0.01)
})

test('actionLimitNm: scales with pattern size', () => {
  // The whole reason median_cd_nm entered the contract: a fixed 0.15 nm is
  // ~4x too strict at a 68 nm CD.
  assert.equal(actionLimitNm(50), 0.5)
  assert.ok(Math.abs(actionLimitNm(68) - 0.68) < 1e-12)
})

test('resolveNominalCd: a measured CD is used and reported as measured', () => {
  assert.deepEqual(resolveNominalCd(32.4), { nm: 32.4, assumed: false })
})

test('resolveNominalCd: a missing CD falls back to the monitor wafer, flagged', () => {
  // `assumed` is the point of the return shape — the caller has to be able to
  // say on screen that the line it drew was not measured.
  for (const missing of [null, undefined]) {
    assert.deepEqual(resolveNominalCd(missing), { nm: MONITOR_WAFER_CD_NM, assumed: true })
  }
})

test('resolveNominalCd: a non-positive CD is treated as missing, not as data', () => {
  // Zero would make the limit 0 and paint every tool red; a negative CD would
  // invert the comparison and pass everything. Both are contract violations
  // (see test_fleet_today_median_cd_is_positive_when_present), so the client
  // degrades to the documented fallback rather than rendering nonsense.
  assert.deepEqual(resolveNominalCd(0), { nm: MONITOR_WAFER_CD_NM, assumed: true })
  assert.deepEqual(resolveNominalCd(-5), { nm: MONITOR_WAFER_CD_NM, assumed: true })
})

test('fractionOfLimit: 1.0 sits exactly on the limit', () => {
  assert.equal(fractionOfLimit(0.15, 15), 1)
  assert.equal(fractionOfLimit(0.68, 68), 1)
})

test('fractionOfLimit: reorders pairs that raw nanometres rank as equal', () => {
  // The reason this index exists. The same 0.24 nm skew is 1.6x the limit on a
  // 15 nm monitor wafer and 0.35x on a 68 nm pattern — so ranking recipes by
  // raw nm puts them level when one is a problem and the other is not.
  const alarming = fractionOfLimit(0.24, 15)
  const fine = fractionOfLimit(0.24, 68)
  assert.ok(alarming > 1, `expected over-limit at 15 nm CD, got ${alarming}`)
  assert.ok(fine < 1, `expected within limit at 68 nm CD, got ${fine}`)
  assert.ok(alarming > fine)
})

test('fractionOfLimit: combining recipes means the worst fraction, not the largest nm', () => {
  // Worked example of the combination rule. Recipe A's skew is SMALLER in nm
  // but worse against its own limit, so a max-by-nm would pick the wrong one.
  const recipes = [
    { skewNm: 0.20, cdNm: 15 },
    { skewNm: 0.50, cdNm: 68 }
  ]
  const worstByNm = recipes.reduce((a, b) => (b.skewNm > a.skewNm ? b : a))
  const worstByIndex = recipes.reduce((a, b) =>
    fractionOfLimit(b.skewNm, b.cdNm) > fractionOfLimit(a.skewNm, a.cdNm) ? b : a
  )
  assert.equal(worstByNm.skewNm, 0.5)
  assert.equal(worstByIndex.skewNm, 0.2)
})
