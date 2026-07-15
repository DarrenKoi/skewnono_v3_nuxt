// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { formatWaferTooltip } from './waferTooltip.ts'

test('measured point shows seq, field, mp, and value', () => {
  const html = formatWaferTooltip({ seq: '42', field: '3,5', mp: 7, n: 1, param: 'CD_X', value: 48.2, unit: 'nm' })
  assert.match(html, /seq 42/)
  assert.match(html, /Field 3,5/)
  assert.match(html, /MP 7/)
  assert.match(html, /CD_X: <b>48.2<\/b> nm/)
  assert.doesNotMatch(html, /avg of/)
})

test('averaged die appends the point count', () => {
  const html = formatWaferTooltip({ seq: '1', field: '0,0', mp: 3, n: 4, param: 'CD_X', value: 50, unit: 'nm' })
  assert.match(html, /MP 3 · avg of 4 pts/)
})

test('failure shows 측정 실패 and no value block', () => {
  const html = formatWaferTooltip({ seq: '9', field: null, mp: null, n: 1, param: 'CD_X', value: null, unit: 'nm' })
  assert.match(html, /seq 9/)
  assert.match(html, /측정 실패/)
  assert.doesNotMatch(html, /Field/)
  assert.doesNotMatch(html, /MP/)
})
