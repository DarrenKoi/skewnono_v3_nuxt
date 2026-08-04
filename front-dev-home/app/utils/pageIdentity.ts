/** Page identity for usage beaconing — see
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  Identity granularity equals the backend's slug granularity — no finer, no coarser.
 *  The backend's authority is `_PAGE_RULES` in back_dev_home/_logging/feature_map.py.
 *  When adding a page to the backend, add a matching rule here: page identity must
 *  collapse at exactly the same granularity the backend does.
 *
 *  Almost every query param is state within a page (fab, ppid, filters) and
 *  must not re-fire the beacon. `tab` on recipe-status is the exception: that
 *  route is a shell over two genuinely different features. */

// Fab segments are `[fab]` route params, so the same page under two fabs has
// two paths. Matches fab_name shape, same as plugins/persist-fab.client.ts.
const FAB_SEGMENT = /^[RM]\d{1,2}[A-C]?$/i

const TAB_ROUTE = 'recipe-status'
const VALID_TABS = new Set(['tat', 'align', 'meas'])

// Ordered rules: longest/most specific first. Each rule is a path fragment
// (after fab stripping) that defines identity granularity. Paths that match
// a rule collapse into it; deeper paths under the same rule share its identity.
// Example: 'recipe-search' matches 'recipe-search', 'recipe-search/compare',
// 'recipe-search/lateral', etc., but 'recipe-search/meas-hist' is more specific
// and has its own rule, so it's tested first.
const IDENTITY_RULES = [
  // Specific sub-pages that have their own backend slugs (must come first)
  '/ebeam/cd-sem/recipe-search/meas-hist',
  '/ebeam/hv-sem/recipe-search/meas-hist',

  // Feature pages (collapse everything under them except those with their own rule)
  '/ebeam/cd-sem/recipe-search',
  '/ebeam/cd-sem/device-statistics',
  '/ebeam/cd-sem/recipe-status',
  '/ebeam/cd-sem/recipe-tat',
  '/ebeam/cd-sem/fail-issue',
  '/ebeam/cd-sem/storage',
  '/ebeam/cd-sem/hardware',
  '/ebeam/cd-sem/live-alarm',
  '/ebeam/cd-sem/skew-check',
  '/ebeam/cd-sem/pm-planning',

  '/ebeam/hv-sem/recipe-search',
  '/ebeam/hv-sem/device-statistics',
  '/ebeam/hv-sem/recipe-status',
  '/ebeam/hv-sem/recipe-tat',
  '/ebeam/hv-sem/fail-issue',
  '/ebeam/hv-sem/storage',
  '/ebeam/hv-sem/hardware',
  '/ebeam/hv-sem/live-alarm',
  '/ebeam/hv-sem/skew-check',

  // Standalone pages
  '/afm',
  '/msr-file',
  '/msr-files',
  '/msr-image',
  '/sem-list',
  '/meas-hist',
  '/tool-roster',
  '/mag-pixel',
  '/chat',
  '/'
]

const firstValue = (raw: unknown): string | null => {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value ? value : null
}

const canonicalPath = (path: string): string => {
  const segments = path.split('/')
  const filtered = segments.filter(segment => segment && !FAB_SEGMENT.test(segment))
  // Preserve leading slash (the split's first empty string is intentional)
  return '/' + filtered.join('/')
}

const collapseToIdentity = (canonical: string): string => {
  // Find the longest matching rule (tested in order)
  for (const rule of IDENTITY_RULES) {
    if (canonical === rule || canonical.startsWith(rule + '/')) {
      return rule
    }
  }
  // Fallback: if no rule matches, use the canonical path itself
  return canonical
}

export const resolvePageIdentity = (
  path: string,
  query: Record<string, unknown>
): string | null => {
  const canonical = canonicalPath(path)

  // recipe-status special case: per-tab identities, null until tab is resolved
  if (canonical.endsWith(TAB_ROUTE)) {
    const tab = firstValue(query.tab)
    if (!tab || !VALID_TABS.has(tab)) return null
    return `${canonical}?tab=${tab}`
  }

  // All other pages: collapse to their identity rule
  return collapseToIdentity(canonical)
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
