import type { MeasHistFacetValue, MeasHistRow } from '~/composables/useMeasHistApi'
import {
  buildCascadedOptions,
  CATEGORY_TO_TOOL_TYPE,
  pruneCascadedFilters,
  type SkewvoirCategory
} from '~/utils/measHistCascade'
import { parseMeasHistQuery, resolveDateRange, stripDateTokens } from '~/utils/measHistQuery'
import { shiftIsoDate } from '../utils/dateTime'
import {
  DEFAULT_MEAS_HIST_SORT,
  isReordered,
  nextMeasHistSort,
  sortMeasHistRows,
  type MeasHistSort,
  type MeasHistSortKey
} from '~/utils/measHistSort'

// No `recipe` field: recipes are found via the search bar only (there is no
// RECIPE dropdown — see FilterBar.vue). Bare recipe fragments use `q`;
// explicit `recipe:value` tokens still reach the recipe request field.
// `category` holds 카테고리 display values ('CD-SEM' | 'HV-SEM'); exactly one
// pick scopes the request to that index, anything else searches both.
export interface MeasHistFilters {
  fab: string[]
  category: string[]
  model: string[]
  eq: string[]
  from: string
  to: string
}

// The option lists FilterBar renders — facet values narrowed by the cascade
// (FAB → 카테고리 → 장비 모델 → EQ, joined through sem_list).
export interface MeasHistFilterOptions {
  fab: MeasHistFacetValue[]
  category: MeasHistFacetValue[]
  model: MeasHistFacetValue[]
  eq: MeasHistFacetValue[]
}

const PAGE_SIZE = 50

