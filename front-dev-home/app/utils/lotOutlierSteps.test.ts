// Lot 상세 팝업의 스텝 카드 × outlier 조인.
// Run: node --test app/utils/lotOutlierSteps.test.ts
//
// 여기서 지키는 것은 **grain 규칙**입니다 — 한 recipe 가 여러 스텝에서 돌 때
// 카드가 사라지지 않고, 같은 outlier 가 각 카드에 붙되 스텝 수가 함께 보고되며,
// 총계를 카드에서 세지 않는다는 것.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildStepOutliers, filterStepOutliers, flaggedStepCount, isFlaggedStep } from './lotOutlierSteps.ts'
import { recipeStepKey } from './recipeStepSort.ts'
import type { DrillDevice, DrillRecipe } from './deviceDrill'

const step = (recipe_id: string, oper_seq: number, samp_seq = 1) =>
  ({ lot_cd: 'R000', recipe_id, oper_seq, samp_seq })

const drillRecipe = (recipe_id: string, flagged_count: number, exempt = false): DrillRecipe => ({
  recipe_id,
  flagged: flagged_count > 0,
  total_params: 4,
  flagged_count,
  parameters: [
    { name: 'CD_1', point_count: 40, flagged: flagged_count > 0, note: flagged_count > 0 ? '> 20' : undefined },
    { name: 'CD_2', point_count: 10, flagged: false }
  ],
  exempt
})

const device = (recipes: DrillRecipe[]): DrillDevice => ({
  lot_cd: 'R000',
  ctn_desc: 'dev',
  recipes,
  flagged_recipe_count: recipes.filter(r => r.flagged).length,
  flagged_param_count: recipes.reduce((sum, r) => sum + r.flagged_count, 0)
})

test('recipe_id 로 스텝에 outlier 를 붙인다', () => {
  const cards = buildStepOutliers([step('A', 10), step('B', 20)], device([drillRecipe('B', 1)]))

  assert.equal(cards.length, 2)
  const a = cards.find(c => c.step.recipe_id === 'A')!
  assert.equal(a.drill, null)
  const b = cards.find(c => c.step.recipe_id === 'B')!
  assert.equal(b.drill?.flagged_count, 1)
})

test('카드의 key 는 recipeStepKey 와 같고, 같은 recipe_id 를 쓰는 두 스텝은 서로 다른 key 를 받는다', () => {
  const steps = [step('SHARED', 10), step('SHARED', 40)]
  const cards = buildStepOutliers(steps, null)

  assert.equal(cards[0]!.key, recipeStepKey(steps[0]!))
  assert.equal(cards[1]!.key, recipeStepKey(steps[1]!))
  assert.notEqual(cards[0]!.key, cards[1]!.key)
})

test('한 recipe 가 두 스텝에 걸리면 카드 두 장이 남고 stepSpan 이 2 다', () => {
  // recipeStepKey 가 recipe_id 를 쓰지 않는 이유와 같은 사정입니다 — 여기서
  // 카드를 접으면 스텝이 조용히 사라집니다.
  const steps = [step('SHARED', 10), step('SHARED', 40)]
  const cards = buildStepOutliers(steps, device([drillRecipe('SHARED', 2)]))

  assert.equal(cards.length, 2)
  assert.deepEqual(cards.map(c => c.stepSpan), [2, 2])
  assert.deepEqual(cards.map(c => c.drill?.flagged_count), [2, 2])
})

test('총계는 카드에서 세지 않는다 — flaggedStepCount 는 스텝 수이지 파라미터 수가 아니다', () => {
  const cards = buildStepOutliers(
    [step('SHARED', 10), step('SHARED', 40), step('CLEAN', 50)],
    device([drillRecipe('SHARED', 2), drillRecipe('CLEAN', 0)])
  )
  assert.equal(flaggedStepCount(cards), 2)
})

test('device 가 null 이면 모든 카드가 drill 없이, 순서 그대로 나온다', () => {
  const steps = [step('A', 10), step('B', 20)]
  const cards = buildStepOutliers(steps, null)

  assert.deepEqual(cards.map(c => c.step.recipe_id), ['A', 'B'])
  assert.ok(cards.every(c => c.drill === null))
  assert.ok(cards.every(c => c.stepSpan === 1))
})

test('입력 순서를 보존하고 입력 배열을 건드리지 않는다', () => {
  // 정렬은 sortSteps 의 일입니다. 이 함수가 순서를 손대면 정렬 칩이 거짓말을 합니다.
  const steps = [step('C', 30), step('A', 10)]
  const copy = [...steps]
  const cards = buildStepOutliers(steps, null)

  assert.deepEqual(cards.map(c => c.step.recipe_id), ['C', 'A'])
  assert.deepEqual(steps, copy)
})

test('초과만 필터는 flagged recipe 의 스텝만 남긴다', () => {
  const cards = buildStepOutliers(
    [step('HIT', 10), step('CLEAN', 20), step('NONE', 30)],
    device([drillRecipe('HIT', 1), drillRecipe('CLEAN', 0)])
  )

  assert.deepEqual(filterStepOutliers(cards, 'all').map(c => c.step.recipe_id),
    ['HIT', 'CLEAN', 'NONE'])
  assert.deepEqual(filterStepOutliers(cards, 'flagged').map(c => c.step.recipe_id),
    ['HIT'])
})

test('분석 제외 job 은 초과가 아니므로 초과만 필터에서 빠진다', () => {
  // 설계상 많이 재는 job 입니다. flagged 가 켜질 수 없으므로 필터의 답도 하나뿐입니다.
  const cards = buildStepOutliers([step('X_CDU', 10)], device([drillRecipe('X_CDU', 0, true)]))

  assert.equal(cards[0]!.drill?.exempt, true)
  assert.equal(filterStepOutliers(cards, 'flagged').length, 0)
})

test('isFlaggedStep 은 drill 없음/미초과/초과 세 경우를 구분한다', () => {
  const noDrill = buildStepOutliers([step('A', 10)], null)[0]!
  const unflagged = buildStepOutliers([step('B', 10)], device([drillRecipe('B', 0)]))[0]!
  const flagged = buildStepOutliers([step('C', 10)], device([drillRecipe('C', 1)]))[0]!

  assert.equal(isFlaggedStep(noDrill), false)
  assert.equal(isFlaggedStep(unflagged), false)
  assert.equal(isFlaggedStep(flagged), true)
})
