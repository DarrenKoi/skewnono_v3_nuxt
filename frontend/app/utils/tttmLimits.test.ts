// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  actionLimitNm,
  formatSignedNm,
  fractionOfLimit,
  isMeasured,
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

// --- the measured gate ------------------------------------------------------

test('isMeasured: NaN and Infinity are NOT measured', () => {
  // The whole reason this predicate is exported rather than re-spelled: a
  // hand-rolled `typeof v === "number"` accepts NaN, and `typeof NaN` IS
  // "number". The old worstFractionOfLimit briefly spelled it that way.
  assert.equal(isMeasured(0.12), true)
  assert.equal(isMeasured(0), true)
  assert.equal(isMeasured(null), false)
  assert.equal(isMeasured(undefined), false)
  assert.equal(isMeasured(Number.NaN), false)
  assert.equal(isMeasured(Number.POSITIVE_INFINITY), false)
  // The spelling that caused the bug, pinned so the difference is visible.
  assert.equal(typeof Number.NaN === 'number', true)
})

// The ranking-key tests that used to sit here moved to tttmCells.test.ts when
// `worstFractionOfLimit` and `maxMeasuredPair` were replaced by `worstPairOf`.
// They were moved rather than deleted: the rules they pin (worst not average,
// null is not zero, NaN is not a ranking, unmeasured sorts last) are properties
// of the ranking itself, not of the function that happened to implement it.

test('formatSignedNm: the minus is U+2212, so the column stays aligned', () => {
  // A hyphen is narrower and rides higher than '+', which visibly ragged a
  // tabular column of residuals. One of the three inline copies had also
  // dropped the glyph entirely on negatives.
  assert.equal(formatSignedNm(0.042), '+0.042')
  assert.equal(formatSignedNm(-0.13), '−0.130')
  assert.equal(formatSignedNm(0), '+0.000')
  assert.equal(formatSignedNm(-0.13).charCodeAt(0), 0x2212)
  assert.equal(formatSignedNm(-0.0123, 4), '−0.0123')
})
