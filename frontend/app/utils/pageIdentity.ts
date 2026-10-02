import { TOOL_TYPES, toolSlug, type ToolType } from './toolType.ts'

/** Page identity for usage beaconing — see
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  THE GOVERNING RULE: two paths produce the same identity if and only if the
 *  backend (backend/_logging/feature_map.py) gives them the same slug
 *  (`page_to_feature`) AND the same tool family (`page_to_family`). Finer than
 *  that double-counts one page; coarser silently loses a real page open.
 *  `__fixtures__/pageIdentityContract.json` is the shared table both sides are
 *  tested against.
 *
 *  The family half arrived 2026-10-02, when page opens began being counted
 *  per tool family. Before it, CD-SEM's Storage and HV-SEM's Storage were one
 *  identity, so moving between them was deduped as a filter change and the
 *  second family's page open was never reported.
 *
 *  The family is not a log field. A page open is POSTed to
 *  /api/page-view/<family> (`pageViewEndpoint`), so it rides in the log row's
 *  existing `path` and the index needed no change. The backend rejects a
 *  beacon whose URL disagrees with its page, which is why `pageFamily` is
 *  pinned to the fixture's family column.
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
// The page has no path segment of its own, so its identity has to be
// synthesized. Matches the backend's `tool_inventory` slug; the tool family is
// prefixed onto it like any other e-beam identity (`cdsem#tool-inventory`).
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
const OPS_PREFIXES = ['/activity', '/admin', '/settings', '/endpoints', '/identify', '/intro', '/notices']

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

/** The family an /ebeam tool segment names, as the backend spells it
 *  (`cd-sem` → `cdsem`), or null for a segment that is no registered tool. */
const ebeamFamily = (segment: string | undefined): string | null => {
  const toolType = segment?.toLowerCase()
  return (TOOL_TYPES as readonly string[]).includes(toolType ?? '')
    ? toolSlug(toolType as ToolType)
    : null
}

/** Which tool family a page belongs to — the backend's `page_to_family`.
 *  /ebeam/<tool>/… belongs to that tool, /afm… to AFM, everything else to none. */
export const pageFamily = (path: string): string | null => {
  const segments = (path.split('?')[0] ?? '').split('/').filter(Boolean)
  if (segments[0] === 'afm') return 'afm'
  if (segments[0] === 'ebeam') return ebeamFamily(segments[1])
  return null
}

/** Where a page open is reported, relative to the API base: the family's own
 *  beacon URL, or the plain one for a page that belongs to none. Mirrors the
 *  backend's `page_view_path`. */
export const pageViewEndpoint = (path: string): string => {
  const family = pageFamily(path)
  return family ? `/page-view/${family}` : '/page-view'
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
    // /ebeam/<tool> and /ebeam/<tool>/<fab> are the same page (the fab hub).
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

/** The identity of the PAGE alone, family aside — what `page_to_feature`'s
 *  slug partitions. `resolvePageIdentity` adds the family half. */
const resolvePage = (
  { path: canonical, ebeam }: Canonical,
  query: Record<string, unknown>
): string | null => {
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

export const resolvePageIdentity = (
  path: string,
  query: Record<string, unknown>
): string | null => {
  if (!path) return null
  if (isOpsPath(path)) return null

  const canonical = canonicalize(path)
  const page = resolvePage(canonical, query)
  if (page === null) return null
  // The same derivation the beacon URL uses (pageViewEndpoint), so the dedup
  // identity and the URL a page open is posted to cannot name different
  // families. Only /ebeam identities take the prefix: /afm's own path already
  // says AFM. `page` always starts with `/` or `#`, so the prefix cannot run
  // into it: `cdsem/storage`, `hvsem#tool-inventory`.
  const family = canonical.ebeam ? pageFamily(path) : null
  return family ? family + page : page
}

const isToolInventory = (identity: string | null): boolean =>
  identity !== null && identity.endsWith(TOOL_INVENTORY_PATH)

/** Decides which navigations are page OPENS worth a beacon. It remembers the
 *  previous page, so the plugin holds exactly one for the app's lifetime.
 *
 *  An unresolvable page (null identity) still ENDS the previous one, so it
 *  resets the memory rather than leaving it standing. Two cases produce null:
 *   - recipe-status before its tab lands: harmless to reset, since this step
 *     never had a beacon to suppress and the mount-time router.replace
 *     resolves within a tick, firing exactly once either way.
 *   - every other unresolvable path (chiefly `/`, the fab/tool picker):
 *     keeping the previous identity would make the NEXT visit to that same
 *     page look like a filter change and drop its beacon — and
 *     "home -> pick a fab -> a page" is exactly that loop. */
export const createPageViewTracker = () => {
  let previous: string | null = null
  return (path: string, query: Record<string, unknown>): boolean => {
    const identity = resolvePageIdentity(path, query)
    const before = previous
    previous = identity
    // Unchanged = a fab switch or a filter change, not a new page open.
    if (identity === null || identity === before) return false
    // 장비 상태 is where picking a tool LANDS: home's tool cards and the fab
    // redirect both go to /ebeam/<tool>/<fab>. Arriving with no ranked page
    // before it (from /, an ops page, or a fresh load) is a waypoint, not a
    // choice. From another ranked page it is a tab the user clicked, so it
    // counts. Excluding it outright, as / is, would rank a page people do
    // open on purpose as unused.
    //
    // Another family's 장비 상태 is not "a ranked page before it": going from
    // one landing to the next is picking a tool again. That case only exists
    // since the family joined the identity — before, the two were equal and
    // the unchanged-identity check above already dropped it.
    return !(isToolInventory(identity) && (before === null || isToolInventory(before)))
  }
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
