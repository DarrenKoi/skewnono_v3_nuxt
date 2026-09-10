import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_RANGE, DEFAULT_STDDEV, DEFAULT_METHOD_CONFIG, PEER_MIN_N
} from './types.ts'

test('range defaults: 10/20% with a div-by-zero guard', () => {
  assert.equal(DEFAULT_RANGE.watchPct, 10)
  assert.equal(DEFAULT_RANGE.abnormalPct, 20)
  assert.ok(DEFAULT_RANGE.minAbsCenter > 0)
})

test('stddev defaults: 2/3 sigma', () => {
  assert.equal(DEFAULT_STDDEV.watchK, 2)
  assert.equal(DEFAULT_STDDEV.abnormalK, 3)
})

test('default method is range (authoritative)', () => {
  assert.equal(DEFAULT_METHOD_CONFIG.method, 'range')
})

test('peer minN: looser for range than stddev', () => {
  assert.equal(PEER_MIN_N.range, 3)
  assert.equal(PEER_MIN_N.stddev, 5)
})
