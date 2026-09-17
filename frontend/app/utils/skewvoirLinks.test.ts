import assert from 'node:assert/strict'
import { test } from 'node:test'
import { hasSkewvoir, skewvoirSearchRoute } from './skewvoirLinks.ts'

test('builds eq + recipe tokens and an uppercase fab', () => {
  assert.deepEqual(
    skewvoirSearchRoute('cd-sem', { eq: ' ECXDX925 ', recipe: 'ADI/ADI_CD_BIAS_001', fab: 'r3' }),
    { path: '/ebeam/cd-sem/skewvoir', query: { q: 'eq:ECXDX925 recipe:ADI/ADI_CD_BIAS_001', fab: 'R3' } }
  )
})

test('omits absent parts so the URL stays clean', () => {
  assert.deepEqual(skewvoirSearchRoute('hv-sem', { eq: 'TP001' }), {
    path: '/ebeam/hv-sem/skewvoir', query: { q: 'eq:TP001' }
  })
  assert.deepEqual(skewvoirSearchRoute('hv-sem', {}).query, {})
})

test('only the two SEM families have 스큐보아', () => {
  assert.equal(hasSkewvoir('cd-sem'), true)
  assert.equal(hasSkewvoir('provision'), false)
})
