// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildWaferAxis } from './waferAxis.ts'

test('grid off: all furniture hidden, no interval', () => {
  const a = buildWaferAxis(false, 154.5, 6.818182, '#9A8E7C')
  assert.equal(a.splitLine.show, false)
  assert.equal(a.axisLabel.show, false)
  assert.equal(a.axisTick.show, false)
  assert.equal(a.interval, undefined)
  assert.equal(a.min, -154.5)
  assert.equal(a.max, 154.5)
})

test('grid on with pitch: die-pitch interval + die-index labels', () => {
  const a = buildWaferAxis(true, 154.5, 6.818182, '#9A8E7C')
  assert.equal(a.splitLine.show, true)
  assert.equal(a.axisLabel.show, true)
  assert.ok(Math.abs((a.interval ?? 0) - 6.818182) < 1e-6)
  assert.equal(a.axisLabel.formatter!(0), '0')
  assert.equal(a.axisLabel.formatter!(6.9), '1')
  assert.equal(a.axisLabel.formatter!(-13.6), '-2')
})

test('grid on without pitch: no interval, rounded-mm label fallback', () => {
  const a = buildWaferAxis(true, 154.5, 0, '#9A8E7C')
  assert.equal(a.interval, undefined)
  assert.equal(a.axisLabel.formatter!(50.4), '50')
})

test('buildWaferAxis labels ticks by die index using the grid offset', () => {
  // With pitchMm = 10 and offsetMm = 4: die index = round((v - 4) / 10).
  // Chosen values discriminate against offset being dropped:
  // v=8: with offset → (8-4)/10 = 0.4 → 0; without offset → 8/10 = 0.8 → 1
  // v=18: with offset → (18-4)/10 = 1.4 → 1; without offset → 18/10 = 1.8 → 2
  // v=-2: with offset → (-2-4)/10 = -0.6 → -1; without offset → -2/10 = -0.2 → 0
  const a = buildWaferAxis(true, 100, 10, '#9A8E7C', 4)
  assert.equal(a.axisLabel.formatter!(8), '0')
  assert.equal(a.axisLabel.formatter!(18), '1')
  assert.equal(a.axisLabel.formatter!(-2), '-1')
})
