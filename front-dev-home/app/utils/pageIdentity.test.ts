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

test('recipe-search sub-pages (compare, open, lateral) are the same identity', () => {
  const base = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search', {})
  const compare = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/compare', {})
  const open = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/open', {})
  const lateral = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/lateral', {})

  assert.equal(base, compare)
  assert.equal(base, open)
  assert.equal(base, lateral)
})

test('recipe-search and recipe-search/meas-hist are different identities', () => {
  const search = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search', {})
  const measHist = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/meas-hist', {})

  assert.notEqual(search, measHist)
})

test('afm sub-paths with different files are the same identity', () => {
  const map608 = resolvePageIdentity('/afm/map608/a.tif', {})
  const mapc01 = resolvePageIdentity('/afm/mapc01/b.tif', {})

  assert.equal(map608, mapc01)
})

test('device-statistics and device-statistics/comparison are the same identity', () => {
  const base = resolvePageIdentity('/ebeam/cd-sem/device-statistics', {})
  const comparison = resolvePageIdentity('/ebeam/cd-sem/device-statistics/comparison', {})

  assert.equal(base, comparison)
})

test('storage and hardware remain different identities', () => {
  const storage = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const hardware = resolvePageIdentity('/ebeam/cd-sem/M14/hardware', {})

  assert.notEqual(storage, hardware)
})

test('fab switch invariance holds on collapsed pages', () => {
  const m14search = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/compare', {})
  const m16search = resolvePageIdentity('/ebeam/cd-sem/M16B/recipe-search/compare', {})
  const m14stats = resolvePageIdentity('/ebeam/cd-sem/M14/device-statistics/comparison', {})
  const m16stats = resolvePageIdentity('/ebeam/cd-sem/M16B/device-statistics/comparison', {})

  assert.equal(m14search, m16search)
  assert.equal(m14stats, m16stats)
})
