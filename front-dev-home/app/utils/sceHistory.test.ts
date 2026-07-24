// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sceParamKeys, sceParamLabel, sceParamSeries } from './sceHistory.ts'

const docs = [
  {
    date: '2026-07-17',
    SCEParam: { SCEParam_SmoothRadius: '7', SCEParam_CorrCoefLimit: '0.20000' }
  },
  {
    date: '2026-07-22',
    SCEParam: { SCEParam_SmoothRadius: '8', SCEParam_FitRangeSt: '40' }
  },
  // Malformed rows must drop out, not crash: no date / non-numeric / no block.
  { SCEParam: { SCEParam_SmoothRadius: '9' } },
  { date: '2026-07-24', SCEParam: { SCEParam_SmoothRadius: 'seven' } },
  { date: '2026-07-26' }
]

test('sceParamKeys: sorted union across the window', () => {
  assert.deepEqual(sceParamKeys(docs), [
    'SCEParam_CorrCoefLimit',
    'SCEParam_FitRangeSt',
    'SCEParam_SmoothRadius'
  ])
  assert.deepEqual(sceParamKeys([]), [])
})

test('sceParamLabel: strips the SCEParam_ prefix only', () => {
  assert.equal(sceParamLabel('SCEParam_SmoothRadius'), 'SmoothRadius')
  assert.equal(sceParamLabel('ImgCond_FocusOffset'), 'ImgCond_FocusOffset')
})

test('sceParamSeries: numeric points with date as ts and key', () => {
  assert.deepEqual(sceParamSeries(docs, 'SCEParam_SmoothRadius'), [
    { ts: '2026-07-17', key: '2026-07-17', value: 7 },
    { ts: '2026-07-22', key: '2026-07-22', value: 8 }
  ])
  // A key absent on some dates yields a shorter series, not NaN holes.
  assert.deepEqual(sceParamSeries(docs, 'SCEParam_FitRangeSt'), [
    { ts: '2026-07-22', key: '2026-07-22', value: 40 }
  ])
})
