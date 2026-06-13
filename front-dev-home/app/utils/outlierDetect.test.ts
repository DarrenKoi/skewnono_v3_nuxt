// Pure-logic tests for outlierDetect. Run: node --test app/utils/outlierDetect.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { detectDeviceOutliers, DEFAULT_OUTLIER_MULTIPLIER } from './outlierDetect.ts'
import type { RecipeInput } from './ruleEngine.ts'

const recipe = (recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd: 'R000',
  recipe_id,
  fac_id: 'R3',
  ctn_desc: '',
  prod_catg_cd: 'DRAM',
  recipe_class: 'Main',
  family: 'Core',
  phase: 'EV',
  memory_class_auto: 'DRAM',
  parameters: points.map((point_count, i) => ({ name: `P_${i}`, point_count }))
})

test('empty device → median 0, no outliers', () => {
  const r = detectDeviceOutliers([])
  assert.equal(r.median, 0)
  assert.equal(r.outlier_count, 0)
  assert.deepEqual(r.outliers, [])
})

test('uniform point counts → no outliers', () => {
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10]), recipe('B', [10, 10])])
  assert.equal(r.median, 10)
  assert.equal(r.outlier_count, 0)
})

test('a single high value is flagged with its recipe_id and name', () => {
  // medians of [10,10,10,10,50] = 10; threshold = 2*10 = 20; 50 > 20.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [50])])
  assert.equal(r.median, 10)
  assert.equal(r.threshold, 20)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.recipe_id, 'B')
  assert.equal(r.outliers[0]?.point_count, 50)
  assert.equal(r.outliers[0]?.name, 'P_0')
})

test('value exactly at threshold is NOT an outlier (strictly greater)', () => {
  // median 10, threshold 20, a 20 must not flag.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [20])])
  assert.equal(r.outlier_count, 0)
})

test('multiplier is configurable', () => {
  // median 10, multiplier 4 → threshold 40; 30 does not flag, 50 does.
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B', [30, 50])], 4)
  assert.equal(r.threshold, 40)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.point_count, 50)
})

test('default multiplier is 2', () => {
  assert.equal(DEFAULT_OUTLIER_MULTIPLIER, 2)
})
