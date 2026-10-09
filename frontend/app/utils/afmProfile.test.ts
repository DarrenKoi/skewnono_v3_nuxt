// Pure-logic tests for afmProfile. Run: node --test app/utils/afmProfile.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { levelLine, overlayProfiles, readProfile, type ProfileLoad } from './afmProfile.ts'

const UM_NM = { x_unit: 'um', y_unit: 'um', z_unit: 'nm', surface_size: '' }

test('readProfile keeps a 1D line as [x, z] pairs with the units its file states, dropping samples with no height', () => {
  const load = readProfile({
    data: [{ x: 0, y: 0, z: 5 }, { x: 1, y: 0, z: null }, { x: 2, y: 0, z: 7 }],
    meta: { ...UM_NM, data_size: '3 x 1' },
    count: 3,
    total: 3
  })
  assert.deepEqual(load, { line: { xUnit: 'um', zUnit: 'nm', data: [[0, 5], [2, 7]], thinned: false } })
})

test('readProfile marks a line the server thinned', () => {
  const load = readProfile({ data: [{ x: 0, y: 0, z: 5 }, { x: 2, y: 0, z: 7 }], meta: { ...UM_NM, data_size: '4 x 1' }, count: 2, total: 4 })
  assert.equal('line' in load && load.line.thinned, true)
})

test('readProfile refuses what cannot be overlaid, with the reason', () => {
  const grid = [{ x: 0, y: 0, z: 1 }, { x: 1, y: 0, z: 2 }, { x: 0, y: 1, z: 3 }, { x: 1, y: 1, z: 4 }]
  assert.deepEqual(readProfile({ data: grid, meta: { ...UM_NM, data_size: '2 x 2' }, count: 4 }), { skip: 'grid' })
  assert.deepEqual(readProfile({ data: [], meta: { ...UM_NM, data_size: '2 x 1' }, count: 0 }), { skip: 'none' })
  assert.deepEqual(readProfile({ data: [{ x: 0, y: 0, z: null }, { x: 1, y: 0, z: null }], meta: { ...UM_NM, data_size: '2 x 1' }, count: 2 }), { skip: 'none' })
  // No metadata: the file states no unit, so nothing says it matches another's.
  assert.deepEqual(readProfile({ data: [{ x: 0, y: 0, z: 1 }, { x: 1, y: 0, z: 2 }], meta: null, count: 2 }), { skip: 'nounit' })
})

const near = (actual: [number, number][], expected: [number, number][]) => {
  assert.equal(actual.length, expected.length)
  actual.forEach(([x, z], i) => {
    assert.equal(x, expected[i]![0])
    assert.ok(Math.abs(z - expected[i]![1]) < 1e-9, `z[${i}] = ${z}, expected ${expected[i]![1]}`)
  })
}

test('levelLine subtracts the least-squares line fitted to the profile itself', () => {
  // x̄ = 1.5, z̄ = 3, Sxx = 5, Sxz = 7 → slope 1.4, intercept 0.9;
  // the fit reads 0.9, 2.3, 3.7, 5.1, so the residuals are 0.1, 0.7, -1.7, 0.9.
  near(levelLine([[0, 1], [1, 3], [2, 2], [3, 6]]), [[0, 0.1], [1, 0.7], [2, -1.7], [3, 0.9]])
})

test('levelLine with no spread in x removes the mean alone', () => {
  near(levelLine([[5, 2], [5, 4]]), [[5, -1], [5, 1]])
  assert.deepEqual(levelLine([]), [])
})

const line = (xUnit: string, zUnit: string): ProfileLoad => ({ line: { xUnit, zUnit, data: [[0, 1], [1, 2]], thinned: false } })

test('overlayProfiles draws the profiles in the selected measurement\'s unit and lists every other with its reason', () => {
  const result = overlayProfiles([
    { key: 'a', load: line('um', 'nm') },
    { key: 'b', load: line('Pixel', 'nm') },
    { key: 'c', load: line('Pixel', 'nm') },
    { key: 'd', load: { skip: 'grid' } },
    { key: 'e', load: { skip: 'failed' } },
    { key: 'f', load: line('nm', 'nm') }
  ], 'c')
  assert.deepEqual(result.unit, { x: 'Pixel', z: 'nm' })
  assert.deepEqual(result.drawn.map(d => d.key), ['b', 'c'])
  assert.deepEqual(result.skipped, [
    { key: 'a', reason: 'unit' },
    { key: 'd', reason: 'grid' },
    { key: 'e', reason: 'failed' },
    { key: 'f', reason: 'unit' }
  ])
})

test('overlayProfiles falls back to the first drawable profile\'s unit when the selected one is not drawable', () => {
  const result = overlayProfiles([
    { key: 'a', load: { skip: 'none' } },
    { key: 'b', load: line('um', 'pm') },
    { key: 'c', load: line('um', 'nm') }
  ], 'a')
  assert.deepEqual(result.unit, { x: 'um', z: 'pm' })
  assert.deepEqual(result.drawn.map(d => d.key), ['b'])
  assert.deepEqual(result.skipped, [{ key: 'a', reason: 'none' }, { key: 'c', reason: 'unit' }])
})

test('overlayProfiles treats two spellings of one unit as the same unit, and has no unit when nothing is drawable', () => {
  const same = overlayProfiles([{ key: 'a', load: line('um', 'nm') }, { key: 'b', load: line('MicroMeter', 'NanoMeter') }], 'a')
  assert.deepEqual(same.drawn.map(d => d.key), ['a', 'b'])
  assert.deepEqual(overlayProfiles([{ key: 'a', load: { skip: 'grid' } }], 'a'), { unit: null, drawn: [], skipped: [{ key: 'a', reason: 'grid' }] })
})
