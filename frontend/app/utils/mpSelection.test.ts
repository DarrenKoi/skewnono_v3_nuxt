// Pure-logic tests for mpSelection. Run: node --test app/utils/mpSelection.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { siteKey, toggleKey, headerState, pickExportRows } from './mpSelection.ts'

test('siteKey composes param and seq and disambiguates same seq across params', () => {
  assert.notEqual(siteKey('CD_A', 1), siteKey('CD_B', 1))
  assert.equal(siteKey('CD_A', 1), siteKey('CD_A', 1))
})

test('toggleKey adds a missing key and removes a present one, without mutating', () => {
  const src = [siteKey('P', 1)]
  const added = toggleKey(src, siteKey('P', 2))
  assert.deepEqual(added, [siteKey('P', 1), siteKey('P', 2)])
  assert.deepEqual(src, [siteKey('P', 1)]) // unmutated
  assert.deepEqual(toggleKey(added, siteKey('P', 1)), [siteKey('P', 2)])
})

test('headerState reflects the visible keys only', () => {
  const k = (n: number) => siteKey('P', n)
  assert.equal(headerState([], new Set([k(1)])), 'none')
  assert.equal(headerState([k(1), k(2), k(3)], new Set()), 'none')
  assert.equal(headerState([k(1), k(2), k(3)], new Set([k(2)])), 'some')
  assert.equal(headerState([k(1), k(2), k(3)], new Set([k(1), k(2), k(3), k(9)])), 'all')
})

test('pickExportRows: empty selection = all rows; otherwise checked ∩ visible by key', () => {
  const rows = [{ param: 'P', seq: 1 }, { param: 'P', seq: 2 }, { param: 'Q', seq: 1 }]
  const keyOf = (r: { param: string, seq: number }) => siteKey(r.param, r.seq)
  assert.deepEqual(pickExportRows(rows, new Set(), keyOf), rows)
  // Selecting P/1 must NOT drag in Q/1 (same seq, different param).
  assert.deepEqual(
    pickExportRows(rows, new Set([siteKey('P', 1)]), keyOf),
    [{ param: 'P', seq: 1 }])
})
