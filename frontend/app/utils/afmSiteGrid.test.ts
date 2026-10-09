// Pure-logic tests for afmSiteGrid. Run: node --test app/utils/afmSiteGrid.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { AfmDetailRow, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { blockRows } from './afmPoints.ts'
import { siteGrid } from './afmSiteGrid.ts'

const H = 'H (nm)'
const row = (point: string, x: unknown, y: unknown, h: unknown, extra: Record<string, unknown> = {}) =>
  ({ 'measurement_point': point, 'Site X': x, 'Site Y': y, 'State': 'COMPLETED', 'Valid': true, [H]: h, ...extra }) as unknown as AfmDetailRow

test('each point sits at its Site X / Site Y index with the column value', () => {
  const grid = siteGrid([row('0001', 0, 0, 10), row('0002', 2, -1, 30)], H)
  assert.deepEqual(grid.xs, [0, 1, 2])
  assert.deepEqual(grid.ys, [-1, 0])
  assert.deepEqual(grid.cells, [
    { x: 0, y: 0, points: ['0001'], value: 10, valued: 1, laps: 1, state: 'COMPLETED', invalid: 0 },
    { x: 2, y: -1, points: ['0002'], value: 30, valued: 1, laps: 1, state: 'COMPLETED', invalid: 0 }
  ])
  assert.equal(grid.min, 10)
  assert.equal(grid.max, 30)
})

test('a repeat lap does not overwrite silently: the last lap is the reading and the laps are counted', () => {
  const grid = siteGrid([row('0001', 0, 0, 10), row('0002', 1, 0, 20), row('0001', 0, 0, 14), row('0002', 1, 0, 26)], H)
  assert.deepEqual(grid.cells.map(c => [c.x, c.points, c.value, c.laps]), [[0, ['0001'], 14, 2], [1, ['0002'], 26, 2]])
})

test('several points of one site are averaged, each by its own last lap', () => {
  const grid = siteGrid([row('0001', 0, 0, 10), row('0002', 0, 0, 20), row('0001', 0, 0, 30)], H)
  assert.deepEqual(grid.cells, [
    { x: 0, y: 0, points: ['0001', '0002'], value: 25, valued: 2, laps: 2, state: 'COMPLETED', invalid: 0 }
  ])
})

test('a FAILED, STOPPED or Valid FALSE reading is never a value', () => {
  const grid = siteGrid([
    row('0001', 0, 0, 99, { State: 'FAILED' }),
    row('0002', 1, 0, 1, { State: 'STOPPED' }),
    row('0003', 2, 0, 50, { Valid: false }),
    row('0004', 3, 0, 40),
    row('0005', 3, 0, 500, { State: 'FAILED' }),
    row('0006', 4, 0, ' ')
  ], H)
  assert.deepEqual(grid.cells.map(c => [c.x, c.value, c.valued, c.state, c.invalid]), [
    [0, null, 0, 'FAILED', 1],
    [1, null, 0, 'STOPPED', 1],
    [2, null, 0, 'COMPLETED', 1],
    [3, 40, 1, 'FAILED', 1],
    [4, null, 0, 'COMPLETED', 1]
  ])
  assert.equal(grid.min, 40)
  assert.equal(grid.max, 40)
})

test('rows without an integer Site X / Site Y are left out, and none is an empty grid', () => {
  const grid = siteGrid([row('0001', null, null, 10), row('0002', '2', '-1', 30), row('0003', 0.5, 0, 20), row('0004', undefined, 1, 20)], H)
  assert.deepEqual(grid.cells.map(c => [c.x, c.y, c.points]), [[2, -1, ['0002']]])
  assert.deepEqual(siteGrid([row('0001', null, null, 10)], H), { xs: [], ys: [], cells: [], min: null, max: null })
})

test('blockRows groups rows by the block they name, in first-appearance order', () => {
  const a = row('0001', 0, 0, 1, { Site: 'LEFT' })
  const b = row('0001', 0, 0, 2, { Site: 'RIGHT' })
  const c = row('0002', 1, 0, 3, { Site: 'LEFT' })
  assert.deepEqual([...blockRows([a, b, c], [])], [['LEFT', [a, c]], ['RIGHT', [b]]])
  const bare = row('0001', 0, 0, 1)
  assert.deepEqual([...blockRows([bare], [{ Site: 'Only', ITEM: 'MEAN' } as AfmSummaryRow])], [['Only', [bare]]])
})
