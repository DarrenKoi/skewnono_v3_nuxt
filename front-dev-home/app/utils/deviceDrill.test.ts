// Pure tests for the drill view-model adapters. Run: node --test app/utils/deviceDrill.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toOutlierDrill, toViolationDrill } from './deviceDrill.ts'
import { evaluateLot, type RecipeInput, type RuleCell } from './ruleEngine.ts'
import { detectDeviceOutliers } from './outlierDetect.ts'

const recipe = (recipe_id: string, points: number[]): RecipeInput => ({
  lot_cd: 'R000', recipe_id, fac_id: 'R3', ctn_desc: '', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 'EV', memory_class_auto: 'DRAM',
  parameters: points.map((point_count, i) => ({ name: `P_${i}`, point_count }))
})

test('outlier drill marks the over-threshold param and its recipe', () => {
  const recipes = [recipe('A', [10, 10, 10, 10]), recipe('B', [50, 10])]
  const result = detectDeviceOutliers(recipes) // median 10, threshold 20
  const drill = toOutlierDrill('R000', 'dev desc', recipes, result)

  assert.equal(drill.lot_cd, 'R000')
  assert.equal(drill.ctn_desc, 'dev desc')
  assert.equal(drill.flagged_param_count, 1)
  assert.equal(drill.flagged_recipe_count, 1)

  const recB = drill.recipes.find(r => r.recipe_id === 'B')!
  assert.equal(recB.flagged, true)
  assert.equal(recB.flagged_count, 1)
  const p0 = recB.parameters.find(p => p.name === 'P_0')!
  assert.equal(p0.flagged, true)
  assert.equal(p0.note, '> 20') // threshold note
  const p1 = recB.parameters.find(p => p.name === 'P_1')!
  assert.equal(p1.flagged, false)

  const recA = drill.recipes.find(r => r.recipe_id === 'A')!
  assert.equal(recA.flagged, false)
})

test('no outliers → every recipe unflagged, counts zero', () => {
  const recipes = [recipe('A', [10, 10]), recipe('B', [10, 10])]
  const drill = toOutlierDrill('R000', '', recipes, detectDeviceOutliers(recipes))
  assert.equal(drill.flagged_param_count, 0)
  assert.equal(drill.flagged_recipe_count, 0)
  assert.ok(drill.recipes.every(r => !r.flagged))
})

test('an exempt PARAMETER is labelled, so a big unflagged number reads as intentional', () => {
  const recipes = [{
    ...recipe('A', []),
    // 준비용 파라미터는 측정 순서의 **맨 앞**에 옵니다 (user-confirmed
    // 2026-08-10). 예전 fixture 는 이것을 뒤에 두었는데, 위치 규칙에서는
    // 뒤에 있는 것이 곧 "측정 파라미터" 라는 뜻입니다.
    parameters: [
      { name: 'Align', point_count: 3 },
      { name: 'Dummy', point_count: 1 },
      { name: 'WAFER_CD', point_count: 5 }
    ]
  }]
  const drill = toOutlierDrill('R000', '', recipes, detectDeviceOutliers(recipes))
  const params = drill.recipes[0]!.parameters

  const align = params.find(p => p.name === 'Align')!
  assert.equal(align.flagged, false)
  assert.equal(align.note, '분석 제외')
  // 값은 감추지 않습니다 — 이유만 답니다.
  assert.equal(align.point_count, 3)

  assert.equal(params.find(p => p.name === 'Dummy')!.note, '분석 제외')
  // 정상 파라미터는 꼬리표가 없습니다.
  assert.equal(params.find(p => p.name === 'WAFER_CD')!.note, undefined)
})

test('an exempt job stays in the list, unflagged and marked', () => {
  const recipes = [recipe('A', [10, 10, 10, 10]), recipe('B_WCDU', [800, 800])]
  const drill = toOutlierDrill('R000', '', recipes, detectDeviceOutliers(recipes))

  const exempt = drill.recipes.find(r => r.recipe_id === 'B_WCDU')!
  // 목록에서 빼면 디바이스가 실제로 돌리는 recipe 가 사라집니다.
  assert.ok(exempt, 'the exempt job must still be listed')
  assert.equal(exempt.exempt, true, 'and it must say why it carries no 초과 badge')
  assert.equal(exempt.flagged, false)
  assert.equal(exempt.flagged_count, 0)
  // 파라미터는 실제 값 그대로 보여줍니다 — 감추는 것이 아니라 설명하는 것입니다.
  assert.equal(exempt.parameters[0]?.point_count, 800)
  assert.equal(exempt.parameters[0]?.flagged, false)

  assert.equal(drill.recipes.find(r => r.recipe_id === 'A')!.exempt, false)
  assert.equal(drill.flagged_recipe_count, 0)
})

