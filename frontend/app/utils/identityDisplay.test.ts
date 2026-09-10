import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import type { Identity } from '../composables/useIdentity.ts'
import { canReleaseDeclaration, displayName, isUnverifiedDeclaration } from './identityDisplay.ts'

const identity = (overrides: Partial<Identity>): Identity => ({
  user_id: '2067928',
  identity_source: 'cookie',
  is_admin: false,
  verified: false,
  member: null,
  ...overrides
})

const member = (emp_nm: string | null) => ({
  empno: '2067928',
  emp_nm,
  dept_nm: null,
  organ_cd: null,
  upper_organ_nm: null
})

describe('displayName', () => {
  it('prefers the stored name over the raw id', () => {
    assert.equal(displayName(identity({ member: member('고대영') })), '고대영')
  })

  it('falls back to the id when the directory has no row', () => {
    assert.equal(displayName(identity({ member: null })), '2067928')
  })

  it('falls back when the row exists but carries no name', () => {
    // A cloud empno whose members row lacks emp_nm — the directory returns
    // the complete Member shape with nulls rather than erroring.
    assert.equal(displayName(identity({ member: member(null) })), '2067928')
    assert.equal(displayName(identity({ member: member('   ') })), '2067928')
  })
})

describe('isUnverifiedDeclaration', () => {
  it('is true only for declared-and-not-verified', () => {
    assert.equal(
      isUnverifiedDeclaration(identity({ identity_source: 'declared', verified: false })),
      true
    )
  })

  it('is false for a verified declaration', () => {
    assert.equal(
      isUnverifiedDeclaration(identity({ identity_source: 'declared', verified: true })),
      false
    )
  })

  it('never marks a cookie identity, whose verified flag means nothing', () => {
    // The backend sends verified: false for cookie callers; the cookie is
    // authoritative, so badging it 미검증 would be false and alarming.
    assert.equal(
      isUnverifiedDeclaration(identity({ identity_source: 'cookie', verified: false })),
      false
    )
  })
})

describe('canReleaseDeclaration', () => {
  it('only a declaration can be dropped', () => {
    assert.equal(canReleaseDeclaration(identity({ identity_source: 'declared' })), true)
    for (const source of ['cookie', 'local', 'token', 'anonymous'] as const) {
      assert.equal(canReleaseDeclaration(identity({ identity_source: source })), false)
    }
  })
})
