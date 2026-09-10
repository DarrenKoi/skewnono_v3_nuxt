import assert from 'node:assert/strict'
import test from 'node:test'
import type { MeasHistFilters } from '../composables/useMeasHistSearch.ts'
import {
  emptyMeasHistFilters,
  hasAnyMeasHistFilter,
  hasNoMeasHistPicks,
  normalizeStoredMeasHistFilters,
  serializeMeasHistFilters
} from './measHistFilters.ts'

const filters = (patch: Partial<MeasHistFilters> = {}): MeasHistFilters => ({
  ...emptyMeasHistFilters(),
  ...patch
})

test('a fresh filter set has no picks and no date window', () => {
  assert.deepEqual(emptyMeasHistFilters(), {
    fab: [],
    category: [],
    model: [],
    eq: [],
    from: '',
    to: ''
  })
})

test('round-trips the four dropdown picks through storage', () => {
  const saved = filters({
    fab: ['M11A'],
    category: ['CD-SEM'],
    model: ['CG6300'],
    eq: ['ECXDX925', 'ECXDX926']
  })

  const restored = normalizeStoredMeasHistFilters(JSON.parse(serializeMeasHistFilters(saved)))

  assert.deepEqual(restored, saved)
})

// The date window is anchored to the backend's retention clock, so an absolute
// from/to saved today can sit wholly outside retention by the next visit.
test('drops the date range on the way out and on the way back in', () => {
  const saved = filters({ fab: ['M11A'], from: '2026-05-01', to: '2026-05-09' })

  assert.deepEqual(JSON.parse(serializeMeasHistFilters(saved)), {
    fab: ['M11A'],
    category: [],
    model: [],
    eq: []
  })

  // Even a key hand-written (or left by an older build) with dates in it comes
  // back cleared, so the default retention window always wins on load.
  const restored = normalizeStoredMeasHistFilters({
    fab: ['M11A'],
    from: '2026-05-01',
    to: '2026-05-09'
  })
  assert.equal(restored.from, '')
  assert.equal(restored.to, '')
})

test('degrades unusable storage payloads to an empty filter set', () => {
  for (const payload of [null, 'M11A', 42, ['M11A']]) {
    assert.deepEqual(normalizeStoredMeasHistFilters(payload), emptyMeasHistFilters())
  }
})

test('keeps only string entries and known categories out of a corrupted payload', () => {
  const restored = normalizeStoredMeasHistFilters({
    fab: ['M11A', 7, null],
    category: ['CD-SEM', 'AFM'],
    model: 'CG6300',
    eq: ['ECXDX925']
  })

  assert.deepEqual(restored, filters({
    fab: ['M11A'],
    category: ['CD-SEM'],
    model: [],
    eq: ['ECXDX925']
  }))
})

test('reports no picks so a vacant filter set drops its storage key', () => {
  assert.equal(hasNoMeasHistPicks(emptyMeasHistFilters()), true)
  // A date range alone is not a pick: it is never written, so it must not keep
  // an otherwise-empty key alive.
  assert.equal(hasNoMeasHistPicks(filters({ from: '2026-05-01' })), true)
  assert.equal(hasNoMeasHistPicks(filters({ eq: ['ECXDX925'] })), false)
})

test('counts either a pick or a date range as an active filter', () => {
  assert.equal(hasAnyMeasHistFilter(emptyMeasHistFilters()), false)
  assert.equal(hasAnyMeasHistFilter(filters({ category: ['HV-SEM'] })), true)
  assert.equal(hasAnyMeasHistFilter(filters({ from: '2026-05-01' })), true)
  assert.equal(hasAnyMeasHistFilter(filters({ to: '2026-05-09' })), true)
})
