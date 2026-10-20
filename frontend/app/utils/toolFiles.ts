import { fabSegment } from './fab.ts'
import { SEM_TOOL_TYPES, type ToolType } from './toolType.ts'

// The explorer page exists only under pages/ebeam/{cd-sem,hv-sem}/[fab]/tool-files;
// a link drawn for another family matches no route. Access is the page's call.
export const hasToolFilesView = (toolType: ToolType): boolean =>
  (SEM_TOOL_TYPES as readonly ToolType[]).includes(toolType)

export const toolFilesRoute = (toolType: ToolType, fab: string, eqpId: string) => ({
  path: `/ebeam/${toolType}/${fabSegment(fab)}/tool-files`,
  query: { eqp: eqpId }
})

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
  home: string
  path: string
  parent: string | null
  crumbs: ToolFilesCrumb[]
  entries: ToolFileEntry[]
  max_bytes: number
}

export type ToolFilesVerdict
  = | 'granted'
    // A trusted identity outside the allowed teams.
    | 'none'
    | 'untrusted_identity'
    | 'directory_unavailable'

export interface ToolFilesAccess {
  verdict: ToolFilesVerdict
  can_write: boolean
  // The teams that get in (backend access.ALLOWED_TEAMS), for the refusal page.
  teams: string[]
}

// The server's `{ error: { code, message } }` body, read off a failed $fetch
// or fetch. A failure that never got a response (network drop, server gone
// mid-write) is 'no_response': whether a write landed is unknown then.
// useAsyncData hands reads over wrapped in a NuxtError that claims 500 and
// keeps the original under `cause`, so the cause is what decides.
export const toolFilesErrorCode = (error: unknown): string => {
  const failure = error as { data?: { error?: { code?: string } }, status?: number, statusCode?: number, cause?: unknown } | null
  const code = failure?.data?.error?.code
  if (code) return code
  if (failure?.cause && typeof failure.cause === 'object') return toolFilesErrorCode(failure.cause)
  return failure?.status || failure?.statusCode ? 'unknown' : 'no_response'
}

export type ToolFileSortKey = 'name' | 'size' | 'modified'
export type SortDirection = 'asc' | 'desc'

const sortValue = (entry: ToolFileEntry, key: ToolFileSortKey): string | number | null => {
  if (key === 'name') return entry.name
  if (key === 'size') return entry.size
  return entry.modified === null ? null : Date.parse(entry.modified)
}

const { compare: compareNames } = new Intl.Collator()

// Folders first, then the column; a missing size or time sinks to the bottom
// in both directions, so "unknown" never reads as "smallest" or "newest".
export const sortToolFileEntries = (
  entries: readonly ToolFileEntry[],
  key: ToolFileSortKey,
  direction: SortDirection
): ToolFileEntry[] => {
  const sign = direction === 'asc' ? 1 : -1
  // Each key is computed once per entry, not once per comparison (Date.parse).
  return entries
    .map(entry => ({ entry, value: sortValue(entry, key) }))
    .sort(({ entry: a, value: left }, { entry: b, value: right }) => {
      if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
      if (left === null || right === null) {
        if (left === right) return compareNames(a.name, b.name)
        return left === null ? 1 : -1
      }
      if (typeof left === 'string' && typeof right === 'string') {
        return sign * compareNames(left, right)
      }
      return sign * ((left as number) - (right as number))
    })
    .map(({ entry }) => entry)
}

export type ToolFileKind = 'all' | 'dir' | 'file'

export const filterToolFileEntries = (
  entries: readonly ToolFileEntry[],
  query: string,
  kind: ToolFileKind = 'all'
): ToolFileEntry[] => {
  const needle = query.trim().toLowerCase()
  return entries.filter(entry =>
    (kind === 'all' || entry.is_dir === (kind === 'dir'))
    && (!needle || entry.name.toLowerCase().includes(needle)))
}

