/**
 * Pure input handling for the self-identification form.
 *
 * Split out of the page because `npm test` runs `node --test` over pure
 * functions only — this repo has no component mounting harness, so logic left
 * inside a `.vue` file is verified by hand or not at all.
 */

/**
 * An employee number as the backend expects it.
 *
 * Inner spaces are removed because a copy-paste out of a directory listing or
 * a chat message routinely carries them, and the resulting lookup would miss
 * for a reason the user cannot see on screen.
 *
 * Case is deliberately left alone: X-prefixed ids are real member ids that
 * access control blocks downstream, and normalizing them here would turn a
 * clear "blocked" screen into a confusing "not found".
 */
export const normalizeEmpno = (raw: string): string => raw.replace(/\s+/g, '')

/**
 * The error to show, or null when the pair is worth sending.
 *
 * Only presence is checked. The authority on which employee numbers exist is
 * the `members` directory, and a client-side format rule would eventually
 * disagree with it — rejecting a real person on the strength of a guess made
 * here, with no way for them to argue. Names keep their inner spacing for the
 * same reason: the server compares against the directory without collapsing
 * it, so trimming here could only cause a mismatch.
 */
export const validateIdentityInput = (empno: string, empNm: string): string | null => {
  if (!normalizeEmpno(empno)) return '사번을 입력해 주세요'
  if (!empNm.trim()) return '이름을 입력해 주세요'
  return null
}
