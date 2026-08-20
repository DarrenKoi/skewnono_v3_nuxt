import { normalizeFab } from '~/utils/fab'

export type DeviceFab = 'R3' | 'M10' | 'M11' | 'M14' | 'M15' | 'M16'

export const DEFAULT_DEVICE_FAB: DeviceFab = 'R3'

const DEVICE_FABS = new Set<DeviceFab>(['R3', 'M10', 'M11', 'M14', 'M15', 'M16'])
const STORAGE_KEYS = {
  fab: 'skewnono:deviceStatistics.selectedFab',
  categories: 'skewnono:deviceStatistics.selectedProdCategories',
  lots: 'skewnono:deviceStatistics.selectedLots',
  techs: 'skewnono:deviceStatistics.selectedTechs',
  judgeSons: 'skewnono:deviceStatistics.judgeSons'
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

  // 룰 판정에 son 파라미터를 포함할지. 룰 화면과 비교 화면이 **한 값을** 봐야
  // 합니다 — 같은 lot 을 두고 두 화면이 다른 위반 수를 말하던 자리가 이미
  // 있었습니다(ComplianceTable 의 모집단 주석). 화면마다 토글을 두면 그 차이가
  // 되돌아옵니다.
  const judgeSons = usePersistedState<boolean>(
    'device-stats:judgeSons',
    STORAGE_KEYS.judgeSons,
    {
      default: () => true,
      normalize: parsed => parsed === false ? false : true
    }
  )

  return {
    selectedFab,
    selectedProdCategories,
    selectedLots,
    selectedTechs,
    judgeSons
  }
}
