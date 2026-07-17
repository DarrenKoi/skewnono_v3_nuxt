// Pure histogram helpers for the AFM Z-value distribution. No DOM/Nuxt imports
// so they run under `node --test`; HistogramChart.vue wires them into useEchart.

export type BinMethod = 'auto' | 'custom'
export type HistogramMode = 'frequency' | 'density' | 'cumulative'

export interface HistogramStats {
  count: number
  mean: number
  stdev: number
  min: number
  max: number
  q1: number
  median: number
  q3: number
  skewness: number
  kurtosis: number
  cv: number
}

export interface HistogramBins {
  centers: number[]
  values: number[]
  binWidth: number
  edges: number[]
}

const clampBins = (n: number): number =>
  !Number.isFinite(n) ? 5 : Math.max(5, Math.min(200, Math.round(n)))

const meanOf = (nums: number[]): number =>
  nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0

const populationStd = (nums: number[], mu: number): number => {
  if (nums.length < 2) return 0
  return Math.sqrt(nums.reduce((a, b) => a + (b - mu) ** 2, 0) / nums.length)
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

// Abramowitz-Stegun erf approximation (max error ~1.5e-7).
const erf = (x: number): number => {
  const sign = x < 0 ? -1 : 1
  const ax = Math.abs(x)
  const t = 1 / (1 + 0.3275911 * ax)
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-ax * ax)
  return sign * y
}

export const histogramStats = (zs: number[]): HistogramStats => {
  const n = zs.length
  if (n === 0) {
    return { count: 0, mean: 0, stdev: 0, min: 0, max: 0, q1: 0, median: 0, q3: 0, skewness: 0, kurtosis: 0, cv: 0 }
  }
  const mean = meanOf(zs)
  const stdev = populationStd(zs, mean)
  const sorted = [...zs].sort((a, b) => a - b)

  let skewness = 0
  let kurtosis = 0
  if (stdev > 0 && n >= 3) {
    let s3 = 0
    for (const z of zs) s3 += ((z - mean) / stdev) ** 3
    skewness = s3 / n
  }
  if (stdev > 0 && n >= 4) {
    let s4 = 0
    for (const z of zs) s4 += ((z - mean) / stdev) ** 4
    kurtosis = s4 / n - 3
  }

  return {
    count: n,
    mean,
    stdev,
    min: sorted[0]!,
    max: sorted[n - 1]!,
    q1: quantile(sorted, 0.25),
    median: quantile(sorted, 0.5),
    q3: quantile(sorted, 0.75),
    skewness,
    kurtosis,
    cv: mean !== 0 ? (stdev / Math.abs(mean)) * 100 : 0
  }
}

export const resolveBinCount = (
  zs: number[],
  method: BinMethod,
  customCount: number
): number => {
  if (method === 'custom') return clampBins(customCount)
  const n = zs.length
  if (n < 1) return 5

  const sturges = clampBins(Math.ceil(1 + Math.log2(n)))
  const sorted = [...zs].sort((a, b) => a - b)
  const range = sorted[n - 1]! - sorted[0]!
  const iqr = quantile(sorted, 0.75) - quantile(sorted, 0.25)
  const fd = (iqr > 0 && range > 0)
    ? clampBins(Math.ceil(range / (2 * iqr * Math.pow(n, -1 / 3))))
    : sturges

  const mean = meanOf(zs)
  const std = populationStd(zs, mean)
  let outliers = 0
  if (std > 0) {
    for (const z of zs) if (Math.abs(z - mean) > 3 * std) outliers++
  }
  return outliers / n > 0.05 ? fd : sturges
}

export const computeHistogram = (
  zs: number[],
  binCount: number,
  mode: HistogramMode
): HistogramBins => {
  const n = zs.length
  const bins = Math.max(1, binCount)
  if (n === 0) return { centers: [0], values: [0], binWidth: 1, edges: [0, 1] }

  let min = Infinity
  let max = -Infinity
  for (const z of zs) {
    if (z < min) min = z
    if (z > max) max = z
  }
  if (max - min === 0) {
    return { centers: [min], values: [n], binWidth: 1, edges: [min - 0.5, min + 0.5] }
  }

  const binWidth = (max - min) / bins
  const counts = new Array(bins).fill(0)
  for (const z of zs) {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((z - min) / binWidth)))
    counts[idx] += 1
  }
  const edges = Array.from({ length: bins + 1 }, (_, i) => min + binWidth * i)
  const centers = Array.from({ length: bins }, (_, i) => min + binWidth * (i + 0.5))

  let values: number[]
  if (mode === 'density') {
    values = counts.map(c => c / (n * binWidth))
  } else if (mode === 'cumulative') {
    let run = 0
    values = counts.map(c => (run += c))
  } else {
    values = counts
  }
  return { centers, values, binWidth, edges }
}

// Fitted normal evaluated at each bin center, scaled to the display mode:
// 'density' = pdf; 'frequency' = pdf · N · binWidth; 'cumulative' = cdf · N.
// Returns [] when stdev is 0 (no meaningful curve).
export const normalCurveOverCenters = (
  stats: HistogramStats,
  mode: HistogramMode,
  binWidth: number,
  centers: number[]
): number[] => {
  const { mean, stdev, count } = stats
  if (stdev <= 0 || count === 0) return []
  const pdf = (x: number) =>
    Math.exp(-((x - mean) ** 2) / (2 * stdev * stdev)) / (stdev * Math.sqrt(2 * Math.PI))
  const cdf = (x: number) => 0.5 * (1 + erf((x - mean) / (stdev * Math.SQRT2)))
  return centers.map((x) => {
    if (mode === 'density') return pdf(x)
    if (mode === 'cumulative') return cdf(x) * count
    return pdf(x) * count * binWidth
  })
}

// Index of the bin whose [edge_i, edge_{i+1}) contains `value`; clamped to a valid bin.
export const binIndexForValue = (edges: number[], value: number): number => {
  const bins = edges.length - 1
  if (bins <= 1) return 0
  for (let i = 0; i < bins; i++) {
    if (value < edges[i + 1]!) return Math.max(0, i)
  }
  return bins - 1
}
