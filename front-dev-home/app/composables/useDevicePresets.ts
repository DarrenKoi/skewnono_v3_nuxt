// Mirrors the localStorage-backed useState pattern in useDeviceCart.ts.

const STORAGE_KEY = 'skewnono:deviceStatistics.presets'

export interface DevicePreset {
  id: string
  name: string
  comments: string
  lots: string[]
  createdAt: string
  fab?: string
}

const persistenceScope = effectScope(true)
let persistenceWatcherAttached = false

const isPreset = (value: unknown): value is DevicePreset => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.id === 'string'
    && typeof record.name === 'string'
    && typeof record.comments === 'string'
    && Array.isArray(record.lots)
    && record.lots.every(lot => typeof lot === 'string')
    && typeof record.createdAt === 'string'
    && (record.fab === undefined || typeof record.fab === 'string')
}

const readSavedPresets = (): DevicePreset[] => {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(isPreset) : []
  } catch {
    return []
  }
}

const persistPresets = (values: DevicePreset[]) => {
  if (typeof window === 'undefined') return
  try {
    if (values.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(values))
    }
  } catch { /* noop */ }
}

const generateId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export const useDevicePresets = () => {
  const presets = useState<DevicePreset[]>(
    'device-presets:list',
    () => readSavedPresets()
  )

  if (!persistenceWatcherAttached) {
    persistenceWatcherAttached = true
    persistenceScope.run(() => {
      watch(presets, next => persistPresets(next))
    })
  }

  const addPreset = (input: { name: string, comments: string, lots: string[], fab?: string }): DevicePreset => {
    const preset: DevicePreset = {
      id: generateId(),
      name: input.name.trim(),
      comments: input.comments.trim(),
      lots: [...input.lots],
      createdAt: new Date().toISOString(),
      fab: input.fab
    }
    presets.value = [preset, ...presets.value]
    return preset
  }

  const removePreset = (id: string) => {
    presets.value = presets.value.filter(preset => preset.id !== id)
  }

  const findPreset = (id: string): DevicePreset | undefined => {
    return presets.value.find(preset => preset.id === id)
  }

  return {
    presets,
    addPreset,
    removePreset,
    findPreset
  }
}
