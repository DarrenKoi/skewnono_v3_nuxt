import { joinApiPath } from '~/utils/apiPath'

// Which adapter is answering for ONE backend feature right now.
//
// The question this exists to answer is not "which deployment is this" but "are
// the numbers on this screen generated?". A home mock can fabricate a
// RELATIONSHIP that does not exist in the fab — CD and FDC are both biased by a
// single per-MSR `health` scalar, so any CD↔FDC correlation drawn from mock data
// is an artifact of the generator (benchmark research §7.3). A screen that draws
// that correlation has to say so, and this is how it knows to.
//
// Reads `/api/health/data-mode`, NOT `/api/health/providers`: the providers
// table is admin-only, and a demo warning only admins can see is not a warning.
//
// One cache key per feature, so several panels asking about the same feature
// share a single request and can never disagree about the answer.
export type DataProvider = 'mock' | 'office'

export interface DataModeResponse {
  feature: string
  provider: DataProvider
}

export const useDataModeApi = () => {
  const config = useRuntimeConfig()

  const fetchDataMode = async (feature: string): Promise<DataModeResponse> =>
    await $fetch<DataModeResponse>(
      joinApiPath(config.public.apiBase, '/health/data-mode'),
      { query: { feature } }
    )

  return { fetchDataMode }
}

/**
 * `isMock` for one feature. Defaults to FALSE while the answer is unknown —
 * loading, offline, or an endpoint that 404s on an older backend.
 *
 * That default is deliberate and is the safer of the two: a marker that appears
 * on real office data teaches an engineer to distrust a true measurement, and
 * once they learn to ignore the badge it is worthless on the day it is right. An
 * absent marker leaves the screen exactly as honest as it was before this
 * composable existed.
 */
export const useDataMode = (feature: string) => {
  const { fetchDataMode } = useDataModeApi()

  const { data } = useAsyncData(
    `data-mode:${feature}`,
    () => fetchDataMode(feature),
    {
      default: (): DataModeResponse | null => null,
      getCachedData: payloadCache
    }
  )

  const isMock = computed(() => data.value?.provider === 'mock')

  return { provider: computed(() => data.value?.provider ?? null), isMock }
}
