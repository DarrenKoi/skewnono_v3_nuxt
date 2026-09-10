import { test } from 'node:test'
import assert from 'node:assert/strict'
import { recipePairKey, recipePairSetKey } from './recipePair.ts'

test('recipePairKey is fab-first with a | separator', () => {
  // The exact string matters: v-for keys and in-flight caches across the
  // recipe-search family all assume this one format.
  assert.equal(recipePairKey('R3', 'RECIPE_A'), 'R3|RECIPE_A')
})

test('recipePairKey keeps same-name recipes from different fabs distinct', () => {
  assert.notEqual(recipePairKey('R3', 'RECIPE_A'), recipePairKey('M16B', 'RECIPE_A'))
})

test('recipePairSetKey is order-insensitive and comma-joined', () => {
  const a = { fab_name: 'R3', recipe_name: 'RECIPE_A' }
  const b = { fab_name: 'M16B', recipe_name: 'RECIPE_A' }
  assert.equal(recipePairSetKey([a, b]), 'M16B|RECIPE_A,R3|RECIPE_A')
  assert.equal(recipePairSetKey([b, a]), recipePairSetKey([a, b]))
})
