// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { assignCompareColors, compareBoxPoints } from './hardwareCompare.ts'

test('assignCompareColors: reserves palette[0], cycles palette[1..]', () => {
  const palette = ['#sel', '#a', '#b']
  const colors = assignCompareColors(['T1', 'T2', 'T3'], palette)
  assert.equal(colors['T1'], '#a')
  assert.equal(colors['T2'], '#b')
  // Wraps back to the first non-selected color.
  assert.equal(colors['T3'], '#a')
})

test('assignCompareColors: falls back to ramp when palette has < 2 entries', () => {
  const colors = assignCompareColors(['T1'], ['#only'])
  assert.ok(colors['T1'] && colors['T1'] !== '#only')
})

test('assignCompareColors: empty ids → empty map', () => {
  assert.deepEqual(assignCompareColors([], ['#a', '#b']), {})
})

test('compareBoxPoints: aligns values to the condition axis, omits missing modes', () => {
  const settings = {
    T1: { c0: '1.001', c1: '0.998', c2: '1.004' },
    T2: { c0: '1.000', c2: 'not-a-number' } // lacks c1; c2 non-numeric → dropped
  }
  const conditions = ['c0', 'c1', 'c2']
  const series = compareBoxPoints(settings, ['T1', 'T2'], conditions)

  assert.deepEqual(series[0], { id: 'T1', values: [[0, 1.001], [1, 0.998], [2, 1.004]] })
  // T2: c0 present, c1 absent, c2 non-numeric → only the c0 point survives.
  assert.deepEqual(series[1], { id: 'T2', values: [[0, 1.0]] })
})

test('compareBoxPoints: unknown tool id → empty values, no throw', () => {
  const series = compareBoxPoints({}, ['ghost'], ['c0'])
  assert.deepEqual(series, [{ id: 'ghost', values: [] }])
})
