// Pure-logic tests for fab. Run: node --test app/utils/fab.test.ts
// The rule under test: when no fab is remembered, we fall back to R3.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_FAB,
  NO_FAB,
  hasFab,
  fabSegment,
  normalizeFab,
  sameFab,
  sortFabNames,
  extractFabNames
} from './fab.ts'

test('the default fab is R3', () => {
  assert.equal(DEFAULT_FAB, 'R3')
})

test('the sentinel is not itself a fab', () => {
  // 'all' means "nothing selected", so it must never survive resolution as a URL segment.
  assert.equal(NO_FAB, 'all')
  assert.notEqual(DEFAULT_FAB, NO_FAB)
})

test('hasFab is true only for a real remembered fab', () => {
  assert.equal(hasFab('R3'), true)
  assert.equal(hasFab('M16B'), true)
  assert.equal(hasFab(NO_FAB), false)
  assert.equal(hasFab(''), false)
  assert.equal(hasFab(undefined), false)
  assert.equal(hasFab(null), false)
})

test('fabSegment keeps a remembered fab, lowercased for the URL', () => {
  // Fab names are stored uppercase (fab_name from the API) but routed lowercase.
  assert.equal(fabSegment('R3'), 'r3')
  assert.equal(fabSegment('R4'), 'r4')
  assert.equal(fabSegment('M16B'), 'm16b')
  assert.equal(fabSegment('r4'), 'r4')
})

test('fabSegment falls back to R3 when nothing is remembered', () => {
  // Every shape "no memory" can take: the sentinel, an empty string, or an
  // unset store value before the persist plugin has run.
  const fallback = DEFAULT_FAB.toLowerCase()
  assert.equal(fabSegment(NO_FAB), fallback)
  assert.equal(fabSegment(''), fallback)
  assert.equal(fabSegment(undefined), fallback)
  assert.equal(fabSegment(null), fallback)
})

// The backend returns fab_name in whichever case its source DB stores it — 'R3' from one,
// 'r3' from another. Everything below pins the app's response to that.

test('normalizeFab canonicalizes to uppercase and trims', () => {
  assert.equal(normalizeFab('r3'), 'R3')
  assert.equal(normalizeFab('R3'), 'R3')
  assert.equal(normalizeFab('m16b'), 'M16B')
  assert.equal(normalizeFab(' r3 '), 'R3')
  assert.equal(normalizeFab(''), '')
  assert.equal(normalizeFab(undefined), '')
  assert.equal(normalizeFab(null), '')
})

test('DEFAULT_FAB is already canonical', () => {
  assert.equal(normalizeFab(DEFAULT_FAB), DEFAULT_FAB)
})

test('sameFab compares across the casings the backend mixes', () => {
  assert.equal(sameFab('r3', 'R3'), true)
  assert.equal(sameFab('R3', 'r3'), true)
  assert.equal(sameFab('M16B', 'm16b'), true)
  assert.equal(sameFab('R3', 'R4'), false)
  assert.equal(sameFab('R3', undefined), false)
  assert.equal(sameFab(undefined, 'R3'), false)
})

test('fabSegment produces the same URL whatever case it is handed', () => {
  assert.equal(fabSegment('R3'), fabSegment('r3'))
  assert.equal(fabSegment('M16B'), fabSegment('m16b'))
})

test('the sentinel is recognised in any casing', () => {
  // A lowercase-only check would let 'ALL' through and build /ebeam/cd-sem/all.
  assert.equal(hasFab('ALL'), false)
  assert.equal(hasFab('All'), false)
  assert.equal(fabSegment('ALL'), DEFAULT_FAB.toLowerCase())
  assert.equal(fabSegment('All'), DEFAULT_FAB.toLowerCase())
})

test('sortFabNames keeps R-before-M ordering regardless of case', () => {
  // The parse regex used to be uppercase-only, so a lowercase name fell through
  // to localeCompare and silently landed in the wrong group.
  assert.deepEqual(
    ['m11', 'R3', 'r4', 'M16'].sort(sortFabNames),
    ['R3', 'r4', 'M16', 'm11']
  )
  assert.deepEqual(
    ['M11', 'R3', 'R4', 'M16'].sort(sortFabNames),
    ['R3', 'R4', 'M16', 'M11']
  )
})

test('sortFabNames orders suffixed fabs within the same fac', () => {
  assert.deepEqual(['m16b', 'M16A', 'm16c'].sort(sortFabNames), ['M16A', 'm16b', 'm16c'])
})

test('extractFabNames folds mixed casing into one canonical entry', () => {
  // Two DBs reporting the same fab differently must not become two picker options.
  assert.deepEqual(
    extractFabNames([{ fab_name: 'R3' }, { fab_name: 'r3' }, { fab_name: 'M16' }]),
    ['R3', 'M16']
  )
})

test('extractFabNames drops rows with no fab name', () => {
  // An empty option in the fab picker is never selectable-meaningful.
  assert.deepEqual(extractFabNames([{ fab_name: '' }, { fab_name: 'R3' }]), ['R3'])
  assert.deepEqual(extractFabNames([]), [])
})

test('fabSegment never yields a value that would build a broken URL', () => {
  for (const input of [NO_FAB, '', undefined, null, 'R3', 'M11']) {
    const segment = fabSegment(input)
    assert.notEqual(segment, '', `fabSegment(${String(input)}) produced an empty segment`)
    assert.notEqual(segment, NO_FAB, `fabSegment(${String(input)}) leaked the sentinel into a URL`)
  }
})
