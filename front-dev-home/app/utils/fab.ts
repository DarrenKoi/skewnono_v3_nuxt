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

export const hasFab = (fab: string | null | undefined): boolean => {
  const normalized = normalizeFab(fab)
  return normalized !== '' && normalized !== normalizeFab(NO_FAB)
}

// Case-insensitive equality — use this instead of `===` for anything that touches a
// backend-supplied fab_name.
export const sameFab = (a: string | null | undefined, b: string | null | undefined): boolean => {
  const left = normalizeFab(a)
  return left !== '' && left === normalizeFab(b)
}

// The remembered fab in canonical form, or R3 when there is nothing to remember.
export const resolveFab = (fab: string | null | undefined): string =>
  hasFab(fab) ? normalizeFab(fab) : DEFAULT_FAB

// The same value as a URL segment. Fab names are stored uppercase but routed lowercase.
export const fabSegment = (fab: string | null | undefined): string =>
  resolveFab(fab).toLowerCase()

// Sort: R fabs first (ascending), then M fabs (newest fac first — M16 before M11),
// with letter suffixes ascending within the same fac. Parses case-insensitively so a
// lowercase name cannot fall through to localeCompare and land in the wrong group.
export const sortFabNames = (a: string, b: string): number => {
  const parse = (label: string) => {
    const match = normalizeFab(label).match(/^([RM])(\d+)([A-Z]?)$/)
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
