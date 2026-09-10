import type { MeasHistFacets, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { KnownValues } from '~/utils/measHistQuery'

// Facet options for the search filters. One shared useAsyncData cache key per
// scope, so every dropdown and the query parser read the same fetch.
//
// No toolType = the skewvoir default: facets across BOTH indices (the search
// scopes to one family only when the 카테고리 dropdown is picked, so the
// option universe and the parser's known-eq list must cover both).
export const useMeasHistFacets = (toolType?: MeasHistToolType) => {
  const { fetchMeasHistFacets } = useMeasHistApi()

  const { data: facets, pending, error } = useAsyncData<MeasHistFacets>(
    `meas-hist-facets:${toolType ?? 'all'}`,
    () => fetchMeasHistFacets(toolType),
    {
      default: () => ({
        tool_type: toolType ?? null,
        anchor: '',
        retention_days: 60,
        fab: [],
        model: [],
        eq: []
      }),
      getCachedData: payloadCache
    }
  )

  // What the search-text parser needs to identify a token by exact match
  // rather than by guessing at its shape. No `recipe` list: recipes are never
  // faceted (see MeasHistFacets), so an otherwise-unclassified token is
  // sent through the parser's cross-field `q` fallback instead.
  const known = computed<KnownValues>(() => ({
    eq: (facets.value?.eq ?? []).map(v => v.value)
  }))

  // Empty until facets land; callers must not compute dates from wall clock.
  const anchor = computed(() => facets.value?.anchor ?? '')
  const retentionDays = computed(() => facets.value?.retention_days ?? 60)

  return { facets, pending, error, known, anchor, retentionDays }
}
