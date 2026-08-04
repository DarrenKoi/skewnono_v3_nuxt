// Picking the data point a reader meant when they clicked near it.
//
// ECharts only fires a series 'click' on a hit against the rendered element, so
// with `onClick` alone the target is exactly as wide as the symbol — 7px on the
// correlation scatter, 5px on the sequence trend. Readers miss, nothing
// happens, and the chart feels broken rather than precise.
//
// Pairing `onGridClick` with these helpers makes the whole plot area the
// target: the click lands wherever it lands, and the nearest point wins.

import type { GridClickDetail } from '~/composables/useEchart'

// How far a click may sit from a point and still select it. Beyond this the
// reader was not aiming at anything — on a wafer map, a click in the empty
// corner outside the wafer should select nothing rather than snap to whichever
// edge die happens to be closest.
const DEFAULT_MAX_DISTANCE_PX = 44

export interface NearestOptions {
  // Override the pick radius, in screen pixels. Charts whose points are packed
  // tighter than the default can afford a smaller one.
  maxDistancePx?: number
  // Ignore the y axis and pick on x alone. Right for a trend read left-to-right
  // (a time series with one point per timestamp), where the reader means "that
  // moment" and the vertical position of the cursor carries no intent.
  xOnly?: boolean
}

export interface NearestCandidate<T> {
  x: number
  y: number
  item: T
}

// Returns the candidate nearest the click in SCREEN space, or null when the
// closest one is further than the pick radius. Screen space is what matters:
// x and y hold different units (nm against seconds), so a raw data-space
// distance would silently weigh whichever axis has the larger numbers.
export const nearestPoint = <T>(
  candidates: readonly NearestCandidate<T>[],
  detail: GridClickDetail,
  options: NearestOptions = {}
): T | null => {
  const maxDistance = options.maxDistancePx ?? DEFAULT_MAX_DISTANCE_PX
  let best: { item: T, distance: number } | null = null

  for (const candidate of candidates) {
    if (!Number.isFinite(candidate.x)) continue
    const dx = (candidate.x - detail.x) / detail.dataPerPixelX
    const dy = options.xOnly || !Number.isFinite(candidate.y)
      ? 0
      : (candidate.y - detail.y) / detail.dataPerPixelY
    const distance = Math.hypot(dx, dy)
    if (!best || distance < best.distance) best = { item: candidate.item, distance }
  }

  if (!best || best.distance > maxDistance) return null
  return best.item
}

// The category-axis case: `x` arrives as a fractional position between category
// indices, so the nearest point is just the rounded index. Returns null when
// the click rounds outside the data — clicking the padding past the last
// category should not select the last point.
export const nearestIndex = (x: number, length: number): number | null => {
  if (!Number.isFinite(x) || length <= 0) return null
  const index = Math.round(x)
  if (index < 0 || index >= length) return null
  return index
}
