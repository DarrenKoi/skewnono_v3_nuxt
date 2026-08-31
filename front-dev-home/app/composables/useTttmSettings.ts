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
  /**
   * Selected eqp_ids. NULL MEANS ALL, EMPTY MEANS NONE — see resolveSelection
   * in utils/tttmFleetSubset. Empty is what 해제 on the last model group
   * leaves; it is not persisted as a working setup (a reload normalises it
   * back to all), because nobody reopens the page to compare nothing.
   */
  tools: string[] | null
  /** null = every recipe the server chooses to answer with. */
  recipeId: string | null
  /**
   * Measured features of `recipeId` to fold — empty folds every feature.
   *
   * Meaningless without a recipe — the same parameter name in another recipe
   * measures something else — so `setRecipe` clears them and the API layer
   * refuses to send them alone. Stored beside the recipe rather than in a
   * second entry because the two are one scope: a reload that restored the
   * parameters but not their recipe would name features of a recipe nobody
   * picked. Several rather than one since 2026-08-27: the N배화 group is
   * "tools that match on each of these", and the map is PCA over them.
   */
  parameters: string[]
  /**
   * How many weeks of runs the server gathers — one of WINDOW_WEEKS, sent as
   * `window_weeks` on the check, the recipe picker AND the pm_planning fleet
   * fetch. One setting rather than one per request because every panel
   * describes ONE group: a 1-week group in the 스큐 cards and a 3-week group in
   * the PM 튜닝 cards would be two different groups under one name.
   */
  windowWeeks: WindowWeeks
  /**
   * The N배화 판정 임계값 in nm, as the tolerance knob leaves it. Null until the
   * user moves it, and the payload's own `current_tolerance` stands in.
   *
   * Shared for exactly the reason `windowWeeks` is: a 0.05 nm group in the
   * 스큐 cards and a 0.08 nm group in the PM 튜닝 cards would be two different
   * groups under one name. It was a per-page `ref` until 2026-08-30, which is
   * why the old PM 플래닝 page had to caption "tolerance 는 TTTM 페이지의
   * 설정을 따릅니다" three times over — and then quietly use the server default
   * anyway, because a local ref cannot cross a route.
   */
  tolerance: number | null
}

export type TttmSettingsMap = Record<string, TttmScopeSettings>

const STORAGE_KEY = 'tttm-settings'

export const tttmScopeKey = (toolType: string, fabName: string) =>
  `${toolType}:${fabName.toUpperCase()}`

const EMPTY: TttmScopeSettings = {
  tools: null,
  recipeId: null,
  parameters: [],
  windowWeeks: DEFAULT_WINDOW_WEEKS,
  tolerance: null
}

const strings = (raw: unknown): string[] =>
  Array.isArray(raw) ? raw.filter((t): t is string => typeof t === 'string') : []

// localStorage is user-writable and survives deploys, so anything read back has
// to be treated as untrusted rather than as the shape we last wrote.
const normalizeScope = (raw: unknown): TttmScopeSettings => {
  if (typeof raw !== 'object' || raw === null) return { ...EMPTY }
  const value = raw as Partial<TttmScopeSettings>
  const recipeId = typeof value.recipeId === 'string' ? value.recipeId : null
  const tools = strings(value.tools)
  // Entries written while `[]` meant all (before 2026-08-27) — and a
  // deliberately emptied selection — both land as "all": neither is a
  // working setup worth restoring as "compare nothing".
  const legacyParameter = (value as { parameter?: unknown }).parameter
  const parameters = strings(value.parameters).concat(
    typeof legacyParameter === 'string' ? [legacyParameter] : []
  )
  return {
    tools: tools.length ? tools : null,
    recipeId,
    // Dropped when the recipe did not survive normalisation: a parameter
    // without its recipe is a feature name with nothing to resolve it against,
    // and the server 400s on the pair. Entries written before the list
    // existed carried one `parameter`, folded in above so a working pick
    // survives the upgrade.
    parameters: recipeId ? parameters : [],
    // Entries written before this field existed land here as the default;
    // a hand-edited value outside the choices does too, rather than 400ing.
    windowWeeks: normalizeWindowWeeks(value.windowWeeks),
    // A knob position, so any finite positive number is legitimate here. It is
    // NOT clamped to the slider's range: that range arrives on the payload and
    // varies with the answer, so clamping is the view's job at the moment it
    // has one — clamping to a guess here would rewrite a good stored value.
    tolerance: typeof value.tolerance === 'number' && Number.isFinite(value.tolerance) && value.tolerance > 0
      ? value.tolerance
      : null
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

  const setTools = (toolType: string, fabName: string, tools: string[] | null) =>
    write(toolType, fabName, { ...read(toolType, fabName), tools })

  // Changing the recipe CLEARS the parameter rather than carrying it across:
  // parameter names are recipe-local, so "Para_13" in the recipe just picked is
  // a different feature from the "Para_13" the user was looking at — and it may
  // not exist there at all. Silently keeping it would relabel the group.
  const setRecipe = (toolType: string, fabName: string, recipeId: string | null) =>
    write(toolType, fabName, { ...read(toolType, fabName), recipeId, parameters: [] })

  const setParameters = (toolType: string, fabName: string, parameters: string[]) => {
    const current = read(toolType, fabName)
    // No recipe, no parameters — refused rather than clamped: a parameter
    // name is recipe-local and the server 400s on the pair.
    if (!current.recipeId) return
    write(toolType, fabName, { ...current, parameters })
  }

  // The window outlives a recipe change: it is a statement about evidence,
  // not about the recipe, and the recipe picker itself is re-fetched under it.
  const setWindow = (toolType: string, fabName: string, windowWeeks: WindowWeeks) =>
    write(toolType, fabName, { ...read(toolType, fabName), windowWeeks })

  // Committed on the slider's `change` (pointer release), never on `input`:
  // this write replaces the whole scope object, which re-renders every control
  // reading it, and the range input fires on every drag frame.
  const setTolerance = (toolType: string, fabName: string, tolerance: number) =>
    write(toolType, fabName, { ...read(toolType, fabName), tolerance })

  return { all, read, write, setTools, setRecipe, setParameters, setWindow, setTolerance }
}
