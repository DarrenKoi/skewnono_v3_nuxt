import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyToolType } from './toolType.ts'

test('classifyToolType recognizes both VeritySEM prefixes case-insensitively', () => {
  for (const model of [
    'VERITYSEM_4',
    'VeritySEM_4',
    'veritysem_4',
    'VERITY_SEM_5',
    'Verity_SEM_5',
    'verity_sem_5'
  ]) {
    assert.equal(classifyToolType(model), 'verity-sem', model)
  }
})

test('classifyToolType keeps an unrelated model unclassified', () => {
  assert.equal(classifyToolType('ZZ9000'), null)
})
