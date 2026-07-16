import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFailSummaryItems,
  buildTatSummaryItems,
  recipeStatusSummaryValueClass,
  resolveRecipeStatusSummaryValue
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

test('buildFailSummaryItems supports the Meas fail label', () => {
  assert.deepEqual(buildFailSummaryItems({
    failLabel: 'Meas fails',
    failCount: '7',
    totalMeasurements: '210',
    failRatio: '3.33%'
  }), [
    { label: 'Meas fails', value: '7', tone: 'danger' },
    { label: 'Total measurements', value: '210' },
    { label: 'Fail ratio', value: '3.33%' }
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

test('recipeStatusSummaryValueClass resolves default and danger tones exclusively', () => {
  assert.equal(recipeStatusSummaryValueClass(), 'text-(--sk-ink)')
  assert.equal(recipeStatusSummaryValueClass('danger'), 'text-(--sk-bad)')
})

test('resolveRecipeStatusSummaryValue masks retained values while pending', () => {
  assert.equal(resolveRecipeStatusSummaryValue(true, '1,234'), '—')
  assert.equal(resolveRecipeStatusSummaryValue(false, '1,234'), '1,234')
})

test('resolveRecipeStatusSummaryValue keeps unavailable values masked', () => {
  assert.equal(resolveRecipeStatusSummaryValue(false, undefined), '—')
})
