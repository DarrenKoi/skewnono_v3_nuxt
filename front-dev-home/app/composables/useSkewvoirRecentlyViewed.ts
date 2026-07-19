import type { MeasHistToolType } from '~/composables/useMeasHistApi'
import {
  addSkewvoirRecentItem,
  buildSkewvoirRecentItem,
  normalizeSkewvoirRecentItems,
  type SkewvoirRecentItem,
  type SkewvoirRecentMeasurement,
  type SkewvoirRecentMode
} from '~/utils/skewvoirRecent'

export interface SkewvoirRecentEntry extends SkewvoirRecentItem {
  // An entry is disabled only when every measurement has left retention. A
  // partially expired Time-Series can still reopen with its remaining rows.
  expired: boolean
  expiredCount: number
}

const STORAGE_KEY = 'skewvoir-recently-viewed'
const MAX_ITEMS = 15
const RETENTION_DAYS = 60

// Kept alongside the usePersistedState watcher for refresh(): re-reads what
// another tab may have written since this SPA instance last touched storage.
const readAll = (): SkewvoirRecentItem[] => {
  if (!import.meta.client) return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return normalizeSkewvoirRecentItems(raw ? JSON.parse(raw) : [])
  } catch {
    return []
  }
}

const shiftIso = (iso: string, days: number): string => {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
  dt.setUTCDate(dt.getUTCDate() - days)
  return dt.toISOString().slice(0, 10)
}

export const useSkewvoirRecentlyViewed = (toolType: MeasHistToolType) => {
  const all = usePersistedState<SkewvoirRecentItem[]>(
    'skewvoir-recently-viewed-store',
    STORAGE_KEY,
    { default: () => [], normalize: normalizeSkewvoirRecentItems }
  )
  // The retention floor comes from the backend's anchor, never wall clock —
  // the Phase 1 mock's clock is frozen well before today.
  const anchor = useState<string>('skewvoir-recent-anchor', () => '')

  const setAnchor = (value: string) => {
    if (value) anchor.value = value
  }

  const items = computed<SkewvoirRecentEntry[]>(() => {
    const floor = anchor.value ? shiftIso(anchor.value, RETENTION_DAYS) : ''
    return all.value
      .filter(item => item.toolType === toolType)
      .map((item) => {
        const expiredCount = floor
          ? item.measurements.filter(measurement =>
            Boolean(measurement.capturedAt)
            && measurement.capturedAt.slice(0, 10) < floor
          ).length
          : 0
        return {
          ...item,
          expired: item.measurements.length > 0 && expiredCount === item.measurements.length,
          expiredCount
        }
      })
  })

  const record = (
    mode: SkewvoirRecentMode,
    measurements: SkewvoirRecentMeasurement[],
    viewedAt = new Date().toISOString()
  ) => {
    const item = buildSkewvoirRecentItem(toolType, mode, measurements, viewedAt)
    if (!item) return null
    all.value = addSkewvoirRecentItem(all.value, item, MAX_ITEMS)
    return item
  }

  const remove = (id: string) => {
    all.value = all.value.filter(item => item.id !== id)
  }

  const clear = () => {
    all.value = all.value.filter(item => item.toolType !== toolType)
  }

  const refresh = () => {
    all.value = readAll()
  }

  return { items, record, remove, clear, refresh, setAnchor }
}
