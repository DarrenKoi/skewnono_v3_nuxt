import { joinApiPath } from '~/utils/apiPath'
import type { AfmMeasurement } from '~/composables/useAfmCart'

export interface AfmFileRow {
  filename: string
  recipe_name: string
  lot_id: string
  slot_number: string | number
  measured_info: string
  formatted_date: string
  time?: string
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

export const AFM_SUMMARY_ITEMS: AfmSummaryItem[] = ['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE']

export interface AfmSummaryRow {
  Site: string
  ITEM: AfmSummaryItem | string
  [measurementKey: string]: string | number
}

export interface AfmDetailRow {
  'measurement_point': string
  'Site ID': string
  'Site X': number
  'Site Y': number
  'Point No': number
  'X (um)': number
  'Y (um)': number
  'Method ID': number
  'State': string
  'Valid': boolean
  'Left_H (nm)': number
  'Left_H_Valid': boolean
  'Right_H (nm)': number
  'Right_H_Valid': boolean
  'Ref_H (nm)': number
  'Ref_H_Valid': boolean
  'Pick Up Count': number
  'Sample Count': number
  'Approach Count': number
  'Mileage': number
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

export type AfmImageType = 'align' | 'tip' | 'capture' | 'tiff'

export interface AfmAnalysisImage {
  name: string
  url: string
}

export interface AfmAnalysisImagesResponse {
  success: boolean
  data: AfmAnalysisImage[]
  count: number
  tool: string
}

// Backend rows carry the measurement time as a raw HHMMSS code separate from
// formatted_date; fold it into the display date so lists show "YYYY-MM-DD HH:MM:SS".
const formatMeasuredAt = (row: AfmFileRow): string => {
  const code = row.time ?? ''
  if (!/^\d{4,6}$/.test(code)) return row.formatted_date
  const padded = code.padEnd(6, '0')
  return `${row.formatted_date} ${padded.slice(0, 2)}:${padded.slice(2, 4)}:${padded.slice(4, 6)}`
}

export const useAfmDetailApi = () => {
  const base = useRuntimeConfig().public.apiBase

  // Every AFM read is GET /afm/files[/<filename>/<rest>]?tool=<TOOL>.
  const get = <T>(tool: string, filename = '', rest = '') =>
    $fetch<T>(
      joinApiPath(base, `/afm/files${filename && `/${encodeURIComponent(filename)}`}${rest}`),
      { query: { tool } }
    )

  const useAfmFiles = (tool: string) =>
    useAsyncData(`afm-files:${tool}`, async () => {
      const res = await get<AfmFilesResponse>(tool)
      return res.data.map<AfmMeasurement>(row => ({
        filename: row.filename,
        recipeName: row.recipe_name,
        lotId: row.lot_id,
        slotNumber: row.slot_number,
        measuredInfo: row.measured_info,
        formattedDate: formatMeasuredAt(row),
        hasProfile: row.has_profile,
        hasData: row.has_data,
        hasImage: row.has_image,
        hasAlign: row.has_align,
        hasTip: row.has_tip
      }))
    })

  const fetchDetail = (tool: string, filename: string) =>
    get<AfmDetailResponse>(tool, filename)

  const useAfmDetail = (tool: string, filename: string) =>
    useAsyncData(`afm-detail:${tool}:${filename}`, () => fetchDetail(tool, filename))

  const fetchProfile = (tool: string, filename: string, point: string) =>
    get<AfmProfileResponse>(tool, filename, `/profile/${encodeURIComponent(point)}`)

  const fetchImage = (tool: string, filename: string, point: string) =>
    get<AfmImageResponse>(tool, filename, `/image/${encodeURIComponent(point)}`)

  const fetchAnalysisImages = (tool: string, filename: string, imageType: AfmImageType) =>
    get<AfmAnalysisImagesResponse>(tool, filename, `/images/${imageType}`)

  return { useAfmFiles, useAfmDetail, fetchDetail, fetchProfile, fetchImage, fetchAnalysisImages }
}