// `toolType` keys the session state and NOTHING else — it never reaches
// buildParams. The search itself still always spans both SEM families unless
// the 카테고리 filter narrows it (the per-route tool type only scopes the
// workspace shell — recent items, selection — not the search itself). It is
// taken here for the same reason useSkewvoirSearchSelection takes it: the
// CD-SEM and HV-SEM landings are separate screens, and arriving at one should
// not show a session the user built on the other.
export const useMeasHistSearch = (toolType: MeasHistToolType) => {
  const { searchMeasHist } = useMeasHistApi()
  const { facets, pending: facetsPending, error: facetsError, known, anchor, retentionDays } = useMeasHistFacets()
  // Fleet table powering the dropdown cascade. Shares the app-wide 'sem-list'
  // cache; an empty list just degrades the cascade to un-narrowed options.
  const { data: semRows } = useSemList()

  // Fix 4: while `known.eq` is empty (facets still loading, or the fetch
  // failed outright), the parser's classify() has no eq list to match
  // against, so a perfectly valid equipment id like `ECDX160` falls through
  // to the terminal `recipe` branch — a substring query that returns zero
  // rows under a green RECIPE chip instead of the honest "can't recognize
  // equipment ids yet" it actually is. Spec §7 already disables the facet
  // *dropdowns* on load failure; disabling the search action too (smaller
  // change than a separate warning banner, and consistent with how
  // FilterBar already goes inert on the same signal) keeps the search bar
  // from ever silently misclassifying an eq token while facets aren't ready.
  const searchDisabled = computed(() => facetsPending.value || Boolean(facetsError.value))

  // A search session is SPA-scoped, not component-scoped. Opening a row
  // navigates to the analysis route, which unmounts SearchLanding — with plain
  // `ref`s every part of the session (typed query, dropdown picks, the rows
  // themselves) was rebuilt from scratch on the way back, so returning to pick
  // a second measurement meant retyping and re-searching. `useState` keeps
  // exactly one ref per key for the lifetime of the SPA, so the landing
  // re-mounts onto the session it left.
  //
  // Session state, not persisted: a reload starts clean. The curated selection
  // next door earns its localStorage (usePersistedState) by being a set the
  // user assembled deliberately; a result page is just the last thing the
  // backend said.
  const key = (name: string) => `meas-hist-search:${toolType}:${name}`

  const queryText = useState(key('query-text'), () => '')
  const narrowText = useState(key('narrow-text'), () => '')

  // The retention window is anchored to the backend's declared clock, never to
  // wall-clock today — the Phase 1 mock's data ends at a frozen NOW.
  const defaultRange = computed(() => ({
    start: anchor.value ? shiftIsoDate(anchor.value, retentionDays.value) : '',
    end: anchor.value
  }))

  const filters = useState<MeasHistFilters>(
    key('filters'),
    () => ({ fab: [], category: [], model: [], eq: [], from: '', to: '' })
  )

  // Cascaded dropdown options: FAB stays the full facet list (top of the
  // cascade); 카테고리/모델/EQ narrow as upstream picks land. The parser's
  // `known.eq` deliberately stays the UN-narrowed facet list — a typed eq
  // token must be recognized regardless of dropdown state.
  const filterOptions = computed<MeasHistFilterOptions>(() => {
    const cascaded = buildCascadedOptions(
      { model: facets.value.model, eq: facets.value.eq },
      semRows.value,
      { fab: filters.value.fab, category: filters.value.category, model: filters.value.model }
    )
    return { fab: facets.value.fab, ...cascaded }
  })

  // Chips render as you type — no round-trip needed to see how a token was read.
  const parsed = computed(() => parseMeasHistQuery(queryText.value, known.value))

  const rows = useState<MeasHistRow[]>(key('rows'), () => [])
  const total = useState(key('total'), () => 0)
  const capped = useState(key('capped'), () => false)
  const outOfRetention = useState(key('out-of-retention'), () => false)
  // A search still in flight when the user opens a row resolves into these
  // shared refs, not a discarded component's — so it keeps its spinner and
  // still lands its rows when they come back.
  const pending = useState(key('pending'), () => false)
  const error = useState<string | null>(key('error'), () => null)
  // False until the first search runs — drives the "type something" empty state.
  const searched = useState(key('searched'), () => false)

  const hasActiveFilters = computed(() =>
    filters.value.fab.length > 0
    || filters.value.category.length > 0
    || filters.value.model.length > 0
    || filters.value.eq.length > 0
    || Boolean(filters.value.from)
    || Boolean(filters.value.to)
  )

  const hasMore = computed(() => rows.value.length < Math.min(total.value, 10000))

  // Search-bar fields and dropdown fields feed the same request params.
  const union = (a: string[], b: string[]) => [...new Set([...a, ...b])]

  // Single source of truth for the effective date range — a `date:` token
  // wins over the 기간 dropdown (see resolveDateRange's doc comment / spec
  // §6.3). FilterBar renders this same value as its 기간 chip instead of
  // deriving its own, so the displayed range can never drift from the range
  // actually sent to the backend.
  const resolvedRange = computed(() =>
    resolveDateRange(
      parsed.value.date,
      filters.value.from,
      filters.value.to,
      defaultRange.value.start,
      defaultRange.value.end
    )
  )

  const buildParams = (offset: number) => {
    const p = parsed.value
    const { start: from, end: to } = resolvedRange.value

    // Exactly one 카테고리 pick scopes to that index; zero or both means the
    // backend searches meas_hist_cdsem AND meas_hist_hvsem together.
    const pickedTools = filters.value.category
      .map(category => CATEGORY_TO_TOOL_TYPE[category as SkewvoirCategory])
      .filter(Boolean)

    return {
      toolType: pickedTools.length === 1 ? pickedTools[0] : undefined,
      fab: filters.value.fab,
      model: filters.value.model,
      eq: union(filters.value.eq, p.eq),
      // No recipe dropdown to union in. Only an explicit `recipe:value` token
      // reaches this structured field; bare fragments use cross-field `q`.
      recipe: p.recipe,
      lot: p.lot,
      msr: p.msr,
      q: p.q,
      from,
      to,
      offset,
      limit: PAGE_SIZE
    }
  }

  // Which request currently owns the session refs. Needed because those refs
  // now outlive the component: a response that arrives after the user opened a
  // measurement no longer lands in a discarded ref, it lands in the one the
  // next visit is reading. The damaging case is a `loadMore` still in flight
  // when a row is opened — its `[...rows.value, ...res.rows]` would splice
  // old-query rows onto whatever the next search returned, under that search's
  // total. Every run claims a token; only the run still holding the newest one
  // is allowed to write.
  const requestToken = useState(key('request-token'), () => 0)

  const run = async (offset: number) => {
    const token = requestToken.value + 1
    requestToken.value = token
    pending.value = true
    error.value = null
    try {
      const res = await searchMeasHist(buildParams(offset))
      if (token !== requestToken.value) return
      rows.value = offset === 0 ? res.rows : [...rows.value, ...res.rows]
      total.value = res.total
      capped.value = res.capped
      outOfRetention.value = res.out_of_retention
    } catch {
      // Keep the current rows on failure — losing results to a transient blip
      // is worse than showing stale ones next to a retry.
      if (token !== requestToken.value) return
      error.value = '검색에 실패했습니다.'
    } finally {
      // Only the newest request owns the spinner. A superseded one clearing it
      // would report "done" while its replacement is still running.
      if (token === requestToken.value) pending.value = false
    }
  }

  // Explicit: Enter or the Search button. Searching per keystroke would fire a
  // full OpenSearch query for every character of a lot id. Also refuses while
  // facets aren't ready (Fix 4) — belt-and-suspenders alongside SearchBar's
  // own disabled state, since a search fired with an empty `known.eq` can
  // silently misclassify a valid eq token as a recipe substring.
  const search = async () => {
    if (searchDisabled.value) return
    searched.value = true
    narrowText.value = ''
    await run(0)
  }

  const loadMore = async () => {
    if (!hasMore.value || pending.value) return
    await run(rows.value.length)
  }

  // Instant, local narrowing of the rows already loaded. Never hits the network.
  const narrowedRows = computed(() => {
    const needle = narrowText.value.trim().toLowerCase()
    if (!needle) return rows.value
    return rows.value.filter(row =>
      row.lot_id.toLowerCase().includes(needle)
      || row.full_name.toLowerCase().includes(needle)
      || row.eqp_id.toLowerCase().includes(needle)
      || row.fab_name.toLowerCase().includes(needle)
    )
  })

  // Column ordering, applied on top of the narrowing above. Sorting after
  // narrowing is the correct order of the two: narrowing is a set operation and
  // sorting an ordering one, so doing it the other way would re-sort on every
  // keystroke of 결과 내 좁히기 for no change in the visible order.
  //
  // Session state like the rest of the search, so returning from an analysis
  // finds the table ordered the way it was left. Defaults to the backend's own
  // timestamp-desc, meaning nothing moves until a header is actually clicked.
  const sort = useState<MeasHistSort>(key('sort'), () => ({ ...DEFAULT_MEAS_HIST_SORT }))

  const sortedRows = computed(() => sortMeasHistRows(narrowedRows.value, sort.value))

  const toggleSort = (column: MeasHistSortKey) => {
    sort.value = nextMeasHistSort(sort.value, column)
  }

  // The sort covers only what has been LOADED. While more rows remain unfetched
  // and the user has moved off the backend's own order, the table is showing a
  // re-ordered page rather than a re-ordered result set — a difference the UI
  // has to state, since a `RECIPE ↑` header otherwise reads as authoritative
  // over all `total` hits. Clearing it is what 더 보기 is for.
  const sortIsPartial = computed(() => isReordered(sort.value) && hasMore.value)

  const resetFilters = () => {
    filters.value = { fab: [], category: [], model: [], eq: [], from: '', to: '' }
  }

  // A 기간 dropdown edit is "last write wins": it must not merely set
  // filters.from/to alongside a `date:` token that still sits in queryText,
  // or resolvedRange stays derived from that (unchanged) token, the popover
  // label snaps back to it on the next re-search, and hasActiveFilters lights
  // up 초기화 for a date the query silently ignores (see resolveDateRange's
  // precedence doc comment). Stripping the token first makes filters.from/to
  // the sole source of truth for resolvedRange again.
  const setDateRange = (range: { start: string, end: string }) => {
    queryText.value = stripDateTokens(queryText.value, parsed.value.date)
    filters.value = { ...filters.value, from: range.start, to: range.end }
  }

  const reset = () => {
    // Supersede any in-flight request first, so its response can't repopulate
    // the rows we are about to clear (and so its spinner stops with them).
    requestToken.value += 1
    pending.value = false
    queryText.value = ''
    narrowText.value = ''
    // Cleared here but deliberately NOT in `search()`: the sort is a view
    // preference over whatever the results are, so running a new query keeps
    // it, while an explicit full reset puts the table back to newest-first.
    sort.value = { ...DEFAULT_MEAS_HIST_SORT }
    resetFilters()
    rows.value = []
    total.value = 0
    capped.value = false
    outOfRetention.value = false
    error.value = null
    searched.value = false
  }

  // A dropdown change is one deliberate act, so it re-searches immediately —
  // unlike typing, which waits for Enter. Before searching, prune downstream
  // picks the cascade no longer offers (a CD-SEM model surviving a switch to
  // HV-SEM would silently zero the search): the prune assignment re-fires
  // this watcher once, and that second pass — now a no-op prune — searches.
  //
  // The watcher stays bound to the calling component's scope even though the
  // state above is now SPA-scoped: it is a side effect of a *mounted* search
  // screen, and disposing it on unmount is what stops a dropdown change from
  // firing a search into a page nobody is looking at.
  watch(() => filters.value, () => {
    const pruned = pruneCascadedFilters(filters.value, filterOptions.value)
    if (pruned) {
      filters.value = pruned
      return
    }
    if (searched.value) void search()
  }, { deep: true })

  return {
    queryText,
    narrowText,
    filters,
    parsed,
    rows,
    narrowedRows,
    sortedRows,
    sort,
    sortIsPartial,
    toggleSort,
    total,
    capped,
    outOfRetention,
    pending,
    error,
    searched,
    hasMore,
    hasActiveFilters,
    defaultRange,
    resolvedRange,
    anchor,
    retentionDays,
    facets,
    filterOptions,
    facetsPending,
    searchDisabled,
    search,
    loadMore,
    reset,
    resetFilters,
    setDateRange
  }
}
