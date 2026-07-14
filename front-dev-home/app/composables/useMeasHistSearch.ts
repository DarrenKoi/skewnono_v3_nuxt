import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import { parseMeasHistQuery, removeToken, resolveDateRange } from '~/utils/measHistQuery'

// No `recipe` field: recipes are found via the search bar only (there is no
// RECIPE dropdown — see FilterBar.vue). The parser's `recipe` tokens still
// reach the request; they're unioned in at buildParams below.
export interface MeasHistFilters {
  fab: string[]
  model: string[]
  eq: string[]
  from: string
  to: string
}

const PAGE_SIZE = 50

// Subtract days from an ISO YYYY-MM-DD without touching wall clock.
const shiftIso = (iso: string, days: number): string => {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1))
  dt.setUTCDate(dt.getUTCDate() - days)
  return dt.toISOString().slice(0, 10)
}

export const useMeasHistSearch = (toolType: MeasHistToolType) => {
  const { searchMeasHist } = useMeasHistApi()
  const { facets, pending: facetsPending, known, anchor, retentionDays } = useMeasHistFacets(toolType)

  const queryText = ref('')
  const narrowText = ref('')

  // The retention window is anchored to the backend's declared clock, never to
  // wall-clock today — the Phase 1 mock's data ends at a frozen NOW.
  const defaultRange = computed(() => ({
    start: anchor.value ? shiftIso(anchor.value, retentionDays.value) : '',
    end: anchor.value
  }))

  const filters = ref<MeasHistFilters>({ fab: [], model: [], eq: [], from: '', to: '' })

  // Chips render as you type — no round-trip needed to see how a token was read.
  const parsed = computed(() => parseMeasHistQuery(queryText.value, known.value))

  const rows = ref<MeasHistRow[]>([])
  const total = ref(0)
  const capped = ref(false)
  const outOfRetention = ref(false)
  const pending = ref(false)
  const error = ref<string | null>(null)
  // False until the first search runs — drives the "type something" empty state.
  const searched = ref(false)

  const hasActiveFilters = computed(() =>
    filters.value.fab.length > 0
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

    return {
      toolType,
      fab: filters.value.fab,
      model: filters.value.model,
      eq: union(filters.value.eq, p.eq),
      // No recipe dropdown to union in — the parser's tokens ARE the recipe
      // filter (see MeasHistFilters's doc comment).
      recipe: p.recipe,
      lot: p.lot,
      msr: p.msr,
      from,
      to,
      offset,
      limit: PAGE_SIZE
    }
  }

  const run = async (offset: number) => {
    pending.value = true
    error.value = null
    try {
      const res = await searchMeasHist(buildParams(offset))
      rows.value = offset === 0 ? res.rows : [...rows.value, ...res.rows]
      total.value = res.total
      capped.value = res.capped
      outOfRetention.value = res.out_of_retention
    } catch {
      // Keep the current rows on failure — losing results to a transient blip
      // is worse than showing stale ones next to a retry.
      error.value = '검색에 실패했습니다.'
    } finally {
      pending.value = false
    }
  }

  // Explicit: Enter or the Search button. Searching per keystroke would fire a
  // full OpenSearch query for every character of a lot id.
  const search = async () => {
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

  const resetFilters = () => {
    filters.value = { fab: [], model: [], eq: [], from: '', to: '' }
  }

  // A 기간 dropdown edit is "last write wins": it must not merely set
  // filters.from/to alongside a `date:` token that still sits in queryText,
  // or resolvedRange stays derived from that (unchanged) token, the popover
  // label snaps back to it on the next re-search, and hasActiveFilters lights
  // up 초기화 for a date the query silently ignores (see resolveDateRange's
  // precedence doc comment). Stripping the token first makes filters.from/to
  // the sole source of truth for resolvedRange again.
  const setDateRange = (range: { start: string, end: string }) => {
    const dateTokens = parsed.value.date
    queryText.value = dateTokens.reduce((text, token) => removeToken(text, token), queryText.value)
    filters.value = { ...filters.value, from: range.start, to: range.end }
  }

  const reset = () => {
    queryText.value = ''
    narrowText.value = ''
    resetFilters()
    rows.value = []
    total.value = 0
    capped.value = false
    outOfRetention.value = false
    error.value = null
    searched.value = false
  }

  // A dropdown change is one deliberate act, so it re-searches immediately —
  // unlike typing, which waits for Enter.
  watch(() => filters.value, () => {
    if (searched.value) void search()
  }, { deep: true })

  return {
    queryText,
    narrowText,
    filters,
    parsed,
    rows,
    narrowedRows,
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
    facetsPending,
    search,
    loadMore,
    reset,
    resetFilters,
    setDateRange
  }
}
