// The end/tick labels of a colour scale.
//
// Decimals follow the magnitude — 0 from 100 up, 1 from 10, 2 from 1, 3 below —
// so a ±0.3 nm range reads "-0.3 … 0.3" instead of the "-0 … 0" an integer
// label gives it. Trailing zeros are dropped, and a value that rounds to zero
// prints "0", never "-0".
const magnitudeDecimals = (abs: number) => abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : 3

export const formatScaleLabel = (value: number, decimals?: number): string => {
  if (!Number.isFinite(value)) return '—'
  return String(Number(value.toFixed(decimals ?? magnitudeDecimals(Math.abs(value)))) + 0) // + 0 turns −0 into 0
}

// One formatter for a whole scale (min · mid · max, or a visualMap's labels).
//   1. Each non-zero end keeps the decimals its own magnitude needs — the
//      smaller end governs, so 0.25 … 100 does not print "0 … 100".
//   2. If the two ends still print alike, decimals widen until they differ.
//   3. Past MAX_DECIMALS that cannot work (1e-9 … 4e-9); exponent form takes
//      over, with as many digits as it takes to tell the ends apart.
// A flat or non-finite range has nothing to tell apart: the per-value rule.
const MAX_DECIMALS = 8
const MAX_EXP_DIGITS = 15
export const scaleFormatter = (min: number, max: number): (value: number) => string => {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return value => formatScaleLabel(value)
  const ends = [min, max].filter(v => v !== 0).map(v => magnitudeDecimals(Math.abs(v)))
  let decimals = Math.max(...ends)
  while (decimals < MAX_DECIMALS && formatScaleLabel(min, decimals) === formatScaleLabel(max, decimals)) decimals++
  if (formatScaleLabel(min, decimals) !== formatScaleLabel(max, decimals)) return value => formatScaleLabel(value, decimals)
  let digits = 0
  while (digits < MAX_EXP_DIGITS && min.toExponential(digits) === max.toExponential(digits)) digits++
  return value => Number.isFinite(value) ? (value === 0 ? '0' : value.toExponential(digits)) : '—'
}
