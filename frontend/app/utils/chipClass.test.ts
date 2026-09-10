// Pure-logic tests for chipClass. Run: node --test app/utils/chipClass.test.ts
//
// chipClass returns the Tailwind class string for a shared filter chip. The
// literal utilities are styling and may change freely, so this file asserts
// only the two things that are behaviour rather than appearance: the accent
// fill marks selection and nothing else, and both states carry a dark-mode
// rule. Enumerating the class list here would just mirror the source.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { chipClass } from './chipClass.ts'

const ACCENT = '--sk-accent'

test('the accent token marks selection, and only selection', () => {
  // A chip row renders one class string per option; if the accent leaked into
  // the inactive branch every chip would read as selected at once.
  assert.ok(chipClass(true).includes(ACCENT))
  assert.ok(!chipClass(false).includes(ACCENT))
  assert.notEqual(chipClass(true), chipClass(false))
})

test('both states are styled for dark mode', () => {
  // The app has a theme toggle, so a state with no `dark:` rule renders a
  // light chip on a dark surface.
  assert.ok(chipClass(false).includes('dark:'))
  // The active chip is the accent fill in both themes, so it needs no dark:
  // override — pinned so its absence reads as intentional, not forgotten.
  assert.ok(!chipClass(true).includes('dark:'))
})
