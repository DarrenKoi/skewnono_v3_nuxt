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

// --- 특수 측정 job 제외 (user-confirmed 2026-08-05) ---

test('an exempt job is never flagged, however many points it measures', () => {
  const r = detectDeviceOutliers([recipe('A', [10, 10, 10, 10]), recipe('B_WCDU', [800])])
  assert.equal(r.outlier_count, 0, 'a full-map job measures a lot by design')
  assert.deepEqual(r.outliers, [])
})

test('all four suffixes are excluded', () => {
  const r = detectDeviceOutliers([
    recipe('A', [10, 10, 10, 10]),
    recipe('B_WCDU', [800]),
    recipe('C_FCDU', [800]),
    recipe('D_FULL', [800]),
    recipe('E_HALF', [800])
  ])
  assert.equal(r.median, 10, 'the baseline is the normal recipes only')
  assert.equal(r.outlier_count, 0)
})

// 이것이 이 규칙의 진짜 이유입니다. exempt job 이 기준선에 남아 있으면 중앙값이
// 끌려 올라가 **정상 recipe 의 진짜 과다 측정이 문턱 아래로 숨습니다**.
test('excluding exempt jobs keeps a real outlier in a normal recipe visible', () => {
  const rows = [
    recipe('A', [10, 10, 10, 10, 10, 10]),
    recipe('B', [40]), // 진짜 과다 측정 — 정상 recipe 인데 4배
    recipe('X_FULL', [400, 400, 400, 400, 400, 400, 400])
  ]
  const r = detectDeviceOutliers(rows)

  // exempt 를 세면 중앙값이 400 쪽으로 끌려가 threshold 가 40 을 넘고 B 가 숨습니다.
  assert.equal(r.median, 10)
  assert.equal(r.threshold, 20)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]?.recipe_id, 'B')
})

test('a device measuring ONLY exempt jobs reports an empty baseline, not a huge one', () => {
  const r = detectDeviceOutliers([recipe('A_WCDU', [500, 500]), recipe('B_FCDU', [500])])
  assert.equal(r.median, 0)
  assert.equal(r.outlier_count, 0)
})
