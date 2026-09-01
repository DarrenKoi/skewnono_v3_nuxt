// Pure tests for the R3 룰 준수 워크북 빌더.
// Run: node --test app/utils/complianceExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { COMPLIANCE_HEADERS, buildComplianceWorkbook, complianceFileName } from './complianceExport.ts'
import { evaluateLot } from './ruleEngine.ts'
import type { LotHealth, RecipeInput, RuleCell } from './ruleEngine.ts'

const recipe = (
  recipe_id: string,
  entries: [string, number, (Partial<{ mother: boolean, region: number }>)?][]
): RecipeInput => ({
  lot_cd: 'R0A8',
  recipe_id,
  fac_id: 'R3',
  ctn_desc: 'DEV EV',
  prod_catg_cd: 'DRAM',
  recipe_class: 'Main',
  family: 'Core',
  phase: 'EV',
  memory_class_auto: 'DRAM',
  parameters: entries.map(([name, point_count, extra]) => ({ name, point_count, ...extra }))
})

const cell = (caps: RuleCell['caps'], fac_id = 'R3'): RuleCell => ({
  id: 'c1',
  selector: { fac_id, recipe_class: 'Main', family: 'Core', phase_in: ['EV'] },
  caps,
  name_overrides: []
})

// 판정은 손으로 짓지 않고 엔진에게 받습니다 — 이 빌더가 지켜야 하는 것은
// evaluateLot 의 출력을 칸으로 옮기는 규칙이지 판정 그 자체가 아닙니다.
const judge = (
  recipes: RecipeInput[],
  caps: RuleCell['caps'],
  judgeSons = true,
  fac_id = 'R3'
): LotHealth => evaluateLot('R0A8', recipes, [cell(caps, fac_id)], { judgeSons })

const sheetOf = (health: LotHealth, judgeSons = true) =>
  buildComplianceWorkbook({ health, ctn_desc: 'DEV EV', judgeSons, exportedAt: 'T' })

test('한 파라미터가 한 줄, 초과는 초과라고 적는다', () => {
  const rows = sheetOf(judge(
    [recipe('RCP-001', [['WAFER_CD', 13], ['EDGE_L', 8], ['CD_BAR', 3]])],
    { WAFER: 9, EDGE: 20, _other: 12 }
  ))[1]!.rows

  assert.deepEqual(rows[0], [...COMPLIANCE_HEADERS])
  assert.deepEqual(rows.slice(1), [
    ['R0A8', 'RCP-001', '상한 초과', 'WAFER_CD', 13, 9, '초과', ''],
    ['R0A8', 'RCP-001', '상한 초과', 'EDGE_L', 8, 20, '', ''],
    ['R0A8', 'RCP-001', '상한 초과', 'CD_BAR', 3, 12, '', '']
  ])
})

// 정상은 빈 칸입니다 — '정상' 을 적으면 두 문자열이 같은 폭으로 늘어서서
// 열을 훑을 때 초과가 눈에 튀지 않고, 자동 필터도 한 번에 안 끝납니다.
test('정상 파라미터의 초과 칸은 빈 칸이다', () => {
  const rows = sheetOf(judge([recipe('RCP-001', [['WAFER_CD', 5]])], { WAFER: 9, _other: 20 }))[1]!.rows
  assert.equal(rows[1]?.[6], '')
  assert.equal(rows[1]?.[2], '정상')
})

// point_count 와 cap 은 **숫자**로 나갑니다. 문자열로 내면 엑셀에서 정렬도
// 조건부 서식도 걸리지 않습니다.
test('measure_points 와 cap 은 숫자로 나간다', () => {
  const rows = sheetOf(judge([recipe('RCP-001', [['WAFER_CD', 13]])], { WAFER: 9, _other: 20 }))[1]!.rows
  assert.equal(typeof rows[1]?.[4], 'number')
  assert.equal(typeof rows[1]?.[5], 'number')
})

