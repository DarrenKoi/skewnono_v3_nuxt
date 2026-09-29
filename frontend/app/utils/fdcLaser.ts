import { median, medianAbsoluteDeviation, MAD_TO_SIGMA } from './stats.ts'

export const LASER_OUTLIER_SIGMA = 3

export interface LaserRow { ts: string, epoch: number, x1: number, y1: number }

export const laserOutliers = (rows: LaserRow[], channel: 'x1' | 'y1') => {
  const valid = rows.filter(row => Number.isFinite(row[channel]))
  const values = valid.map(row => row[channel])
  const baseline = values.length ? median(values) : null
  const points: { ts: string, epoch: number, deviation: number }[] = []
  if (baseline === null || baseline === 0) return { baseline, total: valid.length, points, band: null }

  const threshold = LASER_OUTLIER_SIGMA * MAD_TO_SIGMA * medianAbsoluteDeviation(values)
  const width = threshold / Math.abs(baseline) * 100
  for (const row of valid) {
    if (Math.abs(row[channel] - baseline) > threshold && Number.isFinite(row.epoch)) {
      points.push({ ts: row.ts, epoch: row.epoch, deviation: (row[channel] - baseline) / baseline * 100 })
    }
  }
  return { baseline, total: valid.length, points, band: { lo: width === 0 ? 0 : -width, hi: width } }
}
