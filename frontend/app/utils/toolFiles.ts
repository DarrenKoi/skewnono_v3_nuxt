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
  home: string
  path: string
  parent: string | null
  crumbs: ToolFilesCrumb[]
  entries: ToolFileEntry[]
  // One budget for a zip download's files together, not one per file.
  max_bytes: number
  max_batch_files: number
}

export type ToolFilesVerdict
  = | 'granted'
    // A trusted identity outside the allowed teams.
    | 'none'
    | 'pending'
    | 'rejected'
    | 'untrusted_identity'
    | 'directory_unavailable'
    | 'store_unavailable'

export interface ToolFilesRequest {
  // New on every (re)request; approve/reject send back the one on screen.
  request_id: string
  // Plain text from the requester: interpolate, never v-html.
  reason: string
  // The team at request time, display only.
  dept_nm: string | null
  requested_at: string
  status: 'pending' | 'rejected'
}

export interface ToolFilesRequestRow extends ToolFilesRequest {
  empno: string
  emp_nm: string | null
}

export interface ToolFilesGrantRow {
  empno: string
  granted_at: string
  granted_by: string
  // The grantee's current name and team when the directory knows them.
  emp_nm: string | null
  dept_nm: string | null
}

export interface ToolFilesAccess {
  verdict: ToolFilesVerdict
  can_write: boolean
  // The teams that get in by default (backend access.ALLOWED_TEAMS).
  teams: string[]
  // Only for 'pending' and 'rejected': the caller's own request.
  request?: ToolFilesRequest
}

export const TOOL_FILES_REASON_MAX = 200

