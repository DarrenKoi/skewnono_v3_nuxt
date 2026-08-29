import type { ToolType } from './toolType'

// Single source of truth for the ebeam feature slugs that appear after the tool-type segment
// in a URL like `/ebeam/{toolType}/.../{feature}`. Used to detect the active feature and to
// strip / append feature segments when rewriting URLs.
export const FEATURE_SLUGS = [
  'storage',
  'recipe-search',
  // recipe-tat / fail-issue merged into recipe-status; their old routes
  // redirect via route middleware before any layout observes the path, so
  // the legacy slugs never appear in route.path and are not listed here.
  'recipe-status',
  'hardware',
  'live-alarm',
  'device-statistics',
  'skewvoir',
  'tttm',
  'pm-planning'
] as const

export type FeatureSlug = typeof FEATURE_SLUGS[number]

// Matches `/{slug}` immediately followed by either another `/` or the end of the path.
export const FEATURE_SLUG_REGEX = new RegExp(
  `/(${FEATURE_SLUGS.join('|')})(?:/|$)`
)

// Strip a trailing `/{slug}(/...)` suffix off a path — used when rewriting the feature segment.
export const FEATURE_SLUG_SUFFIX_REGEX = new RegExp(
  `/(${FEATURE_SLUGS.join('|')})(/.*)?$`
)

// Features that live at `/ebeam/{toolType}/{feature}` (no fab segment). These pages do not
// depend on the URL fab — they ignore it (skewvoir is a placeholder) or keep a fab of their
// own, separate from the navigation store (device-statistics, whose fab is a fac_id and so
// must never be written into the fab_name-grained store).
export const FABLESS_FEATURES = new Set<FeatureSlug>(['device-statistics', 'skewvoir'])

export const isFablessFeature = (feature: string): feature is FeatureSlug => {
  return FABLESS_FEATURES.has(feature as FeatureSlug)
}

// Features whose page holds exactly ONE fab. tttm and pm-planning argue from one
// fab's fleet (a skew matrix / an N배화 group is per-fab by construction), so a
// multi-fab URL has no meaning there: the sidebar's multi-select affordances are
// disabled on these pages and useFabRoute collapses a multi-fab segment to the
// primary. Disjoint from FABLESS_FEATURES by definition — a page must read the
// URL fab to pin it.
export const SINGLE_FAB_FEATURES = new Set<FeatureSlug>(['tttm', 'pm-planning'])

export const isSingleFabFeature = (feature: string): feature is FeatureSlug => {
  return SINGLE_FAB_FEATURES.has(feature as FeatureSlug)
}

// Which tool families each feature exists for — the ONE statement of the fact.
// useNavigation's enablement gate and LabMenu's link targets both derive from
// it. It used to live as an if-chain in useNavigation plus a hardcoded
// `scope === 'tttm' || scope === 'pm-planning'` in LabMenu, and forgetting the
// second copy when adding a cd-sem-only page would build menu links to URLs
// with no page behind them.
export const FEATURE_TOOL_TYPES: Record<FeatureSlug, readonly ToolType[]> = {
  'storage': ['cd-sem', 'hv-sem'],
  'recipe-search': ['cd-sem', 'hv-sem'],
  'recipe-status': ['cd-sem', 'hv-sem'],
  'hardware': ['cd-sem', 'hv-sem'],
  'live-alarm': ['cd-sem', 'hv-sem'],
  'device-statistics': ['cd-sem'],
  'skewvoir': ['cd-sem', 'hv-sem'],
  'tttm': ['cd-sem'],
  'pm-planning': ['cd-sem']
}

export const featureSupportsToolType = (feature: string, toolType: ToolType): boolean =>
  FEATURE_TOOL_TYPES[feature as FeatureSlug]?.includes(toolType) ?? false

export const matchFeatureFromPath = (path: string): FeatureSlug | '' => {
  const match = path.match(FEATURE_SLUG_REGEX)
  return (match?.[1] as FeatureSlug | undefined) ?? ''
}

/**
 * Which FEATURE TAB is highlighted for a path — `'index'` is 장비 상태, and
 * null means "not an ebeam page, so no tab at all".
 *
 * Derived from FEATURE_SLUGS rather than matched by its own if-chain. It WAS
 * such a chain, inside FeatureTabs.vue, and it drifted: `/pm-planning` was
 * never added to it, so it fell through to the `'index'` default and lit
 * 장비 상태 while the user was on a 실험실 page (fixed 2026-08-30). Any slug
 * added here in future is recognised by construction — which is the actual
 * fix, the missing branch being only the symptom.
 *
 * 장비 상태 is the fallback because the fab landing page has no slug of its
 * own; `storage` joins it because 스토리지 is a SUB-TAB of 장비 상태
 * (EbeamEquipmentStatusSubTabs), so the parent tab staying lit there is right.
 */
export const activeFeatureTab = (path: string): FeatureSlug | 'index' | null => {
  if (!(path === '/ebeam' || path.startsWith('/ebeam/'))) return null
  const feature = matchFeatureFromPath(path)
  return feature === '' || feature === 'storage' ? 'index' : feature
}
