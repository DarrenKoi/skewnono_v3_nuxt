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
  'skew-check'
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
// depend on the URL fab — they ignore it (skewvoir is a placeholder) or manage their own
// fab via the navigation store + localStorage (device-statistics).
export const FABLESS_FEATURES = new Set<FeatureSlug>(['device-statistics', 'skewvoir'])

export const isFablessFeature = (feature: string): feature is FeatureSlug => {
  return FABLESS_FEATURES.has(feature as FeatureSlug)
}

export const matchFeatureFromPath = (path: string): FeatureSlug | '' => {
  const match = path.match(FEATURE_SLUG_REGEX)
  return (match?.[1] as FeatureSlug | undefined) ?? ''
}

// Top-level pages reached from the header's right-hand icon row. They sit outside the
// `/ebeam` tree but still show the feature tabs, because the icon is the only way in —
// without the tabs there is no way back to the main pages. Every static `to="/…"` in
// AppHeader.vue belongs here; features.test.ts fails if one is missing.
export const HEADER_INFO_PATHS = [
  '/intro',
  '/endpoints',
  '/mag-pixel',
  '/chat',
  '/activity',
  '/settings'
] as const

// Matches the page itself and anything nested under it, but never a longer sibling
// segment (`/chatroom` is not `/chat`).
export const isHeaderInfoPath = (path: string): boolean =>
  HEADER_INFO_PATHS.some(base => path === base || path.startsWith(`${base}/`))
