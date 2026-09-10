import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyToolType, toolSlug, TOOL_TYPES, SEM_TOOL_TYPES, otherSemFamily, hasStorageView } from './toolType.ts'

test('classifyToolType recognizes both VeritySEM prefixes case-insensitively', () => {
  for (const model of [
    'VERITYSEM_4',
    'VeritySEM_4',
    'veritysem_4',
    'VERITY_SEM_5',
    'Verity_SEM_5',
    'verity_sem_5'
  ]) {
    assert.equal(classifyToolType(model), 'veritysem', model)
  }
})

test('classifyToolType keeps an unrelated model unclassified', () => {
  assert.equal(classifyToolType('ZZ9000'), null)
})

test('AMAT tool types carry no hyphen', () => {
  assert.equal(classifyToolType('PROVISION_10'), 'provision')
  assert.ok(TOOL_TYPES.includes('veritysem'))
  // Regression guard: TOOL_TYPES is the source ToolType is derived from, so a
  // future edit that reintroduces the old hyphenated literal here widens
  // ToolType right along with it and the compiler says nothing — only a
  // runtime check on the array's contents catches that.
  assert.equal((TOOL_TYPES as readonly string[]).indexOf('verity-sem'), -1)
})

test('toolSlug maps every tool type to its backend slug', () => {
  assert.equal(toolSlug('cd-sem'), 'cdsem')
  assert.equal(toolSlug('hv-sem'), 'hvsem')
  assert.equal(toolSlug('veritysem'), 'veritysem')
  assert.equal(toolSlug('provision'), 'provision')
})

test('SEM_TOOL_TYPES names the CD/HV-only scope explicitly', () => {
  assert.deepEqual([...SEM_TOOL_TYPES], ['cd-sem', 'hv-sem'])
})

test('otherSemFamily pairs CD-SEM and HV-SEM', () => {
  assert.equal(otherSemFamily('cd-sem'), 'hv-sem')
  assert.equal(otherSemFamily('hv-sem'), 'cd-sem')
})

test('otherSemFamily has no answer outside the SEM pair', () => {
  // 삼항으로 짜면 veritysem 이 조용히 cd-sem 이 되어 엉뚱한 계열을 붙인다.
  assert.equal(otherSemFamily('veritysem'), null)
  assert.equal(otherSemFamily('provision'), null)
})

test('hasStorageView is true only where a storage route exists', () => {
  assert.equal(hasStorageView('cd-sem'), true)
  assert.equal(hasStorageView('hv-sem'), true)
  // pages/ebeam/{veritysem,provision}/[fab]/ 에는 index.vue 뿐입니다. true 를
  // 돌려주면 장비 상태 서브탭이 없는 라우트로 링크를 겁니다.
  assert.equal(hasStorageView('veritysem'), false)
  assert.equal(hasStorageView('provision'), false)
})

test('hasStorageView covers exactly the CD/HV scope', () => {
  // 새 계열에 스토리지 화면을 붙이는 날 SEM_TOOL_TYPES 도 같이 넓히라는 뜻입니다.
  // 한쪽만 손대면 링크와 라우트가 다시 어긋납니다.
  assert.deepEqual(TOOL_TYPES.filter(hasStorageView), [...SEM_TOOL_TYPES])
})
