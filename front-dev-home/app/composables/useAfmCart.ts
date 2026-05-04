// Per-tool AFM working set: viewed measurements, the current grouping cart, saved group
// snapshots, and recent search terms. Keyed by toolId so each AFM tool keeps its own state.
// Mirrors the useDeviceCart pattern: useState shares one ref across client-side navigation,
// and watchers in a detached effect scope persist to localStorage across full reloads.
// Watchers live for the lifetime of the SPA — bounded by tool count, no disposal needed.

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

const persistenceScope = effectScope(true)
const persistenceWatchers = new Set<string>()

function readJSON<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

// Synchronous: an acknowledged user action (add/remove/save) must be durable before the
// next event loop tick, otherwise a tab close mid-debounce silently drops the change.
function writeJSON(key: string, value: unknown) {
  if (typeof window === 'undefined') return
  try {
    if (Array.isArray(value) && value.length === 0) {
      window.localStorage.removeItem(key)
    } else {
      window.localStorage.setItem(key, JSON.stringify(value))
    }
  } catch { /* noop */ }
}

function generateId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export const useAfmCart = (toolId: string) => {
  const historyKey = storageKey('viewHistory', toolId)
  const groupedKey = storageKey('groupedData', toolId)
  const savedKey = storageKey('savedGroups', toolId)
  const recentKey = storageKey('recentSearches', toolId)

  const viewHistory = useState<AfmHistoryEntry[]>(
    `afm-cart:viewHistory:${toolId}`,
    () => readJSON<AfmHistoryEntry[]>(historyKey, [])
  )
  const groupedData = useState<AfmGroupedEntry[]>(
    `afm-cart:grouped:${toolId}`,
    () => readJSON<AfmGroupedEntry[]>(groupedKey, [])
  )
  const savedGroups = useState<AfmSavedGroup[]>(
    `afm-cart:saved:${toolId}`,
    () => readJSON<AfmSavedGroup[]>(savedKey, [])
  )
  const recentSearches = useState<string[]>(
    `afm-cart:recent:${toolId}`,
    () => readJSON<string[]>(recentKey, [])
  )

  if (!persistenceWatchers.has(toolId)) {
    persistenceWatchers.add(toolId)
    persistenceScope.run(() => {
      watch(viewHistory, next => writeJSON(historyKey, next))
      watch(groupedData, next => writeJSON(groupedKey, next))
      watch(savedGroups, next => writeJSON(savedKey, next))
      watch(recentSearches, next => writeJSON(recentKey, next))
    })
  }

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
