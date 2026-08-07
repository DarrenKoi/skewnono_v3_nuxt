export type RecipeSearchSource = 'redis' | 'opensearch'

export interface RecipeSelectionEntry {
  name: string
  fab_name: string
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

/** Same `${fab}|${name}` pairing recipeSearchMatch's toRecipeSearchResults
 * uses for its dedupe key — one convention across both utils. */
const entryKey = (name: string, fabName: string) => `${fabName}|${name}`

const toEntry = (value: unknown): RecipeSelectionEntry | null => {
  if (typeof value === 'string') {
    const name = value.trim()
    return name ? { name, fab_name: '', source: 'redis' } : null
  }
  if (!value || typeof value !== 'object') return null

  const candidate = value as Record<string, unknown>
  const name = typeof candidate.name === 'string' ? candidate.name.trim() : ''
  const fabName = typeof candidate.fab_name === 'string' ? candidate.fab_name.trim().toUpperCase() : ''
  return name && isSource(candidate.source)
    ? { name, fab_name: fabName, source: candidate.source }
    : null
}

export const normalizeRecipeSelectionEntries = (
  parsed: unknown
): RecipeSelectionEntry[] => {
  if (!Array.isArray(parsed)) return []
  const byKey = new Map<string, RecipeSelectionEntry>()
  for (const value of parsed) {
    const entry = toEntry(value)
    if (!entry) continue
    const key = entryKey(entry.name, entry.fab_name)
    const existing = byKey.get(key)
    if (!existing || entry.source === 'redis') byKey.set(key, entry)
  }
  return [...byKey.values()]
}

export const upsertRecipeSelection = (
  entries: RecipeSelectionEntry[],
  rawName: string,
  fabName: string,
  source: RecipeSearchSource
): RecipeSelectionEntry[] => {
  const name = rawName.trim()
  if (!name) return entries
  const key = entryKey(name, fabName)
  const index = entries.findIndex(entry => entryKey(entry.name, entry.fab_name) === key)
  if (index < 0) return [...entries, { name, fab_name: fabName, source }]
  if (entries[index]!.source === 'redis' || source === 'opensearch') return entries
  return entries.map((entry, at) => at === index ? { name, fab_name: fabName, source: 'redis' } : entry)
}

export const removeRecipeSelection = (
  entries: RecipeSelectionEntry[],
  name: string,
  fabName: string
): RecipeSelectionEntry[] => {
  const key = entryKey(name, fabName)
  return entries.filter(entry => entryKey(entry.name, entry.fab_name) !== key)
}

export const promoteRecipeSelectionsToRedis = (
  entries: RecipeSelectionEntry[],
  rows: Array<{ recipe_name: string, fab_name: string }>
): RecipeSelectionEntry[] => {
  const fabByName = new Map<string, string>()
  for (const row of rows) {
    if (!fabByName.has(row.recipe_name)) fabByName.set(row.recipe_name, row.fab_name)
  }
  let changed = false
  const next = entries.map((entry) => {
    if (entry.source === 'opensearch' && fabByName.has(entry.name)) {
      changed = true
      return { ...entry, fab_name: fabByName.get(entry.name)!, source: 'redis' as const }
    }
    return entry
  })
  return changed ? normalizeRecipeSelectionEntries(next) : entries
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

export const recipesForCompare = (
  entries: RecipeSelectionEntry[]
): Array<{ recipe_name: string, fab_name: string }> | null =>
  canCompareRecipeSelection(entries)
    ? entries.map(entry => ({ recipe_name: entry.name, fab_name: entry.fab_name }))
    : null
