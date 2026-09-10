import { test } from 'node:test'
import assert from 'node:assert/strict'
import { analyzeRadialProfile, type RadialSample } from './radialAnalysis.ts'

const sample = (sequence: number, radius: number, value: number): RadialSample => ({ sequence, radius, value })
const close = (actual: number | null, expected: number, epsilon = 1e-8) => {
  assert.notEqual(actual, null)
  assert.ok(Math.abs(actual! - expected) < epsilon, `${actual} !== ${expected}`)
}

test('linear fit recovers the trend and returns zero residuals', () => {
  const result = analyzeRadialProfile([
    sample(1, 20, 5),
    sample(2, 40, 9),
    sample(3, 60, 13),
    sample(4, 80, 17)
  ], { model: 'linear' })

  assert.equal(result.status, 'fitted')
  assert.deepEqual(result.points.map(point => point.radius), [20, 40, 60, 80])
  for (const point of result.points) close(point.residual, 0)
  close(result.metrics.r2, 1)
  close(result.metrics.spanDelta, 12)
})

test('quadratic fit captures curvature that a linear fit leaves behind', () => {
  const points = Array.from({ length: 9 }, (_, i) => {
    const radius = 10 + i * 10
    return sample(i + 1, radius, 3 + 0.02 * radius + 0.004 * radius ** 2)
  })
  const linear = analyzeRadialProfile(points, { model: 'linear' })
  const quadratic = analyzeRadialProfile(points, { model: 'quadratic' })

  assert.equal(quadratic.status, 'fitted')
  assert.ok(quadratic.metrics.rmse! < 1e-10)
  assert.ok(linear.metrics.rmse! > 1)
  assert.ok(quadratic.metrics.cvRmse! < linear.metrics.cvRmse!)
})

test('fit curve stays inside the observed radius range', () => {
  const result = analyzeRadialProfile([
    sample(1, 35, 1),
    sample(2, 55, 2),
    sample(3, 75, 3),
    sample(4, 95, 4)
  ], { model: 'linear', curveSteps: 20 })

  assert.equal(result.curve[0]!.radius, 35)
  assert.equal(result.curve[result.curve.length - 1]!.radius, 95)
})

test('cubic fit refuses too few measured sites or distinct radii', () => {
  const tooFew = analyzeRadialProfile([
    sample(1, 10, 1), sample(2, 20, 2), sample(3, 30, 3), sample(4, 40, 4)
  ], { model: 'cubic' })
  assert.equal(tooFew.status, 'insufficient')

  const repeated = analyzeRadialProfile([
    sample(1, 10, 1), sample(2, 10, 2), sample(3, 20, 3),
    sample(4, 20, 4), sample(5, 30, 5), sample(6, 30, 6)
  ], { model: 'cubic' })
  assert.equal(repeated.status, 'insufficient')
})

test('raw mode preserves observations and still calculates radial IQR bins', () => {
  const result = analyzeRadialProfile([
    sample(1, 10, 2), sample(2, 12, 4), sample(3, 80, 10), sample(4, 82, 14)
  ], { model: 'none', binCount: 2 })

  assert.equal(result.status, 'raw')
  assert.equal(result.curve.length, 0)
  assert.equal(result.bins.length, 2)
  close(result.bins[0]!.median, 3)
  close(result.bins[1]!.median, 12)
})

test('prediction interval is wider than confidence interval', () => {
  const result = analyzeRadialProfile([
    sample(1, 10, 3.1), sample(2, 20, 4.8), sample(3, 30, 7.2),
    sample(4, 40, 8.9), sample(5, 50, 11.3), sample(6, 60, 12.8)
  ], { model: 'linear' })
  const middle = result.curve[Math.floor(result.curve.length / 2)]!

  assert.notEqual(middle.confidenceLower, null)
  assert.notEqual(middle.predictionLower, null)
  const confidenceWidth = middle.confidenceUpper! - middle.confidenceLower!
  const predictionWidth = middle.predictionUpper! - middle.predictionLower!
  assert.ok(predictionWidth > confidenceWidth)
})

test('non-finite and negative-radius rows are excluded rather than coerced', () => {
  const result = analyzeRadialProfile([
    sample(1, 10, 1), sample(2, 20, 2), sample(3, 30, 3), sample(4, 40, 4),
    sample(5, -1, 99), sample(6, Number.NaN, 99), sample(7, 50, Number.NaN)
  ], { model: 'linear' })

  assert.equal(result.metrics.n, 4)
  assert.deepEqual(result.points.map(point => point.sequence), [1, 2, 3, 4])
})
