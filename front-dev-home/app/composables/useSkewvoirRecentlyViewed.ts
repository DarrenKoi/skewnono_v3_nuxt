import type { MeasHistToolType } from '~/composables/useMeasHistApi'

// A measurement the user opened in the analysis workspace. Phase 1 persists to
// localStorage (fully offline), same as useSkewvoirSavedViews. Phase 2/3 swaps
// the read/write internals for a per-user Flask blueprint; this surface stays.
export interface SkewvoirRecentItem {
  msr: string
  toolType: MeasHistToolType
  lot: string
  recipe: string
  eq: string
  fab: string
  capturedAt: string
  viewedAt: string
}

export interface SkewvoirRecentEntry extends SkewvoirRecentItem {
  // Outside the 60-day retention window: the row is remembered but the data is
  // gone, so the entry is shown greyed rather than silently dropped.
  expired: boolean
}

const STORAGE_KEY = 'skewvoir-recently-viewed'
const MAX_ITEMS = 15
const RETENTION_DAYS = 60

const readAll = (): SkewvoirRecentItem[] => {
  if (!import.meta.client) return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as SkewvoirRecentItem[]) : []
  } catch {
    return []
  }
}

const writeAll = (items: SkewvoirRecentItem[]) => {
  if (!import.meta.client) return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
}

const shiftIso = (iso: string, days: number): string => {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
  dt.setUTCDate(dt.getUTCDate() - days)
  return dt.toISOString().slice(0, 10)
}

export const useSkewvoirRecentlyViewed = (toolType: MeasHistToolType) => {
  const all = useState<SkewvoirRecentItem[]>('skewvoir-recently-viewed-store', () => readAll())
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
      .map(item => ({
        ...item,
        expired: Boolean(floor) && item.capturedAt.slice(0, 10) < floor
      }))
  })

  const record = (item: SkewvoirRecentItem) => {
    const deduped = all.value.filter(existing => existing.msr !== item.msr)
    all.value = [item, ...deduped].slice(0, MAX_ITEMS)
    writeAll(all.value)
  }

  const remove = (msr: string) => {
    all.value = all.value.filter(item => item.msr !== msr)
    writeAll(all.value)
  }

  const clear = () => {
    all.value = all.value.filter(item => item.toolType !== toolType)
    writeAll(all.value)
  }

  const refresh = () => {
    all.value = readAll()
  }

  return { items, record, remove, clear, refresh, setAnchor }
}
