import assert from 'node:assert/strict'
import test from 'node:test'
import {
  filterToolFileEntries,
  formatFileSize,
  sortToolFileEntries,
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
