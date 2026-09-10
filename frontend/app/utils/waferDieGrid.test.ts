import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildDieGridSegments, dieCentreTicks, dieGridLineData } from './waferDieGrid.ts'
import type { WaferGeometry } from './waferGeometry.ts'

const geo = (pitchXmm: number, pitchYmm: number, offsetXmm = 0, offsetYmm = 0): WaferGeometry => ({
  sizeMm: 300,
  radiusMm: 150,
  centerNm: 150_000_000,
  pitchXmm,
  pitchYmm,
  offsetXmm,
  offsetYmm,
  originCol: 0,
  originRow: 0
})

test('boundaries sit on half-pitch offsets between die centres', () => {
  const segments = buildDieGridSegments(geo(10, 10), 150)
  const xs = segments.filter(([a, b]) => a[0] === b[0]).map(([a]) => a[0])
  // Die centres are at k·10, so boundaries land at ±5, ±15, ±25, …
  assert.ok(xs.includes(5))
  assert.ok(xs.includes(-5))
  assert.ok(xs.includes(145))
  assert.ok(!xs.some(x => x % 10 === 0)) // never through a die centre
})

test('die boundaries shift with the die-grid offset', () => {
  // Pitch 10, offset 2 → die centres at 2 + k·10, boundaries at 7, -3, 17, …
  const segments = buildDieGridSegments(geo(10, 10, 2, 0), 150)
  const xs = segments.filter(([a, b]) => a[0] === b[0]).map(([a]) => a[0])
  assert.ok(xs.includes(7))
  assert.ok(xs.includes(-3))
  assert.ok(!xs.includes(5)) // the unshifted boundary must be gone
})

test('an explicit zero offset is identical to omitting it', () => {
  // Pins that the offset-free path really is the offset=0 path, so the grid
  // above (which asserts the unshifted boundaries) still covers both.
  assert.deepEqual(
    buildDieGridSegments(geo(12.52, 10.34, 0, 0), 150),
    buildDieGridSegments(geo(12.52, 10.34), 150)
  )
})

test('every segment is a chord of the wafer circle', () => {
  for (const [start, end] of buildDieGridSegments(geo(12.52, 10.34), 150)) {
    for (const [x, y] of [start, end]) {
      const r = Math.hypot(x, y)
      assert.ok(Math.abs(r - 150) < 0.01, `endpoint (${x},${y}) should sit on the circle, r=${r}`)
    }
    // A vertical boundary keeps x fixed; a horizontal one keeps y fixed.
    assert.ok(start[0] === end[0] || start[1] === end[1])
  }
})

test('boundaries outside the wafer are dropped', () => {
  const segments = buildDieGridSegments(geo(100, 100), 150)
  const xs = segments.filter(([a, b]) => a[0] === b[0]).map(([a]) => a[0])
  assert.deepEqual([...new Set(xs)].sort((a, b) => a - b), [-50, 50])
})

test('unknown pitch yields no grid for that axis', () => {
  const onlyY = buildDieGridSegments(geo(0, 10), 150)
  assert.ok(onlyY.length > 0)
  assert.ok(onlyY.every(([a, b]) => a[1] === b[1])) // horizontal lines only
  assert.equal(buildDieGridSegments(geo(0, 0), 150).length, 0)
})

test('a degenerate tiny pitch is refused instead of flooding the map', () => {
  assert.equal(buildDieGridSegments(geo(0.01, 0.01), 150).length, 0)
})

test('dieCentreTicks lands on the die centres the boundaries enclose', () => {
  // Pitch 10, offset 2 → centres at 2 + k·10; the boundaries above are at 7, -3, …
  assert.deepEqual(dieCentreTicks(10, 45, 2), [-38, -28, -18, -8, 2, 12, 22, 32, 42])
})

test('every die centre is exactly midway between two die boundaries', () => {
  // The axis labels and the drawn lattice must come from one lattice, or the
  // number sits off the band it names — the double-grid bug in miniature.
  const g = geo(12.52, 10.34, 0, 4.61)
  const bounds = buildDieGridSegments(g, 150)
    .filter(([a, b]) => a[1] === b[1]).map(([a]) => a[1])
    .sort((a, b) => a - b)
  for (const centre of dieCentreTicks(g.pitchYmm, 150, g.offsetYmm)) {
    const below = Math.max(...bounds.filter(b => b < centre))
    const above = Math.min(...bounds.filter(b => b > centre))
    if (!Number.isFinite(below) || !Number.isFinite(above)) continue // outermost band
    assert.ok(Math.abs((below + above) / 2 - centre) < 0.01,
      `centre ${centre} is not midway between ${below} and ${above}`)
  }
})

test('dieCentreTicks refuses an unknown or degenerate pitch', () => {
  assert.deepEqual(dieCentreTicks(0, 150, 0), [])
  assert.deepEqual(dieCentreTicks(0.01, 150, 0), []) // same safety valve as the grid
})

test('dieGridLineData separates segments with null gaps', () => {
  const data = dieGridLineData(geo(100, 0), 150)
  assert.equal(data.length, 6) // 2 segments × (start, end, gap)
  assert.deepEqual(data[2], [null, null])
  assert.deepEqual(data[5], [null, null])
})
