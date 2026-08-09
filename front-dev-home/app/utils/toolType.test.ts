import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyToolType, toolSlug, TOOL_TYPES, SEM_TOOL_TYPES } from './toolType.ts'

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
  assert.ok(!TOOL_TYPES.includes('verity-sem' as never))
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
