// Pure: five-number summary for the MDC fleet boxplot. Quartiles use R-7 linear
// interpolation (numpy/Excel default). min/max are the true extremes — hardware
// fleets are 4-6 tools, so whisker fencing would hide real tools. (CD site
// distributions DO want fencing — see iqrFences in stats.ts.)
import { quantileSorted } from './stats.ts'

export interface BoxStats {
  min: number
  q1: number
  median: number
  q3: number
  max: number
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
