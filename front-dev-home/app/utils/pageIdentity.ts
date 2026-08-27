/** Page identity for usage beaconing — see
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  THE GOVERNING RULE: two paths produce the same identity if and only if the
 *  backend's `page_to_feature` (back_dev_home/_logging/feature_map.py) maps them
 *  to the same slug. Finer than that double-counts one page; coarser silently
 *  loses a real page open. `__fixtures__/pageIdentityContract.json` is the
 *  shared table both sides are tested against.
 *
 *  The ONE approved exception: recipe-status ?tab=align and ?tab=meas share the
 *  backend slug `fail_issue`, but the product counts Align Fail and Meas Fail as
 *  separate opens. Fixture rows expressing that carry `finerThanSlug: true`.
 *  Nothing else may.
 *
 *  No slug strings live here — the backend owns that vocabulary. This table
 *  holds route fragments only, with one synthesized exception:
 *  TOOL_INVENTORY_PATH, which no real route ever produces (see its own
 *  comment below).
 *
 *  Almost every query param is state within a page (fab, ppid, filters) and
 *  must not re-fire the beacon. `tab` on recipe-status is the exception: that
 *  route is a shell over two genuinely different features. */

// Fab segments are `[fab]` route params, so the same page under two fabs has
// two paths. Matches fab_name shape, same as plugins/persist-fab.client.ts and
// the backend's _FAB_SEGMENT.
//
// A comma-separated list is a fab segment too — buildFabSegment joins the
// selected fabs, so a multi-fab session routes through /ebeam/<tool>/m14,r3/…
// Matching a single code only left the list in the canonical path, where no
// rule matches it, so every multi-fab page fell through to `landing` and shared
// ONE identity: the beacon fired for the first page of the session and deduped
// every page after it. The backend mislabelled the same paths `cdsem`.
const FAB_CODE = String.raw`[RM]\d{1,2}[A-C]?`
const FAB_SEGMENT = new RegExp(`^${FAB_CODE}(,${FAB_CODE})*$`, 'i')

const TAB_ROUTE = 'recipe-status'
const VALID_TABS = new Set(['tat', 'align', 'meas'])

// The canonical path for the fab-hub shape: /ebeam/<tool> and
// /ebeam/<tool>/<fab> with no page segment after them, which is
// [fab]/index.vue — EbeamToolInventoryView, 장비 상태.
//
// Unlike every other entry in IDENTITY_RULES this is NOT a route fragment.
// The four tool families share no path segment for this page, so the identity
// they must all collapse onto has to be synthesized. Matches the backend's
// `tool_inventory` slug.
//
// Deliberately spelled with a leading `#`, not `/`: a canonical path is always
// built as `'/' + segments.join('/')`, so no real route can ever produce a
// leading `#`. Spelling this as `/tool-inventory` would share a namespace with
// real route fragments — if a page ever appeared at that path, its canonical
// form would collide with this constant and silently merge into the fab hub,
// an agreement the contract fixture cannot catch because both halves would
// agree with each other.
const TOOL_INVENTORY_PATH = '#tool-inventory'

// Ops pages are logged but never ranked — the backend returns None for them.
// Mirrors _OPS_PAGE_PREFIXES.
const OPS_PREFIXES = ['/activity', '/admin', '/settings', '/endpoints', '/identify', '/intro']

// Ordered rules: longest/most specific first. Each entry is a path fragment of
// the canonical path (fab and, under /ebeam, the tool already removed). A path
// that equals a rule — or nests under it — takes that rule's identity, which is
// exactly how the backend's prefix tables collapse sub-pages.
const IDENTITY_RULES = [
  // Nested children whose own backend rule is more specific than their parent's.
  '/recipe-search/meas-hist',

  // E-beam pages.
  '/recipe-search',
  '/device-statistics',
  '/recipe-status',
  '/recipe-tat',
  '/fail-issue',
  '/storage',
  '/hardware',
  '/live-alarm',
  '/tttm',
  '/pm-planning',
  '/pm-tune',
  '/skewvoir',
  TOOL_INVENTORY_PATH,

  // Standalone pages.
  '/afm',
  '/msr-file',
  '/msr-files',
  '/msr-image',
  '/sem-list',
  '/tool-roster',
  '/mag-pixel',
  '/chat'
]

