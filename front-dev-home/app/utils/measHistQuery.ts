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
  // Uncategorized tokens. The backend searches each term as a
  // case-insensitive substring across the fixed searchable-field allowlist.
  q: string[]
  // Tokens that matched no field — surfaced in the UI so a typo is
  // distinguishable from a genuine no-hit.
  unknown: string[]
}

// Real values from the facets endpoint. Optional: search must not block on
// facets loading, so the parser degrades to shape rules alone without them.
//
// No `recipe` list: the office index carries hundreds of recipes, and
// aggregating them all server-side just to recognize search-bar tokens is
// exactly the cost the RECIPE dropdown's removal was meant to avoid. Instead,
// any token that survives every other classification rule falls through to
// cross-field `q` (see classify()'s final branch). That keeps the parser's
// promise that no typed token is silently dropped while also allowing partial
// equipment ids such as `ECXDX` to find `ECXDX925`.
export interface KnownValues {
  eq: string[]
}

export const PARSED_FIELDS = ['eq', 'lot', 'recipe', 'msr', 'date', 'q', 'unknown'] as const

type ParsedField = typeof PARSED_FIELDS[number]

const SEPARATORS = /[\s,;]+/
const PREFIXED = /^(lot|recipe|eq|msr|date|q):(.*)$/i
// 20260315_CNT_CONTACT_CHECK_..._6LD257421_ECXDX925 — recipe names contain
// underscores too, so the leading 8-digit date is what makes an msr an msr.
const MSR = /^\d{8}_.+_.+_.+$/
const DATE_DASHED = /^(\d{4})-(\d{2})-(\d{2})$/
const DATE_COMPACT = /^(\d{4})(\d{2})(\d{2})$/
// 6LD257421 (3 alnum + 6 digits), RKPB240012 (4 alnum + 6 digits). Spec §4.2
// widens the tail to 6-8 digits — the office index carries lot ids longer
// than the mock's uniformly-6-digit ones, and a 7-8 digit lot id must not
// fall through to cross-field `q`. Eq ids top out at 8 total
// chars (prefix + 3 digits, see back_dev_home/sem_list/providers/mock.py),
// below this pattern's 9-char minimum (3+6), so widening cannot swallow one.
const LOT = /^[A-Z0-9]{3,4}\d{6,8}$/i

const emptyQuery = (): ParsedQuery => ({ eq: [], lot: [], recipe: [], msr: [], date: [], q: [], unknown: [] })

// '20260510' | '2026-05-10' -> '2026-05-10'. null if neither shape matches,
// OR if the shape matches but the calendar date isn't real (2026-13-45,
// 2026-02-30, 99999999). A digit-shape-only check would let those through as
// `date`, and an invalid `from`/`to` bound silently widens the backend's
// query to the full retention window (Fix 1) — the worst direction of
// failure for this feature. Round-trip through Date.UTC and confirm the
// components come back unchanged; JS Date normalizes overflow (month 13
// rolls into the next year, day 45 rolls past month end) instead of
// rejecting it, so a component mismatch after the round trip is exactly the
// signal an invalid calendar date leaves behind. Date.UTC on the token's own
// explicit y/m/d is not wall-clock "now" — no violation of the no-wall-clock
// rule.
const normalizeDate = (token: string): string | null => {
  const m = DATE_DASHED.exec(token) ?? DATE_COMPACT.exec(token)
  if (!m) return null

  const year = Number(m[1])
  const month = Number(m[2])
  const day = Number(m[3])
  const dt = new Date(Date.UTC(year, month - 1, day))
  const roundTrips = dt.getUTCFullYear() === year
    && dt.getUTCMonth() === month - 1
    && dt.getUTCDate() === day
  if (!roundTrips) return null

  return `${m[1]}-${m[2]}-${m[3]}`
}

const classify = (token: string, known?: KnownValues): { field: ParsedField, value: string } => {
  const prefixed = PREFIXED.exec(token)
  if (prefixed) {
    const field = prefixed[1]!.toLowerCase() as 'lot' | 'recipe' | 'eq' | 'msr' | 'date' | 'q'
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
  // same as 'ECDX625'. If facets are not loaded, the token safely falls
  // through to cross-field `q` instead of being dropped.
  if (known && known.eq.some(v => v.toLowerCase() === token.toLowerCase())) {
    return { field: 'eq', value: token }
  }

  if (LOT.test(token)) return { field: 'lot', value: token }

  // Every other shape rule missed. Search it across every allowed field rather
  // than guessing `recipe`: a prefix such as ECXDX is useful even though it is
  // not an exact equipment facet value. A genuine typo still returns zero rows
  // instead of being dropped and silently widening the query to everything.
  // `unknown` is reserved for a malformed `field:` prefix (e.g.
  // `date:notadate`) — see the prefixed-date branch above.
  return { field: 'q', value: token }
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

// Strip every parsed date token out of the raw text — the pure step a 기간
// dropdown edit performs before it overwrites filters.from/to, so a date
// token typed in the search bar can't keep winning over the freshly-picked
// range (see resolveDateRange's precedence doc comment / spec §6.3).
// Extracted out of useMeasHistSearch's setDateRange so it's a plain function
// this repo's node --test suite can call directly — a test that only
// re-implements removeToken/resolveDateRange inline exercises those
// functions, not the composable's actual token-strip step, and would keep
// passing even if that step were deleted from setDateRange.
export const stripDateTokens = (text: string, dateTokens: string[]): string =>
  dateTokens.reduce((acc, token) => removeToken(acc, token), text)

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
