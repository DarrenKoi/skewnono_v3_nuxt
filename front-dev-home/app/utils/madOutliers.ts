// Robust outlier detection via median + MAD (modified z-score).
// Resistant to a few extreme values masking themselves the way classic
// mean±std does, which matters for the small MSR selections on skewvoir.
// Pure + framework-free (mirrors outlierDetect.ts), unit-tested with node --test.

export const MAD_DEFAULT_K = 3.5
export const MAD_DEFAULT_MIN_N = 5

// 0.6745 = 0.75 quantile of the standard normal; scales MAD so the
// modified z-score is comparable to a standard z-score for normal data.
const MAD_SCALE = 0.6745

const median = (values: number[]): number => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!
}

export const detectMadOutliers = (
  values: number[],
  k: number = MAD_DEFAULT_K,
  minN: number = MAD_DEFAULT_MIN_N
): boolean[] => {
  if (values.length < minN) return values.map(() => false)

  const med = median(values)
  const mad = median(values.map(v => Math.abs(v - med)))

  // MAD = 0 means ≥half the values equal the median; dividing would be NaN/Inf.
  // Fall back to flagging only values that differ from the median, so a
  // constant series flags nothing.
  if (mad === 0) return values.map(v => v !== med)

  return values.map(v => Math.abs((MAD_SCALE * (v - med)) / mad) > k)
}
