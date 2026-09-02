// Pure-logic tests for tableExport. Run: node --test app/utils/tableExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { guardFormulaCell, safeSheetName, toSheetRows } from './tableExport.ts'

// 클립보드 TSV 에는 칸 타입이 없어 Excel 이 첫 글자로 수식 여부를 짐작합니다.
// 사무실 식별자 하나가 =HYPERLINK(...) 이면 붙여넣은 사람의 Excel 이 실행합니다.
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

// `.xlsx` 로 나가는 값은 정규화만 하고 문자열로 눕히지 않습니다 — office
// 식별자 `0012` 가 `12` 로 줄거나 `-1.5` 가 텍스트로 굳으면 통일한 의미가
// 없습니다. 수식 방어를 여기서 부르지 않는 것도 같은 이유입니다(xlsx.ts 주석).
test('toSheetRows 는 null 만 빈 칸으로 눕히고 타입은 보존한다', () => {
  assert.deepEqual(
    toSheetRows(['a', 'b', 'c'], [[1, null, 'x'], [-1.5, undefined, '=1+1']]),
    [['a', 'b', 'c'], [1, '', 'x'], [-1.5, '', '=1+1']]
  )
})

test('toSheetRows 는 행이 없어도 헤더 한 줄을 낸다', () => {
  assert.deepEqual(toSheetRows(['a'], []), [['a']])
})

// 31자를 넘기면 exceljs 가 던지고, []:*?/\ 는 엑셀이 시트 이름에 금지합니다.
// AFM 의 `Profile (point ...)` 처럼 office 값이 시트 이름에 섞이는 자리가 있어
// 자르기만으로는 부족합니다.
test('safeSheetName 은 금지 문자를 눕히고 31자로 자른다', () => {
  assert.equal(safeSheetName('Summary (by site)'), 'Summary (by site)')
  assert.equal(safeSheetName('R0A8/CD:1*2?[x]'), 'R0A8_CD_1_2_x_')
  assert.equal(safeSheetName('P'.repeat(40)).length, 31)
  assert.equal(safeSheetName('   '), 'Sheet')
  assert.equal(safeSheetName(''), 'Sheet')
})
