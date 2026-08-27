// Run: cd front-dev-home && node --test app/utils/skewvoirAnalysis/chipLattice.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildChipLattice } from './chipLattice.ts'

test('compacted axes: only occupied cols/rows, labelled with real indices, +row on top', () => {
  const l = buildChipLattice(['-1,2', '3,-1', '3,-1', '0, 0'])
  assert.equal(l.cols, 3)
  assert.equal(l.rows, 3)
  assert.deepEqual(l.colLabels, [-1, 0, 3])
  assert.deepEqual(l.rowLabels, [2, 0, -1])
  assert.deepEqual(l.cells.get('-1,2'), { col: 1, row: 1 })
  assert.deepEqual(l.cells.get('3,-1'), { col: 3, row: 3 })
  assert.deepEqual(l.cells.get('0, 0'), { col: 2, row: 2 })
  assert.equal(l.cells.size, 3)
})

test('unparseable chips are omitted, never placed at (0,0)', () => {
  const l = buildChipLattice(['garbage', '1,1'])
  assert.equal(l.cells.has('garbage'), false)
  assert.deepEqual(l.cells.get('1,1'), { col: 1, row: 1 })
  assert.deepEqual(buildChipLattice([]).cells.size, 0)
})