// Distinct routes the backend gives ONE slug, so they must share one identity.
// /tool-roster is the page; /sem-list is its historical alias. /pm-tune is
// pm-planning's path between 2026-08-17 and 2026-08-27: the backend kept the pm_planning
// slug for both, so the two must collapse here too.
const IDENTITY_ALIASES: Record<string, string> = {
  '/sem-list': '/tool-roster',
  '/pm-tune': '/pm-planning'
}

const firstValue = (raw: unknown): string | null => {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value ? value : null
}

interface Canonical {
  /** Path with fab (and, under /ebeam, the tool) removed. */
  path: string
  /** True for /ebeam routes. An unmapped e-beam page has no identity at all
   *  (the backend returns None for it) — there is deliberately no tool-family
   *  fallback, because "CD-SEM" is not a page and must never be ranked as one. */
  ebeam: boolean
}

const canonicalize = (rawPath: string): Canonical => {
  const segments = rawPath.split('/').filter(Boolean)

  if (segments[0] === 'ebeam') {
    // A bare /ebeam names no tool and is not a page.
    if (!segments[1]) return { path: '/ebeam', ebeam: true }
    const rest = segments.slice(2).filter(segment => !FAB_SEGMENT.test(segment))
    // /ebeam/<tool> and /ebeam/<tool>/<fab> are the same page (the fab hub);
    // the synthetic path is what all four tool families collapse onto.
    if (rest.length === 0) return { path: TOOL_INVENTORY_PATH, ebeam: true }
    return { path: '/' + rest.join('/'), ebeam: true }
  }

  return { path: '/' + segments.filter(segment => !FAB_SEGMENT.test(segment)).join('/'), ebeam: false }
}

const matchRule = (canonical: string): string | null => {
  for (const rule of IDENTITY_RULES) {
    if (canonical === rule || canonical.startsWith(rule + '/')) {
      return IDENTITY_ALIASES[rule] ?? rule
    }
  }
  return null
}

const isOpsPath = (path: string): boolean => {
  const clean = path.split('?')[0] ?? path
  const trimmed = clean.length > 1 ? clean.replace(/\/+$/, '') : clean
  return OPS_PREFIXES.some(prefix => trimmed === prefix || trimmed.startsWith(prefix + '/'))
}

export const resolvePageIdentity = (
  path: string,
  query: Record<string, unknown>
): string | null => {
  if (!path) return null
  if (isOpsPath(path)) return null

  const { path: canonical, ebeam } = canonicalize(path)

  // The hub at / is a waypoint everyone passes through, not a ranked feature.
  // The backend returns None for it, so the beacon must not fire either — and
  // a null here means report() returns before its $fetch, so no row is written
  // at all rather than a weight-0 one.
  if (canonical === '/') return null

  // recipe-status carries two features behind one route.
  if (canonical === `/${TAB_ROUTE}` || canonical.endsWith(`/${TAB_ROUTE}`)) {
    // No tab yet — RecipeStatusView's mount-time router.replace supplies one
    // within a tick, and that navigation is the one worth counting.
    const tab = firstValue(query.tab)
    if (!tab || !VALID_TABS.has(tab)) return null
    return `${canonical}?tab=${tab}`
  }

  const matched = matchRule(canonical)
  if (matched) return matched

  // Unmapped e-beam page: no identity, no beacon — exactly as the backend
  // returns None. The old tool-segment fallback is how CD-SEM kept reappearing
  // in the ranking. A page ranks once it has an IDENTITY_RULES entry (and a
  // matching backend rule); a standalone page still falls back to its own path.
  return ebeam ? null : canonical
}

export const buildPageViewPath = (
  path: string,
  query: Record<string, unknown>
): string => {
  const tab = firstValue(query.tab)
  if (path.includes(TAB_ROUTE) && tab && VALID_TABS.has(tab)) {
    return `${path}?tab=${tab}`
  }
  return path
}
