import assert from 'node:assert/strict'
import test from 'node:test'
import {
  TOOL_FILES_REASON_MAX,
  describeToolFilesGrants,
  filterToolFileEntries,
  formatFileSize,
  pendingToolFilesRequests,
  sortToolFileEntries,
  toolFilesAccessView,
  toolFilesErrorCode,
  toolFilesErrorMessage,
  toolFilesReasonValid,
  type ToolFileEntry,
  type ToolFilesGrantRow,
  type ToolFilesRequestRow
} from './toolFiles.ts'

const entry = (name: string, extra: Partial<ToolFileEntry> = {}): ToolFileEntry => ({
  name,
  path: `/${name}`,
  is_dir: false,
  size: 10,
  modified: '2026-10-16T09:00:00+09:00',
  ...extra
})

test('folders stay above files whichever way a column sorts', () => {
  const rows = [entry('b.log'), entry('LOG', { is_dir: true, size: null }), entry('a.log')]
  assert.deepEqual(sortToolFileEntries(rows, 'name', 'asc').map(e => e.name), ['LOG', 'a.log', 'b.log'])
  assert.deepEqual(sortToolFileEntries(rows, 'name', 'desc').map(e => e.name), ['LOG', 'b.log', 'a.log'])
})

test('size and time sort numerically, and a missing value goes last in both directions', () => {
  const rows = [
    entry('mid', { size: 200, modified: '2026-10-15T09:00:00+09:00' }),
    entry('none', { size: null, modified: null }),
    entry('big', { size: 3000, modified: '2026-10-16T09:00:00+09:00' }),
    entry('small', { size: 9, modified: '2026-10-01T09:00:00+09:00' })
  ]
  assert.deepEqual(sortToolFileEntries(rows, 'size', 'asc').map(e => e.name), ['small', 'mid', 'big', 'none'])
  assert.deepEqual(sortToolFileEntries(rows, 'size', 'desc').map(e => e.name), ['big', 'mid', 'small', 'none'])
  assert.deepEqual(sortToolFileEntries(rows, 'modified', 'desc').map(e => e.name), ['big', 'mid', 'small', 'none'])
})

test('the name filter is case-insensitive and keeps folders that match only', () => {
  const rows = [entry('EVENT_01.log'), entry('RECIPE', { is_dir: true }), entry('event_02.LOG')]
  assert.deepEqual(filterToolFileEntries(rows, 'event').map(e => e.name), ['EVENT_01.log', 'event_02.LOG'])
  assert.deepEqual(filterToolFileEntries(rows, '  ').map(e => e.name), ['EVENT_01.log', 'RECIPE', 'event_02.LOG'])
})

test('sizes read in binary units, folders read as nothing', () => {
  assert.equal(formatFileSize(null), '')
  assert.equal(formatFileSize(512), '512 B')
  assert.equal(formatFileSize(2048), '2.0 KB')
  assert.equal(formatFileSize(157286400), '150.0 MB')
  assert.equal(formatFileSize(5 * 1024 ** 3), '5.0 GB')
})

test('each server error code reads as its own Korean line, unknown codes fall back', () => {
  assert.equal(toolFilesErrorMessage('tool_unreachable'), '장비에 연결하지 못했습니다. 장비 상태를 확인한 뒤 다시 시도해 주세요.')
  assert.equal(toolFilesErrorMessage('file_unavailable'), '파일이 없거나 접근할 수 없습니다.')
  assert.equal(toolFilesErrorMessage('too_large'), '파일이 다운로드 상한보다 커서 받지 못했습니다.')
  assert.equal(toolFilesErrorMessage('something_new'), '요청을 처리하지 못했습니다.')
})

test('write failures say what happened to the file', () => {
  assert.equal(toolFilesErrorMessage('file_exists'), '같은 이름이 있어 올리지 않았습니다.')
  assert.match(toolFilesErrorMessage('transfer_uncertain'), /새로고침/)
  assert.equal(toolFilesErrorMessage('write_disabled'), '서버에서 파일 쓰기가 꺼져 있습니다.')
  assert.equal(toolFilesErrorMessage('write_not_supported'), '이 연결 방식에서는 파일을 쓸 수 없습니다.')
  // The download wording would be wrong for an upload over the cap.
  assert.equal(toolFilesErrorMessage('too_large', 'upload'), '파일이 업로드 상한보다 커서 올리지 않았습니다.')
  assert.equal(toolFilesErrorMessage('tool_unreachable', 'upload'), toolFilesErrorMessage('tool_unreachable'))
})

