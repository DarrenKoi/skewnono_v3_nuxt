// Pure-logic tests for headerNav. Run: node --test app/utils/headerNav.test.ts
// The invariant: the header's icon row and the pages that keep the feature tabs are one
// list, so a page cannot be reachable from the header while rendering no tabs.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { HEADER_LINKS, HEADER_INFO_PATHS, isHeaderInfoPath } from './headerNav.ts'

test('every header link has an icon and a label', () => {
  for (const link of HEADER_LINKS) {
    assert.ok(link.icon.startsWith('i-lucide-'), `${link.label} has no lucide icon`)
    assert.ok(link.label.length > 0, `${link.to} has no aria-label`)
  }
})

test('the info paths are exactly the fixed targets of the icon row', () => {
  // Derived, not hand-maintained — this is what makes the two lists impossible to drift.
  assert.deepEqual(
    HEADER_INFO_PATHS,
    HEADER_LINKS.filter(link => link.to !== null).map(link => link.to)
  )
})

test('/chat is reachable from the header and keeps its tabs', () => {
  // The regression this list exists to prevent: /chat is reachable only from its header
  // icon, so losing the tabs there left no way back to the main pages.
  assert.ok(HEADER_LINKS.some(link => link.to === '/chat'))
  assert.equal(isHeaderInfoPath('/chat'), true)
})

test('the fab-scoped live-alarm link is not an info path', () => {
  // Its target is computed per remembered tool/fab and lands inside /ebeam, where the tabs
  // come from isEbeamRoute instead.
  const dynamic = HEADER_LINKS.filter(link => link.to === null)
  assert.equal(dynamic.length, 1)
  assert.equal(dynamic[0]?.label, '라이브 알람')
  assert.ok(!HEADER_INFO_PATHS.includes(null as unknown as string))
})

test('every info path is an absolute top-level path, listed once', () => {
  for (const path of HEADER_INFO_PATHS) {
    assert.ok(path.startsWith('/'), `${path} is not absolute`)
    assert.ok(!path.endsWith('/'), `${path} has a trailing slash, which breaks prefix matching`)
  }
  assert.equal(new Set(HEADER_INFO_PATHS).size, HEADER_INFO_PATHS.length)
})

test('isHeaderInfoPath matches sub-routes but not partial segments', () => {
  assert.equal(isHeaderInfoPath('/settings'), true)
  assert.equal(isHeaderInfoPath('/settings/profile'), true)
  assert.equal(isHeaderInfoPath('/chat/'), true)
  assert.equal(isHeaderInfoPath('/chatroom'), false)
  assert.equal(isHeaderInfoPath('/intro-video'), false)
})

test('isHeaderInfoPath excludes the hub index and the ebeam tree', () => {
  // The hub shows no tabs; ebeam routes match on isEbeamRoute instead.
  assert.equal(isHeaderInfoPath('/'), false)
  assert.equal(isHeaderInfoPath('/ebeam/cd-sem/r3'), false)
  assert.equal(isHeaderInfoPath('/afm'), false)
})
