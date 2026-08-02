// Pure-logic tests for deviceProfile. Run: node --test app/utils/deviceProfile.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupRecipesByLot, buildDeviceOutliers, attachProfile } from './deviceProfile.ts'
import type { RecipeInput } from './ruleEngine.ts'

const recipe = (lot_cd: string, recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd,
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

test('groupRecipesByLot: buckets by lot_cd, preserving encounter order', () => {
  const map = groupRecipesByLot([
    recipe('R000', 'A', [1]),
    recipe('R0A1', 'B', [2]),
    recipe('R000', 'C', [3])
  ])
  assert.deepEqual([...map.keys()], ['R000', 'R0A1'])
  assert.deepEqual(map.get('R000')!.map(r => r.recipe_id), ['A', 'C'])
})

test('groupRecipesByLot: empty input → empty map', () => {
  assert.equal(groupRecipesByLot([]).size, 0)
})

test('buildDeviceOutliers: each device gets its OWN baseline, not a fleet-wide one', () => {
  // R000 measures ~10 points; R0A1 measures ~100. If the baseline were pooled,
  // every R0A1 parameter would read as an outlier of R000's median.
  const map = buildDeviceOutliers([
    recipe('R000', 'A', [10, 10, 10, 12]),
    recipe('R0A1', 'B', [100, 100, 100, 120])
  ])
  assert.equal(map.get('R000')!.median, 10)
  assert.equal(map.get('R0A1')!.median, 100)
  assert.equal(map.get('R000')!.outlier_count, 0)
  assert.equal(map.get('R0A1')!.outlier_count, 0)
})

test('buildDeviceOutliers: flags a parameter above median × 2', () => {
  const map = buildDeviceOutliers([recipe('R000', 'A', [10, 10, 10, 50])])
  const r = map.get('R000')!
  assert.equal(r.median, 10)
  assert.equal(r.outlier_count, 1)
  assert.equal(r.outliers[0]!.point_count, 50)
})

test('attachProfile: merges metrics onto the row without dropping its own fields', () => {
  const row = { lot_cd: 'R000', avail_recipe: 42 }
  const out = attachProfile(row, { median: 128, threshold: 256, outliers: [], outlier_count: 0 })
  assert.equal(out.lot_cd, 'R000')
  assert.equal(out.avail_recipe, 42)
  assert.equal(out.point_median, 128)
  assert.equal(out.has_profile, true)
})

test('attachProfile: a lot with no recipe_params is distinguishable from a real zero', () => {
  const missing = attachProfile({ lot_cd: 'R000' }, undefined)
  assert.equal(missing.point_median, 0)
  assert.equal(missing.has_profile, false)

  const measuredZero = attachProfile({ lot_cd: 'R000' }, { median: 0, threshold: 0, outliers: [], outlier_count: 0 })
  assert.equal(measuredZero.point_median, 0)
  assert.equal(measuredZero.has_profile, true)
})
