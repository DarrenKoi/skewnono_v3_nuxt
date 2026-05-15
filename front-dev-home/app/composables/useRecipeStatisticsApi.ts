import { joinApiPath } from '~/utils/apiPath'

export interface SummaryRow {
  lot_cd: string
  fac_id: string
  para_all: number
  para_16: number
  para_13: number
  para_9: number
  para_5: number
  para_16_percent: number
  para_13_percent: number
  para_9_percent: number
  para_5_percent: number
  ctn_desc: string
  total_recipe: number
  avail_recipe: number
  avail_recipe_percent: number
}

export interface RecipeInfoRow {
  lot_cd: string
  fac_id: string
  oper_id: string
  oper_desc: string
  oper_seq: number
  samp_seq: number
  eqp_id: string
  recipe_id: string
  skip_yn: string
  chg_tm: string
  ctn_desc: string
  para_all: number
  para_16: number
  para_13: number
  para_9: number
  para_5: number
  para_16_percent: number
  para_13_percent: number
  para_9_percent: number
  para_5_percent: number
}

export type SummaryBucketKey
  = 'all_summary' | 'only_normal_summary' | 'mother_normal_summary' | 'only_sample_summary'

export type RecipeInfoBucketKey
  = 'all_rcp_info' | 'only_normal_rcp_info' | 'mother_normal_rcp_info' | 'only_sample_rcp_info'

export const summaryToRecipeInfoBucket: Record<SummaryBucketKey, RecipeInfoBucketKey> = {
  all_summary: 'all_rcp_info',
  only_normal_summary: 'only_normal_rcp_info',
  mother_normal_summary: 'mother_normal_rcp_info',
  only_sample_summary: 'only_sample_rcp_info'
}

export type SummaryBucketPayload = Record<SummaryBucketKey, SummaryRow[]>

export type BucketPayload
  = SummaryBucketPayload & Record<RecipeInfoBucketKey, RecipeInfoRow[]>

export interface RecipeStatisticsResponse {
  date: string | null
  buckets: BucketPayload | Record<string, never>
}

// Trend endpoint only carries summary buckets — recipe-info rows are
// excluded server-side to keep the payload small (the trend chart never
// reads them).
export interface RecipeTrendResponse {
  dates: string[]
  trend: Record<string, SummaryBucketPayload>
}

export const useRecipeStatisticsApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRecipeStatistics = async (lotCds: string[] = []): Promise<RecipeStatisticsResponse> => {
    const query = lotCds.length > 0 ? { lot_cds: lotCds.join(',') } : undefined

    return await $fetch<RecipeStatisticsResponse>(
      joinApiPath(base, '/cdsem/device-statistics/recipe-statistics'),
      { query }
    )
  }

  const fetchRecipeTrend = async (
    lotCds: string[] = [],
    startDate?: string,
    endDate?: string
  ): Promise<RecipeTrendResponse> => {
    const query: Record<string, string> = {}
    if (lotCds.length > 0) query.lot_cds = lotCds.join(',')
    if (startDate) query.start_date = startDate
    if (endDate) query.end_date = endDate

    return await $fetch<RecipeTrendResponse>(
      joinApiPath(base, '/cdsem/device-statistics/recipe-trend'),
      { query: Object.keys(query).length > 0 ? query : undefined }
    )
  }

  return {
    fetchRecipeStatistics,
    fetchRecipeTrend
  }
}
