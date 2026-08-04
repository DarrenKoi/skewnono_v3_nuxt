// Pure-logic tests for lotHealth. Zero deps:
//   node --test app/utils/lotHealth.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  augmentRow, buildLotVerdicts, extractStage, isJudgeExempt, paraTotal, recipeKey,
  scopeRecipesToBucket, verdictSortValue,
  type RuleSet
} from './lotHealth.ts'
import type { RecipeInput, RuleCell } from './ruleEngine.ts'

// --- fixtures ---

// EDGE cap 10; WAFER 13; _other 9. Core/Main/DRAM 만 매칭됩니다.
const coreCell: RuleCell = {
  id: 'r3-core-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: []
}

const rules: RuleSet = {
  cells: [coreCell],
  thresholds: { yellow_at: 0.1, red_at: 0.2 }
}

const recipe = (
  recipe_id: string,
  edgePoints: number,
  extra: Partial<RecipeInput> = {}
): RecipeInput => ({
  lot_cd: 'R000',
  recipe_id,
  fac_id: 'R3',
  ctn_desc: 'EV DRAM Core lot R000',
  prod_catg_cd: 'DRAM',
  recipe_class: 'Main',
  family: 'Core',
  phase: 'EV',
  memory_class_auto: 'DRAM',
  parameters: [{ name: 'EDGE_L', point_count: edgePoints }],
  ...extra
})

const rulesByFab = { R3: rules }

// --- judged verdicts ---

test('a violating recipe drives the ratio and the colour', () => {
  const rows = [recipe('A', 20), recipe('B', 5), recipe('C', 5), recipe('D', 5)]
  const v = buildLotVerdicts(rows, rulesByFab).get('R000')!

  assert.equal(v.kind, 'judged')
  assert.equal(v.violation_recipes, 1)
  assert.equal(v.judged_recipes, 4)
  assert.equal(v.violation_ratio, 0.25)
  assert.equal(v.health, 'red') // 0.25 >= red_at 0.2
})

test('server thresholds win over the seed defaults', () => {
  const rows = [recipe('A', 20), recipe('B', 5), recipe('C', 5), recipe('D', 5)]
  const lenient: RuleSet = { cells: [coreCell], thresholds: { yellow_at: 0.5, red_at: 0.9 } }
  const v = buildLotVerdicts(rows, { R3: lenient }).get('R000')!

  // Same 0.25 ratio, but this fab's own thresholds call it green.
  assert.equal(v.violation_ratio, 0.25)
  assert.equal(v.health, 'green')
})

// --- gray / coverage ---

test('gray recipes leave the denominator and are counted by reason', () => {
  const rows = [
    recipe('A', 20),
    // memory_class 를 모르면 이 cell 에 매칭되지 않습니다 -> gray B.
    recipe('B', 5, { memory_class_auto: 'unknown' }),
    recipe('C', 5, { memory_class_auto: 'unknown' })
  ]
  const v = buildLotVerdicts(rows, rulesByFab).get('R000')!

  assert.equal(v.total_recipes, 3)
  assert.equal(v.gray_recipes, 2)
  assert.equal(v.judged_recipes, 1)
  // 분모는 판정된 1건 -> 1/1
  assert.equal(v.violation_ratio, 1)
  assert.deepEqual(v.gray_reasons, { 'memory_class 미설정': 2 })
})

test('coverage is judged over total', () => {
  const rows = [
    recipe('A', 5),
    recipe('B', 5),
    recipe('C', 5, { memory_class_auto: 'unknown' })
  ]
  const v = buildLotVerdicts(rows, rulesByFab).get('R000')!
  assert.equal(v.coverage, 2 / 3)
})

// --- no-rules fabs ---

test('a fab with no rules is no-verdict, not green', () => {
  const rows = [recipe('A', 5, { lot_cd: 'M11A', fac_id: 'M11' })]
  const v = buildLotVerdicts(rows, rulesByFab).get('M11A')!

  assert.equal(v.kind, 'no-rules')
  assert.equal(v.health, null, 'no rules must not read as a passing colour')
  assert.equal(v.violation_ratio, null)
  assert.equal(v.coverage, 0)
  assert.equal(v.total_recipes, 1, 'the recipes still exist, they are just unjudgeable')
})

