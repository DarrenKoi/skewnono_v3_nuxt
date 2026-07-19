// Cart of selected device lots, shared between the device-statistics list page and its comparison
// sub-page. Backed by usePersistedState: one useState ref across client-side navigation,
// localStorage persists across full reloads / direct URL hits.

export const useDeviceCart = () => {
  const selectedDeviceLots = usePersistedState<string[]>(
    'device-cart:selectedLots',
    'skewnono:deviceStatistics.selectedDeviceLots',
    { default: () => [], normalize: normalizeStringArray }
  )

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
