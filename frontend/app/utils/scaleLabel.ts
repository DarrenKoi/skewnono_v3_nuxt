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

// Decimals for a whole scale: the magnitude rule, widened until the two ends
// read differently. Chosen per value, 0.2231 and 0.2234 both print "0.223" and
// a scale with width reads as flat.
const MAX_DECIMALS = 8
export const scaleDecimals = (min: number, max: number): number => {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return 2
  let decimals = magnitudeDecimals(Math.max(Math.abs(min), Math.abs(max)))
  while (min !== max && decimals < MAX_DECIMALS && formatScaleLabel(min, decimals) === formatScaleLabel(max, decimals)) decimals++
  return decimals
}
