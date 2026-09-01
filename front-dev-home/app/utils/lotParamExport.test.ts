// Pure tests for the lot 파라미터 export builder.
// Run: node --test app/utils/lotParamExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { LOT_PARAM_HEADERS, buildLotParamRows, lotParamFileName } from './lotParamExport.ts'
import { evaluateLot } from './ruleEngine.ts'
import type { RecipeInput, RecipeResult, RuleCell } from './ruleEngine.ts'

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

// 판정은 손으로 짓지 않고 **엔진에게 받습니다** — 이 빌더가 지켜야 하는 것은
// evaluateLot 의 출력을 칸으로 옮기는 규칙이지, 판정 그 자체가 아닙니다.
const cell = (caps: RuleCell['caps']): RuleCell => ({
  id: 'c1',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['EV'] },
  caps,
  name_overrides: []
})

const judge = (recipes: RecipeInput[], caps: RuleCell['caps']): RecipeResult[] =>
  evaluateLot('R000', recipes, [cell(caps)]).recipes

test('one row per parameter, joined on recipe_id', () => {
  const recipes = [params('RCP-001', [['WAFER_CD', 13], ['EDGE_L', 8]])]
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'CBL ETCH CD')],
    recipes,
    judge(recipes, { WAFER: 9, EDGE: 20, _other: 12 })
  )

  // WAFER_CD 는 상한 9 를 넘겨 초과, EDGE_L 은 EDGE 상한 20 안이라 빈 칸.
  assert.deepEqual(rows, [
    ['R000', 'CBL ETCH CD', 'RCP-001', '상한 초과', 'WAFER_CD', '13', '9', '초과', ''],
    ['R000', 'CBL ETCH CD', 'RCP-001', '상한 초과', 'EDGE_L', '8', '20', '', '']
  ])
})

test('headers name what the user asked for', () => {
  assert.deepEqual([...LOT_PARAM_HEADERS], [
    'lot_cd', 'step', 'recipe_id', 'recipe_판정', 'parameter',
    'measure_points', 'cap', '상한 초과', '비고'
  ])
})

// 판정이 없는 두 경우는 서로 다른 사실입니다 — 하나는 고쳐야 할 일(룰이 없다),
// 다른 하나는 정상(이 job 은 원래 판정 대상이 아니다). 한 말로 뭉개면 파일을
// 읽는 사람이 그 둘을 구별할 수 없습니다.
test('판정이 없는 recipe 는 왜 없는지를 적는다', () => {
  const recipes = [params('RCP-001', [['WAFER_CD', 13]])]
  const noRules = buildLotParamRows([infoRow('RCP-001', 'step')], recipes, [])
  assert.equal(noRules[0]?.[3], '룰 없음')
  assert.equal(noRules[0]?.[8], '룰 없음')
  assert.equal(noRules[0]?.[7], '', '판정하지 않은 행에 초과를 적으면 안 됩니다')

  const exempt = [params('RCP_WCDU_01', [['WAFER_CD', 104]])]
  const rows = buildLotParamRows([infoRow('RCP_WCDU_01', 'step')], exempt, [])
  assert.equal(rows[0]?.[3], '판정 범위 밖(특수 job)')
})

// gray recipe(룰 미정·어노테이션 미설정)를 빈 칸으로 두면 깨끗한 recipe 와
// 파일에서 같아집니다 — 화면의 '판정 제외' 와 같은 말을 적습니다.
test('gray recipe 는 사유를 모든 행에 적는다', () => {
  const recipes = [params('RCP-001', [['WAFER_CD', 13], ['EDGE_L', 8]])]
  // fac_id 가 맞지 않는 셀뿐이라 룰을 못 찾습니다 → gray A.
  const gray = evaluateLot('R000', recipes, [{
    ...cell({ WAFER: 9, _other: 20 }),
    selector: { fac_id: 'M11', recipe_class: 'Main' }
  }]).recipes
  const rows = buildLotParamRows([infoRow('RCP-001', 'step')], recipes, gray)
  assert.deepEqual(rows.map(r => r[3]), ['판정 제외', '판정 제외'])
  assert.deepEqual(rows.map(r => r[8]), ['룰 미정', '룰 미정'])
  assert.deepEqual(rows.map(r => r[7]), ['', ''], 'gray 는 초과로 세지 않습니다')
})

