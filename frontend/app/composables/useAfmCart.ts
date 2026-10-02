// Per-tool AFM working set: viewed measurements, the current grouping cart, saved group
// snapshots, and recent search terms. Keyed by toolId so each AFM tool keeps its own state.
// Each slice is a usePersistedState ref: shared across client-side navigation, persisted
// to localStorage across full reloads (one watcher per tool×slice for the SPA lifetime).

export interface AfmMeasurement {
  filename: string
  recipeName: string
  lotId: string
  slotNumber: number | string
  measuredInfo: string
  formattedDate: string
  hasProfile?: boolean
  hasData?: boolean
  hasImage?: boolean
  hasAlign?: boolean
  hasTip?: boolean
}

export interface AfmHistoryEntry extends AfmMeasurement {
  toolId: string
  viewedAt: string
}

export interface AfmGroupedEntry extends AfmMeasurement {
  toolId: string
  addedAt: string
}

export interface AfmSavedGroup {
  id: string
  name: string
  description: string
  items: AfmGroupedEntry[]
  createdAt: string
}

const MAX_HISTORY = 10
const MAX_SAVED_GROUPS = 10
const MAX_RECENT_SEARCHES = 5

type StorageKind = 'viewHistory' | 'groupedData' | 'savedGroups' | 'recentSearches'

const persistedSlice = <T>(kind: StorageKind, toolId: string) =>
  usePersistedState<T[]>(
    `afm-cart:${kind}:${toolId}`,
    `skewnono:afm.${kind}.${toolId}`,
    { default: () => [], normalize: parsed => Array.isArray(parsed) ? parsed as T[] : [] }
  )

export const useAfmCart = (toolId: string) => {
  const viewHistory = persistedSlice<AfmHistoryEntry>('viewHistory', toolId)
  const groupedData = persistedSlice<AfmGroupedEntry>('groupedData', toolId)
  const savedGroups = persistedSlice<AfmSavedGroup>('savedGroups', toolId)
  const recentSearches = persistedSlice<string>('recentSearches', toolId)

  const groupedFilenames = computed(() => new Set(groupedData.value.map(item => item.filename)))
  const isInGroup = (filename: string) => groupedFilenames.value.has(filename)

  const addToHistory = (measurement: AfmMeasurement) => {
    const next = viewHistory.value.filter(item => item.filename !== measurement.filename)
    next.unshift({ ...measurement, toolId, viewedAt: new Date().toISOString() })
    viewHistory.value = next.slice(0, MAX_HISTORY)
  }

  const clearHistory = () => {
    viewHistory.value = []
  }

  const addToGroup = (measurement: AfmMeasurement) => {
    if (isInGroup(measurement.filename)) return
    groupedData.value = [
      ...groupedData.value,
      { ...measurement, toolId, addedAt: new Date().toISOString() }
    ]
  }

  const removeFromGroup = (filename: string) => {
    groupedData.value = groupedData.value.filter(item => item.filename !== filename)
  }

  const toggleGroup = (measurement: AfmMeasurement) =>
    isInGroup(measurement.filename) ? removeFromGroup(measurement.filename) : addToGroup(measurement)

  const clearGroup = () => {
    groupedData.value = []
  }

  // The save form is the only caller: it trims both fields and refuses an empty name.
  const saveCurrentGroup = (name: string, description: string) => {
    if (groupedData.value.length === 0) return
    const snapshot: AfmSavedGroup = {
      id: generateUuid(),
      name,
      description,
      items: [...groupedData.value],
      createdAt: new Date().toISOString()
    }
    const deduped = savedGroups.value.filter(group => group.name !== snapshot.name)
    savedGroups.value = [snapshot, ...deduped].slice(0, MAX_SAVED_GROUPS)
  }

  // `merge` keeps what is already in the group and appends only the new files.
  const loadSavedGroup = (groupId: string, merge = false) => {
    const found = savedGroups.value.find(group => group.id === groupId)
    if (!found) return
    groupedData.value = merge
      ? [...groupedData.value, ...found.items.filter(item => !isInGroup(item.filename))]
      : [...found.items]
  }

  const removeSavedGroup = (groupId: string) => {
    savedGroups.value = savedGroups.value.filter(group => group.id !== groupId)
  }

  const recordRecentSearch = (term: string) => {
    const trimmed = term.trim()
    if (trimmed.length < 2) return
    const next = [trimmed, ...recentSearches.value.filter(existing => existing !== trimmed)]
    recentSearches.value = next.slice(0, MAX_RECENT_SEARCHES)
  }

  const clearRecentSearches = () => {
    recentSearches.value = []
  }

  return {
    viewHistory,
    groupedData,
    savedGroups,
    recentSearches,
    isInGroup,
    addToHistory,
    clearHistory,
    addToGroup,
    removeFromGroup,
    toggleGroup,
    clearGroup,
    saveCurrentGroup,
    loadSavedGroup,
    removeSavedGroup,
    recordRecentSearch,
    clearRecentSearches
  }
}
