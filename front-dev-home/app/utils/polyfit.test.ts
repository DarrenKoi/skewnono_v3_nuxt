// Pure-logic tests for polyfit. Run: node --test app/utils/polyfit.test.ts
// Coefficients are low-order first ([c0, c1, … cd]), matching polyval.
//
// Note: polyfit.ts describes itself as the skewvoir Radius Plot fit line, but
// nothing in the repo imports it today — the module is currently unreferenced.
// These tests therefore also serve as its only executable specification, which
// is why the degenerate cases are pinned as tightly as the happy path.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { polyfit, polyval } from './polyfit.ts'

// Floating-point compare — the normal equations lose a few digits even on
// exactly-fittable data, so equality is always approximate.
const close = (actual: number | undefined, expected: number, tol = 1e-9) => {
  assert.ok(actual != null, 'coefficient missing')
  assert.ok(
    Math.abs(actual - expected) < tol,
    `expected ${expected} ± ${tol}, got ${actual}`
  )
}

test('polyfit recovers an exact straight line', () => {
  // y = 1 + 2x
  const coeffs = polyfit([0, 1, 2, 3], [1, 3, 5, 7], 1)
  assert.ok(coeffs)
  assert.equal(coeffs.length, 2)
  close(coeffs[0], 1)
  close(coeffs[1], 2)
})

test('polyfit recovers an exact quadratic', () => {
  // y = 3 - 0.5x + 2x²
  const xs = [-2, -1, 0, 1, 2]
  const ys = xs.map(x => 3 - 0.5 * x + 2 * x ** 2)
  const coeffs = polyfit(xs, ys, 2)
  assert.ok(coeffs)
  assert.equal(coeffs.length, 3)
  close(coeffs[0], 3)
  close(coeffs[1], -0.5)
  close(coeffs[2], 2)
})

test('polyfit on over-determined noisy data matches the closed-form least squares', () => {
  // slope = Sxy/Sxx = 4.5/5 = 0.9, intercept = ȳ - slope·x̄ = 2.25 - 1.35 = 0.9
  const coeffs = polyfit([0, 1, 2, 3], [1, 2, 2, 4], 1)
  assert.ok(coeffs)
  close(coeffs[0], 0.9, 1e-9)
  close(coeffs[1], 0.9, 1e-9)
})

test('polyfit minimises the squared residual (perturbing any coefficient is worse)', () => {
  const xs = [0, 1, 2, 3, 4]
  const ys = [1, 2, 2, 4, 3]
  const coeffs = polyfit(xs, ys, 2)
  assert.ok(coeffs)
  const sse = (c: number[]) => xs.reduce((acc, x, i) => acc + (ys[i]! - polyval(c, x)) ** 2, 0)
  const best = sse(coeffs)
  for (let i = 0; i < coeffs.length; i++) {
    for (const step of [1e-3, -1e-3]) {
      const nudged = [...coeffs]
      nudged[i] = nudged[i]! + step
      assert.ok(sse(nudged) > best, `nudging c${i} by ${step} should raise the SSE`)
    }
  }
})

test('polyfit clamps the degree to the sample count so a few points cannot overfit', () => {
  // Two points can only support a line, whatever degree is asked for.
  const coeffs = polyfit([0, 10], [1, 3], 5)
  assert.ok(coeffs)
  assert.equal(coeffs.length, 2)
  close(coeffs[0], 1)
  close(coeffs[1], 0.2)
})

test('polyfit returns null when there is nothing to fit', () => {
  assert.equal(polyfit([], [], 1), null) // no samples
  assert.equal(polyfit([5], [1], 1), null) // one sample clamps to degree 0
  assert.equal(polyfit([0, 1, 2], [1, 2, 3], 0), null) // degree below linear
  assert.equal(polyfit([0, 1, 2], [1, 2, 3], -1), null)
})

test('polyfit returns null on a degenerate (singular) system', () => {
  // Every x identical — the normal equations have no unique solution. The
  // Radius Plot hits this when every measured point shares one radius.
  assert.equal(polyfit([1, 1, 1], [1, 2, 3], 1), null)
})

test('polyfit leaves the caller arrays untouched', () => {
  const xs = [0, 1, 2, 3]
  const ys = [1, 3, 5, 7]
  polyfit(xs, ys, 2)
  assert.deepEqual(xs, [0, 1, 2, 3])
  assert.deepEqual(ys, [1, 3, 5, 7])
})

test('polyfit handles a radius-plot shaped fit (mm radius, degree 2)', () => {
  // Centre-to-edge CD signature: radius 0…150 mm, CD around 2 units. Larger
  // x means Σx⁴ reaches ~5e8, so this also guards the conditioning.
  const xs = [0, 25, 50, 75, 100, 125, 150]
  const ys = xs.map(x => 2 - 0.001 * x + 0.00002 * x ** 2)
  const coeffs = polyfit(xs, ys, 2)
  assert.ok(coeffs)
  close(coeffs[0], 2, 1e-6)
  close(coeffs[1], -0.001, 1e-9)
  close(coeffs[2], 0.00002, 1e-12)
  // The fit line the chart draws must land on the samples.
  for (const [i, x] of xs.entries()) close(polyval(coeffs, x), ys[i]!, 1e-6)
})

// KNOWN GAP: polyfit sizes the fit off `xs` alone and never checks that `ys`
// matches. A short `ys` reads `undefined`, poisoning every sum, so the caller
// gets a NaN coefficient vector rather than the null that signals "no fit" —
// and a NaN fit line silently vanishes from the chart instead of being caught.
// A long `ys` has its tail dropped without complaint. Harmless today (see the
// header note: polyfit has no callers in the app yet), and pinned here so
// adding a length guard produces a visible diff rather than a quiet fix.
test('KNOWN GAP — mismatched xs/ys lengths yield NaN or truncation, not null', () => {
  const short = polyfit([0, 1, 2, 3], [1, 2, 3], 1)
  assert.ok(short)
  assert.ok(short.every(Number.isNaN), `expected all-NaN coefficients, got ${short}`)

  // Extra ys are dropped: the outlier 99 does not move the fit through y = 1 + x.
  const long = polyfit([0, 1, 2], [1, 2, 3, 99], 1)
  assert.ok(long)
  close(long[0], 1)
  close(long[1], 1)
})

test('polyval evaluates coefficients low-order first', () => {
  // 1 + 2·2 + 3·4 = 17
  assert.equal(polyval([1, 2, 3], 2), 17)
  assert.equal(polyval([7], 3), 7) // constant
  assert.equal(polyval([0, 1], 5), 5) // identity
})

test('polyval of no coefficients is zero', () => {
  assert.equal(polyval([], 5), 0)
})