// 이름으로 잇습니다. 순서로 이으면 mother 버킷처럼 한쪽만 좁혀진 날 한 칸씩
// 밀린 cap 이 조용히 붙습니다.
test('파라미터 판정은 이름으로 이어 붙는다', () => {
  const judged = judge([params('RCP-001', [['A', 1], ['WAFER_CD', 13]])], { WAFER: 9, _other: 20 })
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'step')],
    [params('RCP-001', [['WAFER_CD', 13]])], // 화면이 A 를 걸러낸 상태
    judged
  )
  assert.deepEqual(rows[0]?.slice(4), ['WAFER_CD', '13', '9', '초과', ''])
})

// 원본 순서가 곧 정보입니다. 이름순으로 정렬하면 "WAFER" 가 알파벳상 거의
// 끝이라 가장 중요한 파라미터가 표 맨 아래로 밀립니다.
test('parameter order is the source order, never sorted', () => {
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'step')],
    [params('RCP-001', [['WAFER_CD', 13], ['EDGE_L', 8], ['CD_BAR', 3]])],
    []
  )
  assert.deepEqual(rows.map(r => r[4]), ['WAFER_CD', 'EDGE_L', 'CD_BAR'])
})

// 화면 순서 그대로 나가야 합니다 — 표와 파일이 다른 순서면 둘을 나란히 놓고
// 읽을 수 없습니다.
test('recipe order is the caller order, never re-sorted', () => {
  const rows = buildLotParamRows(
    [infoRow('RCP-B', 'step B'), infoRow('RCP-A', 'step A')],
    [params('RCP-A', [['P', 1]]), params('RCP-B', [['Q', 2]])],
    []
  )
  assert.deepEqual(rows.map(r => r[2]), ['RCP-B', 'RCP-A'])
})

test('a recipe with no parameters still gets a row', () => {
  const rows = buildLotParamRows([infoRow('RCP-001', 'step')], [], [])
  assert.deepEqual(rows, [['R000', 'step', 'RCP-001', '룰 없음', '', '', '', '', '룰 없음']])
})

test('a recipe present only in recipe-params is not invented', () => {
  // 조인의 축은 화면이 보여주는 recipe 목록입니다. params 쪽에만 있는 recipe 를
  // 끌어오면 파일이 화면보다 많은 것을 말하게 됩니다.
  const rows = buildLotParamRows([], [params('RCP-GHOST', [['P', 1]])], [])
  assert.deepEqual(rows, [])
})

test('zero measure points is written, not blanked', () => {
  // "" 는 파라미터가 없다는 뜻으로 이미 쓰고 있으므로, 0 을 빈 칸으로 내보내면
  // 두 사실이 한 칸에서 뭉갭니다.
  const rows = buildLotParamRows(
    [infoRow('RCP-001', 'step')],
    [params('RCP-001', [['EDGE_EX_L', 0]])],
    []
  )
  assert.equal(rows[0]?.[5], '0')
})

test('filename sanitises the lot code and names the bucket', () => {
  assert.equal(lotParamFileName('R0A8', 'only_normal'), 'R0A8_only_normal_params.csv')
  assert.equal(lotParamFileName('R0/A8', 'all'), 'R0_A8_all_params.csv')
  assert.equal(lotParamFileName('', 'all'), 'unknown_all_params.csv')
})

// 페이지가 넘기는 것은 API 의 버킷 키라 "_summary" 가 붙어 있습니다. 그대로
// 쓰면 파일 이름이 스스로를 요약이라고 잘못 소개합니다.
test('filename drops the bucket key\'s _summary tail', () => {
  assert.equal(lotParamFileName('R0A8', 'all_summary'), 'R0A8_all_params.csv')
  assert.equal(
    lotParamFileName('R0A8', 'mother_normal_summary'),
    'R0A8_mother_normal_params.csv'
  )
  // 꼬리가 아니라 중간에 있으면 건드리지 않습니다.
  assert.equal(lotParamFileName('R0A8', 'summary_x'), 'R0A8_summary_x_params.csv')
})

test('초과만 상태의 내보내기는 파일 이름으로 구별된다', () => {
  // 같은 lot·같은 버킷에서 두 번 내려받으면 전체 파일과 초과 파일이 한
  // 폴더에 섞입니다. 행 수는 파일을 열어야 보이므로 이름이 말해야 합니다.
  assert.equal(lotParamFileName('R123', 'only_normal_summary'), 'R123_only_normal_params.csv')
  assert.equal(lotParamFileName('R123', 'only_normal_summary', true), 'R123_only_normal_params_flagged.csv')
  assert.equal(lotParamFileName('R123', 'only_normal_summary', false), 'R123_only_normal_params.csv')
})