// The server re-decodes latin-1-read names as UTF-8 or cp949; a name that
// still holds U+0080–U+00FF matched neither, so its bytes are corrupted.
// ponytail: a real Latin-1 accent would be flagged too; none is known on tools.
export const looksUndecoded = (name: string): boolean => /[\u0080-\u00ff]/.test(name)

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
  forbidden: 'FTP 접속은 지정된 팀만 쓸 수 있습니다.',
  tool_not_found: '장비 목록에서 이 장비를 찾지 못했습니다.',
  tool_ambiguous: '같은 장비 ID가 장비 목록에 여러 번 있어 대상을 정하지 못했습니다.',
  tool_mismatch: '선택한 장비 종류나 FAB이 이 장비와 맞지 않습니다.',
  tool_unreachable: '장비에 연결하지 못했습니다. 장비 상태를 확인한 뒤 다시 시도해 주세요.',
  tool_timeout: '장비 응답이 너무 느려 중단했습니다. 잠시 후 다시 시도해 주세요.',
  file_unavailable: '파일이 없거나 접근할 수 없습니다.',
  too_large: '파일이 다운로드 상한보다 커서 받지 못했습니다.',
  listing_too_large: '폴더의 항목이 너무 많아 목록을 불러오지 못했습니다.',
  bad_path: '열 수 없는 경로입니다.',
  name_unencodable: '이 이름으로는 올릴 수 없습니다. 파일 이름에 장비가 쓰지 못하는 글자(예: 한글)가 있는지 확인해 주세요.',
  tool_encoding: '장비가 보낸 파일 이름을 읽지 못했습니다. 서버의 FTP 인코딩 설정(SKEWNONO_TOOL_FTP_ENCODING)을 확인해 주세요.',
  untrusted_identity: '직접 입력한 사번이나 API 토큰으로는 장비 파일을 열 수 없습니다.',
  directory_unavailable: '구성원 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  file_exists: '같은 이름이 있어 올리지 않았습니다.',
  transfer_uncertain: '파일이 저장되었는지 확인하지 못했습니다. 새로고침해서 목록을 확인해 주세요.',
  write_disabled: '서버에서 파일 쓰기가 꺼져 있습니다.',
  write_not_supported: '이 연결 방식에서는 파일을 쓸 수 없습니다.',
  bad_request: '요청 내용이 올바르지 않습니다.',
  too_many_requests: '요청이 많아 잠시 멈췄습니다. 잠시 후 다시 시도해 주세요.',
  no_response: '결과를 확인할 수 없습니다. 새로고침해 주세요.'
}

const UPLOAD_MESSAGES: Record<string, string> = {
  too_large: '파일이 업로드 상한보다 커서 올리지 않았습니다.'
}

export const toolFilesErrorMessage = (code: string, action?: 'upload'): string =>
  (action === 'upload' ? UPLOAD_MESSAGES[code] : undefined)
  ?? ERROR_MESSAGES[code]
  ?? '요청을 처리하지 못했습니다.'

const VERDICT_MESSAGES: Record<Exclude<ToolFilesVerdict, 'granted'>, { title: string, description: string }> = {
  none: {
    title: 'FTP 접속은 지정된 팀만 쓸 수 있습니다.',
    description: '아래 팀 소속 구성원에게만 열려 있습니다.'
  },
  untrusted_identity: {
    title: '로그인 정보를 확인할 수 없습니다.',
    description: '직접 입력한 사번이나 API 토큰으로는 장비 파일을 열 수 없습니다. 사내 로그인 상태로 다시 접속해 주세요.'
  },
  directory_unavailable: {
    title: '구성원 정보를 확인하지 못했습니다.',
    description: '소속 팀을 확인할 수 없어 권한을 판정하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  }
}

export const toolFilesVerdictMessage = (verdict: Exclude<ToolFilesVerdict, 'granted'>) =>
  VERDICT_MESSAGES[verdict]
