import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import {
  addMeasHistSelection,
  removeMeasHistSelection,
  setMeasHistSelections,
  toggleMeasHistSelection
} from '~/utils/measHistSelection'

// Mirrors recipe-search's persistent working set. Search results may be
// replaced repeatedly; selected measurements remain available by tool type.
const storageKey = (toolType: MeasHistToolType) =>
  `skewnono:skewvoir.selection.${toolType}`

const persistenceScope = effectScope(true)
const persistenceWatchers = new Set<MeasHistToolType>()

const readRows = (key: string): MeasHistRow[] => {
  if (typeof window === 'undefined') return []
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(key) ?? '[]')
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is MeasHistRow =>
      typeof item === 'object'
      && item !== null
      && typeof (item as { msr?: unknown }).msr === 'string'
    )
  } catch {
    return []
  }
}

const writeRows = (key: string, rows: MeasHistRow[]) => {
  if (typeof window === 'undefined') return
  try {
    if (rows.length) window.localStorage.setItem(key, JSON.stringify(rows))
    else window.localStorage.removeItem(key)
  } catch { /* localStorage can be unavailable in restricted browser contexts */ }
}

export const useSkewvoirSearchSelection = (toolType: MeasHistToolType) => {
  const key = storageKey(toolType)
  const selected = useState<MeasHistRow[]>(
    `skewvoir:search-selection:${toolType}`,
    () => readRows(key)
  )

  if (!persistenceWatchers.has(toolType)) {
    persistenceWatchers.add(toolType)
    persistenceScope.run(() => {
      watch(selected, rows => writeRows(key, rows), { flush: 'sync' })
    })
  }

  const has = (msr: string) => selected.value.some(row => row.msr === msr)

  const add = (row: MeasHistRow) => {
    selected.value = addMeasHistSelection(selected.value, row)
  }

  const remove = (msr: string) => {
    selected.value = removeMeasHistSelection(selected.value, msr)
  }

  const toggle = (row: MeasHistRow) => {
    selected.value = toggleMeasHistSelection(selected.value, row)
  }

  const setMany = (rows: MeasHistRow[], enabled: boolean) => {
    selected.value = setMeasHistSelections(selected.value, rows, enabled)
  }

  const clear = () => {
    selected.value = []
  }

  const count = computed(() => selected.value.length)

  return { selected, count, has, add, remove, toggle, setMany, clear }
}
