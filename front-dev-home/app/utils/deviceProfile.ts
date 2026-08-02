// Per-device measurement profile (D22) — the 과다 측정 signal that used to live on
// its own /device-statistics/profile page. It now rides along in the comparison
// page's Lot 요약 table, because both surfaces are the same grain (one row per
// device) and the standalone page duplicated every other column.
//
// Deliberately bucket-independent: the outlier baseline is every point_count the
// device measures, so switching the summary bucket must NOT move the median. A
// bucket-scoped baseline would make "이 디바이스는 과다 측정인가" depend on which
// step filter the user happens to be looking at.
// Value import carries the explicit .ts so `node --test` resolves it without a
// bundler (see lotHealth.ts) — type-only imports are erased and don't need it.
import { detectDeviceOutliers, type DeviceOutlierResult } from './outlierDetect.ts'
import type { RecipeInput } from './ruleEngine'

export interface DeviceProfile {
  /** Median point_count across every parameter the device measures. */
  point_median: number
  /** Parameters whose point_count exceeds median × multiplier. */
  outlier_count: number
}

/** Group flat recipe rows by device. Exported so the drill-down can reuse it. */
export const groupRecipesByLot = (recipes: RecipeInput[]): Map<string, RecipeInput[]> => {
  const map = new Map<string, RecipeInput[]>()
  for (const r of recipes) {
    const bucket = map.get(r.lot_cd)
    if (bucket) bucket.push(r)
    else map.set(r.lot_cd, [r])
  }
  return map
}

/** lot_cd → full outlier result (median, threshold, and the flagged parameters). */
export const buildDeviceOutliers = (recipes: RecipeInput[]): Map<string, DeviceOutlierResult> => {
  const out = new Map<string, DeviceOutlierResult>()
  for (const [lot_cd, rows] of groupRecipesByLot(recipes)) {
    out.set(lot_cd, detectDeviceOutliers(rows))
  }
  return out
}

/**
 * Attach the profile metrics to a summary row.
 *
 * A missing result is NOT zero-filled into `point_median: 0` and left at that —
 * the caller needs to tell "measured 0" apart from "recipe_params hasn't landed
 * for this lot", so `has_profile` carries that distinction to the cell renderer.
 */
export const attachProfile = <T>(row: T, result: DeviceOutlierResult | undefined): T & DeviceProfile & { has_profile: boolean } => ({
  ...row,
  point_median: result?.median ?? 0,
  outlier_count: result?.outlier_count ?? 0,
  has_profile: result !== undefined
})
