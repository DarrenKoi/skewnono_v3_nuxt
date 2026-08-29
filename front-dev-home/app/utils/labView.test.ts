import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_PANELS, LAB_PANELS, normalizePanels } from './labView.ts'

// The stored panel selection is untrusted input (localStorage), and the one
// thing it must never do is decide the ORDER cards render in — that order is
// editorial, and a hand-edited or click-ordered array would silently reshuffle
// the argument the page makes.

test('unknown names are dropped', () => {
  assert.deepEqual(normalizePanels(['map', 'nope', 42, null]), ['map'])
})

test('canonical order is restored, not the stored order', () => {
  assert.deepEqual(normalizePanels(['pm', 'verdict', 'map']), ['verdict', 'map', 'pm'])
})

test('duplicates collapse', () => {
  assert.deepEqual(normalizePanels(['trend', 'trend']), ['trend'])
})

test('an empty selection is legitimate — everything off', () => {
  assert.deepEqual(normalizePanels([]), [])
})

test('a non-array is refused, so the caller can fall back to the preset', () => {
  for (const raw of [null, undefined, 'map', {}, 7]) {
    assert.equal(normalizePanels(raw), null)
  }
})

test('every preset names real panels, in canonical order', () => {
  for (const panels of Object.values(DEFAULT_PANELS)) {
    assert.deepEqual(normalizePanels(panels), panels)
  }
})

test('the two presets between them cover every panel', () => {
  const covered = new Set(Object.values(DEFAULT_PANELS).flat())
  // A panel no preset turns on is a panel most users would never discover.
  assert.deepEqual([...covered].sort(), LAB_PANELS.map(p => p.value).sort())
})
