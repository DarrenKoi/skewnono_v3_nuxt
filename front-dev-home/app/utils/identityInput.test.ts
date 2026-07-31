import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { normalizeEmpno, validateIdentityInput } from './identityInput.ts'

describe('normalizeEmpno', () => {
  it('trims surrounding whitespace', () => {
    assert.equal(normalizeEmpno('  2067928 '), '2067928')
  })

  it('strips inner spaces a copy-paste carries', () => {
    // Pasting out of a directory or a chat message routinely brings these
    // along, and the lookup would then miss for a reason invisible on screen.
    assert.equal(normalizeEmpno('206 7928'), '2067928')
  })

  it('leaves an X-prefixed id intact', () => {
    // X-prefixed ids are real member ids that access control blocks later.
    // Mangling one here would turn a clear "blocked" screen into a confusing
    // "not found".
    assert.equal(normalizeEmpno(' X1234567 '), 'X1234567')
  })

  it('does not change the case', () => {
    assert.equal(normalizeEmpno('x1234567'), 'x1234567')
  })
})

describe('validateIdentityInput', () => {
  it('accepts an ordinary pair', () => {
    assert.equal(validateIdentityInput('2067928', '고대영'), null)
  })

  it('rejects an empty employee number', () => {
    assert.match(validateIdentityInput('', '고대영') ?? '', /사번/)
  })

  it('rejects a whitespace-only employee number', () => {
    assert.match(validateIdentityInput('   ', '고대영') ?? '', /사번/)
  })

  it('rejects an empty name', () => {
    assert.match(validateIdentityInput('2067928', '  ') ?? '', /이름/)
  })

  it('reports the employee number first when both are empty', () => {
    // The form shows one error line, and the employee number is the field
    // filled first — pointing at the name would send the user to the wrong box.
    assert.match(validateIdentityInput('', '') ?? '', /사번/)
  })

  it('accepts a name with an inner space', () => {
    // Names are compared against the directory server-side, which does not
    // collapse inner spacing. Rejecting it here would block a legitimate name
    // before it ever got the chance to match.
    assert.equal(validateIdentityInput('2067928', '고 대영'), null)
  })
})

describe('validateIdentityInput length bounds', () => {
  it('accepts the real empno shapes', () => {
    // user-confirmed formats: 7 digits, or an X/x prefix plus digits.
    assert.equal(validateIdentityInput('2067928', '고대영'), null)
    assert.equal(validateIdentityInput('x2363321', '김철수'), null)
  })

  it('refuses an over-long empno with the server message', () => {
    assert.equal(validateIdentityInput('9'.repeat(10), '김철수'), '사번이 너무 깁니다')
  })

  it('refuses an over-long name with the server message', () => {
    assert.equal(validateIdentityInput('2067928', '김'.repeat(65)), '이름이 너무 깁니다')
  })

  it('measures the empno after space removal, as the server will receive it', () => {
    // 9 digits + a space: what is SENT is 9 chars, so it must pass.
    const spaced = '9'.repeat(4) + ' ' + '9'.repeat(5)
    assert.equal(validateIdentityInput(spaced, '김철수'), null)
  })

  it('accepts exactly the bounds', () => {
    assert.equal(validateIdentityInput('9'.repeat(9), '김'.repeat(64)), null)
  })
})
