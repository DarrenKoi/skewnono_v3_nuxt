import type { MeasHistFacets, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { KnownValues } from '~/utils/measHistQuery'

// Facet options for the search filters. One shared useAsyncData cache key per
// tool type, so every dropdown and the query parser read the same fetch.
export const useMeasHistFacets = (toolType: MeasHistToolType) => {
  const { fetchMeasHistFacets } = useMeasHistApi()

  const { data: facets, pending, error } = useAsyncData<MeasHistFacets>(
    `meas-hist-facets:${toolType}`,
    () => fetchMeasHistFacets(toolType),
    {
      default: () => ({
        tool_type: toolType,
        anchor: '',
        retention_days: 60,
        fab: [],
        model: [],
        eq: [],
        recipe: []
      }),
      getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
    }
  )

  // What the search-text parser needs to identify a token by exact match
  // rather than by guessing at its shape.
  const known = computed<KnownValues>(() => ({
    eq: (facets.value?.eq ?? []).map(v => v.value),
    recipe: (facets.value?.recipe ?? []).map(v => v.value)
  }))

  // Empty until facets land; callers must not compute dates from wall clock.
  const anchor = computed(() => facets.value?.anchor ?? '')
  const retentionDays = computed(() => facets.value?.retention_days ?? 60)

  return { facets, pending, error, known, anchor, retentionDays }
}
