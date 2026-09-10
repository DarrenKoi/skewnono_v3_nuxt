// Pure-logic tests for afmHeatmap. Run: node --test app/utils/afmHeatmap.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  filterProfileByOutlier,
  heatmapStats,
  OUTLIER_DEFAULT_THRESHOLD,
  HEATMAP_COLOR_RAMPS
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

test('spectral ramp is unchanged from the current heatmap', () => {
  assert.deepEqual(HEATMAP_COLOR_RAMPS.spectral, ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'])
})

test('every color ramp is a non-empty string array; defaults present', () => {
  for (const ramp of Object.values(HEATMAP_COLOR_RAMPS)) {
    assert.ok(Array.isArray(ramp) && ramp.length > 0)
  }
  assert.equal(OUTLIER_DEFAULT_THRESHOLD.iqr, 1.5)
  assert.equal(OUTLIER_DEFAULT_THRESHOLD.zscore, 3)
})
