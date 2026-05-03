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

export type BucketPayload
  = Record<SummaryBucketKey, SummaryRow[]> & Record<RecipeInfoBucketKey, RecipeInfoRow[]>

export interface RecipeStatisticsResponse {
  date: string | null
  buckets: BucketPayload | Record<string, never>
}

const joinRecipeStatisticsApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const useRecipeStatisticsApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRecipeStatistics = async (lotCds: string[] = []): Promise<RecipeStatisticsResponse> => {
    const query = lotCds.length > 0 ? { lot_cds: lotCds.join(',') } : undefined

    return await $fetch<RecipeStatisticsResponse>(
      joinRecipeStatisticsApiPath(base, '/device-statistics/recipe-statistics'),
      { query }
    )
  }

  return {
    fetchRecipeStatistics
  }
}
