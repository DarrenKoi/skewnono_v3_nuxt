// Pure: deterministic identity-color assignment for multi-selected measurement
// sites, mirroring hardwareCompare.ts. A selected site's color IS its identity
// across the wafer map, radius plot, distribution and points table, so one
// source assigns it. Kept out of the composable — and free of cross-imports, so
// the caller passes the ramp (SK_SITE) — so it can be unit-tested under
// node --test. Selection order (the insertion order of the site-key list)
// drives the mapping; keys past the ramp get NO entry — consumers paint those a
// neutral tone. We cap rather than cycle because a repeated hue would be a false
// identity match (two different points sharing a color).

export function assignSiteColors(
  orderedSiteKeys: readonly string[],
  ramp: readonly string[]
): Record<string, string> {
  const out: Record<string, string> = {}
  orderedSiteKeys.forEach((key, i) => {
    if (i < ramp.length) out[key] = ramp[i]!
  })
  return out
}
