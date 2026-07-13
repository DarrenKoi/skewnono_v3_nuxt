// Single source of truth for the ebeam feature slugs that appear after the tool-type segment
// in a URL like `/ebeam/{toolType}/.../{feature}`. Used to detect the active feature and to
// strip / append feature segments when rewriting URLs.
export const FEATURE_SLUGS = [
  'storage',
  'recipe-search',
  // recipe-tat / fail-issue merged into recipe-status; the old slugs stay
  // listed so fab-switching on a stale URL still strips them before redirect.
  'recipe-status',
  'recipe-tat',
  'fail-issue',
  'hardware',
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
