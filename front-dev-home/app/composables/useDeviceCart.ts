// Cart of selected device lots, shared between the device-statistics list page and its comparison
// sub-page. Backed by useState so client-side navigation between the two pages reuses one ref;
// localStorage persists across full reloads / direct URL hits.

const SELECTED_DEVICE_LOTS_STORAGE_KEY = 'skewnono:deviceStatistics.selectedDeviceLots'

// watch() inside <script setup> registers in the component's effect scope and dies on unmount.
// We need the persistence watcher to survive client-side navigation between the list page and
// the comparison sub-page, so host it inside a detached effect scope (one per app instance).
const persistenceScope = effectScope(true)
let persistenceWatcherAttached = false

const readSavedDeviceLots = (): string[] => {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(SELECTED_DEVICE_LOTS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === 'string')
      : []
  } catch {
    return []
  }
}

const persistDeviceLots = (values: string[]) => {
  if (typeof window === 'undefined') return
  try {
    if (values.length === 0) {
      window.localStorage.removeItem(SELECTED_DEVICE_LOTS_STORAGE_KEY)
    } else {
      window.localStorage.setItem(SELECTED_DEVICE_LOTS_STORAGE_KEY, JSON.stringify(values))
    }
  } catch { /* noop */ }
}

export const useDeviceCart = () => {
  const selectedDeviceLots = useState<string[]>(
    'device-cart:selectedLots',
    () => readSavedDeviceLots()
  )

  if (!persistenceWatcherAttached) {
    persistenceWatcherAttached = true
    persistenceScope.run(() => {
      watch(selectedDeviceLots, next => persistDeviceLots(next))
    })
  }

  const selectedDeviceLotSet = computed(() => new Set(selectedDeviceLots.value))

  const isDeviceSelected = (lot: string) => selectedDeviceLotSet.value.has(lot)

  const toggleDeviceSelect = (lot: string) => {
    selectedDeviceLots.value = selectedDeviceLotSet.value.has(lot)
      ? selectedDeviceLots.value.filter(currentLot => currentLot !== lot)
      : [...selectedDeviceLots.value, lot]
  }

  const clearDeviceSelection = () => {
    selectedDeviceLots.value = []
  }

  // Bulk add — preserves insertion order, dedups against current selection.
  const addDeviceLots = (lots: string[]) => {
    const set = selectedDeviceLotSet.value
    const next = [...selectedDeviceLots.value]
    for (const lot of lots) {
      if (!set.has(lot)) next.push(lot)
    }
    if (next.length !== selectedDeviceLots.value.length) {
      selectedDeviceLots.value = next
    }
  }

  // Bulk remove — used by the page-level "deselect all on this page" toggle.
  const removeDeviceLots = (lots: string[]) => {
    const removalSet = new Set(lots)
    const next = selectedDeviceLots.value.filter(lot => !removalSet.has(lot))
    if (next.length !== selectedDeviceLots.value.length) {
      selectedDeviceLots.value = next
    }
  }

  return {
    selectedDeviceLots,
    selectedDeviceLotSet,
    isDeviceSelected,
    toggleDeviceSelect,
    clearDeviceSelection,
    addDeviceLots,
    removeDeviceLots
  }
}