test('an explicit null ruleset is treated as no-rules', () => {
  const rows = [recipe('A', 5, { lot_cd: 'M11A', fac_id: 'M11' })]
  const v = buildLotVerdicts(rows, { R3: rules, M11: null }).get('M11A')!
  assert.equal(v.kind, 'no-rules')
})

test('an empty cell list is no-rules, not "everything is gray"', () => {
  // 빈 cells 로 evaluateLot 을 돌리면 전부 gray 가 되어 "룰이 없다" 와
  // "룰은 있는데 어노테이션이 없다" 가 한 값으로 뭉갭니다.
  const rows = [recipe('A', 5)]
  const v = buildLotVerdicts(rows, { R3: { cells: [], thresholds: rules.thresholds } }).get('R000')!
  assert.equal(v.kind, 'no-rules')
  assert.equal(v.gray_recipes, 0)
})

test('rules present but EVERY recipe gray is no-verdict, not green', () => {
  // 이 경로가 예전에 green 을 냈습니다: 판정 대상이 0건이면 ratio 가 0 이 되고
  // classifyHealth(0) 이 green 이라, 아무것도 못 본 lot 이 "깨끗함" 으로 보였습니다.
  // fab 에 룰이 없는 경우만 막아 두었기 때문에 이쪽으로 새어 나왔습니다.
  const rows = [
    recipe('A', 5, { memory_class_auto: 'unknown' }),
    recipe('B', 5, { memory_class_auto: 'unknown' })
  ]
  const v = buildLotVerdicts(rows, rulesByFab).get('R000')!

  assert.equal(v.judged_recipes, 0)
  assert.equal(v.gray_recipes, 2)
  assert.equal(v.health, null, '아무것도 판정하지 못한 lot 은 색을 가질 수 없습니다')
  assert.equal(v.violation_ratio, null)
  assert.equal(v.kind, 'no-rules')
  assert.equal(v.coverage, 0)
})

// --- judge-exempt jobs (_WCDU / _FCDU / _FULL, user-confirmed 2026-08-04) ---

test('isJudgeExempt matches the three suffixes, case-insensitive, at the end only', () => {
  assert.equal(isJudgeExempt('RCP-R000-001_WCDU'), true)
  assert.equal(isJudgeExempt('RCP-R000-001_FCDU'), true)
  assert.equal(isJudgeExempt('RCP-R000-001_full'), true)
  // 접미사가 아니라 중간에 있으면 판정 대상입니다.
  assert.equal(isJudgeExempt('RCP_FULL-R000-001'), false)
  assert.equal(isJudgeExempt('RCP-R000-001'), false)
  assert.equal(isJudgeExempt(''), false)
})

test('exempt recipes leave BOTH the numerator and the denominator', () => {
  const rows = [
    recipe('A', 20), // violating
    recipe('B', 5),
    // 위반 point 수라도 판정 외 job 이면 아무 데도 집계되지 않아야 합니다.
    recipe('C_WCDU', 99),
    recipe('D_FULL', 99)
  ]
  const v = buildLotVerdicts(rows, rulesByFab).get('R000')!

  assert.equal(v.total_recipes, 2, 'exempt jobs must not dilute the denominator')
  assert.equal(v.judged_recipes, 2)
  assert.equal(v.violation_recipes, 1)
  assert.equal(v.exempt_recipes, 2)
  assert.equal(v.coverage, 1, 'coverage stays intact when only exempt jobs are removed')
})

test('a lot whose recipes are ALL exempt still gets a verdict carrying the count', () => {
  const rows = [recipe('A_FCDU', 5), recipe('B_FULL', 5)]
  const v = buildLotVerdicts(rows, rulesByFab).get('R000')!

  assert.equal(v.kind, 'no-rules')
  assert.equal(v.health, null)
  assert.equal(v.total_recipes, 0)
  assert.equal(v.exempt_recipes, 2, 'the tooltip needs the count to explain the empty coverage')
})

