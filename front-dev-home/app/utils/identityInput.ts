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
 * Mirrors the server's bounds (`_auth/routes.py MAX_EMPNO_LEN/MAX_NAME_LEN`),
 * so an over-long paste fails here with the same verdict instead of a round
 * trip. The empno bound is a format fact (user-confirmed: real employee
 * numbers are under 10 characters — `2067928`, `x2363321`); the name bound
 * is transport-only.
 */
export const MAX_EMPNO_LEN = 9
export const MAX_NAME_LEN = 64

/**
 * The error to show, or null when the pair is worth sending.
 *
 * Presence and the length bounds are checked — nothing else. The authority
 * on which employee numbers exist is the `members` directory, and any finer
 * client-side format rule would eventually disagree with it — rejecting a
 * real person on the strength of a guess made here, with no way for them to
 * argue. Names keep their inner spacing for the same reason: the server
 * compares against the directory without collapsing it, so trimming here
 * could only cause a mismatch.
 */
export const validateIdentityInput = (empno: string, empNm: string): string | null => {
  if (!normalizeEmpno(empno)) return '사번을 입력해 주세요'
  if (!empNm.trim()) return '이름을 입력해 주세요'
  if (normalizeEmpno(empno).length > MAX_EMPNO_LEN) return '사번이 너무 깁니다'
  if (empNm.trim().length > MAX_NAME_LEN) return '이름이 너무 깁니다'
  return null
}
