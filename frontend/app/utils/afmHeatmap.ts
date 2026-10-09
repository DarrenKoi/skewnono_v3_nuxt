// Pure heatmap analysis helpers for one AFM point's scan height map. No DOM/Nuxt imports
// so they run under `node --test`; HeatmapChart.vue wires them into useEchart.
import { meanOf, populationStd } from './afmHistogram.ts'
import { quantileSorted } from './stats.ts'
import type { AfmMeasuredPoint, AfmProfilePoint } from '~/composables/useAfmDetailApi'

// How many decimals a Z value needs to be read in its file's unit: a height that
// is 110.51 in nm is 0.11051 in um, and two decimals would print it as 0.11.
const Z_DECIMALS: Record<string, number> = { um: 5, nm: 2, pm: 0 }
export const formatZ = (value: number, unit?: string | null): string =>
  value.toFixed(Z_DECIMALS[unit ?? ''] ?? 2)

export type OutlierMethod = 'none' | 'iqr' | 'zscore'

export const OUTLIER_DEFAULT_THRESHOLD: Record<OutlierMethod, number> = {
  none: 0,
  iqr: 1.5,
  zscore: 3
}

// The samples that carry a height. Statistics and marks are built from these; the
// lattice test (profileGrid) still reads every sample, so a missing one is a hole
// in the map rather than a reason to stop drawing cells.
export const measuredPoints = (points: AfmProfilePoint[]): AfmMeasuredPoint[] =>
  points.filter((p): p is AfmMeasuredPoint => typeof p.z === 'number' && Number.isFinite(p.z))

export interface HeatmapFilterResult {
  kept: AfmMeasuredPoint[]
  removed: number
}

export interface HeatmapStats {
  count: number
  min: number
  max: number
  mean: number
}

export const filterProfileByOutlier = (
  points: AfmMeasuredPoint[],
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

export const heatmapStats = (points: AfmMeasuredPoint[]): HeatmapStats => {
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

// A 1D profile is one scan line, stored in the same X/Y/Z shape as a grid with Y fixed
// at 0. The file's DataSize ("1024 x 1") is what tells the two apart; only when it is
// missing or unreadable do the samples decide, by all sharing one y.
export const isLineProfile = (points: AfmProfilePoint[], dataSize?: string | null): boolean => {
  const declared = /^\s*(\d+)\s*x\s*(\d+)\s*$/i.exec(dataSize ?? '')
  if (declared) return Number(declared[2]) === 1
  return points.length > 1 && points.every(p => p.y === points[0]!.y)
}

export interface ProfileGrid {
  xs: number[]
  ys: number[]
}

// Positions along one axis step evenly, give or take the rounding the file prints them with.
const evenlySpaced = (sorted: number[]): boolean => {
  if (sorted.length < 3) return true
  const step = (sorted.at(-1)! - sorted[0]!) / (sorted.length - 1)
  return sorted.every((v, i) => i === 0 || Math.abs(v - sorted[i - 1]! - step) <= step * 0.05)
}

// The scan's lateral positions, ascending, when the samples form a full, evenly stepped
// lattice: exactly one per (x, y) pair. That is what lets the map draw each sample as a
// cell sized by the chart itself. Category bands are all one width, so anything else
// (ragged rows, repeated positions, uneven steps) would be drawn somewhere it is not;
// the caller keeps those as dots at their real positions.
export const profileGrid = (points: AfmProfilePoint[]): ProfileGrid | null => {
  const xs = [...new Set(points.map(p => p.x))].sort((a, b) => a - b)
  const ys = [...new Set(points.map(p => p.y))].sort((a, b) => a - b)
  const full = points.length > 0
    && xs.length * ys.length === points.length
    && new Set(points.map(p => `${p.x},${p.y}`)).size === points.length
  return full && evenlySpaced(xs) && evenlySpaced(ys) ? { xs, ys } : null
}

// An axis name with the unit its file declared ("X (μm)"). Units differ from file to
// file (um / nm / pm / Pixel) and are never unified, so none is ever assumed.
// The long spellings are the ones the object metadata was quoted with (MicroMeter).
const UNIT_SYMBOL: Record<string, string> = {
  um: 'μm', micrometer: 'μm', nanometer: 'nm', picometer: 'pm'
}
export const axisTitle = (axis: string, unit?: string | null): string =>
  unit ? `${axis} (${UNIT_SYMBOL[unit.toLowerCase()] ?? unit})` : axis
