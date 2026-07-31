/**
 * Display rules for the header identity pill — pure so they can be tested
 * without mounting anything (`npm test` covers pure functions only).
 *
 * The states these encode come from the self-identification spec (§5, §11):
 * a *declared* identity is the only one with anything to undo (DELETE
 * /api/identify drops the declaration), and declared-but-unverified is the
 * only state that wears the 미검증 badge. A cookie identity is authoritative
 * rather than verified — a stronger thing — so it must never carry the badge,
 * and `verified: false` on it means nothing.
 */

import type { Identity } from '~/composables/useIdentity'

/** The name the header greets the caller by: the stored/directory name when
 * one exists, the raw id otherwise (`local-dev` at home, an empno whose
 * directory row is missing on the cloud). */
export function displayName(identity: Identity): string {
  const name = identity.member?.emp_nm?.trim()
  return name || identity.user_id
}

/** True only for a self-declared identity the directory could not confirm. */
export function isUnverifiedDeclaration(identity: Identity): boolean {
  return identity.identity_source === 'declared' && !identity.verified
}

/** Whether "본인이 아닙니다" applies: only a declaration can be dropped. */
export function canReleaseDeclaration(identity: Identity): boolean {
  return identity.identity_source === 'declared'
}
