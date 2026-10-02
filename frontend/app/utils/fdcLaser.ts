import { median, medianAbsoluteDeviation, MAD_TO_SIGMA } from './stats.ts'

export const LASER_OUTLIER_SIGMA = 3
// x1/y1 are written with two decimals ('0.78'). A stable tool has MAD 0, and
// a one-step change is quantization, not an outlier, so the band never
// shrinks below one step.
export const LASER_RESOLUTION = 0.01

export interface LaserRow { ts: string, epoch: number, x1: number, y1: number }

export const laserOutliers = (rows: LaserRow[], channel: 'x1' | 'y1') => {
  const valid = rows.filter(row => Number.isFinite(row[channel]))
  const values = valid.map(row => row[channel])
  const baseline = values.length ? median(values) : null
  const points: { ts: string, epoch: number, deviation: number }[] = []
  // Every plottable point, outliers included - for the "show all" toggle.
  const all: typeof points = []
  if (baseline === null || baseline === 0) return { baseline, total: valid.length, points, all, band: null }

  // The epsilon keeps 0.75 - 0.74 (= 0.010000000000000009) inside the band.
  const threshold = Math.max(LASER_OUTLIER_SIGMA * MAD_TO_SIGMA * medianAbsoluteDeviation(values), LASER_RESOLUTION + 1e-9)
  const width = threshold / Math.abs(baseline) * 100
  for (const row of valid) {
    if (!Number.isFinite(row.epoch)) continue
    const point = { ts: row.ts, epoch: row.epoch, deviation: (row[channel] - baseline) / baseline * 100 }
    all.push(point)
    if (Math.abs(row[channel] - baseline) > threshold) points.push(point)
  }
  return { baseline, total: valid.length, points, all, band: { lo: -width, hi: width } }
}
