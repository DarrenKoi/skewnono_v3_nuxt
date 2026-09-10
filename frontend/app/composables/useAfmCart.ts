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
  tools: string[]
  createdAt: string
  itemCount: number
}

const MAX_HISTORY = 10
const MAX_SAVED_GROUPS = 10
const MAX_RECENT_SEARCHES = 5

type StorageKind = 'viewHistory' | 'groupedData' | 'savedGroups' | 'recentSearches'
const storageKey = (kind: StorageKind, toolId: string) => `skewnono:afm.${kind}.${toolId}`

const arrayOf = <T>(parsed: unknown): T[] => Array.isArray(parsed) ? parsed as T[] : []

const persistedSlice = <T>(kind: StorageKind, stateKind: string, toolId: string) =>
  usePersistedState<T[]>(
    `afm-cart:${stateKind}:${toolId}`,
    storageKey(kind, toolId),
    { default: () => [], normalize: arrayOf<T> }
  )

function generateId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export const useAfmCart = (toolId: string) => {
  const viewHistory = persistedSlice<AfmHistoryEntry>('viewHistory', 'viewHistory', toolId)
  const groupedData = persistedSlice<AfmGroupedEntry>('groupedData', 'grouped', toolId)
  const savedGroups = persistedSlice<AfmSavedGroup>('savedGroups', 'saved', toolId)
  const recentSearches = persistedSlice<string>('recentSearches', 'recent', toolId)

  const groupedFilenames = computed(() => new Set(groupedData.value.map(item => item.filename)))
  const isInGroup = (filename: string) => groupedFilenames.value.has(filename)

  const addToHistory = (measurement: AfmMeasurement) => {
    const next = viewHistory.value.filter(item => item.filename !== measurement.filename)
    next.unshift({ ...measurement, toolId, viewedAt: new Date().toISOString() })
    viewHistory.value = next.slice(0, MAX_HISTORY)
  }

  const removeFromHistory = (filename: string) => {
    viewHistory.value = viewHistory.value.filter(item => item.filename !== filename)
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

  const clearGroup = () => {
    groupedData.value = []
  }

  const saveCurrentGroup = (name: string, description = '') => {
    if (groupedData.value.length === 0) return
    const snapshot: AfmSavedGroup = {
      id: generateId(),
      name: name.trim() || `Group ${new Date().toLocaleString()}`,
      description: description.trim(),
      items: [...groupedData.value],
      tools: Array.from(new Set(groupedData.value.map(item => item.toolId))),
      createdAt: new Date().toISOString(),
      itemCount: groupedData.value.length
    }
    const deduped = savedGroups.value.filter(group => group.name !== snapshot.name)
    savedGroups.value = [snapshot, ...deduped].slice(0, MAX_SAVED_GROUPS)
  }

  const loadSavedGroup = (groupId: string) => {
    const found = savedGroups.value.find(group => group.id === groupId)
    if (found) groupedData.value = [...found.items]
  }

  const removeSavedGroup = (groupId: string) => {
    savedGroups.value = savedGroups.value.filter(group => group.id !== groupId)
  }

  const clearSavedGroups = () => {
    savedGroups.value = []
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
    removeFromHistory,
    clearHistory,
    addToGroup,
    removeFromGroup,
    clearGroup,
    saveCurrentGroup,
    loadSavedGroup,
    removeSavedGroup,
    clearSavedGroups,
    recordRecentSearch,
    clearRecentSearches
  }
}
