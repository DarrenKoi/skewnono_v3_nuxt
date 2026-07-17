// Pure-logic tests for csvDownload. Run: node --test app/utils/csvDownload.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCsvContent, escapeCsvValue } from './csvDownload.ts'

test('buildCsvContent joins header and rows with CRLF and quotes every value', () => {
  const out = buildCsvContent(['a', 'b'], [[1, 'x'], [2, 'y']])
  assert.equal(out, '"a","b"\r\n"1","x"\r\n"2","y"')
})

test('buildCsvContent escapes embedded quotes and keeps commas inside quotes', () => {
  const out = buildCsvContent(['h'], [['a"b'], ['c,d']])
  assert.equal(out, '"h"\r\n"a""b"\r\n"c,d"')
})

test('escapeCsvValue renders null/undefined as an empty quoted string', () => {
  assert.equal(escapeCsvValue(null), '""')
  assert.equal(escapeCsvValue(undefined), '""')
})
