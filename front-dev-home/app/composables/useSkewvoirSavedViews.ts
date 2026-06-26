import type { LocationQueryRaw } from 'vue-router'
import type { MeasHistToolType } from '~/composables/useMeasHistApi'

// A named, shareable analysis bookmark. `query` is the full analysis-link query
// (lot/recipe/eq/mp/view) so restoring a saved view is just navigateTo(query).
export interface SkewvoirSavedView {
  id: string
  name: string
  toolType: MeasHistToolType
  query: LocationQueryRaw
  createdBy: string
  createdAt: string
}

const STORAGE_KEY = 'skewvoir-saved-views'

// Phase 1 persists to localStorage (fully offline). Phase 2/3 swap the read/write
// internals for a `saved_views` Flask blueprint so views are shared across people
// — this composable's surface stays identical, per the cross-phase principle.
// createdBy is a Phase-1 placeholder; Phase 2/3 replaces it with the real user.
const CURRENT_USER = 'me'

const readAll = (): SkewvoirSavedView[] => {
  if (!import.meta.client) return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? (parsed as SkewvoirSavedView[]) : []
  } catch {
    return []
  }
}

const writeAll = (views: SkewvoirSavedView[]) => {
  if (!import.meta.client) return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(views))
}

export const useSkewvoirSavedViews = (toolType: MeasHistToolType) => {
  // Shared reactive store across consumers of the same tool within a session.
  const all = useState<SkewvoirSavedView[]>('skewvoir-saved-views-store', () => readAll())

  const views = computed(() => all.value.filter(v => v.toolType === toolType))

  const refresh = () => {
    all.value = readAll()
  }

  const save = (name: string, query: LocationQueryRaw): SkewvoirSavedView => {
    const trimmed = name.trim() || 'Untitled view'
    // Stable-enough id without Date.now()/Math.random() coupling at module load.
    const id = `${toolType}-${trimmed}-${all.value.length}-${new Date().getTime()}`
    const view: SkewvoirSavedView = {
      id,
      name: trimmed,
      toolType,
      query,
      createdBy: CURRENT_USER,
      createdAt: new Date().toISOString()
    }
    all.value = [view, ...all.value]
    writeAll(all.value)
    return view
  }

  const remove = (id: string) => {
    all.value = all.value.filter(v => v.id !== id)
    writeAll(all.value)
  }

  return { views, refresh, save, remove }
}
