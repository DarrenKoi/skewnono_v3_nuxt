import { normalizeFab } from '~/utils/fab'

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

// Canonicalize before the guard, never inside it — a guard that accepted 'r3' would narrow
// the value to DeviceFab while leaving it lowercase. Values reach here from localStorage and
// from saved presets, and fab identity arrives in whichever case its source DB used.
export const toDeviceFab = (value: unknown): DeviceFab | null => {
  if (typeof value !== 'string') return null
  const canonical = normalizeFab(value)
  return isDeviceFab(canonical) ? canonical : null
}

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
      normalize: parsed => toDeviceFab(parsed) ?? DEFAULT_DEVICE_FAB,
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
