// Pure: turn the skewvoir search-bar text into structured query fields.
//
// The parser lives client-side (not in Flask) so the backend has a single
// structured input contract, and so detection can lean on the facets response
// — a token that *is* a known eqp_id needs no prefix regex to guess at.
// See docs/superpowers/specs/2026-07-14-skewvoir-search-design.md §4.

export interface ParsedQuery {
  eq: string[]
  lot: string[]
  recipe: string[]
  msr: string[]
  // Always normalized to YYYY-MM-DD.
  date: string[]
  // Tokens that matched no field — surfaced in the UI so a typo is
  // distinguishable from a genuine no-hit.
  unknown: string[]
}

// Real values from the facets endpoint. Optional: search must not block on
// facets loading, so the parser degrades to shape rules alone without them.
export interface KnownValues {
  eq: string[]
  recipe: string[]
}

export const PARSED_FIELDS = ['eq', 'lot', 'recipe', 'msr', 'date', 'unknown'] as const

type ParsedField = typeof PARSED_FIELDS[number]

const SEPARATORS = /[\s,;]+/
const PREFIXED = /^(lot|recipe|eq|msr|date):(.*)$/i
// 20260315_CNT_CONTACT_CHECK_..._6LD257421_ECXDX925 — recipe names contain
// underscores too, so the leading 8-digit date is what makes an msr an msr.
const MSR = /^\d{8}_.+_.+_.+$/
const DATE_DASHED = /^(\d{4})-(\d{2})-(\d{2})$/
const DATE_COMPACT = /^(\d{4})(\d{2})(\d{2})$/
// 6LD257421 (3 alnum + 6 digits), RKPB240012 (4 alnum + 6 digits).
const LOT = /^[A-Z0-9]{3,4}\d{6}$/i

const emptyQuery = (): ParsedQuery => ({ eq: [], lot: [], recipe: [], msr: [], date: [], unknown: [] })

// '20260510' | '2026-05-10' -> '2026-05-10'. null if neither.
const normalizeDate = (token: string): string | null => {
  const m = DATE_DASHED.exec(token) ?? DATE_COMPACT.exec(token)
  return m ? `${m[1]}-${m[2]}-${m[3]}` : null
}

// A recipe facet value is 'CNT/CNT_CONTACT_CHECK_001'. Users type either the
// full name, the bare recipe name, or a fragment of either.
const matchesKnownRecipe = (token: string, known: string[], exact: boolean): boolean => {
  const t = token.toLowerCase()
  return known.some((full) => {
    const f = full.toLowerCase()
    const bare = f.includes('/') ? f.slice(f.indexOf('/') + 1) : f
    return exact ? f === t || bare === t : f.includes(t)
  })
}

const classify = (token: string, known?: KnownValues): { field: ParsedField, value: string } => {
  const prefixed = PREFIXED.exec(token)
  if (prefixed) {
    const field = prefixed[1]!.toLowerCase() as 'lot' | 'recipe' | 'eq' | 'msr' | 'date'
    const raw = prefixed[2]!
    if (field === 'date') {
      const iso = normalizeDate(raw)
      return iso ? { field: 'date', value: iso } : { field: 'unknown', value: raw }
    }
    return { field, value: raw }
  }

  const iso = normalizeDate(token)
  if (iso) return { field: 'date', value: iso }

  if (MSR.test(token)) return { field: 'msr', value: token }

  // Case-insensitive: the backend upper-cases both sides of the eq compare
  // (see back_dev_home/meas_hist/data.py), so 'ecdx625' must classify the
  // same as 'ECDX625' — otherwise it silently falls through to 'unknown'
  // and the token is dropped from the request instead of matched.
  if (known && known.eq.some(v => v.toLowerCase() === token.toLowerCase())) {
    return { field: 'eq', value: token }
  }

  if (known && matchesKnownRecipe(token, known.recipe, true)) {
    return { field: 'recipe', value: token }
  }

  if (LOT.test(token)) return { field: 'lot', value: token }

  if (known) {
    return matchesKnownRecipe(token, known.recipe, false)
      ? { field: 'recipe', value: token }
      : { field: 'unknown', value: token }
  }

  // No facets yet — assume a recipe fragment rather than crying "unknown" at
  // something we simply cannot check.
  return { field: 'recipe', value: token }
}

export const parseMeasHistQuery = (text: string, known?: KnownValues): ParsedQuery => {
  const parsed = emptyQuery()
  const tokens = text.trim().split(SEPARATORS).filter(Boolean)

  for (const token of tokens) {
    const { field, value } = classify(token, known)
    if (!value) continue
    const bucket = parsed[field]
    if (!bucket.includes(value)) bucket.push(value)
  }

  return parsed
}

// Drop one token from the raw text (used by the × on a parsed chip). Matches
// the bare token and any `field:token` form, and re-joins on single spaces so
// the remaining text stays well-formed.
//
// Date is the only field whose parsed/displayed value differs from the raw
// token typed (`20260510` -> `2026-05-10`), so a chip's × passes the
// NORMALIZED value while the raw text still holds the compact/dashed form.
// A plain string compare misses that token entirely, so also compare via
// normalizeDate (reusing the same normalizer parseMeasHistQuery uses) rather
// than duplicating the date regexes here.
export const removeToken = (text: string, token: string): string =>
  text
    .trim()
    .split(SEPARATORS)
    .filter(Boolean)
    .filter((raw) => {
      const prefixed = PREFIXED.exec(raw)
      const bare = prefixed ? prefixed[2]! : raw
      if (bare.toLowerCase() === token.toLowerCase()) return false
      return normalizeDate(bare) !== token
    })
    .join(' ')

// Resolve the effective from/to for a meas_hist search request.
//
// Precedence: a `date:` token typed in the search bar WINS over the 기간
// dropdown — the user just typed it, and the spec (§6.3) requires the two
// to act as ONE parameter with one visible source of truth rather than two
// competing inputs. The dropdown only applies when there is no date token;
// the default retention-window bounds apply when neither is set. The 기간
// chip that FilterBar renders must be a projection of this same result, not
// an independently-derived value, or the two can show different ranges
// again.
export const resolveDateRange = (
  dateTokens: string[],
  filterFrom: string,
  filterTo: string,
  defaultStart: string,
  defaultEnd: string
): { start: string, end: string } => {
  const sorted = [...dateTokens].sort()
  return {
    start: sorted[0] || filterFrom || defaultStart,
    end: sorted[sorted.length - 1] || filterTo || defaultEnd
  }
}