test('bucket scoping still applies before the exempt filter', () => {
  const rows = [recipe('A', 5), recipe('B_WCDU', 5)]
  const v = buildLotVerdicts(
    rows, rulesByFab, new Set([recipeKey('R000', 'A')])
  ).get('R000')!
  // 버킷에 없는 exempt recipe 는 exempt 로도 세지 않습니다.
  assert.equal(v.exempt_recipes, 0)
  assert.equal(v.total_recipes, 1)
})

// --- bucket scoping (the whole reason the filter exists) ---

test('bucket keys scope the verdict to the selected bucket', () => {
  const rows = [recipe('A', 20), recipe('B', 5), recipe('C', 5), recipe('D', 5)]

  const all = buildLotVerdicts(rows, rulesByFab).get('R000')!
  // 위반 recipe 'A' 가 빠진 버킷 -> 같은 lot 이라도 판정이 달라져야 합니다.
  const withoutViolator = buildLotVerdicts(
    rows,
    rulesByFab,
    new Set(['B', 'C', 'D'].map(id => recipeKey('R000', id)))
  ).get('R000')!

  assert.equal(all.violation_recipes, 1)
  assert.equal(withoutViolator.violation_recipes, 0)
  assert.equal(withoutViolator.total_recipes, 3)
  assert.notEqual(all.health, withoutViolator.health)
})

test('a bucket that excludes every recipe of a lot drops the lot entirely', () => {
  const rows = [recipe('A', 20)]
  const verdicts = buildLotVerdicts(rows, rulesByFab, new Set([recipeKey('R000', 'ZZZ')]))
  assert.equal(verdicts.has('R000'), false)
})

test('recipeKey separates lot and recipe unambiguously', () => {
  assert.notEqual(recipeKey('R00', '0-A'), recipeKey('R000', '-A'))
})

// --- scopeRecipesToBucket: 두 축(recipe · 파라미터)을 좁히는 유일한 지점 ---

const mixed = (recipe_id: string): RecipeInput => recipe(recipe_id, 5, {
  parameters: [
    { name: 'EDGE_L', point_count: 5, mother: true },
    { name: 'EDGE_R', point_count: 40, mother: false },
    { name: 'WAFER_CD', point_count: 9 } // 플래그 없음 = mother 아님
  ]
})

test('scoping drops recipes outside the bucket', () => {
  const scoped = scopeRecipesToBucket(
    [mixed('A'), mixed('B')], new Set([recipeKey('R000', 'A')]), false
  )
  assert.deepEqual(scoped.map(r => r.recipe_id), ['A'])
})

test('without motherOnly every parameter survives', () => {
  const scoped = scopeRecipesToBucket([mixed('A')], new Set([recipeKey('R000', 'A')]), false)
  assert.equal(scoped[0]!.parameters.length, 3)
})

test('motherOnly keeps only mother parameters', () => {
  const scoped = scopeRecipesToBucket([mixed('A')], new Set([recipeKey('R000', 'A')]), true)
  assert.deepEqual(scoped[0]!.parameters.map(p => p.name), ['EDGE_L'])
})

test('motherOnly does not mutate the source rows', () => {
  // 같은 recipeParams 배열을 버킷을 바꿔 가며 다시 좁힙니다. 원본을 건드리면
  // 두 번째 버킷은 이미 잘려 나간 배열을 보게 됩니다.
  const rows = [mixed('A')]
  scopeRecipesToBucket(rows, new Set([recipeKey('R000', 'A')]), true)
  assert.equal(rows[0]!.parameters.length, 3)
})

