// The end/tick labels of a colour scale.
//
// Decimals follow the value's magnitude — 0 from 100 up, 1 from 10, 2 from 1,
// 3 below — so a ±0.3 nm range reads "-0.3 … 0.3" instead of the "-0 … 0" an
// integer label gives it. Trailing zeros are dropped, and a value that rounds
// to zero prints "0", never "-0".
export const formatScaleLabel = (value: number): string => {
  if (!Number.isFinite(value)) return '—'
  const abs = Math.abs(value)
  const decimals = abs >= 100 ? 0 : abs >= 10 ? 1 : abs >= 1 ? 2 : 3
  return String(Number(value.toFixed(decimals)) + 0) // + 0 turns −0 into 0
}
