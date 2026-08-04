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
 *  holds route fragments only.
 *
 *  Almost every query param is state within a page (fab, ppid, filters) and
 *  must not re-fire the beacon. `tab` on recipe-status is the exception: that
 *  route is a shell over two genuinely different features. */

// Fab segments are `[fab]` route params, so the same page under two fabs has
// two paths. Matches fab_name shape, same as plugins/persist-fab.client.ts and
// the backend's _FAB_SEGMENT.
const FAB_SEGMENT = /^[RM]\d{1,2}[A-C]?$/i

const TAB_ROUTE = 'recipe-status'
const VALID_TABS = new Set(['tat', 'align', 'meas'])

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
  '/skew-check',
  '/pm-planning',
  '/skewvoir',

  // Standalone pages.
  '/afm',
  '/msr-file',
  '/msr-files',
  '/msr-image',
  '/sem-list',
  '/tool-roster',
  '/mag-pixel',
  '/chat',
  '/'
]

// Distinct routes the backend gives ONE slug, so they must share one identity.
// /tool-roster is the page; /sem-list is its historical alias.
const IDENTITY_ALIASES: Record<string, string> = {
  '/sem-list': '/tool-roster'
}

const firstValue = (raw: unknown): string | null => {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value ? value : null
}

interface Canonical {
  /** Path with fab (and, under /ebeam, the tool) removed. */
  path: string
  /** For /ebeam routes, the tool landing page — the identity an unmapped
   *  e-beam page falls back to, matching the backend's `parts[1]` fallback.
   *  Non-empty so the four tool landings never collapse into each other. */
  landing: string | null
}

const canonicalize = (rawPath: string): Canonical => {
  const segments = rawPath.split('/').filter(Boolean)

  if (segments[0] === 'ebeam') {
    const tool = segments[1]
    if (!tool) return { path: '/ebeam', landing: '/ebeam' }
    const landing = `/ebeam/${tool}`
    const rest = segments.slice(2).filter(segment => !FAB_SEGMENT.test(segment))
    // /ebeam/<tool> and /ebeam/<tool>/<fab> are real landing pages; an empty
    // remainder must not become the empty path they would all share.
    if (rest.length === 0) return { path: landing, landing }
    return { path: '/' + rest.join('/'), landing }
  }

  return { path: '/' + segments.filter(segment => !FAB_SEGMENT.test(segment)).join('/'), landing: null }
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

  const { path: canonical, landing } = canonicalize(path)

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

  // Unmapped e-beam page: group by tool, exactly as the backend does.
  return landing ?? canonical
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
