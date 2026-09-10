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
// 값 import 는 recipeStepKey 하나뿐입니다 — 그래도 node --test 가 이 파일을
// 직접 부르므로 확장자를 명시해 번들러 없이도 풀리게 합니다.
import type { RecipeInfoRow } from '~/composables/useRecipeStatisticsApi'
import type { DrillDevice, DrillRecipe } from './deviceDrill'
import { recipeStepKey } from './recipeStepSort.ts'

export type StepFilter = 'all' | 'flagged'

/** 조인에 필요한 최소 field. 테스트가 전체 행을 짓지 않아도 되게 좁힙니다. */
type JoinableStep = Pick<RecipeInfoRow, 'recipe_id' | 'lot_cd' | 'oper_seq' | 'samp_seq'>

export interface StepOutlier<T extends JoinableStep = RecipeInfoRow> {
  /** 카드가 그리는 스텝. grain 의 주인입니다. */
  step: T
  /** 같은 recipe_id 의 outlier 정보. 이 버킷에 파라미터가 없으면 null 입니다. */
  drill: DrillRecipe | null
  /** 이 lot 안에서 같은 recipe_id 를 쓰는 스텝 수. 2 이상이면 화면이 말합니다. */
  stepSpan: number
  /**
   * 카드의 `v-for` 키이자 펼침 상태 키. 조인 시점에 한 번 계산해 두 쓰임이
   * 어긋날 수 없게 합니다. `recipe_id` 는 일부러 넣지 않습니다 — 이유는
   * recipeStepSort.ts 의 `recipeStepKey` docstring 을 보십시오.
   */
  key: string
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
    stepSpan: span.get(step.recipe_id) ?? 1,
    key: recipeStepKey(step)
  }))
}

/** 이 카드가 초과로 잡혔는가. 세 곳(필터·집계·카드)이 같은 술어를 봐야 화면과 숫자가 갈리지 않습니다. */
export const isFlaggedStep = (card: StepOutlier<JoinableStep>): boolean => card.drill?.flagged === true

/** 화면 필터. 'flagged' 는 초과가 걸린 recipe 의 스텝만 남깁니다. */
export const filterStepOutliers = <T extends JoinableStep>(
  cards: StepOutlier<T>[],
  filter: StepFilter
): StepOutlier<T>[] =>
  filter === 'flagged' ? cards.filter(isFlaggedStep) : cards

/** 초과가 걸린 **카드** 수. 파라미터 수도, recipe 수도 아닙니다. */
export const flaggedStepCount = (cards: StepOutlier<JoinableStep>[]): number =>
  cards.filter(isFlaggedStep).length
