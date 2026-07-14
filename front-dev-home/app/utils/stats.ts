// Pure descriptive statistics. No framework deps, no domain knowledge.
// This is the ONLY place these formulas are written down — before this module,
// Pearson lived in two components with different edge-case behaviour.

// NaN, not 0: an empty set has no centre, and 0 would silently poison averages.
export const mean = (values: number[]): number => {
  if (values.length === 0) return Number.NaN
  let sum = 0
  for (const v of values) sum += v
  return sum / values.length
}

// Two-pass sample std (n-1). The one-pass sumsq/n - m^2 shortcut is faster but
// catastrophically cancels when the mean is large relative to the spread — it can
// even return a negative variance. CD values sit at ~1e2 nm with ~1 nm spread, so
// the stability matters. n-1 matches anomaly/peer.ts::looStats.
export const sampleStd = (values: number[]): number => {
  const n = values.length
  if (n < 2) return 0
  const m = mean(values)
  let acc = 0
  for (const v of values) acc += (v - m) ** 2
  return Math.sqrt(acc / (n - 1))
}

// R-7 linear interpolation (numpy/Excel default). Caller pre-sorts and pre-filters.
export const quantileSorted = (sorted: number[], p: number): number => {
  if (sorted.length === 0) return Number.NaN
  const pos = (sorted.length - 1) * p
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo]! + (pos - lo) * (sorted[hi]! - sorted[lo]!)
}

export interface IqrFences {
  q1: number
  q3: number
  lower: number
  upper: number
}

// Tukey 1.5x IQR — for WHISKER RENDERING on CD site distributions only. It is NOT
// an outlier verdict; utils/anomaly/ owns that. And it deliberately does not touch
// boxplotStats.ts, whose true-extreme whiskers are correct for 4-6-tool fleet plots
// where fencing would hide real tools.
export const iqrFences = (values: number[]): IqrFences | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  const q1 = quantileSorted(sorted, 0.25)
  const q3 = quantileSorted(sorted, 0.75)
  const iqr = q3 - q1
  return { q1, q3, lower: q1 - 1.5 * iqr, upper: q3 + 1.5 * iqr }
}

// Centred sums shared by pearson and linearFit.
const centred = (pairs: [number, number][]) => {
  const pts = pairs.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
  const n = pts.length
  if (n === 0) return null
  let mx = 0
  let my = 0
  for (const [x, y] of pts) {
    mx += x
    my += y
  }
  mx /= n
  my /= n
  let sxy = 0
  let sxx = 0
  let syy = 0
  for (const [x, y] of pts) {
    sxy += (x - mx) * (y - my)
    sxx += (x - mx) ** 2
    syy += (y - my) ** 2
  }
  return { n, mx, my, sxy, sxx, syy }
}

// n >= 3 floor: with n = 2 any two distinct points are perfectly collinear, so r is
// trivially +/-1 and means nothing. Returns null (not 0) when undefined, so callers
// must render "no answer" rather than a fake zero that reads as a real finding.
export const pearson = (pairs: [number, number][]): number | null => {
  const c = centred(pairs)
  if (!c || c.n < 3) return null
  if (c.sxx === 0 || c.syy === 0) return null
  return c.sxy / Math.sqrt(c.sxx * c.syy)
}

// Average ranks for ties (1, 2.5, 2.5, 4) — the standard tie correction.
const ranks = (values: number[]): number[] => {
  const idx = values.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0])
  const out = new Array<number>(values.length)
  let i = 0
  while (i < idx.length) {
    let j = i
    while (j + 1 < idx.length && idx[j + 1]![0] === idx[i]![0]) j++
    const avg = (i + j) / 2 + 1
    for (let k = i; k <= j; k++) out[idx[k]![1]] = avg
    i = j + 1
  }
  return out
}

// Spearman rho = Pearson on ranks. Captures ANY monotonic relation, not just a
// linear one, and is far less sensitive to a single wild CD than Pearson.
export const spearman = (pairs: [number, number][]): number | null => {
  const pts = pairs.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
  if (pts.length < 3) return null
  const rx = ranks(pts.map(p => p[0]))
  const ry = ranks(pts.map(p => p[1]))
  return pearson(rx.map((r, i) => [r, ry[i]!] as [number, number]))
}

export interface LinearFit {
  slope: number
  intercept: number
}

export const linearFit = (pairs: [number, number][]): LinearFit | null => {
  const c = centred(pairs)
  if (!c || c.n < 2 || c.sxx === 0) return null
  const slope = c.sxy / c.sxx
  return { slope, intercept: c.my - slope * c.mx }
}
