// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  UNASSIGNED_FAB,
  buildPendingToolMatrix,
  cellRows,
  countByGroup,
  filterByGroup,
  groupOf,
  ipList,
  sortByArrivalDesc
} from './pendingToolMatrix.ts'
import type { PendingToolRow } from './pendingToolMatrix.ts'

const tool = (
  eqp_id: string,
  eqp_model_cd: string,
  fab_name: string,
  eqp_ip = '177.1.1.1',
  updt_dt = '2026-07-01T00:00:00Z'
): PendingToolRow => ({
  fac_id: fab_name.startsWith('R') ? 'R3' : 'M16',
  eqp_id,
  eqp_model_cd,
  eqp_grp_id: 'G-ECD-01',
  vendor_nm: eqp_model_cd.startsWith('VERITYSEM') || eqp_model_cd.startsWith('PROVISION')
    ? 'AMAT'
    : 'HITACHI',
  eqp_ip,
  fab_name,
  updt_dt
})

test('groupOf resolves all four tool types and falls back to unclassified', () => {
  assert.equal(groupOf(tool('A', 'CG6380', 'M16A')), 'cd-sem')
  assert.equal(groupOf(tool('B', 'GT2000', 'M16A')), 'cd-sem')
  assert.equal(groupOf(tool('C', 'TP4000', 'M14B')), 'hv-sem')
  assert.equal(groupOf(tool('D', 'VERITYSEM_4', 'M16A')), 'verity-sem')
  assert.equal(groupOf(tool('E', 'PROVISION_10', 'M11A')), 'provision')
  // A model the company installs next year. This bucket is the only thing
  // keeping a new tool type from vanishing off the arrivals screen.
  assert.equal(groupOf(tool('F', 'ZZ9000', 'M16A')), 'unclassified')
})

test('countByGroup counts every group present', () => {
  const counts = countByGroup([
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M16A'),
    tool('C', 'TP4000', 'M14B'),
    tool('D', 'ZZ9000', 'M16A')
  ])

  assert.equal(counts.get('cd-sem'), 2)
  assert.equal(counts.get('hv-sem'), 1)
  assert.equal(counts.get('unclassified'), 1)
  assert.equal(counts.get('verity-sem'), undefined)
})

test('filterByGroup with all returns everything unchanged', () => {
  const rows = [tool('A', 'CG6380', 'M16A'), tool('C', 'TP4000', 'M14B')]
  assert.deepEqual(filterByGroup(rows, 'all'), rows)
})

test('filterByGroup narrows to one tool type', () => {
  const rows = [tool('A', 'CG6380', 'M16A'), tool('C', 'TP4000', 'M14B')]
  assert.deepEqual(filterByGroup(rows, 'hv-sem').map(r => r.eqp_id), ['C'])
})

test('filterByGroup narrows to unclassified', () => {
  // The domain-critical case: this is the bucket that keeps an unrecognized
  // model type from silently vanishing off the arrivals screen. A sentinel
  // mismatch here would make this filter always return [] with nothing else
  // to catch it.
  const rows = [tool('A', 'CG6380', 'M16A'), tool('F', 'ZZ9000', 'M16A')]
  assert.deepEqual(filterByGroup(rows, 'unclassified').map(r => r.eqp_id), ['F'])
})

test('buildPendingToolMatrix cross-tabulates fab against model', () => {
  const matrix = buildPendingToolMatrix([
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M16A'),
    tool('C', 'GT2000', 'M16B'),
    tool('D', 'CG6380', 'M16B')
  ])

  assert.deepEqual(matrix.fabs, ['M16A', 'M16B'])
  assert.deepEqual(matrix.models, ['CG6380', 'GT2000'])
  assert.deepEqual(matrix.counts, [[2, 0], [1, 1]])
  assert.deepEqual(matrix.fabTotals, [2, 2])
  assert.deepEqual(matrix.modelTotals, [3, 1])
  assert.equal(matrix.total, 4)
})

