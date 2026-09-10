import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_PANELS, normalizePanels, storedPanels } from './labView.ts'

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

test('the preset names real panels, in canonical order', () => {
  assert.deepEqual(normalizePanels(DEFAULT_PANELS), DEFAULT_PANELS)
})

test('the preset leaves pm off — ticking it is what summons 튜닝할 장비', () => {
  assert.ok(!DEFAULT_PANELS.includes('pm'))
})

// The stored shape changed on 2026-09-01, when /pm-planning stopped being a
// route: it was keyed by route slug, and is now the selection itself. Both
// forms are in users' browsers, and neither may hand back the wrong panels.

test('a pre-merge value keeps the tttm pick and drops the pm-planning one', () => {
  assert.deepEqual(
    storedPanels({ 'tttm': ['map', 'verdict'], 'pm-planning': ['map', 'pm'] }),
    ['verdict', 'map']
  )
})

test('a pre-merge value with no tttm key falls back to the preset', () => {
  assert.deepEqual(storedPanels({ 'pm-planning': ['map', 'pm'] }), DEFAULT_PANELS)
})

test('the current form is read as itself', () => {
  assert.deepEqual(storedPanels(['pm', 'map']), ['map', 'pm'])
})

test('everything unticked survives the read — it is a choice, not a missing value', () => {
  assert.deepEqual(storedPanels([]), [])
  assert.deepEqual(storedPanels({ tttm: [] }), [])
})

test('junk falls back to the preset rather than an empty page', () => {
  for (const raw of [null, undefined, 'map', 7, {}]) {
    assert.deepEqual(storedPanels(raw), DEFAULT_PANELS)
  }
})

test('the preset is copied, so a caller cannot mutate it', () => {
  const first = storedPanels(null)
  first.push('pm')
  assert.deepEqual(storedPanels(null), DEFAULT_PANELS)
})
