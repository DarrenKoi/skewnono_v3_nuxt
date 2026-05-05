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
  lake_load_tm: string
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

const joinDeviceStatisticsApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBase}${normalizedPath}`
}

export const useDeviceStatisticsApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchR3DeviceGrp = async (): Promise<R3DeviceGrpRow[]> => {
    return await $fetch<R3DeviceGrpRow[]>(
      joinDeviceStatisticsApiPath(base, '/cdsem/device-statistics/r3-device-grp')
    )
  }

  const fetchDeviceDesc = async (facIds: string[] = []): Promise<DeviceDescRow[]> => {
    const query = facIds.length > 0 ? { fac_id: facIds.join(',') } : undefined

    return await $fetch<DeviceDescRow[]>(
      joinDeviceStatisticsApiPath(base, '/cdsem/device-statistics/device-desc'),
      { query }
    )
  }

  return {
    fetchR3DeviceGrp,
    fetchDeviceDesc
  }
}
