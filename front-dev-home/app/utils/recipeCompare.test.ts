// Pure-logic tests for recipeCompare. Run: node --test app/utils/recipeCompare.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildOverlap,
  classifyCoverage,
  filterOverlap,
  commonParameters
} from './recipeCompare.ts'
import type { CompareRecipe, CompareParameter } from '../composables/useRecipeCompareApi.ts'

const param = (name: string): CompareParameter => ({
  Parameter: name,
  idp: {
    Addressing: 'Yes', Double_Addressing: false, Mother_Para: 'Para_1',
    Region: 1, Meas_Counting: 1, dnumber_removed: 0
  },
  images: { img_add1: 'a1', img_add2: 'a2', image_add3: 'a3', img_meas1: 'm1', img_meas2: 'm2' },
  amp: []
})

const recipe = (id: string, params: string[]): CompareRecipe => ({
  recipe_id: id, fac_id: 'R3', parameters: params.map(param)
})

test('classifyCoverage: all / unique / partial', () => {
  assert.equal(classifyCoverage(3, 3), 'all')
  assert.equal(classifyCoverage(1, 3), 'unique')
  assert.equal(classifyCoverage(2, 3), 'partial')
})

test('buildOverlap marks shared, partial, unique parameters', () => {
  const rows = buildOverlap([
    recipe('A', ['WAFER', 'P5', 'P8']),
    recipe('B', ['WAFER', 'P5']),
    recipe('C', ['WAFER', 'P12'])
  ])
  const byName = Object.fromEntries(rows.map(r => [r.parameter, r]))
  assert.equal(byName.WAFER.coverage, 'all')
  assert.deepEqual(byName.WAFER.presentIn, ['A', 'B', 'C'])
  assert.equal(byName.P5.coverage, 'partial')
  assert.equal(byName.P8.coverage, 'unique')
  assert.equal(byName.P12.coverage, 'unique')
})

test('buildOverlap dedupes a repeated parameter within one recipe', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'WAFER'])])
  assert.equal(rows.length, 1)
  assert.equal(rows[0]?.count, 1)
})

test('filterOverlap + commonParameters', () => {
  const rows = buildOverlap([recipe('A', ['WAFER', 'P5']), recipe('B', ['WAFER'])])
  assert.deepEqual(filterOverlap(rows, 'common').map(r => r.parameter), ['WAFER'])
  assert.deepEqual(filterOverlap(rows, 'unique').map(r => r.parameter), ['P5'])
  assert.deepEqual(filterOverlap(rows, 'all').map(r => r.parameter), ['WAFER', 'P5'])
  assert.deepEqual(commonParameters(rows), ['WAFER'])
})
