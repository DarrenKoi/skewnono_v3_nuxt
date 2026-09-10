import { test } from 'node:test'
import assert from 'node:assert/strict'
import { storageUsageTier } from './storageUsage.ts'

test('storageUsageTier applies the healthy, warning, and critical boundaries', () => {
  assert.equal(storageUsageTier(89), 'healthy')
  assert.equal(storageUsageTier(90), 'warning')
  assert.equal(storageUsageTier(97), 'warning')
  assert.equal(storageUsageTier(98), 'critical')
})
