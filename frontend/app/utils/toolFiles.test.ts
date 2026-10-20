import assert from 'node:assert/strict'
import test from 'node:test'
import {
  filterToolFileEntries,
  looksUndecoded,
  normalizeTypedPath,
  formatFileSize,
  sortToolFileEntries,
  summarizeToolFileSelection,
  toolFilesErrorCode,
  toolFilesErrorMessage,
  type ToolFileEntry
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

test('the kind filter keeps folders, files or both, after the name filter', () => {
  const rows = [entry('LOG', { is_dir: true }), entry('log.txt'), entry('RECIPE', { is_dir: true })]
  assert.deepEqual(filterToolFileEntries(rows, '', 'dir').map(e => e.name), ['LOG', 'RECIPE'])
  assert.deepEqual(filterToolFileEntries(rows, '', 'file').map(e => e.name), ['log.txt'])
  assert.deepEqual(filterToolFileEntries(rows, 'log', 'all').map(e => e.name), ['LOG', 'log.txt'])
})

test('a name still holding latin-1 bytes reads as undecoded; Korean and ASCII do not', () => {
  assert.equal(looksUndecoded('\u00ff\u00fe_scan.log'), true)
  assert.equal(looksUndecoded('측정결과.csv'), false)
  assert.equal(looksUndecoded('README.TXT'), false)
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

test('a failure with no response reads as unknown outcome, not as a refusal', () => {
  assert.equal(toolFilesErrorCode({ data: { error: { code: 'file_exists' } }, status: 409 }), 'file_exists')
  assert.equal(toolFilesErrorCode({ status: 502, data: '<html>' }), 'unknown')
  assert.equal(toolFilesErrorCode(new TypeError('Failed to fetch')), 'no_response')
  assert.equal(toolFilesErrorMessage('no_response'), '결과를 확인할 수 없습니다. 새로고침해 주세요.')
})

// Shapes probed 2026-10-17 against ofetch + Nuxt 4.5's createError: a network
// drop is a FetchError with no response whose cause is the TypeError, and
// useAsyncData's wrapper keeps `input.cause || input` and a default 500.
test('a network drop reads as no_response whether raw or wrapped by useAsyncData', () => {
  const dropped = Object.assign(new Error('[GET] "/api/x": <no response> fetch failed', { cause: new TypeError('fetch failed') }), { name: 'FetchError', response: undefined, status: undefined })
  assert.equal(toolFilesErrorCode(dropped), 'no_response')
  assert.equal(toolFilesErrorCode({ statusCode: 500, status: 500, cause: dropped.cause }), 'no_response')
  assert.equal(toolFilesErrorCode({ statusCode: 500, status: 500, cause: dropped }), 'no_response')
})

test('a wrapped HTTP failure keeps its server code or reads as unknown, never no_response', () => {
  const badGateway = Object.assign(new Error('502'), { name: 'FetchError', response: {}, status: 502 })
  assert.equal(toolFilesErrorCode({ statusCode: 502, status: 502, cause: badGateway }), 'unknown')
  const tooMany = Object.assign(new Error('429'), { name: 'FetchError', response: {}, status: 429, data: { error: { code: 'too_many_requests' } } })
  assert.equal(toolFilesErrorCode({ statusCode: 429, status: 429, data: tooMany.data, cause: tooMany }), 'too_many_requests')
})

test('the rate limiter has its own line', () => {
  assert.equal(toolFilesErrorMessage('too_many_requests'), '요청이 많아 잠시 멈췄습니다. 잠시 후 다시 시도해 주세요.')
})

test('a name the tool cannot carry points at the file name; a bad path does not', () => {
  assert.match(toolFilesErrorMessage('name_unencodable', 'upload'), /한글/)
  assert.equal(toolFilesErrorMessage('bad_path', 'upload'), '열 수 없는 경로입니다.')
})

test('a selection is summed against the cap as one budget, folders never counted', () => {
  const entries = [
    entry('a.log', { size: 600 }),
    entry('b.log', { size: 600 }),
    entry('c.log', { size: null }),
    entry('DIR', { is_dir: true, size: 4096 })
  ]
  const all = new Set(entries.map(e => e.path))
  const summary = summarizeToolFileSelection(entries, all, 1000, 2)
  assert.deepEqual(summary.files.map(e => e.name), ['a.log', 'b.log', 'c.log'])
  assert.equal(summary.bytes, 1200)
  assert.equal(summary.overBytes, true)
  assert.equal(summary.overCount, true)
  const one = summarizeToolFileSelection(entries, new Set(['/a.log']), 1000, 2)
  assert.deepEqual([one.bytes, one.overBytes, one.overCount], [600, false, false])
})

test('a typed path is tidied into the absolute shape the server accepts', () => {
  assert.equal(normalizeTypedPath(' /home/hitachi/ '), '/home/hitachi')
  assert.equal(normalizeTypedPath('LOG//ARCHIVE'), '/LOG/ARCHIVE')
  assert.equal(normalizeTypedPath('\\RECIPE\\'), '/RECIPE')
  assert.equal(normalizeTypedPath(''), '/')
  assert.equal(normalizeTypedPath('/LOG/../RECIPE'), '/LOG/../RECIPE')
})
