import { usePersistedState } from '~/composables/usePersistedState'
import { DEFAULT_WINDOW_WEEKS, normalizeWindowWeeks, type WindowWeeks } from '~/utils/analysisWindow'

// Per-(toolType, fab) TTTM settings: which tools the user compares, which
// recipe, and how far back to gather. Survives a reload because these are a
// working setup, not a filter you re-pick every visit.
//
// One storage entry holding a map, rather than one entry per fab: the scope
// changes as the user moves between fabs, and usePersistedState binds its
// writer to a fixed key at call time, so a key built from a reactive scope
// would register a fresh writer per fab visited and leave the earlier ones
// live. The map keeps exactly one writer for the whole feature.

export interface TttmScopeSettings {
  /** Selected eqp_ids. EMPTY MEANS ALL — see resolveSelection in utils/tttmFleetSubset. */
  tools: string[]
  /** null = every recipe the server chooses to answer with. */
  recipeId: string | null
  /**
   * One measured feature of `recipeId`, or null to fold every feature together.
   *
   * Meaningless without a recipe — the same parameter name in another recipe
   * measures something else — so `setRecipe` clears it and the API layer
   * refuses to send it alone. Stored beside the recipe rather than in a second
   * entry because the two are one scope: a reload that restored the parameter
   * but not its recipe would name a feature of a recipe nobody picked.
   */
  parameter: string | null
  /**
   * How many weeks of runs the server gathers — one of WINDOW_WEEKS, sent as
   * `window_weeks` on the check, the recipe picker AND pm-tune's fleet fetch.
   * Part of the shared scope rather than a per-page setting because the two
   * pages describe ONE group: a 1-week group on TTTM and a 3-week group on
   * PM 튜닝 would be two different groups under one name.
   */
  windowWeeks: WindowWeeks
}

export type TttmSettingsMap = Record<string, TttmScopeSettings>

const STORAGE_KEY = 'tttm-settings'

export const tttmScopeKey = (toolType: string, fabName: string) =>
  `${toolType}:${fabName.toUpperCase()}`

const EMPTY: TttmScopeSettings = {
  tools: [],
  recipeId: null,
  parameter: null,
  windowWeeks: DEFAULT_WINDOW_WEEKS
}

// localStorage is user-writable and survives deploys, so anything read back has
// to be treated as untrusted rather than as the shape we last wrote.
const normalizeScope = (raw: unknown): TttmScopeSettings => {
  if (typeof raw !== 'object' || raw === null) return { ...EMPTY }
  const value = raw as Partial<TttmScopeSettings>
  const recipeId = typeof value.recipeId === 'string' ? value.recipeId : null
  return {
    tools: Array.isArray(value.tools) ? value.tools.filter(t => typeof t === 'string') : [],
    recipeId,
    // Dropped when the recipe did not survive normalisation: a parameter
    // without its recipe is a feature name with nothing to resolve it against,
    // and the server 400s on the pair. Entries written before this field
    // existed simply have no `parameter`, which lands here as null.
    parameter: recipeId && typeof value.parameter === 'string' ? value.parameter : null,
    // Entries written before this field existed land here as the default;
    // a hand-edited value outside the choices does too, rather than 400ing.
    windowWeeks: normalizeWindowWeeks(value.windowWeeks)
  }
}

const normalizeMap = (raw: unknown): TttmSettingsMap => {
  if (typeof raw !== 'object' || raw === null) return {}
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>).map(([key, scope]) => [key, normalizeScope(scope)])
  )
}

export const useTttmSettings = () => {
  const all = usePersistedState<TttmSettingsMap>(
    'tttm-settings-store',
    STORAGE_KEY,
    {
      default: () => ({}),
      normalize: normalizeMap,
      isEmpty: value => Object.keys(value).length === 0
    }
  )

  const read = (toolType: string, fabName: string): TttmScopeSettings =>
    all.value[tttmScopeKey(toolType, fabName)] ?? { ...EMPTY }

  const write = (toolType: string, fabName: string, next: TttmScopeSettings) => {
    // Replace the object rather than mutating it: usePersistedState watches the
    // ref, and an in-place edit of a nested value would not trip the watcher.
    all.value = { ...all.value, [tttmScopeKey(toolType, fabName)]: next }
  }

  const setTools = (toolType: string, fabName: string, tools: string[]) =>
    write(toolType, fabName, { ...read(toolType, fabName), tools })

  // Changing the recipe CLEARS the parameter rather than carrying it across:
  // parameter names are recipe-local, so "Para_13" in the recipe just picked is
  // a different feature from the "Para_13" the user was looking at — and it may
  // not exist there at all. Silently keeping it would relabel the group.
  const setRecipe = (toolType: string, fabName: string, recipeId: string | null) =>
    write(toolType, fabName, { ...read(toolType, fabName), recipeId, parameter: null })

  const setParameter = (toolType: string, fabName: string, parameter: string | null) => {
    const current = read(toolType, fabName)
    // No recipe, no parameter — refused rather than clamped, the same way
    // ScopeBar refuses to drop below two tools.
    if (!current.recipeId) return
    write(toolType, fabName, { ...current, parameter })
  }

  // The window outlives a recipe change: it is a statement about evidence,
  // not about the recipe, and the recipe picker itself is re-fetched under it.
  const setWindow = (toolType: string, fabName: string, windowWeeks: WindowWeeks) =>
    write(toolType, fabName, { ...read(toolType, fabName), windowWeeks })

  return { all, read, write, setTools, setRecipe, setParameter, setWindow }
}
