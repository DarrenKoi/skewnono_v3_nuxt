import assert from 'node:assert/strict'
import test from 'node:test'
import { laserOutliers } from './fdcLaser.ts'

const rows = (values: number[]) => values.map((x1, i) => ({
  ts: `2026-09-${String(i + 1).padStart(2, '0')}T12:00:00`,
  epoch: Date.UTC(2026, 8, i + 1, 12), x1, y1: 200
}))

test('uses the median despite a noisy first sample and retains both outlier tails', () => {
  const input = rows([140, 98, 99, 100, 101, 102, 60])
  const result = laserOutliers(input, 'x1')
  assert.equal(result.baseline, 100)
  assert.equal(result.total, 7)
  assert.deepEqual(result.points, [
    { ts: input[0]!.ts, epoch: input[0]!.epoch, deviation: 40 },
    { ts: input[6]!.ts, epoch: input[6]!.epoch, deviation: -40 }
  ])
  assert.ok(Math.abs(result.band!.hi - 8.8956) < 1e-10)
  assert.ok(Math.abs(result.band!.lo + 8.8956) < 1e-10)
  assert.equal(laserOutliers([...input].reverse(), 'x1').baseline, 100)
})

test('selects y1 independently of x1', () => {
  const input = rows([140, 98, 99, 100, 101, 102, 60])
    .map((row, i) => ({ ...row, y1: [200, 198, 199, 201, 202, 140, 260][i]! }))
  const result = laserOutliers(input, 'y1')
  assert.equal(result.baseline, 200)
  assert.deepEqual(result.points.map(p => p.deviation), [-30, 30])
})

test('equal samples have zero MAD, no outliers and a one-step band', () => {
  const result = laserOutliers(rows([100, 100, 100]), 'x1')
  assert.deepEqual(result.points, [])
  assert.ok(Math.abs(result.band!.hi - 0.01) < 1e-6 && Math.abs(result.band!.lo + 0.01) < 1e-6)
})

test('empty or entirely non-finite input has no baseline or band', () => {
  for (const input of [[], rows([NaN, Infinity])]) {
    assert.deepEqual(laserOutliers(input, 'x1'), { baseline: null, total: 0, points: [], band: null })
  }
})

test('non-finite samples do not affect the baseline, band or valid sample count', () => {
  const input = rows([140, 98, 99, 100, 101, 102, 60])
  assert.deepEqual(laserOutliers([...input, ...rows([NaN, Infinity])], 'x1'), laserOutliers(input, 'x1'))
})

test('a zero median cannot produce percentage deviations', () => {
  assert.deepEqual(laserOutliers(rows([-1, 0, 1]), 'x1'), { baseline: 0, total: 3, points: [], band: null })
})

test('a one-step change at the 0.01 recording resolution is not an outlier', () => {
  // Office values carry two decimals ('0.78'); a stable tool has MAD 0.
  const result = laserOutliers(rows([0.74, 0.74, 0.74, 0.75, 0.74, 0.73, 0.74, 0.80]), 'x1')
  assert.deepEqual(result.points.map(p => Number(p.deviation.toFixed(2))), [8.11])
})