test('health and the outlier baseline see the same scoped rows', () => {
  // 이 함수가 존재하는 이유 그 자체 — 두 소비처가 같은 배열을 받습니다.
  // 40 point 짜리 EDGE_R 은 mother 가 아니므로 mother view 에서는 cap 위반도
  // outlier 후보도 되지 않아야 합니다.
  const keys = new Set([recipeKey('R000', 'A')])
  const everything = scopeRecipesToBucket([mixed('A')], keys, false)
  const motherView = scopeRecipesToBucket([mixed('A')], keys, true)

  assert.equal(buildLotVerdicts(everything, rulesByFab).get('R000')!.violation_recipes, 1)
  assert.equal(buildLotVerdicts(motherView, rulesByFab).get('R000')!.violation_recipes, 0)
  assert.equal(
    motherView.flatMap(r => r.parameters).some(p => p.point_count === 40), false,
    'outlier 기준선도 같은 배열에서 나오므로 40 point 파라미터가 남으면 안 됩니다'
  )
})

// --- multiple lots ---

test('lots are evaluated independently', () => {
  const rows = [
    recipe('A', 20),
    recipe('B', 5, { lot_cd: 'R001' })
  ]
  const verdicts = buildLotVerdicts(rows, rulesByFab)
  assert.equal(verdicts.get('R000')!.violation_recipes, 1)
  assert.equal(verdicts.get('R001')!.violation_recipes, 0)
})

// --- sorting ---

test('no-verdict lots sort last, red first', () => {
  const mk = (health: 'red' | 'yellow' | 'green', ratio: number) => ({
    kind: 'judged' as const, health, violation_ratio: ratio,
    violation_recipes: 0, judged_recipes: 4, total_recipes: 4,
    gray_recipes: 0, gray_reasons: {}, exempt_recipes: 0, coverage: 1
  })
  const order = [
    mk('green', 0), mk('red', 0.5), undefined, mk('yellow', 0.15)
  ].sort((a, b) => verdictSortValue(a) - verdictSortValue(b))

  assert.equal(order[0]!.health, 'red')
  assert.equal(order[1]!.health, 'yellow')
  assert.equal(order[2]!.health, 'green')
  assert.equal(order[3], undefined, 'no-verdict sorts last')
})

// --- stage chip / row augmentation ---

test('stage comes from the lot-level ctn_desc', () => {
  assert.equal(extractStage('t-EV DRAM T1Y 1T development lot R000'), 'EV')
  assert.equal(extractStage('Pool Tech C20 256G development lot R0A1'), 'Pool')
  assert.equal(extractStage('PV NAND lot'), 'PV')
  assert.equal(extractStage(''), '?')
  assert.equal(extractStage(undefined), '?')
})

const summaryRow = (ctn_desc: string, para_16 = 10) => ({
  lot_cd: 'R000', fac_id: 'R3', ctn_desc,
  para_all: para_16 + 6, para_16, para_13: 3, para_9: 2, para_5: 1,
  para_16_percent: 0, para_13_percent: 0, para_9_percent: 0, para_5_percent: 0,
  total_recipe: 10, avail_recipe: 8, avail_recipe_percent: 80
})

test('a row with no verdict still renders as no-verdict, not a crash', () => {
  const row = augmentRow(summaryRow('EV lot'), undefined)
  assert.equal(row.verdict.kind, 'no-rules')
  assert.equal(row.verdict.health, null)
  assert.equal(row.dev_stage, 'EV')
  assert.equal(row.stage_inferred, false)
})

test('augmentRow preserves the original row fields', () => {
  const row = augmentRow(summaryRow('Pool lot', 42), undefined)
  assert.equal(row.para_16, 42)
  assert.equal(row.dev_stage, 'Pool')
})

test('paraTotal sums the four tiers', () => {
  assert.equal(paraTotal(summaryRow('EV lot', 42)), 42 + 3 + 2 + 1)
})

test('within one colour the worse ratio comes first', () => {
  const mk = (ratio: number) => ({
    kind: 'judged' as const, health: 'red' as const, violation_ratio: ratio,
    violation_recipes: 0, judged_recipes: 4, total_recipes: 4,
    gray_recipes: 0, gray_reasons: {}, exempt_recipes: 0, coverage: 1
  })
  assert.ok(verdictSortValue(mk(0.9)) < verdictSortValue(mk(0.3)))
})