test('buildPendingToolMatrix sorts fabs naturally, not lexically', () => {
  const matrix = buildPendingToolMatrix([
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M9A'),
    tool('C', 'CG6380', 'M11A')
  ])

  assert.deepEqual(matrix.fabs, ['M9A', 'M11A', 'M16A'])
})

test('buildPendingToolMatrix buckets a blank fab as 미배정 and sorts it last', () => {
  const matrix = buildPendingToolMatrix([
    tool('A', 'CG6380', ''),
    tool('B', 'CG6380', 'M16A')
  ])

  assert.deepEqual(matrix.fabs, ['M16A', UNASSIGNED_FAB])
  assert.equal(matrix.total, 2)
  // Proves the 미배정 row's tool actually lands in the grid, not just that the
  // bucket earns a label — if the counts loop indexed by raw row.fab_name
  // instead of fabLabel(row.fab_name), this row would come out all-zero.
  assert.deepEqual(matrix.counts, [[1], [1]])
  assert.deepEqual(matrix.fabTotals, [1, 1])
})

test('buildPendingToolMatrix on no rows is empty, not a crash', () => {
  const matrix = buildPendingToolMatrix([])

  assert.deepEqual(matrix.fabs, [])
  assert.deepEqual(matrix.models, [])
  assert.deepEqual(matrix.counts, [])
  assert.equal(matrix.total, 0)
})

test('cellRows returns the tools behind one cell, including the 미배정 bucket', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A'),
    tool('B', 'CG6380', 'M16A'),
    tool('C', 'GT2000', 'M16A'),
    tool('D', 'CG6380', '')
  ]

  assert.deepEqual(cellRows(rows, 'M16A', 'CG6380').map(r => r.eqp_id), ['A', 'B'])
  assert.deepEqual(cellRows(rows, UNASSIGNED_FAB, 'CG6380').map(r => r.eqp_id), ['D'])
})

test('ipList is newline separated, deduped, and order-preserving', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A', '177.1.1.1'),
    tool('B', 'CG6380', 'M16A', '177.1.1.2'),
    tool('C', 'CG6380', 'M16A', '177.1.1.1')
  ]

  assert.equal(ipList(rows), '177.1.1.1\n177.1.1.2')
})

test('ipList skips blank ips', () => {
  assert.equal(ipList([tool('A', 'CG6380', 'M16A', '')]), '')
})

test('sortByArrivalDesc orders newest arrival first', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A', '177.1.1.1', '2026-01-01T00:00:00Z'),
    tool('B', 'CG6380', 'M16A', '177.1.1.2', '2026-07-01T00:00:00Z'),
    tool('C', 'CG6380', 'M16A', '177.1.1.3', '2026-04-01T00:00:00Z')
  ]

  assert.deepEqual(sortByArrivalDesc(rows).map(r => r.eqp_id), ['B', 'C', 'A'])
})

test('sortByArrivalDesc does not mutate its input', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A', '177.1.1.1', '2026-01-01T00:00:00Z'),
    tool('B', 'CG6380', 'M16A', '177.1.1.2', '2026-07-01T00:00:00Z')
  ]
  const original = [...rows]

  sortByArrivalDesc(rows)

  assert.deepEqual(rows, original)
})

test('sortByArrivalDesc sorts an unparseable arrival last', () => {
  // We cannot claim an unparseable date "just arrived" — ranking it ahead of
  // a known-recent row would misrepresent it, so it sorts to the end.
  const rows = [
    tool('A', 'CG6380', 'M16A', '177.1.1.1', 'not a date'),
    tool('B', 'CG6380', 'M16A', '177.1.1.2', '2026-01-01T00:00:00Z')
  ]

  assert.deepEqual(sortByArrivalDesc(rows).map(r => r.eqp_id), ['B', 'A'])
})
