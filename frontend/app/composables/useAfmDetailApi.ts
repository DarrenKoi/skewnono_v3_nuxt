import { joinApiPath } from '~/utils/apiPath'

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
  // The key the point picker filters on. It repeats `Site ID` where the recipe
  // records one (`0002_X002_Y-001`, also in the profile file name). `Site ID`,
  // `Site X` and `Site Y` exist only on such recipes, so they arrive through
  // the index signature below rather than as required fields.
  'measurement_point': string
  'Point No': number
  'X (um)': number
  'Y (um)': number
  // The method's name, or a number on recipes that number their methods.
  'Method_ID': string | number
  'State': string
  'Valid': boolean
  // Measurement columns (`<name> (nm)` + `<name>_Valid`) are named by the recipe,
  // so they arrive through the index signature below.
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

// What one profile file declares about itself. Units are one of um / nm / pm / Pixel,
// differ from file to file and are never unified; data_size reads like "1024 x 1".
export interface AfmProfileMeta {
  x_unit: string
  y_unit: string
  z_unit: string
  data_size: string
  surface_size: string
}

export interface AfmProfileResponse {
  success: boolean
  data: AfmProfilePoint[]
  meta?: AfmProfileMeta | null
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
  // Result images only: the stored TIFF this display rendition was converted
  // from. The server names the download (Content-Disposition), so link to it
  // without a `download` name of our own.
  original_url?: string
}

export interface AfmAnalysisImagesResponse {
  success: boolean
  data: AfmAnalysisImage[]
  count: number
  tool: string
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
      return res.data.map(toMeasurement)
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
