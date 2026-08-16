// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  actionLimitNm,
  fractionOfLimit,
  worstFractionOfLimit,
  maxMeasuredPair,
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

// --- worstFractionOfLimit: the ranking key -----------------------------------

const symmetric = (upper: Record<string, number | null>, n: number) => {
  const values: (number | null)[][] = Array.from({ length: n }, () =>
    Array.from({ length: n }, () => null as number | null)
  )
  for (let i = 0; i < n; i++) values[i]![i] = 0
  for (const [key, v] of Object.entries(upper)) {
    const [i, j] = key.split('-').map(Number) as [number, number]
    values[i]![j] = v
    values[j]![i] = v
  }
  return values
}

test('worstFractionOfLimit: takes the worst pair, not the average', () => {
  // A group is only as matched as its loosest pair. Averaging would let the
  // one bad pair hide behind the three good ones and rank this cell as clean.
  const values = symmetric({ '0-1': 0.02, '0-2': 0.02, '1-2': 0.30 }, 3)
  const worst = worstFractionOfLimit(values, 15)
  assert.equal(worst, fractionOfLimit(0.30, 15))
  assert.ok(worst! > 1)
})

test('worstFractionOfLimit: skips null pairs rather than scoring them as zero', () => {
  // null means "this pair has no shared data", not "these tools match
  // perfectly". Treating it as 0 would rank an unmeasured cell as the best one.
  const values = symmetric({ '0-1': null, '0-2': 0.08, '1-2': null }, 3)
  assert.equal(worstFractionOfLimit(values, 15), fractionOfLimit(0.08, 15))
})

test('worstFractionOfLimit: a matrix with no measured pair is null, not 0', () => {
  assert.equal(worstFractionOfLimit(symmetric({ '0-1': null }, 2), 15), null)
  assert.equal(worstFractionOfLimit([], 15), null)
})

test('worstFractionOfLimit: ranks cells that raw nm ranks backwards', () => {
  // The finding this whole change exists for. The 68 nm cell has the LARGER
  // skew in nanometres and the SMALLER problem, so a nm-ordered list shows the
  // wrong cell first.
  const monitor = symmetric({ '0-1': 0.13 }, 2)
  const largePattern = symmetric({ '0-1': 0.30 }, 2)

  const monitorIndex = worstFractionOfLimit(monitor, 15)!
  const largeIndex = worstFractionOfLimit(largePattern, 68)!

  assert.ok(0.13 < 0.30, 'raw nm puts the large-pattern cell first')
  assert.ok(monitorIndex > largeIndex, 'the index puts the monitor cell first')

  const ranked = [
    { cd: 68, values: largePattern },
    { cd: 15, values: monitor }
  ].sort((a, b) =>
    (worstFractionOfLimit(b.values, b.cd) ?? -1) - (worstFractionOfLimit(a.values, a.cd) ?? -1)
  )
  assert.equal(ranked[0]!.cd, 15)
})

test('worstFractionOfLimit: unmeasured cells sort last under the ranking rule', () => {
  // The -1 sentinel PairMatrix uses: a cell carrying no evidence must not
  // outrank a cell that does merely because its index is null.
  const cells = [
    { id: 'empty', index: worstFractionOfLimit(symmetric({ '0-1': null }, 2), 15) },
    { id: 'measured', index: worstFractionOfLimit(symmetric({ '0-1': 0.01 }, 2), 15) }
  ].sort((a, b) => (b.index ?? -1) - (a.index ?? -1))
  assert.deepEqual(cells.map(c => c.id), ['measured', 'empty'])
})

// --- the measured gate ------------------------------------------------------

test('isMeasured: NaN and Infinity are NOT measured', () => {
  // The whole reason this predicate is exported rather than re-spelled: a
  // hand-rolled `typeof v === "number"` accepts NaN, and `typeof NaN` IS
  // "number". worstFractionOfLimit briefly spelled it that way.
  assert.equal(isMeasured(0.12), true)
  assert.equal(isMeasured(0), true)
  assert.equal(isMeasured(null), false)
  assert.equal(isMeasured(undefined), false)
  assert.equal(isMeasured(Number.NaN), false)
  assert.equal(isMeasured(Number.POSITIVE_INFINITY), false)
  // The spelling that caused the bug, pinned so the difference is visible.
  assert.equal(typeof Number.NaN === 'number', true)
})

test('worstFractionOfLimit: a NaN pair is skipped, not ranked', () => {
  // With the old `typeof` gate this returned NaN, which then (a) passed the
  // `severity !== null` guard in PairMatrix, (b) rendered as "CD 대비 NaN×",
  // and (c) made the sort comparator return NaN, so the ordering of the whole
  // list became implementation-defined.
  const values: (number | null)[][] = [
    [0, Number.NaN, 0.06],
    [Number.NaN, 0, null],
    [0.06, null, 0]
  ]
  const worst = worstFractionOfLimit(values, 15)
  assert.equal(Number.isNaN(worst as number), false)
  assert.equal(worst, fractionOfLimit(0.06, 15))
})

test('maxMeasuredPair: upper triangle only, nulls skipped, null when empty', () => {
  assert.equal(maxMeasuredPair([[0, 0.02, 0.12], [0.02, 0, 0.1], [0.12, 0.1, 0]]), 0.12)
  assert.equal(maxMeasuredPair([[0, null], [null, 0]]), null)
  assert.equal(maxMeasuredPair([]), null)
  // The diagonal is 0 by contract and must not be mistaken for a measured pair
  // in a matrix that has none.
  assert.equal(maxMeasuredPair([[0]]), null)
})
