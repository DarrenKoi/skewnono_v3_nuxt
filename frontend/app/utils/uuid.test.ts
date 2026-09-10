import assert from 'node:assert/strict'
import test from 'node:test'

import { generateUuid } from './uuid.ts'

const CANONICAL_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

test('generateUuid returns a canonical lowercase UUID', () => {
  const id = generateUuid()
  assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/)
})

test('generateUuid produces distinct values', () => {
  const ids = new Set(Array.from({ length: 100 }, () => generateUuid()))
  assert.equal(ids.size, 100)
})

test('generateUuid works without crypto.randomUUID (plain-HTTP cloud)', (t) => {
  // The Phase 3 cloud serves over http://, where browsers expose
  // crypto.getRandomValues but NOT crypto.randomUUID. Simulate that context.
  const realCrypto = globalThis.crypto
  const insecureCrypto = {
    getRandomValues: realCrypto.getRandomValues.bind(realCrypto)
  } as Crypto
  Object.defineProperty(globalThis, 'crypto', { value: insecureCrypto, configurable: true })
  t.after(() => {
    Object.defineProperty(globalThis, 'crypto', { value: realCrypto, configurable: true })
  })

  const id = generateUuid()
  assert.match(id, CANONICAL_V4)
  assert.notEqual(id, generateUuid())
})
