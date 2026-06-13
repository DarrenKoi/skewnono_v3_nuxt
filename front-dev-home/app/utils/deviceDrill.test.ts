// Pure tests for the drill view-model adapters. Run: node --test app/utils/deviceDrill.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toOutlierDrill } from './deviceDrill.ts'
import type { RecipeInput } from './ruleEngine.ts'
import { detectDeviceOutliers } from './outlierDetect.ts'

const recipe = (recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd: 'R000', recipe_id, fac_id: 'R3', ctn_desc: '', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 'EV', memory_class_auto: 'DRAM',
  parameters: points.map((point_count, i) => ({ name: `P_${i}`, point_count }))
})

test('outlier drill marks the over-threshold param and its recipe', () => {
  const recipes = [recipe('A', [10, 10, 10, 10]), recipe('B', [50, 10])]
  const result = detectDeviceOutliers(recipes) // median 10, threshold 20
  const drill = toOutlierDrill('R000', 'dev desc', recipes, result)

  assert.equal(drill.lot_cd, 'R000')
  assert.equal(drill.ctn_desc, 'dev desc')
  assert.equal(drill.flagged_param_count, 1)
  assert.equal(drill.flagged_recipe_count, 1)

  const recB = drill.recipes.find(r => r.recipe_id === 'B')!
  assert.equal(recB.flagged, true)
  assert.equal(recB.flagged_count, 1)
  const p0 = recB.parameters.find(p => p.name === 'P_0')!
  assert.equal(p0.flagged, true)
  assert.equal(p0.note, '> 20')          // threshold note
  const p1 = recB.parameters.find(p => p.name === 'P_1')!
  assert.equal(p1.flagged, false)

  const recA = drill.recipes.find(r => r.recipe_id === 'A')!
  assert.equal(recA.flagged, false)
})

test('no outliers → every recipe unflagged, counts zero', () => {
  const recipes = [recipe('A', [10, 10]), recipe('B', [10, 10])]
  const drill = toOutlierDrill('R000', '', recipes, detectDeviceOutliers(recipes))
  assert.equal(drill.flagged_param_count, 0)
  assert.equal(drill.flagged_recipe_count, 0)
  assert.ok(drill.recipes.every(r => !r.flagged))
})
