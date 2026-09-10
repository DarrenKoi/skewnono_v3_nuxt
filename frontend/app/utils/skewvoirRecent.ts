import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'

export type SkewvoirRecentMode = 'single' | 'time-series'

export interface SkewvoirRecentMeasurement {
  msr: string
  lot: string
  recipe: string
  eq: string
  fab: string
  capturedAt: string
}

export interface SkewvoirRecentItem {
  id: string
  toolType: MeasHistToolType
  mode: SkewvoirRecentMode
  measurements: SkewvoirRecentMeasurement[]
  viewedAt: string
}

const isToolType = (value: unknown): value is MeasHistToolType =>
  value === 'cd-sem' || value === 'hv-sem'

const normalizeMeasurement = (value: unknown): SkewvoirRecentMeasurement | null => {
  if (typeof value !== 'object' || value === null) return null
  const item = value as Record<string, unknown>
  if (typeof item.msr !== 'string' || !item.msr.trim()) return null

  return {
    msr: item.msr,
    lot: typeof item.lot === 'string' ? item.lot : '',
    recipe: typeof item.recipe === 'string' ? item.recipe : '',
    eq: typeof item.eq === 'string' ? item.eq : '',
    fab: typeof item.fab === 'string' ? item.fab : '',
    capturedAt: typeof item.capturedAt === 'string' ? item.capturedAt : ''
  }
}

const uniqueMeasurements = (
  measurements: SkewvoirRecentMeasurement[]
): SkewvoirRecentMeasurement[] => {
  const seen = new Set<string>()
  return measurements.filter((measurement) => {
    if (!measurement.msr.trim() || seen.has(measurement.msr)) return false
    seen.add(measurement.msr)
    return true
  })
}

export const skewvoirRecentItemId = (
  toolType: MeasHistToolType,
  mode: SkewvoirRecentMode,
  msrs: string[]
): string => `${toolType}:${mode}:${[...new Set(msrs)].sort().join('|')}`

export const buildSkewvoirRecentItem = (
  toolType: MeasHistToolType,
  mode: SkewvoirRecentMode,
  measurements: SkewvoirRecentMeasurement[],
  viewedAt: string
): SkewvoirRecentItem | null => {
  const unique = uniqueMeasurements(measurements)
  if (!unique.length) return null

  return {
    id: skewvoirRecentItemId(toolType, mode, unique.map(item => item.msr)),
    toolType,
    mode,
    measurements: unique,
    viewedAt
  }
}

export const addSkewvoirRecentItem = (
  items: SkewvoirRecentItem[],
  item: SkewvoirRecentItem,
  maxItems: number
): SkewvoirRecentItem[] => [
  item,
  ...items.filter(existing => existing.id !== item.id)
].slice(0, maxItems)

export const normalizeSkewvoirRecentItems = (value: unknown): SkewvoirRecentItem[] => {
  if (!Array.isArray(value)) return []

  const normalized: SkewvoirRecentItem[] = []
  for (const raw of value) {
    if (typeof raw !== 'object' || raw === null) continue
    const item = raw as Record<string, unknown>
    if (!isToolType(item.toolType)) continue
    const viewedAt = typeof item.viewedAt === 'string' ? item.viewedAt : ''

    // Current shape: one history entry can restore one measurement or a full
    // Time-Series set.
    if ((item.mode === 'single' || item.mode === 'time-series') && Array.isArray(item.measurements)) {
      const measurements = item.measurements
        .map(normalizeMeasurement)
        .filter((measurement): measurement is SkewvoirRecentMeasurement => measurement !== null)
      const current = buildSkewvoirRecentItem(item.toolType, item.mode, measurements, viewedAt)
      if (current) normalized.push(current)
      continue
    }

    // Legacy shape: migrate the old one-MSR entry in place so an upgrade does
    // not erase the user's existing recent list.
    const legacyMeasurement = normalizeMeasurement(item)
    if (!legacyMeasurement) continue
    const legacy = buildSkewvoirRecentItem(item.toolType, 'single', [legacyMeasurement], viewedAt)
    if (legacy) normalized.push(legacy)
  }

  return normalized
}

export const toSkewvoirRecentMeasurement = (row: MeasHistRow): SkewvoirRecentMeasurement => ({
  msr: row.msr,
  lot: row.lot_id,
  recipe: row.full_name,
  eq: row.eqp_id,
  fab: row.fab_name,
  capturedAt: row.timestamp
})
