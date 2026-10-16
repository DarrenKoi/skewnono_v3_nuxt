// Shapes mirror backend/ebeam/tool_files/contracts.py.
export interface ToolFileEntry {
  name: string
  // Opaque server key: send it back verbatim, never build or decode one.
  path: string
  is_dir: boolean
  size: number | null
  modified: string | null
}

export interface ToolFilesCrumb {
  name: string
  path: string
}

export interface ToolFilesListing {
  root: string
  path: string
  parent: string | null
  crumbs: ToolFilesCrumb[]
  entries: ToolFileEntry[]
  max_bytes: number
}

export interface ToolFilesAccess {
  verdict: 'granted' | 'none'
  can_write: boolean
}

export type ToolFileSortKey = 'name' | 'size' | 'modified'
export type SortDirection = 'asc' | 'desc'

const sortValue = (entry: ToolFileEntry, key: ToolFileSortKey): string | number | null => {
  if (key === 'name') return entry.name
  if (key === 'size') return entry.size
  return entry.modified === null ? null : Date.parse(entry.modified)
}

// Folders first, then the column; a missing size or time sinks to the bottom
// in both directions, so "unknown" never reads as "smallest" or "newest".
export const sortToolFileEntries = (
  entries: readonly ToolFileEntry[],
  key: ToolFileSortKey,
  direction: SortDirection
): ToolFileEntry[] => {
  const sign = direction === 'asc' ? 1 : -1
  return [...entries].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    const left = sortValue(a, key)
    const right = sortValue(b, key)
    if (left === null || right === null) {
      if (left === right) return a.name.localeCompare(b.name)
      return left === null ? 1 : -1
    }
    if (typeof left === 'string' && typeof right === 'string') {
      return sign * left.localeCompare(right)
    }
    return sign * ((left as number) - (right as number))
  })
}

export const filterToolFileEntries = (entries: readonly ToolFileEntry[], query: string): ToolFileEntry[] => {
  const needle = query.trim().toLowerCase()
  if (!needle) return [...entries]
  return entries.filter(entry => entry.name.toLowerCase().includes(needle))
}

const UNITS = ['KB', 'MB', 'GB', 'TB']

export const formatFileSize = (bytes: number | null): string => {
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(1)} ${UNITS[unit]}`
}

const ERROR_MESSAGES: Record<string, string> = {
  forbidden: '장비 파일에 접근할 권한이 없습니다.',
  tool_not_found: '장비 목록에서 이 장비를 찾지 못했습니다.',
  tool_ambiguous: '같은 장비 ID가 장비 목록에 여러 번 있어 대상을 정하지 못했습니다.',
  tool_mismatch: '선택한 장비 종류나 FAB이 이 장비와 맞지 않습니다.',
  tool_unreachable: '장비에 연결하지 못했습니다. 장비 상태를 확인한 뒤 다시 시도해 주세요.',
  tool_timeout: '장비 응답이 너무 느려 중단했습니다. 잠시 후 다시 시도해 주세요.',
  file_unavailable: '파일이 없거나 접근할 수 없습니다.',
  too_large: '파일이 다운로드 상한보다 커서 받지 못했습니다.',
  listing_too_large: '폴더의 항목이 너무 많아 목록을 불러오지 못했습니다.',
  bad_path: '열 수 없는 경로입니다.'
}

export const toolFilesErrorMessage = (code: string): string =>
  ERROR_MESSAGES[code] ?? '요청을 처리하지 못했습니다.'
