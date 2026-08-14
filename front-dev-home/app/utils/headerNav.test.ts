// Pure-logic tests for headerNav. Run: node --test app/utils/headerNav.test.ts
// The invariant: the header's menus and the pages that keep the feature tabs are one
// list, so a page cannot be reachable from the header while rendering no tabs.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { HEADER_LINKS, HEADER_INFO_PATHS, headerLinksIn, isHeaderInfoPath, isHeaderLinkActive } from './headerNav.ts'

test('every header link has an icon and a label', () => {
  for (const link of HEADER_LINKS) {
    assert.ok(link.icon.startsWith('i-lucide-'), `${link.label} has no lucide icon`)
    assert.ok(link.label.length > 0, `${link.to} has no aria-label`)
  }
})

test('the two menus partition the list — no entry is dropped by its group', () => {
  // This is the whole reason `group` is a field rather than two exported arrays. If a menu
  // could hold a link the derivation below never sees, the header would offer a page whose
  // feature tabs vanish — the bug this file exists to prevent, in its 2026-08 form.
  const grouped = [...headerLinksIn('lab'), ...headerLinksIn('account')]
  assert.equal(grouped.length, HEADER_LINKS.length)
  assert.deepEqual(new Set(grouped), new Set(HEADER_LINKS))
})

test('실험실 rows explain themselves, 계정 rows do not need to', () => {
  for (const link of headerLinksIn('lab')) {
    assert.ok(link.description, `${link.label} is a two-line lab row with no description`)
  }
  assert.ok(headerLinksIn('account').length > 0)
})

test('채팅 is the only separated row, and it is last in 실험실', () => {
  // 앞의 셋은 조회·계산 도구, 채팅은 대화형 — 구분선이 그 성격 차이를 그립니다.
  const lab = headerLinksIn('lab')
  assert.deepEqual(lab.filter(link => link.separated).map(link => link.label), ['채팅'])
  assert.equal(lab.at(-1)?.label, '채팅')
})

test('no header icon repeats, and none collides with 디바이스 통계', () => {
  // bar-chart-3 belonged to both 사용 통계 and the 디바이스 통계 feature tab, which made the
  // icon useless as an identifier; 사용 통계 moved to activity.
  const icons = HEADER_LINKS.map(link => link.icon)
  assert.equal(new Set(icons).size, icons.length)
  assert.ok(!icons.includes('i-lucide-bar-chart-3'))
})

test('isHeaderLinkActive matches fixed paths by prefix and dynamic ones by fragment', () => {
  const chat = HEADER_LINKS.find(link => link.to === '/chat')!
  assert.equal(isHeaderLinkActive(chat, '/chat'), true)
  assert.equal(isHeaderLinkActive(chat, '/chat/42'), true)
  assert.equal(isHeaderLinkActive(chat, '/chatroom'), false)

  const liveAlarm = HEADER_LINKS.find(link => link.to === null)!
  assert.equal(isHeaderLinkActive(liveAlarm, '/ebeam/cd-sem/r3/live-alarm'), true)
  assert.equal(isHeaderLinkActive(liveAlarm, '/ebeam/cd-sem/r3'), false)
})

test('the info paths are exactly the fixed targets of the menus', () => {
  // Derived, not hand-maintained — this is what makes the two lists impossible to drift.
  assert.deepEqual(
    HEADER_INFO_PATHS,
    HEADER_LINKS.filter(link => link.to !== null).map(link => link.to)
  )
})

test('/chat is reachable from the header and keeps its tabs', () => {
  // The regression this list exists to prevent: /chat is reachable only from the header
  // menu, so losing the tabs there left no way back to the main pages.
  assert.ok(HEADER_LINKS.some(link => link.to === '/chat'))
  assert.equal(isHeaderInfoPath('/chat'), true)
})

test('/tool-roster is reached from the landing page, not the header', () => {
  assert.equal(HEADER_LINKS.some(link => link.to === '/tool-roster'), false)
  assert.equal(HEADER_INFO_PATHS.includes('/tool-roster'), false)
  assert.equal(isHeaderInfoPath('/tool-roster'), false)
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
