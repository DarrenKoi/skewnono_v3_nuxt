// Pure-logic tests for fab. Run: node --test app/utils/fab.test.ts
// The rule under test: when no fab is remembered, we fall back to R3.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_FAB, NO_FAB, hasFab, resolveFab, fabSegment } from './fab.ts'

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

test('resolveFab keeps a remembered fab as-is', () => {
  assert.equal(resolveFab('R3'), 'R3')
  assert.equal(resolveFab('R4'), 'R4')
  assert.equal(resolveFab('M16B'), 'M16B')
})

test('resolveFab falls back to R3 when nothing is remembered', () => {
  // Every shape "no memory" can take: the sentinel, an empty string, or an
  // unset store value before the persist plugin has run.
  assert.equal(resolveFab(NO_FAB), DEFAULT_FAB)
  assert.equal(resolveFab(''), DEFAULT_FAB)
  assert.equal(resolveFab(undefined), DEFAULT_FAB)
  assert.equal(resolveFab(null), DEFAULT_FAB)
})

test('fabSegment lowercases for the URL', () => {
  // Fab names are stored uppercase (fab_name from the API) but URLs are lowercase.
  assert.equal(fabSegment('R3'), 'r3')
  assert.equal(fabSegment('M16B'), 'm16b')
  assert.equal(fabSegment('r4'), 'r4')
})

test('fabSegment applies the R3 fallback before lowercasing', () => {
  assert.equal(fabSegment(NO_FAB), 'r3')
  assert.equal(fabSegment(''), 'r3')
  assert.equal(fabSegment(undefined), 'r3')
})

test('resolveFab never yields a value that would build a broken URL', () => {
  for (const input of [NO_FAB, '', undefined, null, 'R3', 'M11']) {
    const resolved = resolveFab(input)
    assert.notEqual(resolved, '', `resolveFab(${String(input)}) produced an empty segment`)
    assert.notEqual(resolved, NO_FAB, `resolveFab(${String(input)}) leaked the sentinel into a URL`)
  }
})
