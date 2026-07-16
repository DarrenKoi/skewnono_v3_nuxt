import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFailSummaryItems,
  buildTatSummaryItems
} from './recipeStatusSummary.ts'

test('buildFailSummaryItems keeps the agreed labels and order', () => {
  assert.deepEqual(buildFailSummaryItems({
    failLabel: 'Align fails',
    failCount: '12',
    totalMeasurements: '345',
    failRatio: '3.48%'
  }), [
    { label: 'Align fails', value: '12', tone: 'danger' },
    { label: 'Total measurements', value: '345' },
    { label: 'Fail ratio', value: '3.48%' }
  ])
})

test('buildTatSummaryItems keeps the agreed labels and order', () => {
  assert.deepEqual(buildTatSummaryItems({
    totalTat: '1h 02m 03s',
    distinctRecipes: '45',
    totalExecutions: '678',
    avgMeastime: '5s'
  }), [
    { label: 'Total TAT', value: '1h 02m 03s' },
    { label: 'Distinct recipes', value: '45' },
    { label: 'Total executions', value: '678' },
    { label: 'Avg meastime', value: '5s' }
  ])
})
