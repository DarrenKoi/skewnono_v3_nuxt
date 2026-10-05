// Pure-logic tests for ruleExplain. Zero deps — run with Node's built-in runner:
//   node --test app/utils/ruleExplain.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyAnnotation, evaluateRecipe, resolveRuleCell,
  type Annotation, type JudgeOptions, type Parameter, type RecipeInput, type RuleCell
} from './ruleEngine.ts'
import { capSourceLabel, explainRecipe, selectorSummary } from './ruleExplain.ts'

// --- fixtures: providers/rules.py 의 R3 seed 셀 모양 그대로 ---
const wfOverride = { patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains' as const, cap: 13 }
const main = (id: string, selector: Omit<RuleCell['selector'], 'fac_id' | 'recipe_class'>, edge: number, edgeEx: number): RuleCell => ({
  id,
  selector: { fac_id: 'R3', recipe_class: 'Main', ...selector },
  caps: { WAFER: 13, LEVEL: 4, EDGE: edge, EDGE_EX: edgeEx, _other: 9 },
  name_overrides: [wfOverride]
})
const coreEarlyDram = main('r3-core-early-dram', { family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' }, 10, 0)
const coreTvPv = main('r3-core-tvpv', { family: 'Core', phase_in: ['TV', 'PV'] }, 16, 16)
const poolBeforeDram = main('r3-pool-before-dram', { family: 'Pool', yield_check: 'before', memory_class: 'DRAM' }, 10, 0)
const vg = main('r3-vg', { family: 'VG_RTC_Cubic' }, 10, 0)
const sampleDram: RuleCell = {
  id: 'r3-sample-dram',
  selector: { fac_id: 'R3', recipe_class: 'Sample', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 0 },
  name_overrides: [
    { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
    { patterns: ['DUMMY'], match: 'affix', cap: null },
    { patterns: ['ALIGN'], match: 'affix', cap: null }
  ]
}
const CELLS = [coreEarlyDram, coreTvPv, poolBeforeDram, vg, sampleDram]

const recipe = (parameters: Parameter[], over: Partial<RecipeInput> = {}): RecipeInput => ({
  lot_cd: 'R000', recipe_id: 'RCP-1', fac_id: 'R3', ctn_desc: 'step', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 't-EV', memory_class_auto: 'DRAM',
  parameters, ...over
})

/** 화면이 가는 길 그대로: 판정하고, 그 판정이 쓴 입력·셀(`basis`)로 설명합니다. */
const explain = (input: RecipeInput, opts: JudgeOptions & { cells?: RuleCell[] } = {}) => {
  const merged = applyAnnotation(input, opts.annotation)
  const result = evaluateRecipe(merged, resolveRuleCell(merged, opts.cells ?? CELLS), opts)
  const ex = explainRecipe(result.basis.recipe, result, result.basis.cell)
  // 파라미터 행은 deviceDrill 이 그리는 그대로: 엔진 결과 + 화면 출처 표기.
  const gray = ex.cell.kind === 'gray'
  const params = result.results.map(p => ({ ...p, source_label: capSourceLabel(p, gray) }))
  return { result, ex: { ...ex, params } }
}
const param = (ex: ReturnType<typeof explain>['ex'], name: string) => ex.params.find(p => p.name === name)!

test('_other fallback: 이름으로 타입을 못 정한 파라미터는 fallback 으로 적힙니다', () => {
  const { ex } = explain(recipe([{ name: 'WAFER_CD', point_count: 13 }, { name: 'CELL_SP', point_count: 13 }]))
  const p = param(ex, 'CELL_SP')
  assert.equal(p.cap, 9)
  assert.equal(p.cap_source, 'fallback')
  assert.equal(p.source_label, '_other fallback')
  assert.equal(p.over_by, 4)
  assert.equal(param(ex, 'WAFER_CD').source_label, '타입 cap')
  assert.deepEqual(ex.cell, { kind: 'cell', id: 'r3-core-early-dram', summary: 'R3 · Main · Core · t-EV/EV · DRAM' })
  assert.equal(ex.sentence, 'Core · t-EV · DRAM 으로 읽혀 r3-core-early-dram 셀이 적용됐고, CELL_SP 가 cap 9 를 4 초과했습니다.')
})

test('이름 예외: 숫자를 주면 "이름 예외", null 을 주면 "면제" 입니다', () => {
  const named = explain(recipe([{ name: 'CD_WF_1', point_count: 13 }])).ex
  assert.equal(param(named, 'CD_WF_1').cap_source, 'name')
  assert.equal(param(named, 'CD_WF_1').source_label, '이름 예외')

  // Sample 의 `_other` 는 0 이라, 면제가 아니면 point 1 개짜리 Dummy 가 위반입니다.
  const { ex, result } = explain(recipe([{ name: 'Dummy', point_count: 1 }], { recipe_class: 'Sample' }))
  const dummy = param(ex, 'Dummy')
  assert.equal(dummy.cap, null)
  assert.equal(dummy.cap_source, 'exempt')
  assert.equal(dummy.source_label, '면제')
  assert.equal(dummy.over_by, null)
  assert.equal(result.pass, true)
  // Sample 셀은 family·phase 를 키로 쓰지 않으므로 입력 줄에도 문장 머리에도 없습니다.
  assert.ok(!ex.input_rows.some(r => r.label === 'phase' || r.label === 'yield_check'))
  // 면제는 견줄 cap 이 없었던 것이라 "cap 이내" 라고 하지 않습니다.
  assert.equal(ex.sentence, 'Sample · DRAM 으로 읽혀 r3-sample-dram 셀이 적용됐고, cap 이 있는 파라미터가 없습니다(1개 면제).')
})

test('셀에 그 타입의 cap 이 없으면 면제가 아니라 "cap 없음" 입니다', () => {
  const noLevel: RuleCell = { ...coreEarlyDram, caps: { WAFER: 13, EDGE: 10, EDGE_EX: 0, _other: 9 } }
  const { ex } = explain(recipe([{ name: 'LEVEL_1', point_count: 40 }]), { cells: [noLevel] })
  assert.equal(param(ex, 'LEVEL_1').cap, null)
  assert.equal(param(ex, 'LEVEL_1').source_label, 'cap 없음')
  assert.match(ex.sentence, /cap 이 있는 파라미터가 없습니다\(1개 cap 없음\)\.$/)
})

// 회귀: cap 이 null 인 파라미터(cap 없음 · 면제)를 "cap 이내" 로 세면 안 됩니다.
test('cap 없는 파라미터가 섞이면 이내인 개수와 cap 없는 개수를 나눠 말합니다', () => {
  const noLevel: RuleCell = { ...coreEarlyDram, caps: { WAFER: 13, EDGE: 10, EDGE_EX: 0, _other: 9 } }
  const params = [
    { name: 'WAFER_CD', point_count: 13 },
    { name: 'EDGE_L', point_count: 10 },
    { name: 'CELL_SP', point_count: 9 },
    { name: 'LEVEL_1', point_count: 40 }
  ]
  const unset = explain(recipe(params), { cells: [noLevel] })
  assert.equal(unset.result.pass, true, '판정 자체는 그대로입니다')
  assert.match(unset.ex.sentence, /cap 이 있는 파라미터 3개는 모두 이내이고, 1개는 cap 없음입니다\.$/)

  // 면제(Sample 의 Dummy)도 같습니다.
  const exempt = explain(recipe([{ name: 'WAFER_CD', point_count: 13 }, { name: 'Dummy', point_count: 1 }], { recipe_class: 'Sample' })).ex
  assert.match(exempt.sentence, /cap 이 있는 파라미터 1개는 모두 이내이고, 1개는 면제입니다\.$/)

  // 둘이 섞이면 둘 다 적습니다.
  const mixedCell: RuleCell = { ...sampleDram, caps: { WAFER: 13, EDGE: 10, EDGE_EX: 0, _other: 0 } }
  const mixed = explain(recipe([
    { name: 'WAFER_CD', point_count: 13 }, { name: 'LEVEL_1', point_count: 40 }, { name: 'Dummy', point_count: 1 }
  ], { recipe_class: 'Sample' }), { cells: [mixedCell] }).ex
  assert.match(mixed.sentence, /cap 이 있는 파라미터 1개는 모두 이내이고, 2개는 cap 없음·면제입니다\.$/)
})

test('판정에서 뺀 son 과 cap 없는 파라미터가 함께 있으면 범위를 "판정한 파라미터 중" 으로 좁힙니다', () => {
  const noLevel: RuleCell = { ...coreEarlyDram, caps: { WAFER: 13, EDGE: 10, EDGE_EX: 0, _other: 9 } }
  const { ex } = explain(recipe([
    { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
    { name: 'EDGE_L', point_count: 16, mother: false, region: 1 },
    { name: 'LEVEL_1', point_count: 40, mother: true, region: 2 }
  ]), { cells: [noLevel], judgeSons: false })
  assert.match(ex.sentence, /판정한 파라미터 중 cap 이 있는 파라미터 1개는 모두 이내이고, 1개는 cap 없음입니다\.$/)
})

// son 이 mother 의 cap 을 받는 것은 `effectiveCap` 의 한 경로뿐입니다: 자기 cap 이
// `_other` fallback 이고, 같은 region 에 mother 가 있을 때.
const grouped: Parameter[] = [
  { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
  { name: 'CELL_SP', point_count: 13, mother: false, region: 1 }, // fallback → 13 상속
  { name: 'EDGE_L', point_count: 16, mother: false, region: 1 }, // 타입 cap 은 상속이 덮지 않음
  { name: 'LWR', point_count: 13, mother: false, region: 2 } // mother 없는 region
]

test('son 상속: fallback 이던 son 만 mother 의 cap 을 받고 "mother 상속" 으로 적힙니다', () => {
  const { ex } = explain(recipe(grouped))
  assert.deepEqual(ex.params.map(p => [p.name, p.cap, p.cap_source]), [
    ['WAFER_CD', 13, 'type'],
    ['CELL_SP', 13, 'inherited'],
    ['EDGE_L', 10, 'type'],
    ['LWR', 9, 'fallback']
  ])
  assert.equal(param(ex, 'CELL_SP').source_label, 'mother 상속')
  assert.equal(param(ex, 'CELL_SP').over_by, null, '상속받은 13 안이라 위반이 아닙니다')
  assert.equal(ex.sentence, 'Core · t-EV · DRAM 으로 읽혀 r3-core-early-dram 셀이 적용됐고, EDGE_L 가 cap 10 를 6 초과하는 등 파라미터 2개가 cap 을 넘었습니다.')
})

test('judgeSons=false: 출처는 그대로이고, mother 에 얹힌 son 에만 "· 제외" 가 붙습니다', () => {
  const { ex } = explain(recipe(grouped), { judgeSons: false })
  // 상속은 cap 을 정하는 일이고 judgeSons 는 판정에 넣느냐의 일이라 서로 독립입니다.
  assert.deepEqual(ex.params.map(p => [p.name, p.cap_source, p.judged, p.source_label]), [
    ['WAFER_CD', 'type', true, '타입 cap'],
    ['CELL_SP', 'inherited', false, 'mother 상속 · 제외'],
    ['EDGE_L', 'type', false, '타입 cap · 제외'],
    ['LWR', 'fallback', true, '_other fallback']
  ])
  assert.equal(param(ex, 'EDGE_L').over_by, null, '판정에서 뺀 파라미터는 초과분을 적지 않습니다')
  assert.match(ex.sentence, /LWR 가 cap 9 를 4 초과했습니다\.$/)
})

test('판정에서 뺀 파라미터가 있으면 "모든 파라미터" 라고 하지 않습니다', () => {
  const { ex } = explain(recipe(grouped.slice(0, 3)), { judgeSons: false })
  assert.match(ex.sentence, /판정한 파라미터는 모두 cap 이내입니다\.$/)
})

test('Pool 은 phase 를 이깁니다: 셀 축은 yield_check 이고 phase 는 쓰지 않았다고 적습니다', () => {
  // CONTEXT.md §Product Family — "DRAM Pool제 (@Spica PV)". phase 가 PV 여도
  // r3-core-tvpv(EDGE 16)가 아니라 Pool 셀(EDGE 10)이 적용됩니다.
  const pool = recipe([{ name: 'EDGE_L', point_count: 16 }], { family: 'Pool', phase: 'PV' })
  const { ex } = explain(pool, { annotation: { yield_check: 'before' } })
  assert.deepEqual(ex.cell, { kind: 'cell', id: 'r3-pool-before-dram', summary: 'R3 · Main · Pool · 수율 전 · DRAM' })
  assert.equal(ex.sentence, 'Pool · 수율 전 · DRAM 으로 읽혀 r3-pool-before-dram 셀이 적용됐고, EDGE_L 가 cap 10 를 6 초과했습니다.')
  assert.deepEqual(ex.input_rows.filter(r => r.label === 'phase' || r.label === 'yield_check'), [
    { label: 'yield_check', value: '수율 전' },
    { label: 'phase', value: 'PV (Pool 은 셀 선택에 phase 를 쓰지 않습니다)' }
  ])
})

test('Gray-B: 빠진 어노테이션을 이름으로 말하고 cap 출처는 적지 않습니다', () => {
  const noMem = explain(recipe([{ name: 'EDGE_L', point_count: 99 }], { memory_class_auto: 'unknown' })).ex
  assert.deepEqual(noMem.cell, { kind: 'gray', gray: 'B', reason: 'memory_class 미설정' })
  assert.equal(noMem.sentence, 'memory_class 가 없어 판정하지 않았습니다(Gray-B).')
  assert.deepEqual(noMem.params.map(p => [p.cap, p.cap_source, p.source_label, p.over_by]), [[null, 'unset', null, null]])
  // gray 는 셀이 없으니 어느 축이 비었는지 보이도록 두 축을 다 적습니다.
  assert.ok(noMem.input_rows.some(r => r.label === 'phase') && noMem.input_rows.some(r => r.label === 'yield_check'))
  assert.ok(noMem.input_rows.some(r => r.label === 'memory_class' && r.value === '미설정'))

  const noYield = explain(recipe([{ name: 'EDGE_L', point_count: 99 }], { family: 'Pool' })).ex
  assert.equal(noYield.sentence, 'yield_check 가 없어 판정하지 않았습니다(Gray-B).')
  assert.ok(noYield.input_rows.some(r => r.label === 'yield_check' && r.value === '미설정'))
})

test('Gray-A: 맞는 셀이 없다고 말합니다', () => {
  const { ex } = explain(recipe([{ name: 'EDGE_L', point_count: 99 }], { fac_id: 'M14' }))
  assert.deepEqual(ex.cell, { kind: 'gray', gray: 'A', reason: '룰 미정' })
  assert.equal(ex.sentence, '맞는 룰 셀이 없어 판정하지 않았습니다(Gray-A).')
  assert.equal(ex.params[0]!.source_label, null)
})

test('memory_class 의 출처: 자동 · 어노테이션 · VG 기본값', () => {
  const row = (input: RecipeInput, annotation?: Annotation) =>
    explain(input, { annotation }).ex.input_rows.find(r => r.label === 'memory_class')!.value
  const p = [{ name: 'WAFER_CD', point_count: 1 }]
  assert.equal(row(recipe(p)), 'DRAM (자동)')
  assert.equal(row(recipe(p, { memory_class_auto: 'unknown' }), { memory_class: 'DRAM' }), 'DRAM (어노테이션)')
  // D7 — VG·RTC·Cubic 은 class 가 없으면 DRAM 쪽으로 환원됩니다.
  const vgEx = explain(recipe(p, { family: 'VG_RTC_Cubic', phase: null, memory_class_auto: 'unknown' })).ex
  assert.equal(vgEx.input_rows.find(r => r.label === 'memory_class')!.value, 'DRAM (VG·RTC·Cubic 기본값)')
  // VG 셀은 phase 도 memory_class 도 키로 쓰지 않습니다.
  assert.equal(vgEx.sentence, 'VG·RTC·Cubic 으로 읽혀 r3-vg 셀이 적용됐고, 모든 파라미터가 cap 이내입니다.')
})

test('파라미터가 없는 recipe 를 "cap 이내" 라고 하지 않습니다', () => {
  assert.match(explain(recipe([])).ex.sentence, /판정할 파라미터가 없습니다\.$/)
})

test('selectorSummary 는 selector 에 있는 축만 적습니다', () => {
  assert.equal(selectorSummary(coreTvPv), 'R3 · Main · Core · TV/PV')
  assert.equal(selectorSummary(sampleDram), 'R3 · Sample · DRAM')
})

// 회귀: cap 없는 mother 를 물려받아 null 이 된 son 은 면제가 아닙니다.
test('cap 없는 mother 를 상속한 son 은 "면제" 가 아니라 "cap 없음" 으로 셉니다', () => {
  const noLevel: RuleCell = {
    ...coreEarlyDram,
    caps: { WAFER: 13, EDGE: 10, EDGE_EX: 0, _other: 9 },
    name_overrides: []
  }
  const { ex, result } = explain(recipe([
    { name: 'LEVEL_1', point_count: 40, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 13, mother: false, region: 1 }
  ]), { cells: [noLevel] })
  assert.deepEqual(ex.params.map(p => [p.name, p.cap, p.cap_source]), [
    ['LEVEL_1', null, 'unset'],
    ['CELL_SP', null, 'inherited']
  ])
  assert.equal(result.pass, true)
  assert.doesNotMatch(ex.sentence, /면제/)
  assert.match(ex.sentence, /cap 이 있는 파라미터가 없습니다\(2개 cap 없음\)\.$/)
})
