import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeRadialProfile, radialYExtent, type RadialSample } from './radialAnalysis.ts'

const sample = (sequence: number, radius: number, value: number): RadialSample =>
  ({ sequence, radius, value })

const samples = (values: number[]): RadialSample[] =>
  values.map((v, i) => sample(i + 1, 10 + i * 12, v))

test('radialYExtent covers the observed values with padding on both sides', () => {
  const profile = analyzeRadialProfile(samples([20, 21, 22, 23, 24, 25]), { model: 'linear' })
  const extent = radialYExtent(profile, 'none')
  assert.ok(extent)
  assert.ok(extent.min < 20)
  assert.ok(extent.max > 25)
  // Padding stays proportionate — nowhere near a zero-based axis.
  assert.ok(extent.min > 15)
  assert.ok(extent.max < 30)
})

test('radialYExtent tracks a NEW selection range instead of a stale one', () => {
  const wide = radialYExtent(analyzeRadialProfile(samples([100, 140, 180, 120, 160, 150]), { model: 'linear' }), 'none')
  const narrow = radialYExtent(analyzeRadialProfile(samples([30, 31, 32, 31, 30, 32]), { model: 'linear' }), 'none')
  assert.ok(wide && narrow)
  assert.ok(narrow.max < wide.min) // completely re-fitted, no carry-over
})

test('radialYExtent widens for the iqr band bounds', () => {
  const profile = analyzeRadialProfile(samples([20, 28, 20, 28, 20, 28, 20, 28]), { model: 'linear' })
  const base = radialYExtent(profile, 'none')
  const iqr = radialYExtent(profile, 'iqr')
  assert.ok(base && iqr)
  assert.ok(iqr.min <= base.min && iqr.max >= base.max)
})

test('radialYExtent includes prediction-band bounds when that band is shown', () => {
  const profile = analyzeRadialProfile(samples([20, 22, 27, 21, 24, 26, 23, 25]), { model: 'linear' })
  const none = radialYExtent(profile, 'none')
  const prediction = radialYExtent(profile, 'prediction')
  assert.ok(none && prediction)
  assert.ok(prediction.min < none.min)
  assert.ok(prediction.max > none.max)
})

test('radialYExtent gives a flat profile a visible non-zero window', () => {
  const profile = analyzeRadialProfile(samples([50, 50, 50, 50]), { model: 'none' })
  const extent = radialYExtent(profile, 'none')
  assert.ok(extent)
  assert.ok(extent.min < 50 && extent.max > 50)
})

test('radialYExtent returns null when nothing is plotted', () => {
  const profile = analyzeRadialProfile([], { model: 'linear' })
  assert.equal(radialYExtent(profile, 'iqr'), null)
})
