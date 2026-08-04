/** Page identity for usage beaconing — see
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  Identity answers ONE question: "is this the same page as a moment ago?"
 *  It is not a feature slug. Slug vocabulary lives on the backend
 *  (`_logging/feature_map.py`) so the two can never drift apart.
 *
 *  Almost every query param is state within a page (fab, ppid, filters) and
 *  must not re-fire the beacon. `tab` on recipe-status is the exception: that
 *  route is a shell over two genuinely different features. */

// Fab segments are `[fab]` route params, so the same page under two fabs has
// two paths. Matches fab_name shape, same as plugins/persist-fab.client.ts.
const FAB_SEGMENT = /^[RM]\d{1,2}[A-C]?$/i

const TAB_ROUTE = 'recipe-status'
const VALID_TABS = new Set(['tat', 'align', 'meas'])

const firstValue = (raw: unknown): string | null => {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value ? value : null
}

const canonicalPath = (path: string): string =>
  path
    .split('/')
    .filter(segment => segment && !FAB_SEGMENT.test(segment))
    .join('/')

export const resolvePageIdentity = (
  path: string,
  query: Record<string, unknown>
): string | null => {
  const canonical = canonicalPath(path)
  if (!canonical.endsWith(TAB_ROUTE)) return canonical

  // No tab yet — RecipeStatusView's mount-time router.replace supplies one
  // within a tick, and that navigation is the one worth counting.
  const tab = firstValue(query.tab)
  if (!tab || !VALID_TABS.has(tab)) return null
  return `${canonical}?tab=${tab}`
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
