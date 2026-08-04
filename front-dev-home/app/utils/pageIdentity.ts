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
 *  route is a shell over two genuinely different features (recipe_tat and fail_issue). */

// Fab segments are `[fab]` route params, so the same page under two fabs has
// two paths. Matches fab_name shape, same as plugins/persist-fab.client.ts.
const FAB_SEGMENT = /^[RM]\d{1,2}[A-C]?$/i

// Tool slugs (both normalize to same identity since backend treats them identically)
const TOOL_SEGMENT = /^(cd-sem|hv-sem)$/i

const TAB_ROUTE = 'recipe-status'
const VALID_TABS = new Set(['tat', 'align', 'meas'])

// recipe-status tabs map to two backend features: tat→recipe_tat, align/meas→fail_issue.
// Map tabs to canonical tab for identity: align and meas are the same feature.
const RECIPE_STATUS_TAB_MAP: Record<string, string> = {
  tat: 'tat',
  align: 'align',
  meas: 'align' // Same feature as align (fail_issue)
}

// Ordered rules: longest/most specific first. Each rule is a path fragment
// (after fab and tool stripping) that defines identity granularity. Paths that match
// a rule collapse into it; deeper paths under the same rule share its identity.
// Example: 'recipe-search' matches 'recipe-search', 'recipe-search/compare',
// 'recipe-search/lateral', etc., but 'recipe-search/meas-hist' is more specific
// and has its own rule, so it's tested first.
const IDENTITY_RULES = [
  // Specific sub-pages that have their own backend slugs (must come first)
  '/recipe-search/meas-hist',

  // Feature pages (collapse everything under them except those with their own rule)
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

// Paths that should normalize to a canonical identity because they map to the same backend slug
const IDENTITY_CANONICAL_MAP: Record<string, string> = {
  '/skewvoir': '/msr-file',
  '/msr-files': '/msr-file',
  '/msr-image': '/msr-file'
}

const firstValue = (raw: unknown): string | null => {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value ? value : null
}

const canonicalPath = (path: string): string => {
  // For ebeam pages: strip the /ebeam/ prefix (and later remove tool segment)
  // For standalone pages: keep as-is (minus fab segments)
  const segments = path.split('/')
  // Filter: remove empty segments, fab segments, and tool segments
  // Also skip the 'ebeam' segment itself
  const filtered = segments.filter(
    segment =>
      segment
      && segment !== 'ebeam'
      && !FAB_SEGMENT.test(segment)
      && !TOOL_SEGMENT.test(segment)
  )
  // Preserve leading slash
  return '/' + filtered.join('/')
}

const collapseToIdentity = (canonical: string): string => {
  // Find the longest matching rule (tested in order)
  for (const rule of IDENTITY_RULES) {
    if (canonical === rule || canonical.startsWith(rule + '/')) {
      // Check if this rule should normalize to a canonical identity
      const identity = IDENTITY_CANONICAL_MAP[rule] ?? rule
      return identity
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
    const canonicalTab = RECIPE_STATUS_TAB_MAP[tab] || tab
    return `${canonical}?tab=${canonicalTab}`
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
