// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildWaferAxis, type WaferAxisConfig } from './waferAxis.ts'

// `interval` is deliberately absent from WaferAxisConfig — setting it is the
// double-grid bug. Read it off the shape so the tests can prove it stays unset.
const interval = (a: WaferAxisConfig): unknown => (a as unknown as Record<string, unknown>).interval

test('grid off: all furniture hidden, no interval', () => {
  const a = buildWaferAxis(false, 154.5, 6.818182, '#9A8E7C', 0)
  assert.equal(a.splitLine.show, false)
  assert.equal(a.axisLabel.show, false)
  assert.equal(a.axisTick.show, false)
  assert.equal(interval(a), undefined)
  assert.equal(a.min, -154.5)
  assert.equal(a.max, 154.5)
})

test('grid on with pitch: labels are placed on die centres, never by an interval', () => {
  // REGRESSION (the double-grid bug). `interval` is unusable here: ECharts steps
  // it from the axis extent start (-axisMax = -radius·1.03), an arbitrary point
  // off the die lattice, and no interval value can phase-shift it back on. Tick
  // positions must therefore be given explicitly.
  const pitch = 12.52
  const offset = 4.61
  const a = buildWaferAxis(true, 154.5, pitch, '#9A8E7C', offset)
  assert.equal(interval(a), undefined)
  const ticks = a.axisLabel.customValues
  assert.ok(ticks && ticks.length > 0, 'die-index labels must have explicit positions')
  assert.deepEqual(a.axisTick.customValues, ticks, 'ticks and labels must not drift apart')
  for (const v of ticks) {
    const k = (v - offset) / pitch
    assert.ok(Math.abs(k - Math.round(k)) < 1e-9,
      `tick ${v} sits ${(k - Math.round(k)).toFixed(3)} of a pitch off die ${Math.round(k)}'s centre`)
    assert.equal(a.axisLabel.formatter!(v), String(Math.round(k)))
  }
})

test('grid on with pitch: the axis draws no split lines', () => {
  // The die-boundary overlay draws the lattice, chord-clipped to the wafer. An
  // axis grid on top of it would sit half a pitch away — two grids, one wafer.
  const a = buildWaferAxis(true, 154.5, 12.52, '#9A8E7C', 0)
  assert.equal(a.splitLine.show, false)
  assert.equal(a.axisLabel.show, true)
})

test('grid on without pitch: split lines are the fallback lattice', () => {
  // No pitch → the overlay cannot draw anything, so the axis keeps its own
  // auto-tick grid and falls back to rounded-mm labels.
  const a = buildWaferAxis(true, 154.5, 0, '#9A8E7C', 0)
  assert.equal(interval(a), undefined)
  assert.equal(a.splitLine.show, true)
  assert.equal(a.axisLabel.customValues, undefined)
  assert.equal(a.axisTick.customValues, undefined)
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
