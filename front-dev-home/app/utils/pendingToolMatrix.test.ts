// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  STALE_ARRIVAL_DAYS,
  UNASSIGNED_FAB,
  buildPendingToolMatrix,
  cellRows,
  countByGroup,
  filterByGroup,
  groupOf,
  ipList,
  isStaleArrival
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

test('isStaleArrival is exclusive at the threshold', () => {
  const now = new Date('2026-07-30T00:00:00Z')
  const daysAgo = (n: number) =>
    new Date(now.getTime() - n * 86_400_000).toISOString()

  assert.equal(isStaleArrival(daysAgo(STALE_ARRIVAL_DAYS - 1), now), false)
  assert.equal(isStaleArrival(daysAgo(STALE_ARRIVAL_DAYS), now), false)
  assert.equal(isStaleArrival(daysAgo(STALE_ARRIVAL_DAYS + 1), now), true)
})

test('isStaleArrival treats an unparseable arrival as not stale', () => {
  // Never hide a row because its timestamp was malformed — the cost of a
  // missing new arrival is a tool nobody notices is unreachable.
  assert.equal(isStaleArrival('', new Date('2026-07-30T00:00:00Z')), false)
  assert.equal(isStaleArrival('not a date', new Date('2026-07-30T00:00:00Z')), false)
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
