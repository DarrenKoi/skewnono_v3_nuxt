// front-dev-home/app/utils/anomaly/combine.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { combineVerdicts } from './combine.ts'
import type { AnomalyVerdict } from './types.ts'

const mk = (over: Partial<AnomalyVerdict>): AnomalyVerdict => ({
  status: 'evaluated', severity: 'normal', method: 'range', score: 0,
  reason: 'r', metric: 'mean', signal: 'peer', ...over
})

test('worst-of severity wins among evaluated', () => {
  const c = combineVerdicts([mk({ severity: 'normal' }), mk({ severity: 'abnormal', score: 25 })])
  assert.equal(c.status, 'evaluated')
  assert.equal(c.severity, 'abnormal')
})

test('insufficient is ignored for severity but preserved in the array', () => {
  const c = combineVerdicts([mk({ severity: 'normal' }), mk({ status: 'insufficient', score: NaN })])
  assert.equal(c.severity, 'normal') // NOT hidden under insufficient
  assert.equal(c.verdicts.length, 2) // the insufficient one survives
})

test('all insufficient → combined insufficient', () => {
  const c = combineVerdicts([mk({ status: 'insufficient' }), mk({ status: 'insufficient' })])
  assert.equal(c.status, 'insufficient')
})

test('evaluated sorted before insufficient; ties broken by |score|', () => {
  const c = combineVerdicts([
    mk({ status: 'insufficient', score: NaN }),
    mk({ severity: 'watch', score: 12 }),
    mk({ severity: 'watch', score: 18 })
  ])
  assert.equal(c.verdicts[0]!.score, 18) // larger |score| first
  assert.equal(c.verdicts[2]!.status, 'insufficient')
})

test('empty input → insufficient', () => {
  assert.equal(combineVerdicts([]).status, 'insufficient')
})
