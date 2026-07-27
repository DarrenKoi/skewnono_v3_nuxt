export type RecipeSearchSource = 'redis' | 'opensearch'

export interface RecipeSelectionEntry {
  name: string
  source: RecipeSearchSource
}

export interface RecipeSelectionCapabilities {
  open: boolean
  lateral: boolean
  measHist: boolean
  compare: boolean
}

const isSource = (value: unknown): value is RecipeSearchSource =>
  value === 'redis' || value === 'opensearch'

const toEntry = (value: unknown): RecipeSelectionEntry | null => {
  if (typeof value === 'string') {
    const name = value.trim()
    return name ? { name, source: 'redis' } : null
  }
  if (!value || typeof value !== 'object') return null

  const candidate = value as Record<string, unknown>
  const name = typeof candidate.name === 'string' ? candidate.name.trim() : ''
  return name && isSource(candidate.source)
    ? { name, source: candidate.source }
    : null
}

export const normalizeRecipeSelectionEntries = (
  parsed: unknown
): RecipeSelectionEntry[] => {
  if (!Array.isArray(parsed)) return []
  const byName = new Map<string, RecipeSelectionEntry>()
  for (const value of parsed) {
    const entry = toEntry(value)
    if (!entry) continue
    const existing = byName.get(entry.name)
    if (!existing || entry.source === 'redis') byName.set(entry.name, entry)
  }
  return [...byName.values()]
}

export const upsertRecipeSelection = (
  entries: RecipeSelectionEntry[],
  rawName: string,
  source: RecipeSearchSource
): RecipeSelectionEntry[] => {
  const name = rawName.trim()
  if (!name) return entries
  const index = entries.findIndex(entry => entry.name === name)
  if (index < 0) return [...entries, { name, source }]
  if (entries[index]!.source === 'redis' || source === 'opensearch') return entries
  return entries.map((entry, at) => at === index ? { name, source: 'redis' } : entry)
}

export const removeRecipeSelection = (
  entries: RecipeSelectionEntry[],
  name: string
): RecipeSelectionEntry[] => entries.filter(entry => entry.name !== name)

export const promoteRecipeSelectionsToRedis = (
  entries: RecipeSelectionEntry[],
  redisNames: string[]
): RecipeSelectionEntry[] => {
  const catalog = new Set(redisNames)
  let changed = false
  const next = entries.map((entry) => {
    if (entry.source === 'opensearch' && catalog.has(entry.name)) {
      changed = true
      return { ...entry, source: 'redis' as const }
    }
    return entry
  })
  return changed ? next : entries
}

export const capabilitiesForRecipeSelection = (
  entries: RecipeSelectionEntry[]
): RecipeSelectionCapabilities => {
  if (!entries.length) {
    return { open: false, lateral: false, measHist: false, compare: false }
  }
  const redisOnly = entries.every(entry => entry.source === 'redis')
  return { open: redisOnly, lateral: true, measHist: true, compare: redisOnly }
}

export const canCompareRecipeSelection = (
  entries: RecipeSelectionEntry[]
): boolean => entries.length >= 2 && capabilitiesForRecipeSelection(entries).compare
