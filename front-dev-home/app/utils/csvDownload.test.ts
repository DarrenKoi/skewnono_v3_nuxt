// Pure-logic tests for csvDownload. Run: node --test app/utils/csvDownload.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCsvContent, escapeCsvValue, guardFormulaCell } from './csvDownload.ts'

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

// CSV·TSV 에는 칸 타입이 없어 Excel 이 첫 글자로 수식 여부를 짐작합니다. 사무실
// 식별자 하나가 =HYPERLINK(...) 이면 파일을 연 사람의 Excel 이 그것을 실행합니다.
test('수식으로 읽힐 값에는 텍스트 표시를 단다', () => {
  assert.equal(guardFormulaCell('=1+1'), '\'=1+1')
  assert.equal(guardFormulaCell('=HYPERLINK("http://x","c")'), '\'=HYPERLINK("http://x","c")')
  assert.equal(guardFormulaCell('+1+1'), '\'+1+1')
  assert.equal(guardFormulaCell('-1+1'), '\'-1+1')
  assert.equal(guardFormulaCell('@SUM(A1)'), '\'@SUM(A1)')
  assert.equal(guardFormulaCell('\t=1+1'), '\'\t=1+1')
})

// 음수를 감싸면 Excel 에서 텍스트가 되어 정렬도 계산도 안 됩니다. 측정값에
// 음수가 흔하므로(스테이지 좌표 등) 이 구제는 장식이 아닙니다.
test('평범한 숫자는 그대로 둔다', () => {
  for (const value of ['-1.5', '+3', '-0', '1.5', '-1e5', '-.5', '0']) {
    assert.equal(guardFormulaCell(value), value, value)
  }
})

// `-` 는 이 저장소의 표에서 "값 없음" 자리에 흔히 쓰이고, 글자 하나로는 수식이
// 될 수 없습니다.
test('글자 하나짜리 기호와 평범한 문자열은 건드리지 않는다', () => {
  for (const value of ['-', '+', '=', '@', '', 'R000', 'CBL ETCH CD', '— 없음']) {
    assert.equal(guardFormulaCell(value), value, JSON.stringify(value))
  }
})

test('CSV 로 나갈 때도 같은 방어가 걸린다', () => {
  assert.equal(escapeCsvValue('=1+1'), '"\'=1+1"')
  assert.equal(buildCsvContent(['h'], [['=cmd|calc']]), '"h"\r\n"\'=cmd|calc"')
  // 숫자는 그대로 — 파일을 연 쪽에서 여전히 숫자입니다.
  assert.equal(escapeCsvValue(-1.5), '"-1.5"')
})
