// Per-metric radial axis overrides for the 360° beam-profile radars, persisted
// across reloads so a range set once stays set.
//
// Keyed by canonical metric — not by tool or tab — because the band an
// engineer reads `reso_eb` against is a property of the measurement, not of
// which page they opened. One entry therefore serves 데일리 Sharpness and 분기
// BSM alike.

import { canonicalMetricKey, isValidRange, type AxisRange } from '~/utils/profileAxisRange'

const STATE_KEY = 'profile-axis-range'
const STORAGE_KEY = 'sk-profile-axis-range'

type RangeMap = Record<string, AxisRange>

// Storage is user-editable and survives across app versions, so every entry is
// re-validated on read; anything malformed is dropped rather than trusted.
const normalize = (parsed: unknown): RangeMap => {
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  const out: RangeMap = {}
  for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) continue
    const { min, max } = value as { min?: unknown, max?: unknown }
    const range = { min: Number(min), max: Number(max) }
    if (isValidRange(range)) out[canonicalMetricKey(key)] = range
  }
  return out
}

export const useProfileAxisRange = () => {
  const overrides = usePersistedState<RangeMap>(STATE_KEY, STORAGE_KEY, {
    default: () => ({}),
    normalize,
    isEmpty: value => Object.keys(value).length === 0
  })

  const rangeFor = (metric: string): AxisRange | null =>
    overrides.value[canonicalMetricKey(metric)] ?? null

  // Replaces the map rather than mutating it: usePersistedState watches the
  // ref shallowly, so an in-place property write would never reach storage.
  // Clearing rebuilds without the key, so a reset leaves no empty entry behind
  // (an all-empty map is what makes usePersistedState drop the storage key).
  const setRange = (metric: string, range: AxisRange | null) => {
    const key = canonicalMetricKey(metric)
    const rest = Object.fromEntries(Object.entries(overrides.value).filter(([k]) => k !== key))
    overrides.value = isValidRange(range) ? { ...rest, [key]: range } : rest
  }

  return { overrides, rangeFor, setRange }
}
