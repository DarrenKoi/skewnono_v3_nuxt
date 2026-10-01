// Pure heatmap analysis helpers for the AFM wafer heat map. No DOM/Nuxt imports
// so they run under `node --test`; HeatmapChart.vue wires them into useEchart.
import { meanOf, populationStd } from './afmHistogram.ts'
import { quantileSorted } from './stats.ts'
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'

export type OutlierMethod = 'none' | 'iqr' | 'zscore'

export const OUTLIER_DEFAULT_THRESHOLD: Record<OutlierMethod, number> = {
  none: 0,
  iqr: 1.5,
  zscore: 3
}

export interface HeatmapFilterResult {
  kept: AfmProfilePoint[]
  removed: number
}

export interface HeatmapStats {
  count: number
  min: number
  max: number
  mean: number
}

export const filterProfileByOutlier = (
  points: AfmProfilePoint[],
  method: OutlierMethod,
  threshold: number
): HeatmapFilterResult => {
  if (method === 'none' || points.length < 4 || !Number.isFinite(threshold) || threshold <= 0) {
    return { kept: points, removed: 0 }
  }

  const zs = points.map(p => p.z)
  let lower: number
  let upper: number

  if (method === 'zscore') {
    const mu = meanOf(zs)
    const sd = populationStd(zs, mu)
    if (sd === 0) return { kept: points, removed: 0 }
    lower = mu - threshold * sd
    upper = mu + threshold * sd
  } else {
    const sorted = [...zs].sort((a, b) => a - b)
    const q1 = quantileSorted(sorted, 0.25)
    const q3 = quantileSorted(sorted, 0.75)
    const iqr = q3 - q1
    if (iqr === 0) return { kept: points, removed: 0 }
    lower = q1 - threshold * iqr
    upper = q3 + threshold * iqr
  }

  const kept = points.filter(p => p.z >= lower && p.z <= upper)
  return { kept, removed: points.length - kept.length }
}

export const heatmapStats = (points: AfmProfilePoint[]): HeatmapStats => {
  if (points.length === 0) return { count: 0, min: 0, max: 0, mean: 0 }
  let min = Infinity
  let max = -Infinity
  let sum = 0
  for (const p of points) {
    if (p.z < min) min = p.z
    if (p.z > max) max = p.z
    sum += p.z
  }
  return { count: points.length, min, max, mean: sum / points.length }
}
