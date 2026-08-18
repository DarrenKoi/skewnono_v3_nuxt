// Shared factory for localStorage-persisted useState refs.
//
// One `useState` ref per stateKey is shared across client-side navigation; a
// watcher hosted in a detached effect scope (so it survives component
// unmounts) persists every mutation to localStorage. `flush: 'sync'` makes an
// acknowledged user action (add/remove/save) durable before the next event
// loop tick — a tab close right after the click cannot silently drop it.
//
// Watchers live for the lifetime of the SPA — bounded by the distinct
// stateKeys a session touches (tool/fab combinations), no disposal needed.

// NORMALIZE GUARDS THE SHAPE, NOT THE VALUE. `normalize` runs on read and can
// only ask "is this the structure we store?". If a stored value NAMES something
// a server catalogue offers — a recipe, a tool id, a filter option — it can also
// go stale while the shape stays perfect, and nothing here will notice. Whoever
// stores such a value owns reconciling it once that catalogue has answered:
//   - useTttmScope / utils/tttmRecipeScope — one id, cleared by a watcher
//   - utils/tttmFleetSubset resolveSelection — a list, resolved at read time
//   - useMeasHistSearch / utils/measHistCascade — cascaded filters
// The three differ in what counts as "answered" (measHist reads empty facets as
// still-loading; tttm reads an empty array as an answer and null as loading),
// which is why this is a convention stated here rather than a hook offered here.

export interface PersistedStateOptions<T> {
  /** Initial value when storage is empty, unreadable, or fails validation. */
  default: () => T
  /** Validate/coerce the deserialized storage payload into a T. May throw —
   * the factory falls back to `default()`. */
  normalize: (parsed: unknown) => T
  /** When true the storage key is removed instead of written. Defaults to
   * "empty array" so vacant selections don't accumulate keys. */
  isEmpty?: (value: T) => boolean
  /** Storage encoding — defaults to JSON. Override both to store raw strings. */
  serialize?: (value: T) => string
  deserialize?: (raw: string) => unknown
}

const persistenceScope = effectScope(true)
const attachedStateKeys = new Set<string>()

export const usePersistedState = <T>(
  stateKey: string,
  storageKey: string,
  options: PersistedStateOptions<T>
): Ref<T> => {
  const isEmpty = options.isEmpty ?? ((value: T) => Array.isArray(value) && value.length === 0)
  const serialize = options.serialize ?? ((value: T) => JSON.stringify(value))
  const deserialize = options.deserialize ?? ((raw: string): unknown => JSON.parse(raw))

  const read = (): T => {
    if (!import.meta.client) return options.default()
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (raw === null) return options.default()
      return options.normalize(deserialize(raw))
    } catch {
      return options.default()
    }
  }

  const write = (value: T) => {
    if (!import.meta.client) return
    try {
      if (isEmpty(value)) {
        window.localStorage.removeItem(storageKey)
      } else {
        window.localStorage.setItem(storageKey, serialize(value))
      }
    } catch { /* localStorage can be unavailable in restricted browser contexts */ }
  }

  const state = useState<T>(stateKey, read)

  if (!attachedStateKeys.has(stateKey)) {
    attachedStateKeys.add(stateKey)
    persistenceScope.run(() => {
      watch(state, next => write(next), { flush: 'sync' })
    })
  }

  return state
}

// Common normalizer: keep only string entries of a JSON array.
export const normalizeStringArray = (parsed: unknown): string[] =>
  Array.isArray(parsed)
    ? parsed.filter((value): value is string => typeof value === 'string')
    : []
