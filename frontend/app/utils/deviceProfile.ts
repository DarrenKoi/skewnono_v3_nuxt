// Per-device measurement profile (D22) — the 과다 측정 signal that used to live on
// its own /device-statistics/profile page. It now rides along in the comparison
// page's Lot 요약 table, because both surfaces are the same grain (one row per
// device) and the standalone page duplicated every other column.
//
// Bucket-scoped (changed 2026-08-04, user-confirmed). The median and outlier
// count are computed over whatever recipes and parameters the selected bucket
// admits, so they move with the bucket like every other column in the table.
// This reverses the earlier design, which froze the baseline at "every
// point_count the device measures" so a bucket switch could not move the
// median — the bucket is now the analysis scope, not a display filter.
//
// This module does NOT scope anything itself; it profiles whatever rows it is
// handed. The caller narrows once via lotHealth.scopeRecipesToBucket and passes
// the SAME array to buildLotVerdicts, so health and the profile can never end
// up describing different populations within one table row.
// Value import carries the explicit .ts so `node --test` resolves it without a
// bundler (see lotHealth.ts) — type-only imports are erased and don't need it.
import { detectDeviceOutliers, type DeviceOutlierResult } from './outlierDetect.ts'
import type { RecipeInput } from './ruleEngine'

/**
 * null (not 0) when recipe_params has nothing for the lot — "측정 0건" and "아직
 * 안 왔다" must stay distinguishable all the way to the export, and a nullable
 * number says that in the type instead of pairing a zero with a boolean flag.
 */
export interface DeviceProfile {
  /** Median point_count across every parameter the device measures. */
  point_median: number | null
  /** Parameters whose point_count exceeds median × multiplier. */
  outlier_count: number | null
}

/** A row of some other surface, joined with its measurement profile. */
export type Profiled<T> = T & DeviceProfile

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

/**
 * lot_cd → full outlier result (median, threshold, and the flagged parameters).
 *
 * Takes the grouped map rather than the flat rows so the caller can keep the
 * grouping: the drill-down needs the same `RecipeInput[]` this walks, and
 * regrouping the whole payload to recover one lot is a full re-scan per click.
 */
export const buildDeviceOutliers = (byLot: Map<string, RecipeInput[]>): Map<string, DeviceOutlierResult> => {
  const out = new Map<string, DeviceOutlierResult>()
  for (const [lot_cd, rows] of byLot) {
    out.set(lot_cd, detectDeviceOutliers(rows))
  }
  return out
}

/** Attach the profile metrics to a row of another surface (a bucket summary row). */
export const attachProfile = <T>(row: T, result: DeviceOutlierResult | undefined): Profiled<T> => ({
  ...row,
  point_median: result?.median ?? null,
  outlier_count: result?.outlier_count ?? null
})
