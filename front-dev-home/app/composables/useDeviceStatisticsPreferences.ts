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

const stringArrayPref = (stateKey: string, storageKey: string) =>
  usePersistedState<string[]>(stateKey, storageKey, {
    default: () => [],
    normalize: normalizeStringArray
  })

export const useDeviceStatisticsPreferences = () => {
  // The fab is stored as a raw string (not JSON) and always kept in storage.
  const selectedFab = usePersistedState<DeviceFab>(
    'device-stats:selectedFab',
    STORAGE_KEYS.fab,
    {
      default: () => DEFAULT_DEVICE_FAB,
      normalize: parsed =>
        typeof parsed === 'string' && isDeviceFab(parsed) ? parsed : DEFAULT_DEVICE_FAB,
      isEmpty: () => false,
      serialize: value => value,
      deserialize: raw => raw
    }
  )
  const selectedProdCategories = stringArrayPref('device-stats:prodCategories', STORAGE_KEYS.categories)
  const selectedLots = stringArrayPref('device-stats:lots', STORAGE_KEYS.lots)
  const selectedTechs = stringArrayPref('device-stats:techs', STORAGE_KEYS.techs)

  return {
    selectedFab,
    selectedProdCategories,
    selectedLots,
    selectedTechs
  }
}