// gray recipe 를 빈 칸으로 두면 깨끗한 recipe 와 파일에서 같아집니다.
test('gray recipe 는 판정 제외와 사유를 적는다', () => {
  const rows = sheetOf(judge(
    [recipe('RCP-001', [['WAFER_CD', 13]])],
    { WAFER: 9, _other: 20 },
    true,
    'M11' // fac_id 가 맞는 셀이 없어 룰을 못 찾습니다
  ))[1]!.rows
  assert.equal(rows[1]?.[2], '판정 제외')
  assert.equal(rows[1]?.[6], '', 'gray 는 초과로 세지 않습니다')
  assert.equal(rows[1]?.[7], '룰 미정')
})

// son 토글을 끄면 son 은 판정에서 빠집니다. 상한을 넘긴 son 이 그냥 빈 칸이면
// "재 봤더니 상한 안" 과 구별되지 않습니다.
test('판정에서 뺀 son 이 상한을 넘겼으면 그 사실을 적는다', () => {
  const recipes = [recipe('RCP-001', [
    ['WAFER_CD', 5, { mother: true, region: 1 }],
    ['WAFER_SON', 13, { mother: false, region: 1 }]
  ])]
  const rows = sheetOf(judge(recipes, { WAFER: 9, _other: 20 }, false), false)[1]!.rows
  assert.equal(rows[2]?.[6], '', '판정 대상이 아니었으므로 초과 칸은 비어 있습니다')
  assert.equal(rows[2]?.[7], 'son 판정 제외 · 상한 초과')
  assert.equal(rows[1]?.[2], '정상', 'son 을 빼면 이 recipe 는 통과입니다')
})

test('파라미터가 없는 recipe 도 한 줄로 남는다', () => {
  const rows = sheetOf(judge([recipe('RCP-EMPTY', [])], { _other: 20 }))[1]!.rows
  assert.deepEqual(rows[1], ['R0A8', 'RCP-EMPTY', '정상', '', '', '', '', '파라미터 없음'])
})

// 슬라이드오버 머리말과 같은 숫자여야 합니다. son 토글은 거기 없지만, 파일의
// 숫자가 그 토글에 딸려 오므로 파일에는 적습니다.
test('요약은 자세히 머리말과 같은 숫자에 son 토글을 더한다', () => {
  const health = judge(
    [recipe('RCP-001', [['WAFER_CD', 13], ['WAFER_X', 20]]), recipe('RCP-002', [['EDGE_L', 3]])],
    { WAFER: 9, _other: 20 }
  )
  const summary = new Map(sheetOf(health)[0]!.rows.map(r => [r[0], r[1]]))
  assert.equal(summary.get('lot_cd'), 'R0A8')
  assert.equal(summary.get('recipe'), 2)
  assert.equal(summary.get('상한 초과 recipe'), 1)
  assert.equal(summary.get('상한 초과 파라미터'), 2)
  assert.equal(summary.get('son 파라미터 판정'), '포함')
  assert.equal(sheetOf(health, false)[0]!.rows.at(-2)?.[1], '제외')
})

test('시트는 요약과 판정 두 장이다', () => {
  assert.deepEqual(
    sheetOf(judge([recipe('RCP-001', [['A', 1]])], { _other: 20 })).map(s => s.name),
    ['요약', '판정']
  )
})

// 룰을 고치면 같은 디바이스의 판정이 날마다 달라집니다 — 이름이 언제의
// 판정인지 말하지 않으면 다운로드 폴더에서 두 파일을 구별할 수 없습니다.
test('파일 이름은 lot 코드를 씻고 날짜를 붙인다', () => {
  assert.equal(complianceFileName('R0A8', '2026-09-01'), 'R0A8_rule_compliance_2026-09-01.xlsx')
  assert.equal(complianceFileName('R0/A8', '2026-09-01'), 'R0_A8_rule_compliance_2026-09-01.xlsx')
  assert.equal(complianceFileName('', '2026-09-01'), 'unknown_rule_compliance_2026-09-01.xlsx')
})