export const toolFilesReasonValid = (reason: string): boolean => {
  const length = reason.trim().length
  return length > 0 && length <= TOOL_FILES_REASON_MAX
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

// What the checked files would download, against the listing's caps. A size
// the LIST did not give counts as 0 here; the server's byte budget still holds.
export const summarizeToolFileSelection = (
  entries: readonly ToolFileEntry[],
  selected: ReadonlySet<string>,
  maxBytes: number,
  maxFiles: number
) => {
  const files = entries.filter(entry => !entry.is_dir && selected.has(entry.path))
  const bytes = files.reduce((sum, entry) => sum + (entry.size ?? 0), 0)
  return { files, bytes, overBytes: bytes > maxBytes, overCount: files.length > maxFiles }
}

// A path a person typed, tidied into the shape the server's check_path takes:
// absolute, '/' separators, no doubled or trailing slash. '..' is left for the
// server to refuse. A typed non-ASCII name will not match a tool that stores
// it in other bytes (see looksUndecoded); clicking there still works.
export const normalizeTypedPath = (raw: string): string =>
  `/${raw.trim().replace(/\\/g, '/').split('/').filter(Boolean).join('/')}`

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
  forbidden: 'FTP 접속 권한이 없습니다.',
  tool_not_found: '장비 목록에서 이 장비를 찾지 못했습니다.',
  tool_ambiguous: '같은 장비 ID가 장비 목록에 여러 번 있어 대상을 정하지 못했습니다.',
  tool_mismatch: '선택한 장비 종류나 FAB이 이 장비와 맞지 않습니다.',
  tool_unreachable: '장비에 연결하지 못했습니다. 장비 상태를 확인한 뒤 다시 시도해 주세요.',
  tool_timeout: '장비 응답이 너무 느려 중단했습니다. 잠시 후 다시 시도해 주세요.',
  file_unavailable: '파일이 없거나 접근할 수 없습니다.',
  too_large: '파일이 다운로드 상한보다 커서 받지 못했습니다.',
  batch_too_large: '선택한 파일의 합계가 다운로드 상한보다 커서 받지 못했습니다. 나눠서 받아 주세요.',
  too_many_files: '한 번에 받을 수 있는 파일 수를 넘었습니다. 나눠서 받아 주세요.',
  transfers_busy: '다른 다운로드가 진행 중입니다. 잠시 후 다시 시도해 주세요.',
  ftp_busy: '장비 접속 요청이 몰려 잠시 멈췄습니다. 잠시 후 다시 시도해 주세요.',
  listing_too_large: '폴더의 항목이 너무 많아 목록을 불러오지 못했습니다.',
  bad_path: '열 수 없는 경로입니다.',
  name_unencodable: '이 이름으로는 올릴 수 없습니다. 파일 이름에 장비가 쓰지 못하는 글자(예: 한글)가 있는지 확인해 주세요.',
  tool_encoding: '장비가 보낸 파일 이름을 읽지 못했습니다. 서버의 FTP 인코딩 설정(SKEWNONO_TOOL_FTP_ENCODING)을 확인해 주세요.',
  untrusted_identity: '직접 입력한 사번이나 API 토큰으로는 장비 파일을 열 수 없습니다.',
  directory_unavailable: '구성원 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  store_unavailable: '권한 정보를 읽지 못했습니다. 잠시 후 다시 시도해 주세요.',
  file_exists: '같은 이름이 있어 올리지 않았습니다.',
  transfer_uncertain: '파일이 저장되었는지 확인하지 못했습니다. 새로고침해서 목록을 확인해 주세요.',
  write_disabled: '서버에서 파일 쓰기가 꺼져 있습니다.',
  write_not_supported: '이 연결 방식에서는 파일을 쓸 수 없습니다.',
  request_changed: '신청이 바뀌었습니다. 목록을 새로 불러왔으니 다시 확인해 주세요.',
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

const VERDICT_MESSAGES: Record<Exclude<ToolFilesVerdict, 'granted'>, { title: string, description: string, icon: string }> = {
  none: {
    title: 'FTP 접속은 지정된 팀과 승인된 사번만 쓸 수 있습니다.',
    description: '아래 팀 소속이 아니라면(타 팀 파견 등) 사유를 적어 개인 권한을 신청해 주세요.',
    icon: 'i-lucide-lock'
  },
  pending: {
    title: '권한 신청을 검토하고 있습니다.',
    description: '관리자가 승인한 뒤 "승인 확인"을 누르거나 페이지를 새로고침하면 FTP 접속이 열립니다.',
    icon: 'i-lucide-hourglass'
  },
  rejected: {
    title: '권한 신청이 거절되었습니다.',
    description: '사유를 고쳐 다시 신청할 수 있습니다.',
    icon: 'i-lucide-circle-x'
  },
  untrusted_identity: {
    title: '로그인 정보를 확인할 수 없습니다.',
    description: '직접 입력한 사번이나 API 토큰으로는 장비 파일을 열 수 없습니다. 사내 로그인 상태로 다시 접속해 주세요.',
    icon: 'i-lucide-lock'
  },
  directory_unavailable: {
    title: '구성원 정보를 확인하지 못했습니다.',
    description: '소속 팀을 확인할 수 없어 권한을 판정하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    icon: 'i-lucide-lock'
  },
  store_unavailable: {
    title: '권한 정보를 읽지 못했습니다.',
    description: '개인 승인 목록 저장소에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',
    icon: 'i-lucide-lock'
  }
}

export const toolFilesVerdictMessage = (verdict: Exclude<ToolFilesVerdict, 'granted'>) =>
  VERDICT_MESSAGES[verdict]

// Last folder opened per tool and host, so switching A → B → A returns to
// where A was. Provision's two hosts are two disks, so the host is in the key.
export type VisitedPaths = Record<string, string>

export const VISITED_PATHS_CAP = 200

export const visitedPathKey = (toolType: string, eqpId: string, host: 'data' | undefined): string =>
  `${toolType}:${eqpId}:${host ?? 'tool'}`

// Insertion order is recency: a revisit moves to the end, and past the cap the
// oldest falls off, so the stored map stays small however many tools are seen.
export const rememberVisitedPath = (
  paths: VisitedPaths,
  key: string,
  path: string,
  cap = VISITED_PATHS_CAP
): VisitedPaths => {
  if (paths[key] === path) return paths
  const { [key]: _previous, ...rest } = paths
  const entries = Object.entries({ ...rest, [key]: path })
  return Object.fromEntries(entries.slice(Math.max(0, entries.length - cap)))
}

export const normalizeVisitedPaths = (parsed: unknown): VisitedPaths => {
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  return Object.fromEntries(
    Object.entries(parsed).filter((entry): entry is [string, string] =>
      typeof entry[1] === 'string' && entry[1].startsWith('/'))
  )
}
