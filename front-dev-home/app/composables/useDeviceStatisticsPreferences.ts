export type DeviceFab = 'R3' | 'M11' | 'M12' | 'M14' | 'M15' | 'M16'

export const DEFAULT_DEVICE_FAB: DeviceFab = 'R3'

const DEVICE_FABS = new Set<DeviceFab>(['R3', 'M11', 'M12', 'M14', 'M15', 'M16'])
const STORAGE_KEYS = {
  fab: 'skewnono:deviceStatistics.selectedFab',
  categories: 'skewnono:deviceStatistics.selectedProdCategories',
  lots: 'skewnono:deviceStatistics.selectedLots',
  techs: 'skewnono:deviceStatistics.selectedTechs'
} as const

export const isDeviceFab = (value: string): value is DeviceFab =>
  DEVICE_FABS.has(value as DeviceFab)

const readFab = (): DeviceFab => {
  if (!import.meta.client) return DEFAULT_DEVICE_FAB
  try {
    const value = window.localStorage.getItem(STORAGE_KEYS.fab) as DeviceFab | null
    return value && DEVICE_FABS.has(value) ? value : DEFAULT_DEVICE_FAB
  } catch {
    return DEFAULT_DEVICE_FAB
  }
}

const readStringArray = (key: string): string[] => {
  if (!import.meta.client) return []
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === 'string')
      : []
  } catch {
    return []
  }
}

const persistArray = (key: string, values: string[]) => {
  if (!import.meta.client) return
  try {
    if (values.length === 0) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, JSON.stringify(values))
  } catch { /* persistence is best-effort */ }
}

export const useDeviceStatisticsPreferences = () => {
  const selectedFab = ref<DeviceFab>(readFab())
  const selectedProdCategories = ref<string[]>(readStringArray(STORAGE_KEYS.categories))
  const selectedLots = ref<string[]>(readStringArray(STORAGE_KEYS.lots))
  const selectedTechs = ref<string[]>(readStringArray(STORAGE_KEYS.techs))

  watch(selectedFab, (value) => {
    if (!import.meta.client) return
    try {
      window.localStorage.setItem(STORAGE_KEYS.fab, value)
    } catch { /* persistence is best-effort */ }
  })
  watch(selectedProdCategories, value => persistArray(STORAGE_KEYS.categories, value))
  watch(selectedLots, value => persistArray(STORAGE_KEYS.lots, value))
  watch(selectedTechs, value => persistArray(STORAGE_KEYS.techs, value))

  return {
    selectedFab,
    selectedProdCategories,
    selectedLots,
    selectedTechs
  }
}
