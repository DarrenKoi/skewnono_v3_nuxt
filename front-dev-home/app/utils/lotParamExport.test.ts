// Pure tests for the lot 파라미터 export builder.
// Run: node --test app/utils/lotParamExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { LOT_PARAM_HEADERS, buildLotParamRows, lotParamFileName } from './lotParamExport.ts'
import type { RecipeInput } from './ruleEngine.ts'

const infoRow = (recipe_id: string, oper_desc: string, para_all = 0) => ({
  lot_cd: 'R000',
  recipe_id,
  oper_desc,
  para_all,
  fac_id: 'R3',
  ctn_desc: '',
  eqp_id: '',
  oper_id: '',
  oper_seq: 1,
  samp_seq: 1,
  chg_tm: '',
  para_16: 0,
  para_13: 0,
  para_9: 0,
  para_5: 0
} as unknown as Parameters<typeof buildLotParamRows>[0][number])

const params = (recipe_id: string, entries: [string, number][]): RecipeInput => ({
  lot_cd: 'R000',
  recipe_id,
  fac_id: 'R3',
  ctn_desc: '',
  prod_catg_cd: 'DRAM',
  recipe_class: 'Main',
  family: 'Core',
  phase: 'EV',
  memory_class_auto: 'DRAM',
  parameters: entries.map(([name, point_count]) => ({ name, point_count }))
})

test('one row per parameter, joined on recipe_id', () => {
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'SNC2(CELL OPEN ETCH CLN CD)')],
    [params('RCP-001', [['WAFER_CD', 13], ['EDGE_L', 8]])]
  )

  assert.deepEqual(rows, [
    ['R000', 'SNC2(CELL OPEN ETCH CLN CD)', 'RCP-001', 'WAFER_CD', '13'],
    ['R000', 'SNC2(CELL OPEN ETCH CLN CD)', 'RCP-001', 'EDGE_L', '8']
  ])
})

test('headers name what the user asked for', () => {
  assert.deepEqual([...LOT_PARAM_HEADERS], [
    'lot_cd', 'step', 'recipe_id', 'parameter', 'measure_points'
  ])
})

// 원본 순서가 곧 정보입니다. 이름순으로 정렬하면 "WAFER" 가 알파벳상 거의
// 끝이라 가장 중요한 파라미터가 표 맨 아래로 밀립니다.
test('parameter order is the source order, never sorted', () => {
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'step')],
    [params('RCP-001', [['WAFER_CD', 13], ['EDGE_L', 8], ['CD_BAR', 3]])]
  )
  assert.deepEqual(rows.map(r => r[3]), ['WAFER_CD', 'EDGE_L', 'CD_BAR'])
})

// 화면 순서 그대로 나가야 합니다 — 표와 파일이 다른 순서면 둘을 나란히 놓고
// 읽을 수 없습니다.
test('recipe order is the caller order, never re-sorted', () => {
  const rows = buildLotParamRows(
    [infoRow('RCP-B', 'step B'), infoRow('RCP-A', 'step A')],
    [params('RCP-A', [['P', 1]]), params('RCP-B', [['Q', 2]])]
  )
  assert.deepEqual(rows.map(r => r[2]), ['RCP-B', 'RCP-A'])
})

test('a recipe with no parameters still gets a row', () => {
  const rows = buildLotParamRows([infoRow('RCP-001', 'step')], [])
  assert.deepEqual(rows, [['R000', 'step', 'RCP-001', '', '']])
})

test('a recipe present only in recipe-params is not invented', () => {
  // 조인의 축은 화면이 보여주는 recipe 목록입니다. params 쪽에만 있는 recipe 를
  // 끌어오면 파일이 화면보다 많은 것을 말하게 됩니다.
  const rows = buildLotParamRows([], [params('RCP-GHOST', [['P', 1]])])
  assert.deepEqual(rows, [])
})

test('zero measure points is written, not blanked', () => {
  // "" 는 파라미터가 없다는 뜻으로 이미 쓰고 있으므로, 0 을 빈 칸으로 내보내면
  // 두 사실이 한 칸에서 뭉갭니다.
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'step')],
    [params('RCP-001', [['EDGE_EX_L', 0]])]
  )
  assert.equal(rows[0]?.[4], '0')
})

test('filename sanitises the lot code and names the bucket', () => {
  assert.equal(lotParamFileName('R0A8', 'only_normal'), 'R0A8_only_normal_params.csv')
  assert.equal(lotParamFileName('R0/A8', 'all'), 'R0_A8_all_params.csv')
  assert.equal(lotParamFileName('', 'all'), 'unknown_all_params.csv')
})
