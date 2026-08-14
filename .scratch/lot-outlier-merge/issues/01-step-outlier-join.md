# 01 — 스텝 × outlier 조인 순수 함수

Status: resolved
Plan: [`../plan.md`](../plan.md) · Spec: [`../spec.md`](../spec.md)

모달 카드는 **스텝** grain 이고 outlier 정보는 **recipe** grain 입니다
(`RecipeInput` 에 `oper_seq` 가 없습니다). 둘을 `recipe_id` 로 1:N 조인하는
함수를 만듭니다. 컴포넌트 안에 두지 않는 이유는 `node --test` 가 볼 수 없기
때문입니다 — 이 저장소의 프런트엔드 테스트는 순수 함수 전용입니다.

**Files:**

- Create: `front-dev-home/app/utils/lotOutlierSteps.ts`
- Create: `front-dev-home/app/utils/lotOutlierSteps.test.ts`

**Interfaces:**

- Consumes: `DrillDevice` · `DrillRecipe` (type-only) from `./deviceDrill`,
  `RecipeInfoRow` (type-only) from `~/composables/useRecipeStatisticsApi`
- Produces: `StepFilter`, `StepOutlier`, `buildStepOutliers`,
  `filterStepOutliers`, `flaggedStepCount` (계약 전문은 `../plan.md` 의
  Interfaces 절)

---

- [ ] **Step 1: 작업 트리 분리**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git worktree add ../skewnono-lot-outlier-merge -b work/lot-outlier-merge
cd ../skewnono-lot-outlier-merge/front-dev-home
```

이후 모든 티켓은 이 워크트리 안에서 작업합니다.

- [ ] **Step 2: 기준선 확인 — 지금 통과하는지 먼저 본다**

Run: `npm test 2>&1 | tail -5`
Expected: 실패 0건. (워크트리에는 gitignore 된 `office.py` 가 없어 백엔드 skip
수가 본체와 다를 수 있습니다 — 프런트 `npm test` 는 영향받지 않습니다.)

- [ ] **Step 3: 실패하는 테스트를 쓴다**

Create `app/utils/lotOutlierSteps.test.ts`:

```ts
// Lot 상세 팝업의 스텝 카드 × outlier 조인.
// Run: node --test app/utils/lotOutlierSteps.test.ts
//
// 여기서 지키는 것은 **grain 규칙**입니다 — 한 recipe 가 여러 스텝에서 돌 때
// 카드가 사라지지 않고, 같은 outlier 가 각 카드에 붙되 스텝 수가 함께 보고되며,
// 총계를 카드에서 세지 않는다는 것.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildStepOutliers, filterStepOutliers, flaggedStepCount } from './lotOutlierSteps.ts'
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
```

- [ ] **Step 4: 실패를 확인한다**

Run: `npm test 2>&1 | tail -20`
Expected: FAIL — `Cannot find module './lotOutlierSteps.ts'`

- [ ] **Step 5: 최소 구현을 쓴다**

Create `app/utils/lotOutlierSteps.ts`:

```ts
// Lot 상세 팝업의 스텝 카드에 과다 측정(outlier) 정보를 붙입니다.
//
// 두 축의 grain 이 다릅니다. 카드는 **스텝**(RecipeInfoRow — lot_cd/oper_seq/
// samp_seq)이고, outlier 는 **recipe**(RecipeInput → DrillRecipe — recipe_id)
// 입니다. RecipeInput 에는 oper_seq 가 없으므로 조인은 1:N 이고, 한 recipe 가
// 두 스텝에서 돌면 같은 배지가 카드 두 장에 붙는 것이 정상입니다.
//
// 그래서 이 파일은 **세지 않습니다** — 헤더의 초과 총계는
// DeviceOutlierResult.outlier_count 를 그대로 씁니다. 카드를 세면 여러 스텝에
// 걸친 recipe 가 중복 계산됩니다. 여기서 세는 flaggedStepCount 는 "몇 장의
// 카드가 걸렸는가" 라는 화면의 질문이지, 초과 파라미터 개수가 아닙니다.
//
// 판정은 하지 않습니다. 무엇이 초과인지는 toOutlierDrill 이 이미 정했고
// (deviceDrill.ts), 그 규칙에는 분석 제외 층이 둘이나 있습니다. 여기서 다시
// 판정하면 그 테스트가 지키던 것이 풀립니다.
//
// 값 import 는 없습니다(타입만) — 그래도 node --test 가 이 파일을 직접 부르므로
// 런타임 의존은 계속 두지 않습니다.
import type { RecipeInfoRow } from '~/composables/useRecipeStatisticsApi'
import type { DrillDevice, DrillRecipe } from './deviceDrill'

