import { joinApiPath } from '~/utils/apiPath'
import type { RecipeInput } from '~/utils/ruleEngine'

export interface R3DeviceGrpRow {
  id: string
  fac_id: string
  plan_catg_type: string
  prod_catg_cd: string
  tech_cd: string
  den_type: string
  prod_grp_typ: string
  gen_typ: string
  lot_cd: string
  plan_grade_cd: string
  ctn_desc: string
}

export interface DeviceDescRow {
  id: string
  fac_id: string
  lot_cd: string
  ctn_desc: string
  chg_tm: string
  tech_nm: string
  rnd_connector: string
}

/** 한 fab 의 최근 90일 측정 활동 순위 한 건. meas_count 내림차순으로 옵니다. */
export interface MeasActivityRow {
  lot_cd: string
  meas_count: number
}

export const useDeviceStatisticsApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchR3DeviceGrp = async (): Promise<R3DeviceGrpRow[]> => {
    return await $fetch<R3DeviceGrpRow[]>(
      joinApiPath(base, '/cdsem/device-statistics/r3-device-grp')
    )
  }

  const fetchDeviceDesc = async (facIds: string[] = []): Promise<DeviceDescRow[]> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<DeviceDescRow[]>(
      joinApiPath(base, '/cdsem/device-statistics/device-desc'),
      { query }
    )
  }

  const fetchMeasActivity = async (facId: string): Promise<MeasActivityRow[]> => {
    return await $fetch<MeasActivityRow[]>(
      joinApiPath(base, '/cdsem/device-statistics/meas-activity'),
      { query: { fac_id: facId } }
    )
  }

  const fetchRecipeParams = async (lotCds: string[] = []): Promise<RecipeInput[]> => {
    // 빈 목록이면 아예 요청하지 않습니다. 이 엔드포인트는 lot_cds 가 없으면
    // **전 lot** 을 돌려주는데 그것이 599,899 recipe / 약 522 MB 입니다.
    // 예전에는 호출자마다 이 가드를 따로 들고 있어서(3곳), 넷째 호출자가 빠뜨리면
    // 그만이었습니다. 가드는 위험이 있는 곳에 둡니다.
    if (lotCds.length === 0) return []

    return await $fetch<RecipeInput[]>(
      joinApiPath(base, '/cdsem/device-statistics/recipe-params'),
      { query: { lot_cds: lotCds.join(',') } }
    )
  }

  return {
    fetchR3DeviceGrp,
    fetchDeviceDesc,
    fetchMeasActivity,
    fetchRecipeParams
  }
}
