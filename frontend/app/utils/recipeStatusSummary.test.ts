import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFailSummaryItems,
  buildTatSummaryItems,
  recipeStatusDeltaCaption,
  recipeStatusDeltaClass,
  recipeStatusDeltaTitle,
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

const tatInput = { totalTat: '1h', distinctRecipes: '45', totalExecutions: '678', avgMeastime: '5s' }
const failInput = {
  failLabel: 'Align fails' as const,
  failCount: '12',
  totalMeasurements: '345',
  failRatio: '3.48%'
}

test('build*SummaryItems attach each delta to the KPI with the matching key', () => {
  const items = buildTatSummaryItems(tatInput, {
    items: [
      { key: 'avgMeastime', delta: '−1s (−16.7%)', tone: 'ok', title: 't' },
      { key: 'totalExecutions', delta: '+78 (+13.0%)', tone: 'neutral', title: 't' }
    ]
  })
  assert.deepEqual(items.map(item => item.delta?.text), [
    undefined, undefined, '+78 (+13.0%)', '−1s (−16.7%)'
  ])
  assert.deepEqual(items[3]?.delta, { text: '−1s (−16.7%)', tone: 'ok', title: 't' })

  const fail = buildFailSummaryItems(failInput, {
    items: [{ key: 'failRatio', delta: '+0.4%p', tone: 'bad', title: 't' }]
  })
  assert.deepEqual(fail.map(item => item.delta?.text), [undefined, undefined, '+0.4%p'])
})

test('a pending comparison reserves an empty delta on every KPI', () => {
  const items = buildTatSummaryItems(tatInput, { pending: true, anchorIncluded: true })
  for (const item of items) {
    assert.deepEqual(item.delta, { text: '', tone: 'none', title: '', anchorIncluded: true })
  }
})

test('recipeStatusDeltaCaption appears once a delta exists and flags the anchor day', () => {
  assert.equal(recipeStatusDeltaCaption(buildTatSummaryItems(tatInput)), null)
  assert.equal(recipeStatusDeltaCaption(buildTatSummaryItems(tatInput, {})), null)
  assert.equal(
    recipeStatusDeltaCaption(buildFailSummaryItems(failInput, { pending: true })),
    '이전 동일 기간 대비(원시 변화)'
  )
  assert.equal(
    recipeStatusDeltaCaption(buildFailSummaryItems(failInput, { pending: true, anchorIncluded: true })),
    '이전 동일 기간 대비(원시 변화) · 기준일 포함'
  )
})

test('recipeStatusDeltaClass maps every tone to a token colour', () => {
  assert.equal(recipeStatusDeltaClass('ok'), 'text-(--sk-ok)')
  assert.equal(recipeStatusDeltaClass('bad'), 'text-(--sk-bad)')
  assert.equal(recipeStatusDeltaClass('neutral'), 'text-(--sk-ink)')
  assert.equal(recipeStatusDeltaClass('none'), 'text-(--sk-ink-muted)')
})

test('recipeStatusDeltaTitle leads with the full delta text so a clipped value stays readable', () => {
  assert.equal(
    recipeStatusDeltaTitle({ text: '+120h 00m 00s (+150.0%)', tone: 'bad', title: '이전 15일 400건 대비 · 현재 1,000건' }),
    '+120h 00m 00s (+150.0%) · 이전 15일 400건 대비 · 현재 1,000건'
  )
  assert.equal(recipeStatusDeltaTitle({ text: '이전 기간 없음', tone: 'none', title: '' }), '이전 기간 없음')
  assert.equal(recipeStatusDeltaTitle({ text: '', tone: 'none', title: '' }), undefined)
})
