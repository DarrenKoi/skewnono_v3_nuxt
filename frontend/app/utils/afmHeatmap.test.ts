// Pure-logic tests for afmHeatmap. Run: node --test app/utils/afmHeatmap.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  axisTitle,
  filterProfileByOutlier,
  heatmapStats,
  isLineProfile,
  OUTLIER_DEFAULT_THRESHOLD,
  profileGrid
} from './afmHeatmap.ts'

const pts = (zs: number[]) => zs.map((z, i) => ({ x: i, y: i, z }))

test('none keeps all points', () => {
  const r = filterProfileByOutlier(pts([1, 2, 3, 100]), 'none', 1.5)
  assert.equal(r.removed, 0)
  assert.equal(r.kept.length, 4)
})

test('iqr removes a planted high outlier', () => {
  const r = filterProfileByOutlier(pts([10, 11, 12, 13, 12, 11, 200]), 'iqr', 1.5)
  assert.equal(r.removed, 1)
  assert.ok(!r.kept.some(p => p.z === 200))
})

test('zscore removes a planted outlier', () => {
  const r = filterProfileByOutlier(pts([5, 5, 5, 5, 5, 5, 60]), 'zscore', 2)
  assert.ok(r.removed >= 1)
  assert.ok(!r.kept.some(p => p.z === 60))
})

test('fewer than 4 points keeps all', () => {
  const r = filterProfileByOutlier(pts([1, 999, 2]), 'iqr', 1.5)
  assert.equal(r.removed, 0)
})

test('all-equal z (zero spread) keeps all', () => {
  assert.equal(filterProfileByOutlier(pts([7, 7, 7, 7, 7]), 'iqr', 1.5).removed, 0)
  assert.equal(filterProfileByOutlier(pts([7, 7, 7, 7, 7]), 'zscore', 3).removed, 0)
})

test('non-finite or non-positive threshold keeps all', () => {
  assert.equal(filterProfileByOutlier(pts([1, 2, 3, 100]), 'iqr', NaN).removed, 0)
  assert.equal(filterProfileByOutlier(pts([1, 2, 3, 100]), 'iqr', 0).removed, 0)
})

test('heatmapStats computes count/min/max/mean', () => {
  const s = heatmapStats(pts([2, 4, 6]))
  assert.deepEqual(s, { count: 3, min: 2, max: 6, mean: 4 })
})

test('heatmapStats on empty → zeros', () => {
  assert.deepEqual(heatmapStats([]), { count: 0, min: 0, max: 0, mean: 0 })
})

test('outlier threshold defaults', () => {
  assert.equal(OUTLIER_DEFAULT_THRESHOLD.iqr, 1.5)
  assert.equal(OUTLIER_DEFAULT_THRESHOLD.zscore, 3)
})

const line = [{ x: 0, y: 0, z: 1 }, { x: 1, y: 0, z: 2 }, { x: 2, y: 0, z: 3 }]
const grid = [{ x: 0, y: 0, z: 1 }, { x: 1, y: 0, z: 2 }, { x: 0, y: 1, z: 3 }]

test('isLineProfile: the file\'s DataSize decides, whatever the samples look like', () => {
  assert.equal(isLineProfile(line, '1024 x 1'), true)
  assert.equal(isLineProfile(grid, '512 x 64'), false)
  // A grid that came back with a single row is still a grid, and a line with one
  // sample is still a line.
  assert.equal(isLineProfile(line, '512 x 64'), false)
  assert.equal(isLineProfile([{ x: 0, y: 0, z: 1 }], '1 x 1'), true)
  assert.equal(isLineProfile(grid, ' 16384 X 1 '), true)
})

test('isLineProfile: with no readable DataSize, a line is every sample on one y', () => {
  for (const dataSize of [undefined, null, '', '1024', 'n/a']) {
    assert.equal(isLineProfile(line, dataSize), true)
    assert.equal(isLineProfile(grid, dataSize), false)
  }
  // Too few samples to call it a line; the heat map handles them.
  assert.equal(isLineProfile([{ x: 0, y: 0, z: 1 }]), false)
  assert.equal(isLineProfile([]), false)
})

test('axisTitle: carries the unit the file declared, and none when it declared none', () => {
  assert.equal(axisTitle('X', 'um'), 'X (μm)')
  assert.equal(axisTitle('Z', 'pm'), 'Z (pm)')
  assert.equal(axisTitle('X', 'Pixel'), 'X (Pixel)')
  assert.equal(axisTitle('Y', undefined), 'Y')
  assert.equal(axisTitle('Y', ''), 'Y')
})

test('profileGrid: a full lattice yields its sorted axes, whatever order the samples came in', () => {
  const lattice = [3, 1, 2].flatMap(x => [20, 10].map(y => ({ x, y, z: x * y })))
  assert.deepEqual(profileGrid(lattice), { xs: [1, 2, 3], ys: [10, 20] })
})

test('profileGrid: ragged or empty samples are no grid', () => {
  assert.equal(profileGrid(grid), null)
  assert.equal(profileGrid([]), null)
})
