// Saved device-lot presets, persisted via usePersistedState (see useDeviceCart).

const STORAGE_KEY = 'skewnono:deviceStatistics.presets'

export interface DevicePreset {
  id: string
  name: string
  comments: string
  lots: string[]
  createdAt: string
  fab?: string
}

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

const generateId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export const useDevicePresets = () => {
  const presets = usePersistedState<DevicePreset[]>(
    'device-presets:list',
    STORAGE_KEY,
    {
      default: () => [],
      normalize: parsed => Array.isArray(parsed) ? parsed.filter(isPreset) : []
    }
  )

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
