import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { IdpImageInfoRow } from '../composables/useRecipeSearchApi.ts'
import {
  buildRecipeOpenSummaryItems,
  nextRecipeOpenSort,
  sortRecipeOpenRows
} from './recipeOpenTable.ts'

const row = (overrides: Partial<IdpImageInfoRow> = {}): IdpImageInfoRow => ({
  Parameter: 'P1', img_add1: '', img_add2: '', img_meas1: '', img_meas2: '',
  SEQ: 1, Last_SEQ: 3, Region: 1, image_add3: '', Addressing: false,
  Mother_Para: false, Double_Addressing: false, Meas_Counting: 1,
  dnumber_removed: false, ...overrides
})

test('defaults to stable SEQ ascending order and preserves source indices', () => {
  const sorted = sortRecipeOpenRows([
    row({ Parameter: 'third', SEQ: 3 }),
    row({ Parameter: 'first-a', SEQ: 1 }),
    row({ Parameter: 'first-b', SEQ: 1 }),
    row({ Parameter: 'second', SEQ: 2 })
  ])
  assert.deepEqual(sorted.map(item => item.row.Parameter), [
    'first-a', 'first-b', 'second', 'third'
  ])
  assert.deepEqual(sorted.map(item => item.sourceIndex), [1, 2, 3, 0])
})

test('compares text numerically and booleans as false then true', () => {
  const rows = [
    row({ Parameter: 'P10', Double_Addressing: true }),
    row({ Parameter: 'P2', Double_Addressing: false })
  ]
  assert.deepEqual(
    sortRecipeOpenRows(rows, 'Parameter', 'asc').map(item => item.row.Parameter),
    ['P2', 'P10']
  )
  assert.deepEqual(
    sortRecipeOpenRows(rows, 'Double_Addressing', 'asc')
      .map(item => item.row.Double_Addressing),
    [false, true]
  )
})

test('supports descending numeric order', () => {
  const rows = [row({ SEQ: 1 }), row({ SEQ: 3 }), row({ SEQ: 2 })]
  assert.deepEqual(
    sortRecipeOpenRows(rows, 'SEQ', 'desc').map(item => item.row.SEQ),
    [3, 2, 1]
  )
})

test('toggles the active key and starts a new key ascending', () => {
  assert.deepEqual(nextRecipeOpenSort('SEQ', 'asc', 'SEQ'), {
    key: 'SEQ', direction: 'desc'
  })
  assert.deepEqual(nextRecipeOpenSort('SEQ', 'desc', 'Parameter'), {
    key: 'Parameter', direction: 'asc'
  })
})

test('builds the agreed table-header counts', () => {
  assert.deepEqual(buildRecipeOpenSummaryItems(42, 6), [
    { label: '측정 포인트', value: '42' },
    { label: 'Align 포인트', value: '6' }
  ])
})