export type StepFilter = 'all' | 'flagged'

/** 조인에 필요한 최소 field. 테스트가 전체 행을 짓지 않아도 되게 좁힙니다. */
type JoinableStep = Pick<RecipeInfoRow, 'recipe_id'>

export interface StepOutlier<T extends JoinableStep = RecipeInfoRow> {
  /** 카드가 그리는 스텝. grain 의 주인입니다. */
  step: T
  /** 같은 recipe_id 의 outlier 정보. 이 버킷에 파라미터가 없으면 null 입니다. */
  drill: DrillRecipe | null
  /** 이 lot 안에서 같은 recipe_id 를 쓰는 스텝 수. 2 이상이면 화면이 말합니다. */
  stepSpan: number
}

/**
 * 스텝 목록에 outlier 를 붙입니다. **순서는 입력 그대로** — 정렬은 sortSteps 의
 * 일이고, 여기서 손대면 정렬 칩이 거짓말을 합니다.
 */
export const buildStepOutliers = <T extends JoinableStep>(
  steps: T[],
  device: DrillDevice | null
): StepOutlier<T>[] => {
  const byRecipe = new Map<string, DrillRecipe>()
  for (const recipe of device?.recipes ?? []) byRecipe.set(recipe.recipe_id, recipe)

  const span = new Map<string, number>()
  for (const step of steps) span.set(step.recipe_id, (span.get(step.recipe_id) ?? 0) + 1)

  return steps.map(step => ({
    step,
    drill: byRecipe.get(step.recipe_id) ?? null,
    stepSpan: span.get(step.recipe_id) ?? 1
  }))
}

/** 화면 필터. 'flagged' 는 초과가 걸린 recipe 의 스텝만 남깁니다. */
export const filterStepOutliers = <T extends JoinableStep>(
  cards: StepOutlier<T>[],
  filter: StepFilter
): StepOutlier<T>[] =>
  filter === 'flagged' ? cards.filter(card => card.drill?.flagged === true) : cards

/** 초과가 걸린 **카드** 수. 파라미터 수도, recipe 수도 아닙니다. */
export const flaggedStepCount = (cards: StepOutlier<JoinableStep>[]): number =>
  cards.filter(card => card.drill?.flagged === true).length
```

- [ ] **Step 6: 통과를 확인한다**

Run: `npm test 2>&1 | tail -10`
Expected: 신규 7건 포함 전부 pass

- [ ] **Step 7: 정적 게이트**

Run: `npm run typecheck && npm run lint`
Expected: 둘 다 clean

- [ ] **Step 8: 커밋**

신규 파일이라 `git commit -- <path>` 는 쓸 수 없습니다 (아직 git 이 모르는
경로입니다). 정확한 경로만 `add` 한 뒤 커밋합니다.

```bash
cd /Users/daeyoung/Codes/skewnono-lot-outlier-merge
git add front-dev-home/app/utils/lotOutlierSteps.ts \
  front-dev-home/app/utils/lotOutlierSteps.test.ts
git commit -m "feat(device-statistics): join step cards with per-recipe outlier info

Lot 상세 팝업이 스텝 카드에 과다 측정 정보를 함께 그릴 수 있도록, 스텝(step
grain) 과 DrillDevice(recipe grain) 를 recipe_id 로 1:N 조인하는 순수 함수를
추가합니다. 한 recipe 가 여러 스텝에서 돌 때 카드가 접히지 않는 것과, 총계를
카드에서 세지 않는 것이 이 모듈이 지키는 규칙입니다."
```

(경로를 하나하나 대는 것은 저장소 규약입니다 — 한 작업 트리에 여러 에이전트
세션이 붙으므로 `git add -A` 는 다른 세션의 반쯤 된 편집을 쓸어 담습니다.
기존 파일을 고치는 뒤 티켓들은 `git commit -- <경로>` 형태를 씁니다.)
