export type DeviceStatisticsSource = 'r3_device_grp' | 'device_desc'

export interface DeviceStatisticsRow {
  id: string
  source: DeviceStatisticsSource
  fac_id: string
  plan_catg_type: string
  prod_catg_cd: string
  tech_cd: string
  den_type: string
  prod_grp_typ: string
  gen_typ: string
  lot_cd: string
  plan_grade_cd: string
  lake_load_tm: string
  ctn_desc: string
  chg_tm: string
  tech_nm: string
  rnd_connector: string
}

const joinDeviceStatisticsApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const useDeviceStatisticsApi = () => {
  const config = useRuntimeConfig()
  const deviceStatisticsUrl = joinDeviceStatisticsApiPath(config.public.apiBase, '/device-statistics')

  const fetchDeviceStatisticsRows = async (facIds: string[] = []): Promise<DeviceStatisticsRow[]> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<DeviceStatisticsRow[]>(deviceStatisticsUrl, { query })
  }

  return {
    fetchDeviceStatisticsRows
  }
}