const coreEarlyDram: RuleCell = {
  id: 'r3-core-tev-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [{ patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains', cap: 13 }]
}

const dramRecipe = (recipe_id: string, edgePoints: number): RecipeInput => ({
  lot_cd: 'R000', recipe_id, fac_id: 'R3', ctn_desc: 't-EV DRAM Core', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 't-EV', memory_class_auto: 'DRAM',
  parameters: [{ name: 'WAFER_CD', point_count: 13 }, { name: 'EDGE_L', point_count: edgePoints }]
})

test('violation drill flags recipes whose param exceeds its cap, with cap note', () => {
  // EDGE cap is 10. Recipe B measures 16 → violation; A measures 8 → pass.
  const recipes = [dramRecipe('A', 8), dramRecipe('B', 16)]
  const health = evaluateLot('R000', recipes, [coreEarlyDram])
  const drill = toViolationDrill('R000', 'R000 dev', health)

  assert.equal(drill.flagged_recipe_count, 1) // count, not ratio (D22)
  const recB = drill.recipes.find(r => r.recipe_id === 'B')!
  assert.equal(recB.flagged, true)
  const edge = recB.parameters.find(p => p.name === 'EDGE_L')!
  assert.equal(edge.flagged, true)
  assert.equal(edge.note, 'cap 10')
  const recA = drill.recipes.find(r => r.recipe_id === 'A')!
  assert.equal(recA.flagged, false)
})

test('violation drill: judgeSons=false 인 son 은 tint 없이 사유만 답니다', () => {
  // 준수(표시 없음) · 위반(tint + cap) · 판정 제외(cap + 제외, tint 없음)가 서로
  // 다른 모습이어야 합니다. 셋 중 뒤의 둘이 같아지면 토글을 껐다는 사실이 화면에서
  // 사라지고, 상한을 넘긴 son 이 준수한 파라미터처럼 읽힙니다.
  const recipes = [{
    ...dramRecipe('A', 16),
    parameters: [
      // 같은 region 이라야 son 입니다 — mother 없는 region 의 파라미터는 얹혀 갈
      // 상대가 없어 토글과 무관하게 판정됩니다.
      { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
      { name: 'EDGE_L', point_count: 16, mother: false, region: 1 }
    ]
  }]
  const health = evaluateLot('R000', recipes, [coreEarlyDram], { judgeSons: false })
  const params = toViolationDrill('R000', '', health).recipes[0]!.parameters

  const son = params.find(p => p.name === 'EDGE_L')!
  assert.equal(son.flagged, false, 'tint 는 위반에만')
  assert.equal(son.note, 'cap 10 · 제외')
  assert.equal(params.find(p => p.name === 'WAFER_CD')!.note, undefined, '준수한 파라미터는 꼬리표가 없습니다')
})

test('violation drill: gray (unruled) recipes are unflagged', () => {
  // No matching cell for an M-class fab → gray, conservative pass (D14).
  const recipes = [dramRecipe('A', 99)]
  const health = evaluateLot('R000', recipes, []) // empty rules → gray A
  const drill = toViolationDrill('R000', '', health)
  assert.equal(drill.flagged_recipe_count, 0)
  assert.ok(drill.recipes.every(r => !r.flagged))
})

// role 은 판정이 아니라 recipe 의 사실이라 두 어댑터 모두 싣습니다 — 카드를
// 펼쳤을 때 "이 행이 mother 인가 son 인가" 가 어느 화면에서나 보여야 합니다.
test('outlier drill carries mother/son role per parameter', () => {
  const recipes = [{
    ...dramRecipe('A', 16),
    parameters: [
      { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
      { name: 'EDGE_L', point_count: 16, mother: false, region: 1 },
      { name: 'CD_BAR', point_count: 3, mother: false, region: 2 }
    ]
  }]
  const result = detectDeviceOutliers(recipes)
  const params = toOutlierDrill('R000', '', recipes, result).recipes[0]!.parameters
  assert.deepEqual(params.map(p => p.role), ['mother', 'son', null])
})

test('violation drill carries mother/son role per parameter', () => {
  const recipes = [{
    ...dramRecipe('A', 16),
    parameters: [
      { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
      { name: 'EDGE_L', point_count: 16, mother: false, region: 1 }
    ]
  }]
  const health = evaluateLot('R000', recipes, [coreEarlyDram])
  const params = toViolationDrill('R000', '', health).recipes[0]!.parameters
  assert.deepEqual(params.map(p => p.role), ['mother', 'son'])
})
