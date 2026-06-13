// Within-device point-count outlier detection (D22 / grilling Q3).
// Baseline = all parameter point_counts across one device's recipes.
// A parameter is an outlier when point_count > multiplier × median.
// Pure + framework-free (mirrors ruleEngine.ts), unit-tested with node --test.
import type { RecipeInput } from './ruleEngine'

export const DEFAULT_OUTLIER_MULTIPLIER = 2

export interface PointOutlier {
  recipe_id: string
  name: string
  point_count: number
}

export interface DeviceOutlierResult {
  median: number
  threshold: number
  outliers: PointOutlier[]
  outlier_count: number
}

const median = (values: number[]): number => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!
}

export const detectDeviceOutliers = (
  recipes: RecipeInput[],
  multiplier: number = DEFAULT_OUTLIER_MULTIPLIER
): DeviceOutlierResult => {
  const allPoints = recipes.flatMap(r => r.parameters.map(p => p.point_count))
  const med = median(allPoints)
  const threshold = med * multiplier

  const outliers: PointOutlier[] = []
  for (const r of recipes) {
    for (const p of r.parameters) {
      if (p.point_count > threshold) {
        outliers.push({ recipe_id: r.recipe_id, name: p.name, point_count: p.point_count })
      }
    }
  }
  return { median: med, threshold, outliers, outlier_count: outliers.length }
}
