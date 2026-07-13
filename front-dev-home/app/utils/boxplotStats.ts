// Pure: five-number summary for the MDC fleet boxplot. Quartiles use R-7
// linear interpolation (numpy/Excel default). min/max are the true extremes —
// hardware fleets are 4-6 tools, so whisker fencing would hide real tools.

export interface BoxStats {
  min: number
  q1: number
  median: number
  q3: number
  max: number
}

const quantileSorted = (sorted: number[], p: number): number => {
  const pos = (sorted.length - 1) * p
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo]! + (pos - lo) * (sorted[hi]! - sorted[lo]!)
}

export const boxStats = (values: number[]): BoxStats | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  return {
    min: sorted[0]!,
    q1: quantileSorted(sorted, 0.25),
    median: quantileSorted(sorted, 0.5),
    q3: quantileSorted(sorted, 0.75),
    max: sorted[sorted.length - 1]!
  }
}
