// Y-axis range for stable-telemetry trend charts.
//
// ECharts `scale: true` fits the axis tightly to [dataMin, dataMax], so a
// signal wobbling ±0.1% around a stable operating point fills the full chart
// height and reads as violent spikes. `stableYRange` centres the axis on the
// data and guarantees the visible span is at least `minSpanRatio` of the
// data's magnitude, so stable signals draw near-flat while real excursions
// (>> noise) still register. Use it for condition/health trends; keep tight
// scaling for shape charts (sweeps, profiles) where the curve form is the
// signal.

export interface StableYRange {
  min: number
  max: number
  interval: number
}

export interface StableYRangeOptions {
  /** Minimum visible span as a fraction of the data magnitude. */
  minSpanRatio?: number
  /** Extra headroom beyond the data span, as a fraction of the span. */
  padRatio?: number
  /**
   * For non-negative magnitude-of-error metrics (deltas, noise): anchor the
   * axis at 0 and leave 2× headroom above the data, so the series sits in the
   * lower half instead of filling a centred band. Ignored if any value < 0.
   */
  zeroMin?: boolean
}

// Heckbert-style nice number: 1/2/5 × 10^k, so ticks land on round values.
const niceStep = (span: number, splits = 5): number => {
  const raw = span / splits
  const mag = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / mag
  const nice = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10
  return nice * mag
}

const roundToStep = (value: number, step: number, dir: 'floor' | 'ceil'): number => {
  const decimals = Math.max(0, 1 - Math.floor(Math.log10(step)))
  return Number((Math[dir](value / step) * step).toFixed(decimals))
}

export const stableYRange = (
  values: number[],
  { minSpanRatio = 0.25, padRatio = 0.25, zeroMin = false }: StableYRangeOptions = {}
): StableYRange | null => {
  const finite = values.filter(v => Number.isFinite(v))
  if (finite.length === 0) return null
  const lo = Math.min(...finite)
  const hi = Math.max(...finite)
  if (zeroMin && lo >= 0) {
    if (hi === 0) return { min: 0, max: 1, interval: 0.2 }
    const step = niceStep(hi * 2)
    return { min: 0, max: roundToStep(hi * 2, step, 'ceil'), interval: step }
  }
  const magnitude = Math.max(Math.abs(lo), Math.abs(hi))
  if (magnitude === 0) return { min: -1, max: 1, interval: 0.5 }
  const mid = (lo + hi) / 2
  const half = Math.max(((hi - lo) / 2) * (1 + padRatio), (magnitude * minSpanRatio) / 2)
  const step = niceStep(half * 2)
  return {
    min: roundToStep(mid - half, step, 'floor'),
    max: roundToStep(mid + half, step, 'ceil'),
    interval: step
  }
}

// Y-axis range for MDC-style 'tight' trend/trajectory charts: mirrors
// `scale: true` (axis hugs the data so real drift stays visible) but guards
// the one case `scale: true` handles badly — a perfectly flat series (e.g. a
// clamped random walk pinned at its band edge). ECharts pads a degenerate
// [v, v] domain by a fraction of v itself (roughly ±60%), which buries a
// near-1.0 MDC value in a mostly-empty axis. Genuinely varying data (hi >
// lo) returns null so the caller keeps plain `scale: true`.
export const tightYRange = (
  values: number[],
  { minHalfSpanRatio = 0.01 }: { minHalfSpanRatio?: number } = {}
): StableYRange | null => {
  const finite = values.filter(v => Number.isFinite(v))
  if (finite.length === 0) return null
  const lo = Math.min(...finite)
  const hi = Math.max(...finite)
  if (hi > lo) return null
  const half = Math.max(Math.abs(lo) * minHalfSpanRatio, 0.001)
  const step = niceStep(half * 2)
  return {
    min: roundToStep(lo - half, step, 'floor'),
    max: roundToStep(hi + half, step, 'ceil'),
    interval: step
  }
}

// Radial scale for radar charts (indicators take {min, max} only). Same
// stable-span policy: a near-constant 360° profile reads as a near-circle at
// mid-radius instead of a tightly-fitted, exaggerated blob.
export const stableRadialRange = (
  values: number[],
  options?: StableYRangeOptions
): { min: number, max: number } | null => {
  const r = stableYRange(values, options)
  return r ? { min: r.min, max: r.max } : null
}
