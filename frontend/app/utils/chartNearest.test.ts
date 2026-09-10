// Pure-logic tests for chartNearest. Run: node --test app/utils/chartNearest.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { nearestPoint, nearestIndex } from './chartNearest.ts'

// A click at (x, y) on a chart where one pixel is worth one data unit on both
// axes, so distances in the tests read directly as pixels.
const clickAt = (x: number, y: number, perPixel = { x: 1, y: 1 }) => ({
  x,
  y,
  gridIndex: 0,
  dataPerPixelX: perPixel.x,
  dataPerPixelY: perPixel.y
})

const pts = [
  { x: 0, y: 0, item: 'origin' },
  { x: 10, y: 10, item: 'near' },
  { x: 100, y: 100, item: 'far' }
]

test('picks the point nearest the click', () => {
  assert.equal(nearestPoint(pts, clickAt(12, 12)), 'near')
  assert.equal(nearestPoint(pts, clickAt(1, 2)), 'origin')
})

test('a click in empty space selects nothing rather than snapping across the plot', () => {
  // 400px from everything — the reader was not aiming at a point.
  assert.equal(nearestPoint(pts, clickAt(400, 400)), null)
})

test('the pick radius is in screen pixels, not data units', () => {
  // Same 30-unit gap, but each pixel is worth 10 data units here, so the point
  // is only 3px away on screen and is well within reach.
  assert.equal(
    nearestPoint([{ x: 30, y: 0, item: 'a' }], clickAt(0, 0, { x: 10, y: 10 })),
    'a'
  )
  // With one unit per pixel the same gap is 30px — still inside the radius.
  assert.equal(nearestPoint([{ x: 30, y: 0, item: 'a' }], clickAt(0, 0)), 'a')
  // And 300 units at one unit per pixel is out of reach.
  assert.equal(nearestPoint([{ x: 300, y: 0, item: 'a' }], clickAt(0, 0)), null)
})

test('axes with different units are weighed by their own scale', () => {
  // x is seconds (1000 per pixel), y is nm (0.1 per pixel). Candidate A is far
  // in raw x numbers but 2px away; B is close in raw numbers but 50px away.
  const scaled = clickAt(0, 0, { x: 1000, y: 0.1 })
  const a = { x: 2000, y: 0, item: 'a' }
  const b = { x: 0, y: 5, item: 'b' }
  assert.equal(nearestPoint([a, b], scaled), 'a')
})

test('xOnly ignores the vertical miss', () => {
  const points = [{ x: 5, y: 900, item: 'moment' }]
  // 900px above the click: rejected when y counts...
  assert.equal(nearestPoint(points, clickAt(5, 0)), null)
  // ...but on a trend read left-to-right, only the moment matters.
  assert.equal(nearestPoint(points, clickAt(5, 0), { xOnly: true }), 'moment')
})

test('a tighter radius can be requested per chart', () => {
  const points = [{ x: 20, y: 0, item: 'a' }]
  assert.equal(nearestPoint(points, clickAt(0, 0)), 'a')
  assert.equal(nearestPoint(points, clickAt(0, 0), { maxDistancePx: 10 }), null)
})

test('empty candidates and unusable coordinates yield null', () => {
  assert.equal(nearestPoint([], clickAt(0, 0)), null)
  assert.equal(nearestPoint([{ x: NaN, y: 0, item: 'a' }], clickAt(0, 0)), null)
})

test('nearestIndex rounds to the category under the cursor', () => {
  assert.equal(nearestIndex(2.4, 10), 2)
  assert.equal(nearestIndex(2.6, 10), 3)
})

test('nearestIndex rejects a click past the last category', () => {
  assert.equal(nearestIndex(9.6, 10), null)
  assert.equal(nearestIndex(-0.6, 10), null)
  assert.equal(nearestIndex(NaN, 10), null)
  assert.equal(nearestIndex(0, 0), null)
})
