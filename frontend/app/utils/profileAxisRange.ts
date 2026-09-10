// User-overridable radial axis range for the 360° beam-profile radars, shared
// by 데일리 Sharpness and 분기 BSM.
//
// Both tabs plot the same physical per-degree metrics, but the two data
// sources spell them differently: the sharpness docs use snake_case keys over
// per-degree dicts (`reso_eb`, `noise`), the beam_shape docs use the source
// spellings over length-16 arrays (`Reso EB`, `Noise`). Canonicalising the key
// means one operating band and one stored override serve both tabs — a range
// set on the daily chart is the same range on the quarterly one, because it is
// the same measurement.

export interface AxisRange {
  min: number
  max: number
}

// "Reso EB" / "reso_eb" / "RESO_EB" all collapse to `reso_eb`. Metrics without
// a shared spelling (e.g. "Ave. Noise" → `ave_noise`) simply get their own
// slot, which is the correct outcome — they are distinct measurements.
export const canonicalMetricKey = (key: string): string =>
  key.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')

// The operating bands engineers read these metrics against. A fixed band (as
// opposed to a data-fitted one) is the point: it makes a shift between tools
// or over time legible, where a self-scaling axis hides it by re-centring.
// Metrics absent here keep the data-derived range, which is what every radar
// used before this control existed.
export const PROFILE_RANGE_DEFAULTS: Record<string, AxisRange> = {
  reso_eb: { min: 7.5, max: 8.5 },
  noise: { min: 5.7, max: 6.7 }
}

export const isValidRange = (range: AxisRange | null | undefined): range is AxisRange =>
  !!range
  && Number.isFinite(range.min)
  && Number.isFinite(range.max)
  && range.max > range.min

// The range in force when the user has not overridden it, and the target the
// reset button returns to. `derived` is the caller's data-fitted fallback.
export const defaultRangeFor = (metric: string, derived: AxisRange): AxisRange =>
  PROFILE_RANGE_DEFAULTS[canonicalMetricKey(metric)] ?? derived

// An invalid override (inverted, half-typed, corrupt storage) falls through to
// the default rather than blanking the chart.
export const resolveAxisRange = (
  metric: string,
  override: AxisRange | null | undefined,
  derived: AxisRange
): AxisRange => (isValidRange(override) ? override : defaultRangeFor(metric, derived))