const grant = (kind: 'team' | 'emp', value: string, dept_nm: string | null = null): ToolFilesGrantRow => ({
  kind,
  value,
  dept_nm,
  granted_at: '2026-10-17T00:00:00Z',
  granted_by: '2067928'
})

test('team grants carry their member count and warn only on a complete zero', () => {
  const grants = [grant('team', '계측기술팀'), grant('team', '해체된팀')]
  const teams = { teams: [{ dept_nm: '계측기술팀', members: 2 }], complete: true }

  const { teams: rows } = describeToolFilesGrants(grants, teams)

  assert.deepEqual(rows.map(r => [r.value, r.members, r.warnEmpty]), [
    ['계측기술팀', 2, false],
    ['해체된팀', 0, true]
  ])
})

test('an incomplete or missing team list never claims a team is empty', () => {
  const grants = [grant('team', '해체된팀')]

  const partial = describeToolFilesGrants(grants, { teams: [], complete: false }).teams[0]
  const unknown = describeToolFilesGrants(grants, null).teams[0]

  assert.deepEqual([partial?.members, partial?.warnEmpty], [0, false])
  assert.deepEqual([unknown?.members, unknown?.warnEmpty], [null, false])
})

test('an empno grant is marked as kept by a granted team of the same name', () => {
  const grants = [
    grant('team', '계측기술팀'),
    grant('emp', '1000001', '계측기술팀'),
    grant('emp', '1000003', '공정기술팀'),
    grant('emp', '7777777')
  ]

  const { emps } = describeToolFilesGrants(grants, null)

  assert.deepEqual(emps.map(r => [r.value, r.coveredByTeam]), [
    ['1000001', true],
    ['1000003', false],
    ['7777777', false]
  ])
})

test('the access verdict picks one screen', () => {
  const view = (verdict: string) => toolFilesAccessView({ verdict, can_write: false } as never)
  assert.equal(view('granted'), 'explorer')
  assert.equal(view('none'), 'request')
  assert.equal(view('rejected'), 'rejected')
  assert.equal(view('pending'), 'pending')
  assert.equal(view('untrusted_identity'), 'notice')
  assert.equal(view('directory_unavailable'), 'notice')
  assert.equal(view('store_unavailable'), 'notice')
  assert.equal(toolFilesAccessView(null), 'notice')
})

test('a reason must hold something and fit in 200 characters', () => {
  assert.equal(TOOL_FILES_REASON_MAX, 200)
  assert.equal(toolFilesReasonValid('  '), false)
  assert.equal(toolFilesReasonValid('레시피 백업'), true)
  assert.equal(toolFilesReasonValid('가'.repeat(200)), true)
  assert.equal(toolFilesReasonValid('가'.repeat(201)), false)
})

test('a failure with no response reads as unknown outcome, not as a refusal', () => {
  assert.equal(toolFilesErrorCode({ data: { error: { code: 'request_changed' } }, status: 409 }), 'request_changed')
  assert.equal(toolFilesErrorCode({ status: 502, data: '<html>' }), 'unknown')
  assert.equal(toolFilesErrorCode(new TypeError('Failed to fetch')), 'no_response')
  assert.equal(toolFilesErrorMessage('no_response'), '결과를 확인할 수 없습니다. 새로고침해 주세요.')
  assert.equal(toolFilesErrorMessage('request_changed'), '신청이 바뀌었습니다. 새로고침 후 다시 확인해 주세요.')
})

const request = (empno: string, dept_nm: string | null, requested_at: string, status: 'pending' | 'rejected' = 'pending'): ToolFilesRequestRow => ({
  empno,
  emp_nm: null,
  dept_nm,
  requested_at,
  status,
  reason: '백업',
  request_id: empno.repeat(4)
})

test('pending requests list oldest first and count their team\'s pending requests', () => {
  const rows = [
    request('1000002', '계측기술팀', '2026-10-17T02:00:00Z'),
    request('1000003', '공정기술팀', '2026-10-17T01:00:00Z'),
    request('1000009', '계측기술팀', '2026-10-17T00:30:00Z', 'rejected'),
    request('1000001', '계측기술팀', '2026-10-17T00:00:00Z'),
    request('7777777', null, '2026-10-17T03:00:00Z')
  ]

  assert.deepEqual(pendingToolFilesRequests(rows).map(r => [r.empno, r.teamPending]), [
    ['1000001', 2],
    ['1000003', 1],
    ['1000002', 2],
    ['7777777', 0]
  ])
})
