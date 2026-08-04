import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolvePageIdentity, buildPageViewPath } from './pageIdentity.ts'

test('a fab switch on the same page is the same identity', () => {
  const a = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const b = resolvePageIdentity('/ebeam/cd-sem/M16B/storage', {})

  assert.equal(a, b)
})

test('a filter query change is the same identity', () => {
  const a = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const b = resolvePageIdentity('/ebeam/cd-sem/M14/storage', { ppid: 'X1' })

  assert.equal(a, b)
})

test('different pages are different identities', () => {
  assert.notEqual(
    resolvePageIdentity('/ebeam/cd-sem/M14/storage', {}),
    resolvePageIdentity('/ebeam/cd-sem/M14/hardware', {})
  )
})

test('recipe-status tabs are three different identities', () => {
  const tat = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })
  const align = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'align' })
  const meas = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'meas' })

  assert.equal(new Set([tat, align, meas]).size, 3)
})

test('recipe-status without a tab is unresolved', () => {
  // RecipeStatusView writes ?tab= back on mount; firing before that would
  // count one visit twice.
  assert.equal(resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', {}), null)
})

test('an array-valued tab takes its first entry', () => {
  // Vue router surfaces a repeated query key as an array.
  assert.equal(
    resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: ['tat', 'align'] }),
    resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })
  )
})

test('the reported path carries the tab and nothing else', () => {
  assert.equal(
    buildPageViewPath('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat', ppid: 'X1' }),
    '/ebeam/cd-sem/M14/recipe-status?tab=tat'
  )
  assert.equal(
    buildPageViewPath('/ebeam/cd-sem/M14/storage', { ppid: 'X1' }),
    '/ebeam/cd-sem/M14/storage'
  )
})
