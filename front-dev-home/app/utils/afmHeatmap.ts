// Pure heatmap analysis helpers for the AFM wafer heat map. No DOM/Nuxt imports
// so they run under `node --test`; HeatmapChart.vue wires them into useEchart.
import type { AfmProfilePoint } from '~/composables/useAfmDetailApi'

export type OutlierMethod = 'none' | 'iqr' | 'zscore'
export type HeatmapColorScheme = 'spectral' | 'viridis' | 'grayscale'

export const OUTLIER_DEFAULT_THRESHOLD: Record<OutlierMethod, number> = {
  none: 0,
  iqr: 1.5,
  zscore: 3
}

// 'spectral' MUST match the pre-existing heatmap ramp so the default look is unchanged.
export const HEATMAP_COLOR_RAMPS: Record<HeatmapColorScheme, string[]> = {
  spectral: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'],
  viridis: ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'],
  grayscale: ['#111827', '#6b7280', '#e5e7eb']
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

const mean = (nums: number[]): number =>
  nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0

const stdev = (nums: number[], mu: number): number => {
  if (nums.length < 2) return 0
  const variance = nums.reduce((a, b) => a + (b - mu) ** 2, 0) / nums.length
  return Math.sqrt(variance)
}

// Linear-interpolated quantile on an ascending-sorted array; p in [0, 1].
const quantile = (sortedAsc: number[], p: number): number => {
  if (sortedAsc.length === 0) return 0
  if (sortedAsc.length === 1) return sortedAsc[0]!
  const pos = (sortedAsc.length - 1) * p
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sortedAsc[lo]! + (sortedAsc[hi]! - sortedAsc[lo]!) * (pos - lo)
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
    const mu = mean(zs)
    const sd = stdev(zs, mu)
    if (sd === 0) return { kept: points, removed: 0 }
    lower = mu - threshold * sd
    upper = mu + threshold * sd
  } else {
    const sorted = [...zs].sort((a, b) => a - b)
    const q1 = quantile(sorted, 0.25)
    const q3 = quantile(sorted, 0.75)
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
