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

export type ToolFilesVerdict
  = | 'granted'
    | 'none'
    | 'untrusted_identity'
    | 'directory_unavailable'
    | 'store_unavailable'

export interface ToolFilesAccess {
  verdict: ToolFilesVerdict
  can_write: boolean
}

export interface ToolFilesGrantRow {
  kind: 'team' | 'emp'
  value: string
  granted_at: string
  granted_by: string
  // emp rows: the grantee's current team when the directory knows it.
  dept_nm: string | null
}

export interface ToolFilesTeams {
  teams: { dept_nm: string, members: number }[]
  // False when some directory rows were unreadable, so a 0 is not proof.
  complete: boolean
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
  bad_path: '열 수 없는 경로입니다.',
  tool_encoding: '장비가 보낸 파일 이름을 읽지 못했습니다. 서버의 FTP 인코딩 설정(SKEWNONO_TOOL_FTP_ENCODING)을 확인해 주세요.',
  untrusted_identity: '직접 입력한 사번이나 API 토큰으로는 장비 파일을 열 수 없습니다.',
  directory_unavailable: '구성원 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  store_unavailable: '권한 정보를 읽지 못했습니다. 잠시 후 다시 시도해 주세요.',
  file_exists: '같은 이름이 있어 올리지 않았습니다.',
  transfer_uncertain: '파일이 저장되었는지 확인하지 못했습니다. 새로고침해서 목록을 확인해 주세요.',
  write_disabled: '서버에서 파일 쓰기가 꺼져 있습니다.',
  write_not_supported: '이 연결 방식에서는 파일을 쓸 수 없습니다.'
}

const UPLOAD_MESSAGES: Record<string, string> = {
  too_large: '파일이 업로드 상한보다 커서 올리지 않았습니다.'
}

export const toolFilesErrorMessage = (code: string, action?: 'upload'): string =>
  (action === 'upload' ? UPLOAD_MESSAGES[code] : undefined)
  ?? ERROR_MESSAGES[code]
  ?? '요청을 처리하지 못했습니다.'

export interface ToolFilesTeamGrant extends ToolFilesGrantRow {
  // null while the team list is unknown (failed or not loaded).
  members: number | null
  warnEmpty: boolean
}

export interface ToolFilesEmpGrant extends ToolFilesGrantRow {
  // Revoking this row would not shut the person out.
  coveredByTeam: boolean
}

export const describeToolFilesGrants = (
  grants: readonly ToolFilesGrantRow[],
  teams: ToolFilesTeams | null
): { teams: ToolFilesTeamGrant[], emps: ToolFilesEmpGrant[] } => {
  const sizes = new Map(teams?.teams.map(t => [t.dept_nm, t.members]))
  const granted = new Set(grants.filter(g => g.kind === 'team').map(g => g.value))
  return {
    teams: grants
      .filter(g => g.kind === 'team')
      .map((g) => {
        const members = teams ? (sizes.get(g.value) ?? 0) : null
        return { ...g, members, warnEmpty: members === 0 && teams?.complete === true }
      }),
    emps: grants
      .filter(g => g.kind === 'emp')
      .map(g => ({ ...g, coveredByTeam: g.dept_nm !== null && granted.has(g.dept_nm) }))
  }
}

const VERDICT_MESSAGES: Record<Exclude<ToolFilesVerdict, 'granted'>, { title: string, description: string }> = {
  none: {
    title: '장비 파일에 접근할 권한이 없습니다.',
    description: '장비 파일 탐색은 승인된 팀이나 사번만 쓸 수 있습니다. 관리자에게 승인을 요청해 주세요.'
  },
  untrusted_identity: {
    title: '로그인 정보를 확인할 수 없습니다.',
    description: '직접 입력한 사번이나 API 토큰으로는 장비 파일을 열 수 없습니다. 사내 로그인 상태로 다시 접속해 주세요.'
  },
  directory_unavailable: {
    title: '구성원 정보를 확인하지 못했습니다.',
    description: '소속 팀을 확인할 수 없어 권한을 판정하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  },
  store_unavailable: {
    title: '권한 정보를 읽지 못했습니다.',
    description: '승인 목록 저장소에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  }
}

export const toolFilesVerdictMessage = (verdict: Exclude<ToolFilesVerdict, 'granted'>) =>
  VERDICT_MESSAGES[verdict]
