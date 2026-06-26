// front-dev-home/app/utils/anomaly/score.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { scoreByRange, scoreByStddev, bandRange, bandStddev } from './score.ts'
import { DEFAULT_RANGE, DEFAULT_STDDEV } from './types.ts'

test('range bands: normal < 10%, watch 10–20%, abnormal ≥ 20%', () => {
  assert.equal(bandRange(5, DEFAULT_RANGE), 'normal')
  assert.equal(bandRange(10, DEFAULT_RANGE), 'watch')
  assert.equal(bandRange(15, DEFAULT_RANGE), 'watch')
  assert.equal(bandRange(20, DEFAULT_RANGE), 'abnormal')
})

test('range: +14% over center 10 → watch, score is signed %', () => {
  const r = scoreByRange(11.4, 10, DEFAULT_RANGE)
  assert.equal(r.status, 'evaluated')
  assert.equal(r.severity, 'watch')
  assert.ok(Math.abs(r.score - 14) < 1e-6)
  assert.match(r.reason, /\+14/)
  assert.match(r.reason, /실측 11.4/)
})

test('range: |center| below minAbsCenter → insufficient', () => {
  const r = scoreByRange(0.001, 0, DEFAULT_RANGE)
  assert.equal(r.status, 'insufficient')
})

test('range: negative deviation keeps the sign', () => {
  const r = scoreByRange(8, 10, DEFAULT_RANGE) // -20%
  assert.equal(r.severity, 'abnormal')
  assert.ok(r.score < 0)
})

test('stddev bands: normal < 2σ, watch 2–3σ, abnormal ≥ 3σ', () => {
  assert.equal(bandStddev(1.5, DEFAULT_STDDEV), 'normal')
  assert.equal(bandStddev(2, DEFAULT_STDDEV), 'watch')
  assert.equal(bandStddev(3, DEFAULT_STDDEV), 'abnormal')
})

test('stddev: std=0 and equal value → normal, score 0', () => {
  const r = scoreByStddev(10, 10, 0, DEFAULT_STDDEV)
  assert.equal(r.severity, 'normal')
  assert.equal(r.score, 0)
})

test('stddev: std=0 with a different value → abnormal, score is absolute delta', () => {
  const r = scoreByStddev(12, 10, 0, DEFAULT_STDDEV)
  assert.equal(r.severity, 'abnormal')
  assert.equal(r.score, 2)
  assert.match(r.reason, /표준편차 0/)
})

test('non-finite input → insufficient', () => {
  assert.equal(scoreByRange(NaN, 10, DEFAULT_RANGE).status, 'insufficient')
  assert.equal(scoreByStddev(10, NaN, 1, DEFAULT_STDDEV).status, 'insufficient')
})

test('reason never contains forbidden vocabulary', () => {
  const r = scoreByStddev(13, 10, 1, DEFAULT_STDDEV)
  assert.doesNotMatch(r.reason, /z-score|MAD/i)
})
