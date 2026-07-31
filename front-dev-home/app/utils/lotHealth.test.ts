// Pure-logic tests for lotHealth. Zero deps:
//   node --test app/utils/lotHealth.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  augmentRow, buildLotVerdicts, extractStage, recipeKey, verdictSortValue,
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
    lot_cd: 'x', kind: 'judged' as const, health, violation_ratio: ratio,
    violation_recipes: 0, judged_recipes: 0, total_recipes: 0,
    gray_recipes: 0, gray_reasons: {}, coverage: 1
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

test('a row with no verdict still renders as no-verdict, not a crash', () => {
  const row = augmentRow({ lot_cd: 'R000', ctn_desc: 'EV lot' }, undefined)
  assert.equal(row.verdict.kind, 'no-rules')
  assert.equal(row.verdict.health, null)
  assert.equal(row.dev_stage, 'EV')
  assert.equal(row.stage_inferred, false)
})

test('augmentRow preserves the original row fields', () => {
  const row = augmentRow(
    { lot_cd: 'R000', ctn_desc: 'Pool lot', para_16: 42 },
    undefined
  )
  assert.equal(row.para_16, 42)
  assert.equal(row.dev_stage, 'Pool')
})

test('within one colour the worse ratio comes first', () => {
  const mk = (ratio: number) => ({
    lot_cd: 'x', kind: 'judged' as const, health: 'red' as const, violation_ratio: ratio,
    violation_recipes: 0, judged_recipes: 0, total_recipes: 0,
    gray_recipes: 0, gray_reasons: {}, coverage: 1
  })
  assert.ok(verdictSortValue(mk(0.9)) < verdictSortValue(mk(0.3)))
})
