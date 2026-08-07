// Single source of truth for fab identity: how a fab name is canonicalized, compared,
// sorted, and turned into a URL segment — and which fab we use when none is remembered.
//
// Casing is the reason this module exists. The backend reports fab_name in whichever case
// its source DB stores it ('R3' from one, 'r3' from another), so a raw `===` between an
// API value and a stored one silently fails and empties a table. Every fab that enters the
// app is normalized to uppercase; every URL segment is lowercase; every comparison goes
// through sameFab.
//
// The fallback rule: if no fab is remembered — the store is still at its default, the user
// cleared the selection, or localStorage was empty on first visit — we use R3.

// Canonical form is uppercase, matching the fab_name shape used across the app (R3, M16B).
export const DEFAULT_FAB = 'R3'

// Reserved sentinel for "no fab selected". Never rendered in the sidebar, never allowed into
// a URL. Compared case-insensitively, so 'ALL' from any source is still the sentinel.
export const NO_FAB = 'all'

// Canonical uppercase form. Everything that enters from a URL, an API row, or localStorage
// goes through here before it is stored or compared.
export const normalizeFab = (fab: string | null | undefined): string =>
  (fab ?? '').trim().toUpperCase()

const NO_FAB_CANONICAL = NO_FAB.toUpperCase()

export const hasFab = (fab: string | null | undefined): boolean => {
  const normalized = normalizeFab(fab)
  return normalized !== '' && normalized !== NO_FAB_CANONICAL
}

// Case-insensitive equality — use this instead of `===` for anything that touches a
// backend-supplied fab_name.
export const sameFab = (a: string | null | undefined, b: string | null | undefined): boolean => {
  const left = normalizeFab(a)
  return left !== '' && left === normalizeFab(b)
}

// The remembered fab as a URL segment, or R3's when there is nothing to remember.
// Fab names are stored uppercase but routed lowercase.
export const fabSegment = (fab: string | null | undefined): string =>
  (hasFab(fab) ? normalizeFab(fab) : DEFAULT_FAB).toLowerCase()

// Sort: R fabs first (ascending), then M fabs (newest fac first — M16 before M11),
// with letter suffixes ascending within the same fac. Parses case-insensitively so a
// lowercase name cannot fall through to localeCompare and land in the wrong group.
const FAB_LABEL_PATTERN = /^([RM])(\d+)([A-Z]?)$/

export const sortFabNames = (a: string, b: string): number => {
  const parse = (label: string) => {
    const match = normalizeFab(label).match(FAB_LABEL_PATTERN)
    return match ? { prefix: match[1] as 'R' | 'M', num: Number(match[2]), suffix: match[3] ?? '' } : null
  }

  const pa = parse(a)
  const pb = parse(b)
  if (!pa || !pb) return a.localeCompare(b)

  if (pa.prefix !== pb.prefix) return pa.prefix === 'R' ? -1 : 1
  if (pa.num !== pb.num) return pa.prefix === 'R' ? pa.num - pb.num : pb.num - pa.num
  return pa.suffix.localeCompare(pb.suffix)
}

// The distinct fabs present in a set of rows, canonicalized so the same fab reported in two
// casings collapses to one entry. Rows with no fab name are skipped — a blank option is
// never a meaningful thing to pick.
export const extractFabNames = (rows: { fab_name: string }[]): string[] => {
  const names = new Set<string>()
  for (const row of rows) {
    const normalized = normalizeFab(row.fab_name)
    if (normalized !== '') names.add(normalized)
  }
  return Array.from(names).sort(sortFabNames)
}

// ---- 다중 FAB (Phase 1) ----
// 목록 불변식의 단일 소유자: 대문자 정규화, sentinel/공백 제거, 순서 보존 중복 제거.
export const canonicalFabList = (fabs: Iterable<string | null | undefined>): string[] => {
  const out: string[] = []
  for (const fab of fabs) {
    const normalized = normalizeFab(fab)
    if (normalized === '' || normalized === NO_FAB_CANONICAL) continue
    if (!out.includes(normalized)) out.push(normalized)
  }
  return out
}

// URL의 [fab] 세그먼트 → FAB 목록. 무효 세그먼트는 R3 하나로 강등되므로 항상 길이 ≥ 1.
export const parseFabSegment = (segment: string | string[] | null | undefined): string[] => {
  const raw = Array.isArray(segment) ? segment.join(',') : (segment ?? '')
  const fabs = canonicalFabList(raw.split(','))
  return fabs.length > 0 ? fabs : [DEFAULT_FAB]
}

// FAB 목록 → URL 세그먼트. 단일 fabSegment와 같은 규칙: 저장은 대문자, 라우팅은 소문자.
export const buildFabSegment = (fabs: readonly string[]): string => {
  const canonical = canonicalFabList(fabs)
  return (canonical.length > 0 ? canonical : [DEFAULT_FAB]).join(',').toLowerCase()
}

// 체크박스 토글. 마지막 남은 FAB 제거는 무시한다 — 선택이 비면 "아무 데이터도 없음"이
// 아니라 R3 fallback으로 점프해 버려, 사용자가 방금 한 행동과 화면이 어긋난다.
export const toggleFabInList = (fabs: readonly string[], fab: string): string[] => {
  const canonical = canonicalFabList(fabs)
  const target = normalizeFab(fab)
  if (!hasFab(target)) return canonical
  if (!canonical.includes(target)) return [...canonical, target]
  if (canonical.length === 1) return canonical
  return canonical.filter(f => f !== target)
}
