import { joinApiPath } from '~/utils/apiPath'
import type { AfmMeasurement } from '~/composables/useAfmCart'

export interface AfmFileRow {
  filename: string
  recipe_name: string
  lot_id: string
  slot_number: string | number
  measured_info: string
  formatted_date: string
  has_profile?: boolean
  has_data?: boolean
  has_image?: boolean
  has_align?: boolean
  has_tip?: boolean
}

export interface AfmFilesResponse {
  success: boolean
  data: AfmFileRow[]
  total: number
  tool: string
}

export interface AfmInformation {
  [key: string]: string | number | null
}

export type AfmSummaryItem = 'MEAN' | 'STDEV' | 'MIN' | 'MAX' | 'RANGE'

export const AFM_SUMMARY_ITEMS: readonly AfmSummaryItem[] = ['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE']

export interface AfmSummaryRow {
  Site: string
  ITEM: AfmSummaryItem | string
  [measurementKey: string]: string | number
}

export interface AfmDetailRow {
  measurement_point: string
  'Site ID': string
  'Site X': number
  'Site Y': number
  'Point No': number
  'X (um)': number
  'Y (um)': number
  'Method ID': number
  State: string
  Valid: boolean
  'Left_H (nm)': number
  'Left_H_Valid': boolean
  'Right_H (nm)': number
  'Right_H_Valid': boolean
  'Ref_H (nm)': number
  'Ref_H_Valid': boolean
  'Pick Up Count': number
  'Sample Count': number
  'Approach Count': number
  Mileage: number
  [extra: string]: string | number | boolean
}

export interface AfmDetailPayload {
  filename: string
  tool: string
  pickle_filename: string
  information: AfmInformation
  summary: AfmSummaryRow[]
  data: AfmDetailRow[]
  available_points: string[]
}

export interface AfmDetailResponse {
  success: boolean
  data: AfmDetailPayload
  message: string
}

export interface AfmProfilePoint {
  x: number
  y: number
  z: number
}

export interface AfmProfileResponse {
  success: boolean
  data: AfmProfilePoint[]
  count: number
  tool: string
}

export interface AfmImageResponse {
  success: boolean
  data: { filename: string, relative_path: string, url: string }
  tool: string
}

export interface AfmSiteInfo {
  site_id?: string
  site_x?: string | number
  site_y?: string | number
  point_no?: string | number
}

const inFlightFiles = new Map<string, Promise<AfmFilesResponse>>()
const inFlightDetail = new Map<string, Promise<AfmDetailResponse>>()
const inFlightProfile = new Map<string, Promise<AfmProfileResponse>>()
const inFlightImage = new Map<string, Promise<AfmImageResponse>>()

export const useAfmDetailApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchFiles = async (toolName: string): Promise<AfmFilesResponse> => {
    const cacheKey = toolName
    const existing = inFlightFiles.get(cacheKey)
    if (existing) return await existing

    const request = $fetch<AfmFilesResponse>(
      joinApiPath(base, `/afm/files`),
      { query: { tool: toolName } }
    ).finally(() => inFlightFiles.delete(cacheKey))

    inFlightFiles.set(cacheKey, request)
    return await request
  }

  const useAfmFiles = (toolName: string) =>
    useAsyncData(
      `afm-files:${toolName}`,
      async () => {
        const res = await fetchFiles(toolName)
        return res.data.map<AfmMeasurement>(row => ({
          filename: row.filename,
          recipeName: row.recipe_name,
          lotId: row.lot_id,
          slotNumber: row.slot_number,
          measuredInfo: row.measured_info,
          formattedDate: row.formatted_date,
          hasProfile: row.has_profile,
          hasData: row.has_data,
          hasImage: row.has_image,
          hasAlign: row.has_align,
          hasTip: row.has_tip
        }))
      }
    )

  const fetchDetail = async (toolName: string, filename: string): Promise<AfmDetailResponse> => {
    const cacheKey = `${toolName}::${filename}`
    const existing = inFlightDetail.get(cacheKey)
    if (existing) return await existing

    const request = $fetch<AfmDetailResponse>(
      joinApiPath(base, `/afm/files/${encodeURIComponent(filename)}`),
      { query: { tool: toolName } }
    ).finally(() => inFlightDetail.delete(cacheKey))

    inFlightDetail.set(cacheKey, request)
    return await request
  }

  const fetchProfile = async (
    toolName: string,
    filename: string,
    point: string,
    site?: AfmSiteInfo
  ): Promise<AfmProfileResponse> => {
    const cacheKey = `${toolName}::${filename}::${point}::${JSON.stringify(site ?? {})}`
    const existing = inFlightProfile.get(cacheKey)
    if (existing) return await existing

    const query: Record<string, string | number> = { tool: toolName }
    if (site?.site_id) query.site_id = site.site_id
    if (site?.site_x !== undefined) query.site_x = site.site_x
    if (site?.site_y !== undefined) query.site_y = site.site_y
    if (site?.point_no !== undefined) query.point_no = site.point_no

    const path = `/afm/files/${encodeURIComponent(filename)}/profile/${encodeURIComponent(point)}`
    const request = $fetch<AfmProfileResponse>(
      joinApiPath(base, path),
      { query }
    ).finally(() => inFlightProfile.delete(cacheKey))

    inFlightProfile.set(cacheKey, request)
    return await request
  }

  const fetchImage = async (
    toolName: string,
    filename: string,
    point: string
  ): Promise<AfmImageResponse> => {
    const cacheKey = `${toolName}::${filename}::${point}`
    const existing = inFlightImage.get(cacheKey)
    if (existing) return await existing

    const path = `/afm/files/${encodeURIComponent(filename)}/image/${encodeURIComponent(point)}`
    const request = $fetch<AfmImageResponse>(
      joinApiPath(base, path),
      { query: { tool: toolName } }
    ).finally(() => inFlightImage.delete(cacheKey))

    inFlightImage.set(cacheKey, request)
    return await request
  }

  const useAfmDetail = (toolName: string, filename: string) =>
    useAsyncData(
      `afm-detail:${toolName}:${filename}`,
      () => fetchDetail(toolName, filename)
    )

  return {
    fetchFiles,
    useAfmFiles,
    fetchDetail,
    fetchProfile,
    fetchImage,
    useAfmDetail
  }
}
